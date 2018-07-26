from behave import then
from math import isclose
from d3a.models.strategy.const import ConstSettings


@then('the storages buy energy for no more than the min PV selling rate')
def storages_pv_min_selling_rate(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    house2 = list(filter(lambda x: x.name == "House 2", context.simulation.area.children))[0]
    storage1 = list(filter(lambda x: "Storage1" in x.name, house1.children))[0]
    storage2 = list(filter(lambda x: "Storage2" in x.name, house1.children))[0]
    pv = list(filter(lambda x: "PV" in x.name, house2.children))[0]

    for slot, market in house1.past_markets.items():
        for trade in market.trades:
            # Storage 2 should never buy due to break even point being lower than the
            # PV min selling rate
            assert trade.buyer != storage2.name
            if trade.buyer == storage1.name:
                # Storage 1 should buy energy offers with rate more than the PV min sell rate
                assert trade.offer.price / trade.offer.energy >= pv.min_selling_price.m

    for slot, market in house2.past_markets.items():
        assert all(trade.seller == pv.name for trade in market.trades)
        assert all(trade.offer.price / trade.offer.energy >= pv.min_selling_price.m
                   for trade in market.trades)


@then('the PV risk based strategy decrease its sold/unsold offers price as expected')
def pv_risk_based_price_decrease(context):
    house = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: "H1 PV" in x.name, house.children))[0]
    market_maker_rate = context.simulation.simulation_config.market_maker_rate
    slot_length = context.simulation.simulation_config.slot_length.seconds
    tick_length = context.simulation.simulation_config.tick_length.seconds
    wait_time = tick_length * ConstSettings.MAX_OFFER_TRAVERSAL_LENGTH + 1
    number_of_updates_per_slot = int(slot_length/wait_time)

    if pv.strategy.energy_rate_decrease_option.value == 2:
        assert False

    for slot, market in house.past_markets.items():
        price_dec_per_slot = market_maker_rate[slot.hour] * (1 - pv.strategy.risk / 100)
        price_dec_per_update = price_dec_per_slot / number_of_updates_per_slot
        for id, offer in market.offers.items():
            assert isclose((offer.price/offer.energy),
                           market_maker_rate[slot.hour] * pv.strategy.risk / 100)
        for trade in market.trades:
            if trade.seller == pv.name:
                assert any([isclose(trade.offer.price / trade.offer.energy,
                                    (market_maker_rate[slot.hour] - i * price_dec_per_update))
                            for i in range(1, (number_of_updates_per_slot + 1))])


@then('the PV constant based strategy decrease its sold/unsold offers price as expected')
def pv_const_based_price_decrease(context):
    house = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: "H1 PV" in x.name, house.children))[0]
    market_maker_rate = context.simulation.simulation_config.market_maker_rate
    slot_length = context.simulation.simulation_config.slot_length.seconds
    tick_length = context.simulation.simulation_config.tick_length.seconds
    wait_time = tick_length * ConstSettings.MAX_OFFER_TRAVERSAL_LENGTH + 1
    number_of_updates_per_slot = int(slot_length/wait_time)

    if pv.strategy.energy_rate_decrease_option.value == 1:
        assert False

    for slot, market in house.past_markets.items():
        price_dec_per_slot = number_of_updates_per_slot\
                             * pv.strategy.energy_rate_decrease_per_update
        for id, offer in market.offers.items():
            assert isclose((offer.price/offer.energy),
                           market_maker_rate[slot.hour] - price_dec_per_slot)
        for trade in market.trades:
            if trade.seller == pv.name:
                assert any([isclose(trade.offer.price / trade.offer.energy,
                                    (market_maker_rate[slot.hour] -
                                     i * pv.strategy.energy_rate_decrease_per_update))
                            for i in range(1, (number_of_updates_per_slot + 1))])
