import traceback
from collections import OrderedDict
from functools import lru_cache, wraps
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
from d3a import TIME_FORMAT
from d3a.simulation import Simulation, page_lock
from d3a.stats import (
    energy_bills
)
from d3a.util import make_iaa_name, simulation_info


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


def lock_flask_endpoint(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        with page_lock:
            return f(*args, **kwargs)
    return wrapped


def _html_app(area):
    app = Flask(__name__)
    app.jinja_env.globals.update(id=id)

    @app.route("/")
    @lock_flask_endpoint
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
    @lock_flask_endpoint
    def index():
        return {
            'simulation': simulation_info(simulation),
            'root_area': area_tree(simulation.area)
        }

    @app.route("/pause", methods=['GET', 'POST'])
    @lock_flask_endpoint
    def pause():
        changed = False
        if request.method == 'POST':
            changed = simulation.toggle_pause()
        return {'paused': simulation.paused, 'changed': changed}

    @app.route("/reset", methods=['POST'])
    @lock_flask_endpoint
    def reset():
        simulation.reset()
        return {'success': 'ok'}

    @app.route("/stop", methods=['POST'])
    @lock_flask_endpoint
    def stop():
        simulation.stop()
        return {'success': 'ok'}

    @app.route("/save", methods=['POST'])
    @lock_flask_endpoint
    def save():
        return {'save_file': str(simulation.save_state().resolve())}

    @app.route("/status", methods=['GET'])
    @lock_flask_endpoint
    def status():
        return {'status': simulation.status}

    @app.route("/slowdown", methods=['GET', 'POST'])
    @lock_flask_endpoint
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
    @lock_flask_endpoint
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
                    'time_slot': time.format(TIME_FORMAT),
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
    @lock_flask_endpoint
    def area_trigger(area_slug, trigger_name):
        area = _get_area(area_slug)
        triggers = area.available_triggers
        if trigger_name not in triggers:
            return {'error': "Unknown trigger '{}'".format(trigger_name)}, 400

        if request.is_json:
            data = request.get_json(silent=True)
        else:
            data = request.form.to_dict(flat=True)
        try:
            rv = area._fire_trigger(trigger_name, **data)
            return {'success': True, 'response': rv}
        except Exception as ex:
            return (
                {'success': False, 'exception': str(ex), 'traceback': traceback.format_exc()}, 400
            )

    @app.route("/<area_slug>/market/<market_time>")
    @lock_flask_endpoint
    def market(area_slug, market_time):
        area = _get_area(area_slug)
        market, type_ = _get_market(area, market_time)
        return {
            'type': type_,
            'time_slot': market.time_slot.format(TIME_FORMAT),
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
    @lock_flask_endpoint
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
                'total_traded': _total_traded(market),
                'trade_count': len(market.trades),
                'offer_count': len(market.offers),
                'type': type_,
                'time_slot': market.time_slot.format(TIME_FORMAT),
                'url': url_for('market', area_slug=area_slug, market_time=market.time_slot),
            }
            for type_, (time, market)
            in _market_progression(area)
        ]

    def _get_child_traded_energy(market, child):
        return market.traded_energy.get(
            child.name,
            market.traded_energy.get(make_iaa_name(child), '-')
        )

    @app.route("/<area_slug>/results")
    @lock_flask_endpoint
    def results(area_slug):
        area = _get_area(area_slug)
        market = area.current_market
        if market is None:
            return {'error': 'no results yet'}
        return {
            'summary': {
                'avg_trade_price': market.avg_trade_price,
                'max_trade_price': market.max_trade_price,
                'min_trade_price': market.min_trade_price
            },
            'balance': {
                child.slug: market.total_earned(child.slug) - market.total_spent(child.slug)
                for child in area.children
            },
            'energy_balance': {
                child.slug: _get_child_traded_energy(market, child)
                for child in area.children
            },
            'slots': [
                {
                    'volume': sum(trade.offer.energy for trade in slot_market.trades),
                }
                for slot_market in area.past_markets.values()
            ]
        }

    @app.route("/unmatched-loads", methods=['GET'])
    @lock_flask_endpoint
    def unmatched_loads():
        return simulation.endpoint_buffer.unmatched_loads

    @app.route("/cumulative-load-price", methods=['GET'])
    @lock_flask_endpoint
    def cumulative_load():
        return simulation.endpoint_buffer.cumulative_loads

    @app.route("/price-energy-day", methods=['GET'])
    @lock_flask_endpoint
    def price_energy_day():
        return simulation.endpoint_buffer.price_energy_day

    @app.route("/cumulative-grid-trades", methods=['GET'])
    @lock_flask_endpoint
    def cumulative_grid_trades():
        return simulation.endpoint_buffer.cumulative_grid_trades

    @app.route("/<area_slug>/tree-summary")
    def tree_summary(area_slug):
        return simulation.endpoint_buffer.tree_summary[area_slug]

    @app.route("/<area_slug>/bills")
    def bills(area_slug):
        area = _get_area(area_slug)

        def slot_query_param(name):
            if name in request.args:
                try:
                    return pendulum.parse(request.args[name])
                except pendulum.parsing.exceptions.ParserError:
                    area.log.error(
                        'Could not parse timestamp %s, using default for bill computation' %
                        request.args[name])
            return None

        from_slot = slot_query_param('from')
        to_slot = slot_query_param('to')
        result = energy_bills(area, from_slot, to_slot)
        result = OrderedDict(sorted(result.items()))
        if from_slot:
            result['from'] = str(from_slot)
        if to_slot:
            result['to'] = str(to_slot)
        return result

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


def _total_traded(market):
    return sum(trade.offer.energy for trade in market.trades) if market.trades else 0


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


def url_for(target, **kwargs):
    return url_for_original(target, **{**kwargs, '_external': True})
