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
import pytest
from unittest.mock import MagicMock
from math import isclose
from uuid import uuid4
from d3a.models.market.market_structures import Trade
from d3a.d3a_core.sim_results.stats import MarketEnergyBills, primary_unit_prices, \
    recursive_current_markets, total_avg_trade_price

from d3a.d3a_core.util import make_iaa_name
from d3a.models.strategy import BaseStrategy
from d3a_interface.constants_limits import ConstSettings


class FakeArea:
    def __init__(self, name, children=[], past_markets=[]):
        self.name = name
        self.display_type = "Area"
        self.children = children
        self.past_markets = past_markets
        self.strategy = MagicMock(spec=BaseStrategy)
        self.uuid = uuid4()

    @property
    def current_market(self):
        return 'market %s' % self.name if self.children else None


class FakeMarket:
    def __init__(self, trades, name="Area", fees=0.0):
        self.name = name
        self.trades = trades
        self.time_slot = 15
        self.market_fee = fees


class FakeOffer:
    def __init__(self, price, energy, seller):
        self.price = price
        self.energy = energy
        self.seller = seller


def _trade(price, buyer, energy=1, seller=None):
    return Trade('id', 0, FakeOffer(price, energy, seller), seller, buyer, None)


@pytest.fixture
def area():
    return FakeArea('parent',
                    [FakeArea('child1'),
                     FakeArea('child2', [FakeArea('grandchild1', [FakeArea('-')])]),
                     FakeArea('child3', [FakeArea('grandchild2')])])


def test_recursive_current_markets(area):
    markets = list(recursive_current_markets(area))
    assert len(markets) == 4
    assert all(market in markets for market in (
        'market parent', 'market child2', 'market grandchild1', 'market child3'
    ))


@pytest.fixture
def markets():
    """Example with all equal energy prices"""
    return (
        FakeMarket((_trade(5, 'Fridge'), _trade(3, 'PV'), _trade(10, 'IAA 1'))),
        FakeMarket((_trade(1, 'Storage'), _trade(4, 'Fridge'), _trade(6, 'Fridge'),
                    _trade(2, 'Fridge'))),
        FakeMarket((_trade(11, 'IAA 3'), _trade(20, 'IAA 9'), _trade(21, 'IAA 3')))
    )


@pytest.fixture
def markets2():
    """Example with different energy prices to test weighted averaging"""
    return(
        FakeMarket((_trade(11, 'Fridge', 11), _trade(4, 'Storage', 4), _trade(1, 'IAA 1', 10))),
        FakeMarket((_trade(3, 'ECar', 1), _trade(9, 'Fridge', 3), _trade(3, 'Storage', 1)))
    )


def test_total_avg_trade_price(markets, markets2):
    assert total_avg_trade_price(markets) == 3.5
    assert total_avg_trade_price(markets2) == 1.5


def test_primary_unit_prices(markets2):
    prices = list(primary_unit_prices(markets2))
    assert min(prices) == 1
    assert max(prices) == 3


@pytest.fixture
def grid():
    return FakeArea('grid', children=[
        FakeArea('house1',
                 children=[FakeArea('fridge'), FakeArea('pv')],
                 past_markets=[FakeMarket((_trade(2, 'fridge', 2, 'pv'),
                                           _trade(3, 'fridge', 1, 'iaa')), 'house1'),
                               FakeMarket((_trade(1, 'fridge', 2, 'pv'),), 'house1')]),
        FakeArea('house2',
                 children=[FakeArea('e-car')],
                 past_markets=[FakeMarket((_trade(1, 'e-car', 4, 'iaa'),
                                           _trade(1, 'e-car', 8, 'iaa'),
                                           _trade(3, 'iaa', 5, 'e-car')), 'house2'),
                               FakeMarket((_trade(1, 'e-car', 1, 'iaa'),), 'house2')]),
        FakeArea('commercial')
    ], past_markets=[
        FakeMarket((_trade(2, 'house2', 12, 'commercial'),), 'grid'),
        FakeMarket((_trade(1, 'house2', 1, 'commercial'),), 'grid')
    ])


def test_energy_bills(grid):
    ConstSettings.GeneralSettings.KEEP_PAST_MARKETS = True
    m_bills = MarketEnergyBills()
    m_bills.update(grid)
    result = m_bills.bills_results
    assert result['house2']['Accumulated Trades']['bought'] == result['commercial']['sold'] == 13
    assert result['house2']['Accumulated Trades']['spent'] == \
        result['commercial']['earned'] == \
        0.03
    assert result['commercial']['spent'] == result['commercial']['bought'] == 0
    assert result['fridge']['bought'] == 5 and isclose(result['fridge']['spent'], 0.06)
    assert result['pv']['sold'] == 4 and isclose(result['pv']['earned'], 0.03)
    assert 'children' not in result


def test_energy_bills_last_past_market(grid):
    ConstSettings.GeneralSettings.KEEP_PAST_MARKETS = False
    m_bills = MarketEnergyBills()
    m_bills.update(grid)
    result = m_bills.bills_results
    assert result['house2']['Accumulated Trades']['bought'] == result['commercial']['sold'] == 1
    assert result['house2']['Accumulated Trades']['spent'] == \
        result['commercial']['earned'] == \
        0.01
    assert result['commercial']['spent'] == result['commercial']['bought'] == 0
    assert result['fridge']['bought'] == 2 and isclose(result['fridge']['spent'], 0.01)
    assert result['pv']['sold'] == 2 and isclose(result['pv']['earned'], 0.01)
    assert 'children' not in result


@pytest.fixture
def grid2():
    house1 = FakeArea('house1')
    house2 = FakeArea('house2')
    house1.display_type = "House 1 type"
    house2.display_type = "House 2 type"
    return FakeArea(
        'street',
        children=[house1, house2],
        past_markets=[FakeMarket(
            (_trade(2, make_iaa_name(house1), 3, make_iaa_name(house2)),), 'street'
        )]
    )


def test_energy_bills_finds_iaas(grid2):
    m_bills = MarketEnergyBills()
    m_bills.update(grid2)
    result = m_bills.bills_results
    assert result['house1']['bought'] == result['house2']['sold'] == 3


def test_energy_bills_ensure_device_types_are_populated(grid2):
    m_bills = MarketEnergyBills()
    m_bills.update(grid2)
    result = m_bills.bills_results
    assert result["house1"]["type"] == "House 1 type"
    assert result["house2"]["type"] == "House 2 type"


@pytest.fixture
def grid_fees():
    house1 = FakeArea('house1',
                      children=[FakeArea("testPV")],
                      past_markets=[FakeMarket([], name='house1', fees=2.0),
                                    FakeMarket([], name='house1', fees=6.0)])
    house2 = FakeArea('house2',
                      children=[FakeArea("testLoad")],
                      past_markets=[FakeMarket([], name='house2', fees=3.0)])
    house1.display_type = "House 1 type"
    house2.display_type = "House 2 type"
    return FakeArea(
        'street',
        children=[house1, house2],
        past_markets=[FakeMarket(
            (_trade(2, make_iaa_name(house1), 3, make_iaa_name(house2)),), 'street', fees=4.0
        )]
    )


def test_energy_bills_accumulate_fees(grid_fees):
    ConstSettings.GeneralSettings.KEEP_PAST_MARKETS = True
    m_bills = MarketEnergyBills()
    m_bills._update_market_fees(grid_fees, 'past_markets')
    assert m_bills.market_fees['house2'] == 0.03
    assert m_bills.market_fees['street'] == 0.04
    assert m_bills.market_fees['house1'] == 0.08


def test_energy_bills_use_only_last_market_if_not_keep_past_markets(grid_fees):
    ConstSettings.GeneralSettings.KEEP_PAST_MARKETS = False
    m_bills = MarketEnergyBills()
    m_bills._update_market_fees(grid_fees, 'past_markets')
    assert m_bills.market_fees['house2'] == 0.03
    assert m_bills.market_fees['street'] == 0.04
    assert m_bills.market_fees['house1'] == 0.06


def test_energy_bills_report_correctly_market_fees(grid_fees):
    ConstSettings.GeneralSettings.KEEP_PAST_MARKETS = True
    m_bills = MarketEnergyBills()
    m_bills.update(grid_fees)
    result = m_bills.bills_results
    assert result["street"]["house1"]["market_fee"] == 0.08
    assert result["street"]["house2"]["market_fee"] == 0.03
    assert result["street"]['Accumulated Trades']["market_fee"] == 0.04
    assert result["house1"]['Accumulated Trades']["market_fee"] == \
        result["street"]["house1"]["market_fee"]
    assert result["house2"]['Accumulated Trades']["market_fee"] == \
        result["street"]["house2"]["market_fee"]
