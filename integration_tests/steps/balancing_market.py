from behave import given, then
from math import isclose
from functools import reduce
from d3a.device_registry import DeviceRegistry
from d3a.util import make_ba_name
from d3a.models.strategy.const import ConstSettings


@given('we have configured all the balancing_market.default_2a devices in the registry')
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
    for market in house.past_markets:
        assert market.device_registry == device_registry_dict


@then("no balancing market is created")
def check_balancing_market(context):
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    assert len(house.past_balancing_markets) == 0


@then('balancing market of {area} has {b_trade_nr} balancing trades and {s_trade_nr} spot trades')
def number_of_balancing_trades(context, area, b_trade_nr, s_trade_nr):
    b_trade_nr = int(b_trade_nr)
    s_trade_nr = int(s_trade_nr)
    area_object = next(filter(lambda x: x.name == area, context.simulation.area.children))

    for market in area_object.past_balancing_markets:
        if len(market.trades) == 0:
            continue
        reduced_trades = reduce(
            lambda acc, t: acc + 1 if t.buyer == make_ba_name(area_object) else acc,
            market.trades,
            0
        )
        assert b_trade_nr == reduced_trades
        assert len(area_object._markets.past_markets[market.time_slot].trades) == s_trade_nr


@then('balancing market of {area} has {r_trade_nr} reserve trades and {s_trade_nr} spot trades')
def number_of_reserve_trades(context, area, r_trade_nr, s_trade_nr):
    r_trade_nr = int(r_trade_nr)
    s_trade_nr = int(s_trade_nr)
    area_object = next(filter(lambda x: x.name == area, context.simulation.area.children))

    for market in area_object.past_balancing_markets:
        if len(market.trades) == 0:
            continue
        reduced_reserve_trades = reduce(
            lambda acc, t: acc + 1 if t.buyer == area_object.name + " Reserve" else acc,
            market.trades,
            0
        )

        assert r_trade_nr == reduced_reserve_trades
        assert len(area_object._markets.past_markets[market.time_slot].trades) == s_trade_nr


@then('grid has 1 balancing trade from house 1 to house 2')
def grid_has_balancing_trade_h1_h2(context):
    for market in context.simulation.area.past_balancing_markets:
        if len(market.trades) == 0:
            continue

        assert len(market.trades) == 1
        assert market.trades[0].buyer == "BA House 2"
        assert market.trades[0].seller == "BA House 1"

        assert len(context.simulation.area._markets.past_markets[market.time_slot].trades) == 1


@then('grid has {b_t_count} balancing trades from house 1 to house 2')
def grid_has_balancing_trades_h1_h2(context, b_t_count):
    b_t_count = int(b_t_count)
    for market in context.simulation.area.past_balancing_markets:
        if len(market.trades) == 0:
            continue

        assert len(market.trades) == b_t_count
        assert market.trades[0].buyer == "BA House 2"
        assert market.trades[0].seller == "BA House 1"

        past_market = context.simulation.area._markets.past_markets[market.time_slot]
        assert len(past_market.trades) == int(b_t_count / 2)


@then('all trades follow the device registry {device_name} rate for supply and demand')
def follow_device_registry_energy_rate(context, device_name):
    negative_energy_rate = -DeviceRegistry.REGISTRY[device_name][0]
    positive_energy_rate = DeviceRegistry.REGISTRY[device_name][1]

    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))

    assert all(int(round(trade.offer.price / trade.offer.energy, 2)) == int(negative_energy_rate)
               for device in [house1, house2, context.simulation.area]
               for market in device.past_balancing_markets
               for trade in market.trades if trade.offer.energy < 0)

    assert all(int(round(trade.offer.price / trade.offer.energy, 2)) == int(positive_energy_rate)
               for device in [house1, house2, context.simulation.area]
               for market in device.past_balancing_markets
               for trade in market.trades if trade.offer.energy > 0)


def match_balancing_trades_to_spot_trades(context, functor):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))

    for area_object in [house1, house2]:
        for market in area_object.past_balancing_markets:
            if len(market.trades) == 0:
                continue
            past_market = area_object._markets.past_markets[market.time_slot]
            spot_energy = past_market.trades[0].offer.energy
            assert functor(isclose(abs(trade.offer.energy),
                                   abs(spot_energy) *
                                   ConstSettings.BalancingSettings.SPOT_TRADE_RATIO)
                           for trade in market.trades)


@then('all trades are in accordance to the balancing energy ratio')
def follow_balancing_energy_ratio_all(context):
    match_balancing_trades_to_spot_trades(context, all)


@then('every balancing trade matches a spot market trade according to the balancing energy ratio')
def follow_balancing_energy_ratio_any(context):
    match_balancing_trades_to_spot_trades(context, any)


@then('all trades follow one of {device1} or {device2} rates for supply and demand')
def follow_device_registry_energy_rate_or(context, device1, device2):
    negative_energy_rate = (-int(DeviceRegistry.REGISTRY[device1][0]),
                            -int(DeviceRegistry.REGISTRY[device2][0]))
    positive_energy_rate = (int(DeviceRegistry.REGISTRY[device1][1]),
                            int(DeviceRegistry.REGISTRY[device2][1]))

    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))

    assert all(int(round(trade.offer.price / trade.offer.energy, 2)) in negative_energy_rate
               for device in [house1, house2, context.simulation.area]
               for market in device.past_balancing_markets
               for trade in market.trades if trade.offer.energy < 0)

    assert all(int(round(trade.offer.price / trade.offer.energy, 2)) in positive_energy_rate
               for device in [house1, house2, context.simulation.area]
               for market in device.past_balancing_markets
               for trade in market.trades if trade.offer.energy > 0)


@then('there are balancing trades on all markets for every market slot')
def balancing_trades_on_all_markets(context):
    grid = context.simulation.area
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))
    assert all(len(market.trades) > 0
               for area in [grid, house1, house2]
               for market in area.past_markets)
    assert all(len(market.trades) > 0
               for area in [grid, house1, house2]
               for market in area.past_balancing_markets)


@then('there are balancing trades on some markets')
def balancing_trades_exist_on_a_market(context):
    grid = context.simulation.area
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))
    assert any(len(market.trades) > 0
               for area in [grid, house1, house2]
               for market in area.past_balancing_markets)
