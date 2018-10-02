from behave import given, then
from math import isclose
from functools import reduce
from d3a.device_registry import DeviceRegistry
from d3a.util import make_ba_name
from d3a.models.strategy.const import ConstSettings


@given('we have configured all the default_2a devices in the registry')
def configure_default_2a_registry(context):
    DeviceRegistry.REGISTRY = {
        "H1 General Load": (22, 25),
        "H2 General Load": (22, 25),
        "H1 Storage1": (23, 25),
        "H1 Storage2": (23, 25),
    }


@then("the device registry is not empty in market class")
def check_device_registry(context):
    from d3a.setup.balancing_market.test_device_registry import device_registry_dict
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    for slot, market in house.past_markets.items():
        assert market.device_registry == device_registry_dict


@then('balancing market of {area} has {b_trade_nr} balancing trades and {s_trade_nr} spot trades')
def number_of_balancing_trades(context, area, b_trade_nr, s_trade_nr):
    b_trade_nr = int(b_trade_nr)
    s_trade_nr = int(s_trade_nr)
    area_object = next(filter(lambda x: x.name == area, context.simulation.area.children))

    for slot, market in area_object.past_balancing_markets.items():
        if len(market.trades) == 0:
            continue
        assert b_trade_nr == reduce(
            lambda acc, t: acc + 1 if t.buyer == make_ba_name(area_object) else acc,
            market.trades,
            0
        )
        assert len(area_object.past_markets[slot].trades) == s_trade_nr


@then('grid has 1 balancing trade from house 1 to house 2')
def grid_has_balancing_trade(context):
    for slot, market in context.simulation.area.past_balancing_markets.items():
        if len(market.trades) == 0:
            continue

        assert len(market.trades) == 1
        assert market.trades[0].buyer == "BA House 2"
        assert market.trades[0].seller == "BA House 1"

        assert len(context.simulation.area.past_markets[slot].trades) == 1


@then('all trades follow the device registry {device_name} rate for demand')
def follow_device_registry_energy_rate(context, device_name):
    energy_rate = DeviceRegistry.REGISTRY[device_name][0]

    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))

    assert all(int(abs(trade.offer.price / trade.offer.energy)) == int(energy_rate)
               for device in [house1, house2, context.simulation.area]
               for slot, market in device.past_balancing_markets.items()
               for trade in market.trades)


@then('all trades are in accordance to the balancing energy ratio')
def follow_balancing_energy_ratio(context):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))

    for area_object in [house1, house2]:
        for slot, market in area_object.past_balancing_markets.items():
            if len(market.trades) == 0:
                continue
            spot_energy = area_object.past_markets[slot].trades[0].offer.energy
            assert all(isclose(trade.offer.energy,
                               -spot_energy * ConstSettings.BALANCING_SPOT_TRADE_RATIO)
                       for trade in market.trades)


@then('all BAs buy balancing energy according to their balancing ratio')
def balancing_energy_according_to_ratio(context):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    # house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))

    for slot, market in house1.past_markets.items():
        house1_energy = sum(trade.offer.energy
                            for trade in market.trades)

        house1_balancing_supply_energy = \
            sum(abs(trade.offer.energy)
                for trade in house1.past_balancing_markets[slot].trades
                if trade.offer.energy > 0)

        house1_balancing_demand_energy = \
            sum(abs(trade.offer.energy)
                for trade in house1.past_balancing_markets[slot].trades
                if trade.offer.energy < 0)

        print(f"Spot market energy {house1_energy * house1.balancing_spot_trade_ratio} "
              f"balancing energy supply {house1_balancing_supply_energy} "
              f"demand {house1_balancing_demand_energy}")

        assert house1_balancing_demand_energy + 0.00001 >= \
            house1_energy * house1.balancing_spot_trade_ratio
        assert house1_balancing_supply_energy + 0.00001 >= \
            house1_energy * house1.balancing_spot_trade_ratio

        # assert all(balancing_market_offer_energies[e] == v
        #            for e, v in spot_market_offer_energies.items())

    # house2_energy = sum(trade.offer.energy
    #                     for slot, market in house2.past_markets.items()
    #                     for trade in market.trades)
    #
    # house2_balancing_supply_energy = \
    #     sum(trade.offer.energy
    #         for slot, market in house2.past_balancing_markets.items()
    #         for trade in market.trades
    #         if trade.offer.energy > 0)
    #
    # house2_balancing_demand_energy = \
    #     sum(trade.offer.energy
    #         for slot, market in house2.past_balancing_markets.items()
    #         for trade in market.trades
    #         if trade.offer.energy < 0)
    #
    # assert house2_balancing_demand_energy == house2_balancing_supply_energy
    # assert house2_balancing_demand_energy == house2_energy * house2.balancing_spot_trade_ratio
