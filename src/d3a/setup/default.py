from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.simple import OfferStrategy, BuyStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area(
                        'H1 PV 1',
                        strategy=OfferStrategy(offer_chance=.2,
                                               price_fraction_choice=[.023, .026]),
                        appliance=SimpleAppliance()
                    ),
                    Area(
                        'H1 PV 2',
                        strategy=OfferStrategy(offer_chance=.2,
                                               price_fraction_choice=[.024, .025]),
                        appliance=SimpleAppliance()
                    ),
                    Area(
                        'H1 Fridge',
                        strategy=BuyStrategy(max_energy=50),
                        appliance=SimpleAppliance()
                    )
                ]
            ),
            Area(
                'House 2',
                [
                    Area(
                        'H2 PV',
                        strategy=OfferStrategy(offer_chance=.25, price_fraction_choice=[.02]),
                        appliance=SimpleAppliance()
                    ),
                    Area(
                        'H2 Fridge',
                        strategy=BuyStrategy(max_energy=50),
                        appliance=SimpleAppliance()
                    )
                ]
            ),
            Area('Hydro', strategy=OfferStrategy(offer_chance=.1,
                                                 price_fraction_choice=(.02, .05)))
        ],
        config=config
    )
    return area
