from behave import then
from math import isclose
from pendulum import duration
from d3a.models.strategy.const import ConstSettings
from d3a import PENDULUM_TIME_FORMAT


@then('the storages buy energy for no more than the min PV selling rate')
def storages_pv_min_selling_rate(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    house2 = list(filter(lambda x: x.name == "House 2", context.simulation.area.children))[0]
    storage1 = list(filter(lambda x: "Storage1" in x.name, house1.children))[0]
    storage2 = list(filter(lambda x: "Storage2" in x.name, house1.children))[0]
    pv = list(filter(lambda x: "PV" in x.name, house2.children))[0]

    for market in house1.past_markets:
        for trade in market.trades:
            # Storage 2 should never buy due to break even point being lower than the
            # PV min selling rate
            assert trade.buyer != storage2.name
            if trade.buyer == storage1.name:
                # Storage 1 should buy energy offers with rate more than the PV min sell rate
                assert trade.offer.price / trade.offer.energy >= pv.strategy.min_selling_rate

    for market in house2.past_markets:
        assert all(trade.seller == pv.name for trade in market.trades)
        assert all(trade.offer.price / trade.offer.energy >= pv.strategy.min_selling_rate
                   for trade in market.trades)


@then('the PV strategy decrease its sold/unsold offers price as expected')
def pv_price_decrease(context):
    house = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: "H1 PV" in x.name, house.children))[0]
    market_maker_rate = context.simulation.simulation_config.market_maker_rate

    slot_length = context.simulation.simulation_config.slot_length.seconds
    tick_length = context.simulation.simulation_config.tick_length.seconds
    wait_time = tick_length * ConstSettings.GeneralSettings.MAX_OFFER_TRAVERSAL_LENGTH + 1
    number_of_updates_per_slot = int(slot_length/wait_time)

    if pv.strategy.energy_rate_decrease_option.value == 1:
        for market in house.past_markets:
            slot = market.time_slot
            price_dec_per_slot =\
                market_maker_rate[slot.format(PENDULUM_TIME_FORMAT)] * (1 - pv.strategy.risk / 100)
            price_dec_per_update = price_dec_per_slot / number_of_updates_per_slot
            minimum_rate = max((market_maker_rate[slot.format(PENDULUM_TIME_FORMAT)] *
                                pv.strategy.risk / 100), pv.strategy.min_selling_rate)
            for id, offer in market.offers.items():
                assert isclose(round(offer.price/offer.energy, 6), minimum_rate)
            for trade in market.trades:
                if trade.seller == pv.name:
                    assert any([isclose(round(trade.offer.price / trade.offer.energy, 6),
                                        max((market_maker_rate[slot.format(PENDULUM_TIME_FORMAT)] -
                                             i * price_dec_per_update),
                                            pv.strategy.min_selling_rate))
                                for i in range(number_of_updates_per_slot + 1)])

    elif pv.strategy.energy_rate_decrease_option.value == 2:
        for market in house.past_markets:
            slot = market.time_slot
            price_dec_per_slot = number_of_updates_per_slot \
                * pv.strategy.energy_rate_decrease_per_update
            for id, offer in market.offers.items():
                assert isclose(
                    (offer.price / offer.energy),
                    market_maker_rate[slot.format(PENDULUM_TIME_FORMAT)] - price_dec_per_slot
                )
            for trade in market.trades:
                if trade.seller == pv.name:
                    assert any([isclose(trade.offer.price / trade.offer.energy,
                                        (market_maker_rate[slot.format(PENDULUM_TIME_FORMAT)] -
                                         i * pv.strategy.energy_rate_decrease_per_update))
                                for i in range(number_of_updates_per_slot + 1)])
    else:
        assert False


@then("the PV offers energy as expected at an expected price")
def pv_const_energy(context):
    house = list(filter(lambda x: x.name == "House 2", context.simulation.area.children))[0]
    pv = list(filter(lambda x: "H2 PV" in x.name, house.children))[0]
    price_dec_per_slot = 0.1 * int(context.simulation.simulation_config.slot_length.seconds /
                                   context.simulation.simulation_config.tick_length.seconds)
    market_maker_rate = context.simulation.simulation_config.market_maker_rate

    for market in house.past_markets:
        slot = market.time_slot
        for id, offer in market.offers.items():
            if offer.seller == pv.name:
                assert isclose(
                    (offer.price / offer.energy),
                    market_maker_rate[slot.format(PENDULUM_TIME_FORMAT)] - price_dec_per_slot
                )
                assert isclose(offer.energy, pv.strategy.energy_production_forecast_kWh[slot] *
                               pv.strategy.panel_count, rel_tol=0.001)


@then('the load buys at most the energy equivalent of {power_W} W')
def load_buys_200_W(context, power_W):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    load = list(filter(lambda x: "Load" in x.name, house1.children))[0]

    max_desired_energy = float(power_W) * (house1.config.slot_length / duration(hours=1)) / 1000.0
    total_energy_per_slot = []
    for market in house1.past_markets:
        total_energy = sum(trade.offer.energy
                           for trade in market.trades
                           if trade.buyer == load.name)
        assert total_energy <= max_desired_energy
        total_energy_per_slot.append(total_energy)

    assert max(total_energy_per_slot) == max_desired_energy
