from itertools import chain, repeat
from threading import Thread

import pendulum
from flask import Flask, render_template, abort
from flask_api import FlaskAPI

from flask.helpers import url_for
from werkzeug.serving import run_simple
from werkzeug.wsgi import DispatcherMiddleware

from d3a.models.area import Area


_NO_VALUE = {
    'min': None,
    'avg': None,
    'max': None
}


def start_web(interface, port, area):
    app = DispatcherMiddleware(_html_app(area), {'/api': _api_app(area)})
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


def _api_app(root_area: Area):
    app = FlaskAPI(__name__)

    area_slug_map = {}
    areas = [root_area]
    while areas:
        for a in list(areas):
            area_slug_map[a.slug] = a
            areas.remove(a)
            areas.extend(a.children)

    def _get_area(area_slug):
        try:
            return area_slug_map[area_slug]
        except KeyError:
            abort(404)

    @app.route("/")
    def index():
        return {
            'simulation': {
                'config': root_area.config.as_dict(),
                'finished': root_area.current_tick == root_area.config.total_ticks,
                'current_tick': root_area.current_tick
            },
            'root_area': area_tree(root_area)
        }

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
            'ious': {
                buyer: {
                    seller: total for seller, total in seller_total.items()
                }
                for buyer, seller_total in market.ious.items()
            }
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
                'trade_count': len(market.trades),
                'offer_count': len(market.offers),
                'type': type_,
                'time_slot': market.time_slot.format("%H:%M"),
                'url': url_for('market', area_slug=area_slug, market_time=market.time_slot),
            }
            for type_, (time, market)
            in _market_progression(area)
        ]

    return app


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
            area.past_markets.items()
        ),
        zip(
            repeat('open'),
            area.markets.items()
        )
    )


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
