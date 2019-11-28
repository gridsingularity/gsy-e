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
import os
import glob
from math import isclose
from behave import then
from d3a.d3a_core.util import make_iaa_name


@then('all trades are equal to market_clearing_rate')
def test_traded_energy_rate(context):
    def has_one_of_clearing_rates(trade, market):
        return any(isclose((trade.offer.price / trade.offer.energy), clearing_rate)
                   for clearing_rate in market.state.clearing[trade.time])

    assert all(has_one_of_clearing_rates(trade, market)
               for child in context.simulation.area.children
               for market in child.past_markets
               for trade in market.trades
               if trade.time in market.state.clearing and
               market.state.clearing[trade.time] != 0 and
               trade.buyer == make_iaa_name(child))


@then('buyers and sellers are not same')
def test_different_buyer_seller(context):
    assert all(str(trade.offer.seller) != str(trade.buyer)
               for area in context.simulation.area.children
               for market in area.past_markets
               for trade in market.trades)


@then('cumulative traded offer energy equal to cumulative bid energy')
def test_cumulative_offer_bid_energy(context):
    areas = list()
    grid = context.simulation.area
    areas.append(grid)
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    areas.append(house1)

    for area in areas:
        if area.name != "House 1":
            continue
        child_names = [child.name for child in area.children]

        for market in area.past_markets:
            cumulative_traded_bid_energy = 0
            cumulative_traded_offer_energy = 0
            for trade in market.trades:

                if len(market.trades) == 1 or \
                        (trade.seller in child_names and trade.buyer in child_names):
                    # Device-to-device trading, no bid tracked
                    continue
                if trade.buyer in child_names:
                    cumulative_traded_bid_energy += trade.offer.energy
                if trade.seller in child_names:
                    cumulative_traded_offer_energy += trade.offer.energy
            residual = (cumulative_traded_offer_energy - cumulative_traded_bid_energy)
            assert isclose(residual, 0)


@then('all traded energy have finite value')
def test_finite_traded_energy(context):
    grid = context.simulation.area
    # Validate that all trades have less than 100 kWh of energy
    assert all(trade.offer.energy < 100
               for area in grid.children
               for market in area.past_markets
               for trade in market.trades)


@then('there are files with offers, bids & market_clearing_rate for every area')
def test_offer_bid_market_clearing_rate_files(context):
    base_path = os.path.join(context.export_path, "*")
    file_list = [os.path.join(base_path, 'grid-offers.csv'),
                 os.path.join(base_path, 'grid-bids.csv'),
                 os.path.join(base_path, 'grid-market-clearing-rate.csv'),
                 os.path.join(base_path, 'grid', 'house-1-offers.csv'),
                 os.path.join(base_path, 'grid', 'house-1-bids.csv'),
                 os.path.join(base_path, 'grid', 'house-1-market-clearing-rate.csv'),
                 os.path.join(base_path, 'grid', 'house-2-offers.csv'),
                 os.path.join(base_path, 'grid', 'house-2-bids.csv'),
                 os.path.join(base_path, 'grid', 'house-2-market-clearing-rate.csv')]

    assert all(len(glob.glob(f)) == 1 for f in file_list)


@then('the unmatched loads are tested')
def test_export_supply_demand_curve(context):
    sim_data_csv = glob.glob(os.path.join(context.export_path, "*", "plot",
                                          "unmatched_loads_grid.html"))
    if len(sim_data_csv) != 0:
        raise FileExistsError("Not found in {path}".format(path=context.export_path))
