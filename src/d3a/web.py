from itertools import chain, repeat
from threading import Thread

from flask import Flask, render_template
from flask_api import FlaskAPI

from flask.helpers import url_for
from werkzeug.serving import run_simple
from werkzeug.wsgi import DispatcherMiddleware

from d3a.models.area import Area


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

    @app.route("/")
    def index():
        return {
            'simulation': {
                'config': root_area.config.as_dict(),
                'finished': root_area.current_tick == root_area.config.total_ticks,
                'current_tick': root_area.current_tick
            },
            'root_area': {
                'name': root_area.name,
                'children': [],
                'url': url_for('area', area_slug=root_area.slug)
            }
        }

    @app.route("/<area_slug>")
    def area(area_slug):
        area = area_slug_map[area_slug]
        return {
            'name': area.name,
            'slug': area.slug,
            'active': area.active,
            'strategy': area.strategy.__class__.__name__ if area.strategy else None,
            'markets': [
                {
                    'type': type_,
                    'time': time.format("%H:%M"),
                    'url': url_for('market', area_slug=area_slug,
                                   market_time=time.format("%H:%M")),
                    'trade_count': len(market.trades),
                    'offer_count': len(market.offers)
                }
                for type_, (time, market)
                in chain(
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
            ],
        }

    @app.route("/<area_slug>/market/<market_time>")
    def market(area_slug, market_time):
        return {}

    return app
