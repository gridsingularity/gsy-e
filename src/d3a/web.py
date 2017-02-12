import traceback
from functools import lru_cache
from itertools import chain, repeat
from operator import itemgetter
from threading import Thread

import pendulum
from flask import Flask, abort, render_template, request
from flask.helpers import url_for as url_for_original
from flask_api import FlaskAPI
from flask_cors import CORS
from werkzeug.serving import run_simple
from werkzeug.wsgi import DispatcherMiddleware

import d3a
from d3a.simulation import Simulation
from d3a.util import format_interval


_NO_VALUE = {
    'min': None,
    'avg': None,
    'max': None
}


def start_web(interface, port, simulation: Simulation):
    app = DispatcherMiddleware(
        _html_app(simulation.area), {
            '/api': _api_app(simulation)
        }
    )
    t = Thread(
        target=lambda: run_simple(
            interface,
            port,
            app,
            use_debugger=True,
            use_reloader=False
        )
    )
    t.setDaemon(True)
    t.start()
    return t


def _html_app(area):
    app = Flask(__name__)
    app.jinja_env.globals.update(id=id)

    @app.route("/")
    def index():
        return render_template("index.html", root_area=area)

    return app


def _api_app(simulation: Simulation):
    app = FlaskAPI(__name__)
    CORS(app)

    def _get_area(area_slug):
        try:
            return simulation.area.child_by_slug[area_slug]
        except KeyError:
            abort(404)

    @app.route("/")
    def index():
        return {
            'simulation': _simulation_info(simulation),
            'root_area': area_tree(simulation.area)
        }

    @app.route("/pause", methods=['GET', 'POST'])
    def pause():
        changed = False
        if request.method == 'POST':
            changed = simulation.toggle_pause()
        return {'paused': simulation.paused, 'changed': changed}

    @app.route("/reset", methods=['POST'])
    def reset():
        simulation.reset()
        return {'success': 'ok'}

    @app.route("/save", methods=['POST'])
    def save():
        return {'save_file': str(simulation.save_state().resolve())}

    @app.route("/slowdown", methods=['GET', 'POST'])
    def slowdown():
        changed = False
        if request.method == 'POST':
            if request.is_json:
                data = request.get_json(silent=True)
            else:
                data = request.form
            slowdown = data.get('slowdown')
            if not slowdown:
                return {'error': "'slowdown' parameter missing"}, 400
            try:
                slowdown = int(slowdown)
            except ValueError:
                return {'error': "'slowdown' parameter must be numeric"}, 400
            if not -1 < slowdown < 101:
                return {'error': "'slowdown' must be in range 0 - 100"}, 400
            simulation.slowdown = slowdown
            changed = True
        return {'slowdown': simulation.slowdown, 'changed': changed}

    @app.route("/<area_slug>")
    def area(area_slug):
        area = _get_area(area_slug)
        return {
            'name': area.name,
            'slug': area.slug,
            'active': area.active,
            'strategy': area.strategy.__class__.__name__ if area.strategy else None,
            'appliance': area.appliance.__class__.__name__ if area.appliance else None,
            'market_overview_url': url_for('markets', area_slug=area_slug),
            'available_triggers': {
                trigger.name: {
                    'name': trigger.name,
                    'state': trigger.state,
                    'help': trigger.help,
                    'url': url_for('area_trigger', area_slug=area_slug, trigger_name=trigger.name),
                    'parameters': [
                        {
                            'name': name,
                            'type': type_.__name__,
                        }
                        for name, type_ in trigger.params.items()
                    ]
                }
                for trigger in area.available_triggers.values()
            },
            'markets': [
                {
                    'type': type_,
                    'time_slot': time.format("%H:%M"),
                    'url': url_for('market', area_slug=area_slug,
                                   market_time=time),
                    'trade_count': len(market.trades),
                    'offer_count': len(market.offers)
                }
                for type_, (time, market)
                in _market_progression(area)
            ],
        }

    @app.route("/<area_slug>/trigger/<trigger_name>", methods=['POST'])
    def area_trigger(area_slug, trigger_name):
        area = _get_area(area_slug)
        triggers = area.available_triggers
        if trigger_name not in triggers:
            return {'error': "Unknown trigger '{}'".format(trigger_name)}, 400

        if request.is_json:
            data = request.get_json(silent=True)
        else:
            data = request.form
        try:
            rv = area._fire_trigger(trigger_name, **data)
            return {'success': True, 'repsonse': rv}
        except Exception as ex:
            return {'success': False, 'exception': str(ex), 'traceback': traceback.format_exc()}

    @app.route("/<area_slug>/market/<market_time>")
    def market(area_slug, market_time):
        area = _get_area(area_slug)
        market, type_ = _get_market(area, market_time)
        return {
            'type': type_,
            'time_slot': market.time_slot.format("%H:%M"),
            'url': url_for('market', area_slug=area_slug, market_time=market.time_slot),
            'prices': {
                'trade': {
                    'min': market.min_trade_price,
                    'avg': market.avg_trade_price,
                    'max': market.max_trade_price,
                } if market.trades else _NO_VALUE,
                'offer': {
                    'min': market.min_offer_price,
                    'avg': market.avg_offer_price,
                    'max': market.max_offer_price,
                } if market.offers else _NO_VALUE
            },
            'energy_aggregate': _energy_aggregate(market),
            'energy_accounting': [
                {
                    'time': time.format("%H:%M:%S"),
                    'reports': [
                        {
                            'actor': actor,
                            'value': value
                        }
                        for actor, value in acct_dict.items()
                    ]
                }
                for time, acct_dict in sorted(market.actual_energy.items(), key=itemgetter(0))
            ],
            'trades': [
                {
                    'id': t.id,
                    'time': str(t.time),
                    'seller': t.seller,
                    'buyer': t.buyer,
                    'energy': t.offer.energy,
                    'price': t.offer.price / t.offer.energy
                }
                for t in market.trades
            ],
            'offers': [
                {
                    'id': o.id,
                    'seller': o.seller,
                    'energy': o.energy,
                    'price': o.price / o.energy
                }
                for o in market.offers.values()
            ],
            'ious': _ious(market)
        }

    @app.route("/<area_slug>/markets")
    def markets(area_slug):
        area = _get_area(area_slug)
        return [
            {
                'prices': {
                    'trade': {
                        'min': market.min_trade_price,
                        'avg': market.avg_trade_price,
                        'max': market.max_trade_price,
                    } if market.trades else _NO_VALUE,
                    'offer': {
                        'min': market.min_offer_price,
                        'avg': market.avg_offer_price,
                        'max': market.max_offer_price,
                    } if market.offers else _NO_VALUE
                },
                'ious': _ious(market),
                'energy_aggregate': _energy_aggregate(market),
                'trade_count': len(market.trades),
                'offer_count': len(market.offers),
                'type': type_,
                'time_slot': market.time_slot.format("%H:%M"),
                'url': url_for('market', area_slug=area_slug, market_time=market.time_slot),
            }
            for type_, (time, market)
            in _market_progression(area)
        ]

    @app.after_request
    def modify_server_header(response):
        response.headers['Server'] = "d3a/{}".format(d3a.VERSION)
        return response

    return app


@lru_cache()
def area_tree(area):
    return {
        'name': area.name,
        'slug': area.slug,
        'children': [area_tree(child) for child in area.children],
        'url': url_for('area', area_slug=area.slug)
    }


def _market_progression(area):
    return chain(
        zip(
            chain(
                repeat('closed', times=len(area.past_markets) - 1),
                ('current',)
            ),
            list(area.past_markets.items())
        ),
        zip(
            repeat('open'),
            list(area.markets.items())
        )
    )


def _energy_aggregate(market):
    return {
        'traded': {
            actor: round(value, 4)
            for actor, value
            in list(market.traded_energy.items())
            if abs(value) > 0.0000
        },
        'actual': {
            actor: round(value, 4)
            for actor, value
            in list(market.actual_energy_agg.items())
        }
    }


def _ious(market):
    return {
        buyer: {
            seller: round(total, 4)
            for seller, total
            in seller_total.items()
            }
        for buyer, seller_total in list(market.ious.items())
        }


def _get_market(area, market_time):
    if market_time == 'current':
        market = list(area.past_markets.values())[-1]
        type_ = 'current'
    elif market_time.isdigit():
        market = list(area.markets.values())[int(market_time)]
        type_ = 'open'
    elif market_time[0] == '-' and market_time[1:].isdigit():
        market = list(area.past_markets.values())[int(market_time)]
        type_ = 'closed'
    else:
        time = pendulum.parse(market_time)
        try:
            market = area.markets[time]
            type_ = 'open'
        except KeyError:
            try:
                market = area.past_markets[time]
            except KeyError:
                return abort(404)
            type_ = 'closed'
            if market.time_slot == list(area.past_markets.keys())[-1]:
                type_ = 'current'
    return market, type_


def _simulation_info(simulation):
    current_time = format_interval(
        simulation.area.current_tick * simulation.area.config.tick_length
    )
    return {
        'config': simulation.area.config.as_dict(),
        'finished': simulation.finished,
        'current_tick': simulation.area.current_tick,
        'current_time': current_time,
        'current_date': simulation.area.now.format('%Y-%m-%d'),
        'paused': simulation.paused,
        'slowdown': simulation.slowdown
    }


def url_for(target, **kwargs):
    return url_for_original(target, **{**kwargs, '_external': True})
