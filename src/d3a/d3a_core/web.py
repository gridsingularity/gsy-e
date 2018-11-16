import traceback
from functools import lru_cache, wraps
from threading import Thread
import pendulum
from flask import Flask, abort, render_template, request
from flask_api import FlaskAPI
from flask_cors import CORS
from werkzeug.serving import run_simple
from werkzeug.wsgi import DispatcherMiddleware

from d3a.constants import VERSION
from d3a.d3a_core.simulation import Simulation, page_lock

from d3a.d3a_core.sim_results.rest_endpoints import area_endpoint_stats, market_endpoint_stats, \
    markets_endpoints_stats, market_results_endpoint_stats, bills_endpoint_stats, simulation_info,\
    url_for


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
        return area_endpoint_stats(area)

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
        return market_endpoint_stats(area, market_time)

    @app.route("/<area_slug>/markets")
    @lock_flask_endpoint
    def markets(area_slug):
        area = _get_area(area_slug)
        return markets_endpoints_stats(area)

    @app.route("/<area_slug>/results")
    @lock_flask_endpoint
    def results(area_slug):
        area = _get_area(area_slug)
        market = area.current_market
        return market_results_endpoint_stats(area, market)

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
        return bills_endpoint_stats(area, from_slot, to_slot)

    @app.after_request
    def modify_server_header(response):
        response.headers['Server'] = "d3a/{}".format(VERSION)
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
