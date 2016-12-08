import logging
from logging import getLogger
from time import sleep

import click
from click.types import Choice
from click_default_group import DefaultGroup
from colorlog.colorlog import ColoredFormatter
from d3a.models.area import Area
from d3a.models.strategy.simple import BuyStrategy, OfferStrategy
from d3a.web import runweb


log = getLogger(__name__)


@click.group(name='d3a', cls=DefaultGroup, default='run', default_if_no_args=True)
@click.option('-l', '--log-level', type=Choice(list(logging._nameToLevel.keys())), default='DEBUG',
              show_default=True, help="Log level")
def main(log_level):
    handler = logging.StreamHandler()
    handler.setFormatter(
        ColoredFormatter(
            "%(log_color)s%(asctime)s.%(msecs)03d %(levelname)-7s (%(lineno)4d) %(name)-25s: "
            "%(message)s%(reset)s",
            datefmt="%H:%M:%S"
        )
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)


@main.command()
def run():
    a = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 PV', strategy=OfferStrategy(offer_chance=.2,
                                                         price_fraction_choice=[2])),
                    Area('H1 Fridge', strategy=BuyStrategy())
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 PV', strategy=OfferStrategy(offer_chance=.25,
                                                         price_fraction_choice=[2])),
                    Area('H2 Fridge', strategy=BuyStrategy())
                ]
            ),
            Area('Hydro', strategy=OfferStrategy(offer_chance=.1, price_fraction_choice=(3, 4)))
        ]
    )
    a.activate()
    runweb(a)
    for i in range(900):
        log.debug("Tick %d", i)
        log.debug("Min/Max: %s", a.historical_min_max_price)
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
