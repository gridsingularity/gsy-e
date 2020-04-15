"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from behave import then
from math import isclose
from d3a.d3a_core.sim_results.export_unmatched_loads import ExportUnmatchedLoads, \
    get_number_of_unmatched_loads
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.util import make_iaa_name
from d3a import limit_float_precision
from d3a.constants import DEFAULT_PRECISION


@then('the load has no unmatched loads')
def no_unmatched_loads(context):
    unmatched, unmatched_redis = \
        ExportUnmatchedLoads(context.simulation.area).get_current_market_results(
            all_past_markets=True)
    assert get_number_of_unmatched_loads(unmatched) == 0


@then('the load has unmatched loads')
def has_unmatched_loads(context):
    unmatched, unmatched_redis = \
        ExportUnmatchedLoads(context.simulation.area).get_current_market_results(
            all_past_markets=True)
    assert get_number_of_unmatched_loads(unmatched) > 0


@then('the {device} bid is partially fulfilled by the PV offers')
def device_partially_fulfill_bid(context, device):
    grid = context.simulation.area
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    device_name = "H1 General Load" if device == "load" else "H1 Storage"
    load_or_storage = next(filter(lambda x: device_name in x.name, house1.children))
    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))
    pvs = list(filter(lambda x: "H2 PV" in x.name, house2.children))

    for market in house1.past_markets:
        slot = market.time_slot
        if len(market.trades) == 0:
            continue
        for trade in market.trades:
            assert load_or_storage.strategy.bid_update.initial_rate[market.time_slot] <= \
                   round(trade.offer.price / trade.offer.energy, DEFAULT_PRECISION) <= \
                   load_or_storage.strategy.bid_update.final_rate[market.time_slot]

        # Assert one trade for each PV
        assert len(market.trades) == 5
        assert all(trade.buyer == load_or_storage.name for trade in market.trades)
        assert all(trade.seller == make_iaa_name(house1)
                   for trade in house1.get_past_market(slot).trades)
        assert len(grid.get_past_market(slot).trades) == 5
        assert all(trade.buyer == make_iaa_name(house1)
                   for trade in grid.get_past_market(slot).trades)
        assert all(trade.seller == make_iaa_name(house2)
                   for trade in grid.get_past_market(slot).trades)

        pv_names = [pv.name for pv in pvs]
        assert len(grid.get_past_market(slot).trades) == 5
        assert all(trade.buyer == make_iaa_name(house2)
                   for trade in house2.get_past_market(slot).trades)
        assert all(trade.seller in pv_names
                   for trade in house2.get_past_market(slot).trades)


@then('the PV always provides constant power according to load demand')
def pv_constant_power(context):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    load = next(filter(lambda x: "H1 General Load" in x.name, house1.children))

    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))
    pv = next(filter(lambda x: "H2 PV" in x.name, house2.children))

    load_energies_set = set()
    pv_energies_set = set()
    for market in house1.past_markets:
        for trade in market.trades:
            if trade.buyer == load.name:
                load_energies_set.add(trade.offer.energy)

    for market in house2.past_markets:
        for trade in market.trades:
            if trade.seller == pv.name:
                pv_energies_set.add(trade.offer.energy)

    assert len(load_energies_set) == 1
    assert len(pv_energies_set) == 1
    assert load_energies_set == pv_energies_set


@then('the storage is never selling energy')
def storage_never_selling(context):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    storage = next(filter(lambda x: "H1 Storage" in x.name, house1.children))

    for market in storage.past_markets:
        for trade in market.trades:
            assert trade.seller != storage.name
            assert trade.buyer == storage.name


@then('the storage final SOC is {soc_level}%')
def final_soc_full(context, soc_level):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    storage = next(filter(lambda x: "H1 Storage" in x.name, house1.children))
    if soc_level == '0':
        soc_level = ConstSettings.StorageSettings.MIN_ALLOWED_SOC * 100.0
    final_soc = list(storage.strategy.state.charge_history.values())[-2]
    assert isclose(final_soc, float(soc_level))


@then('the energy rate for all trades are in between initial and final buying rate of storage')
def energy_rate_average_between_min_and_max_ess_pv(context):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    storage = next(filter(lambda x: "H1 Storage" in x.name, house1.children))

    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))
    pv = next(filter(lambda x: "H2 PV" in x.name, house2.children))

    for market in house1.past_markets:
        for trade in market.trades:
            if trade.buyer == storage.name:
                initial = storage.strategy.bid_update.initial_rate[market.time_slot]
                final = storage.strategy.bid_update.final_rate[market.time_slot]
                assert initial <= (trade.offer.price / trade.offer.energy) <= final

    for market in house2.past_markets:
        for trade in market.trades:
            if trade.seller == pv.name:
                initial = storage.strategy.bid_update.initial_rate[market.time_slot]
                final = storage.strategy.bid_update.final_rate[market.time_slot]
                assert initial <= (trade.offer.price / trade.offer.energy) <= final


@then('the storage is never buying energy and is always selling energy')
def storage_never_buys_always_sells(context):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    storage = next(filter(lambda x: "H1 Storage" in x.name, house1.children))

    for market in house1.past_markets:
        for trade in market.trades:
            assert trade.buyer != storage.name
            assert trade.seller == storage.name


@then('all the trade rates are between load device buying boundaries')
def trade_rates_break_even(context):

    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    storage = next(filter(lambda x: "H1 Storage" in x.name, house1.children))

    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))
    load = next(filter(lambda x: "H2 General Load" in x.name, house2.children))

    for area in [house1, house2, storage, load]:
        for market in area.past_markets:
            for trade in market.trades:
                assert load.strategy.bid_update.initial_rate[market.time_slot] <= \
                       limit_float_precision(trade.offer.price / trade.offer.energy) <= \
                       load.strategy.bid_update.final_rate[market.time_slot]


@then('CEP posted the residual offer at the old rate')
def cep_offer_residual_offer_rate(context):
    house = next(filter(lambda x: "House" in x.name, context.simulation.area.children))
    cep = next(filter(lambda x: "Commercial Energy Producer" in x.name, house.children))

    for market in house.past_markets:
        if len(market.trades) > 0:
            for id, offer in market.offers.items():
                assert isclose((offer.price / offer.energy),
                               cep.strategy.energy_rate[market.time_slot])


@then('Energy producer is {producer} & consumer is {consumer}')
def energy_origin(context, producer, consumer):
    trade_count = 0

    for market in context.simulation.area.past_markets:
        if len(market.trades) > 0:
            for trade in market.trades:
                trade_count += 1
                assert trade.buyer_origin == consumer
                assert trade.seller_origin == producer

    assert trade_count > 0


@then('trades are matched only on the Grid market')
def trades_matched_on_grid(context):
    from d3a.models.market.market_structures import Offer, Bid
    # Assert that all grid trades contain Offer objects, bid trades are not tracked
    assert all(type(trade.offer) == Offer
               for market in context.simulation.area.past_markets
               for trade in market.trades)

    # Assert that all House 1 trades contain Bid objects
    house1 = next(c for c in context.simulation.area.children if c.name == "House 1")
    assert all(type(trade.offer) == Bid
               for market in house1.past_markets
               for trade in market.trades)

    # Assert that all House 2 trades contain Offer objects
    house2 = next(c for c in context.simulation.area.children if c.name == "House 2")
    assert all(type(trade.offer) == Offer
               for market in house2.past_markets
               for trade in market.trades)
