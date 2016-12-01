import logging
from logging import getLogger
from threading import Thread
from time import sleep

import click
from colorlog.colorlog import ColoredFormatter
from d3a.models.area import Area
from d3a.models.strategy import BuyStrategy, OfferStrategy
from flask.app import Flask
from flask.templating import render_template


log = getLogger(__name__)


def runweb(area):
    app = Flask(__name__)
    app.jinja_env.globals.update(id=id)

    @app.route("/")
    def index():
        return render_template("index.html", root_area=area)

    t = Thread(target=lambda: app.run(debug=True, use_reloader=False))
    t.setDaemon(True)
    t.start()
    return t


@click.command(name='d3a')
def main():
    handler = logging.StreamHandler()
    handler.setFormatter(
        ColoredFormatter(
            "%(log_color)s%(asctime)s.%(msecs)03d %(levelname)-7s (%(lineno)4d) %(name)-25s: "
            "%(message)s%(reset)s",
            datefmt="%H:%M:%S"
        )
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    a = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 PV', strategy=OfferStrategy(offer_chance=.2)),
                    Area('H1 Fridge', strategy=BuyStrategy(buy_chance=.3))
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 PV', strategy=OfferStrategy(offer_chance=.25)),
                    Area('H2 Fridge', strategy=BuyStrategy(buy_chance=.4))
                ]
            )
        ]
    )
    a.activate()
    runweb(a)
    for i in range(200):
        log.debug("Tick %d", i)
        a.tick()
    for time, m in a.markets.items():
        print()
        print(time)
        print(m.display())
    log.info("Run finished. Ctrl-C to quit.")
    try:
        while True:
            sleep(.5)
    except KeyboardInterrupt:
        log.info("Quitting")
