from behave import then
from math import isclose


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


@then('the PV risk based strategy decrease its unsold offers price as expected')
def pv_risk_based_price_decrease(context):
    house = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: "H1 PV" in x.name, house.children))[0]
    mmr = context.simulation.simulation_config.market_maker_rate

    risk = pv.strategy.risk

    for slot, market in house.past_markets.items():
        for id, offer in market.offers.items():
            print("Slot: " + str(slot))
            print("Seller: " + str(offer.seller))
            print("Unsold Offered Rate: " + str(offer.price/offer.energy))
            print("Market Maker Rate: " + str(mmr[slot.hour]))
            print("Risk based Rate: " + str(mmr[slot.hour] * risk / 100))
            assert isclose((offer.price/offer.energy),
                           mmr[slot.hour] * risk / 100)

        for trade in market.trades:
            if trade.seller == pv.name and pv.strategy.energy_rate_decrease_option.value == 1:
                assert isclose((trade.offer.price/trade.offer.energy), mmr[slot.hour] * risk/100)
    # assert False
