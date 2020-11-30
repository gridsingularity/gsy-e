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
from unittest.mock import MagicMock, Mock
from math import isclose
from pendulum import today, now
from uuid import uuid4

from d3a.models.market.market_structures import Trade
from d3a_interface.sim_results.bills import MarketEnergyBills
from d3a.d3a_core.sim_results.endpoint_buffer import SimulationEndpointBuffer
from d3a.d3a_core.util import make_iaa_name
from d3a import constants


class FakeArea:
    def __init__(self, name, children=[], past_markets=[]):
        self.name = name
        self.display_type = "Area"
        self.children = children
        self.past_markets = past_markets
        self.strategy = None
        self.uuid = uuid4()
        self.parent = None
        self.baseline_peak_energy_import_kWh = None
        self.baseline_peak_energy_export_kWh = None
        self.import_capacity_kWh = None
        self.export_capacity_kWh = None
        self.stats = MagicMock()
        self.stats.imported_energy = Mock()
        self.stats.exported_energy = Mock()

    @property
    def current_market(self):
        return self.past_markets[-1] if self.past_markets else None

    def get_state(self):
        return {}


class FakeMarket:
    def __init__(self, trades, name="Area", fees=0.0):
        self.name = name
        self.trades = trades
        self.time_slot = today(tz=constants.TIME_ZONE)
        self.market_fee = fees
        self.const_fee_rate = fees
        self.time_slot_str = self.time_slot.format(constants.DATE_TIME_FORMAT) \
            if self.time_slot is not None \
            else None


class FakeOffer:
    def __init__(self, price, energy, seller):
        self.price = price
        self.energy = energy
        self.seller = seller
        self.energy_rate = price / energy
        self.id = str(uuid4())


def _trade(price, buyer, energy=1, seller=None, fee_price=0.):
    return Trade('id', now(tz=constants.TIME_ZONE), FakeOffer(price, energy, seller),
                 seller, buyer, None, fee_price=fee_price)


@pytest.fixture
def area():
    return FakeArea('parent',
                    [FakeArea('child1'),
                     FakeArea('child2', [FakeArea('grandchild1', [FakeArea('-')])]),
                     FakeArea('child3', [FakeArea('grandchild2')])])


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


@pytest.fixture
def grid():
    fridge = FakeArea('fridge')
    pv = FakeArea('pv')
    house1 = FakeArea('house1',
                      children=[fridge, pv])
    house1.past_markets = [FakeMarket((_trade(1, 'fridge', 2, 'pv'),), 'house1')]
    fridge.parent = house1
    pv.parent = house1

    e_car = FakeArea('e-car')
    house2 = FakeArea('house2',
                      children=[e_car])
    house2.past_markets = [FakeMarket((_trade(1, 'e-car', 1, 'iaa'),), 'house2')]
    e_car.parent = house2

    commercial = FakeArea('commercial')
    grid = FakeArea('grid', children=[house1, house2, commercial])
    grid.past_markets = [FakeMarket((_trade(1, 'house2', 1, 'commercial'),), 'grid')]
    house1.parent = grid
    house2.parent = grid
    commercial.parent = grid
    return grid


def test_energy_bills(grid):
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid, True)
    epb.current_market_time_slot_str = grid.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid)
    m_bills = MarketEnergyBills()
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    result = m_bills.bills_results

    assert result['house2']['Accumulated Trades']['bought'] == result['commercial']['sold'] == 1
    assert result['house2']['Accumulated Trades']['spent'] == result['commercial']['earned'] == \
        0.01
    assert result['commercial']['spent'] == result['commercial']['bought'] == 0
    assert result['fridge']['bought'] == 2 and isclose(result['fridge']['spent'], 0.01)
    assert result['pv']['sold'] == 2 and isclose(result['pv']['earned'], 0.01)
    assert 'children' not in result

    grid.children[0].past_markets = [FakeMarket((_trade(2, 'fridge', 2, 'pv'),
                                                 _trade(3, 'fridge', 1, 'iaa')), 'house1')]
    grid.children[1].past_markets = [FakeMarket((_trade(1, 'e-car', 4, 'iaa'),
                                                _trade(1, 'e-car', 8, 'iaa'),
                                                _trade(3, 'iaa', 5, 'e-car')), 'house2')]
    grid.past_markets = [FakeMarket((_trade(2, 'house2', 12, 'commercial'),), 'grid')]
    epb.current_market_time_slot_str = grid.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid)
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict)
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
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid, True)
    epb.current_market_time_slot_str = grid.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid)
    m_bills = MarketEnergyBills()
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    result = m_bills.bills_results
    assert result['house2']['Accumulated Trades']['bought'] == result['commercial']['sold'] == 1
    assert result['house2']['Accumulated Trades']['spent'] == \
        result['commercial']['earned'] == \
        0.01
    external_trades = result['house2']['External Trades']
    assert external_trades['total_energy'] == external_trades['bought'] - external_trades['sold']
    assert external_trades['total_cost'] == external_trades['spent'] - external_trades['earned']
    assert result['commercial']['spent'] == result['commercial']['bought'] == 0
    assert result['fridge']['bought'] == 2 and isclose(result['fridge']['spent'], 0.01)
    assert result['pv']['sold'] == 2 and isclose(result['pv']['earned'], 0.01)
    assert 'children' not in result


@pytest.fixture
def grid2():
    house1 = FakeArea('house1')
    house2 = FakeArea('house2')
    grid = FakeArea(
        'street',
        children=[house1, house2],
        past_markets=[FakeMarket(
            (_trade(2, make_iaa_name(house1), 3, make_iaa_name(house2)),), 'street'
        )]
    )
    house1.parent = grid
    house2.parent = grid
    return grid


def test_energy_bills_finds_iaas(grid2):
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid2, True)
    epb.current_market_time_slot_str = grid2.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid2)
    m_bills = MarketEnergyBills()
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    result = m_bills.bills_results
    assert result['house1']['bought'] == result['house2']['sold'] == 3


def test_energy_bills_ensure_device_types_are_populated(grid2):
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid2, True)
    epb.current_market_time_slot_str = grid2.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid2)
    m_bills = MarketEnergyBills()
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    result = m_bills.bills_results
    assert result["house1"]["type"] == "Area"
    assert result["house2"]["type"] == "Area"


@pytest.fixture
def grid_fees():
    house1 = FakeArea('house1',
                      children=[FakeArea("testPV")],
                      past_markets=[FakeMarket([], name='house1', fees=6.0)])
    house2 = FakeArea('house2',
                      children=[FakeArea("testLoad")],
                      past_markets=[FakeMarket((_trade(2, "testload", 3, "IAA house2",
                                                       fee_price=3.0),), name='house2', fees=3.0)])
    house1.display_type = "House 1 type"
    house2.display_type = "House 2 type"
    grid = FakeArea(
        'street',
        children=[house1, house2],
        past_markets=[FakeMarket((_trade(2, make_iaa_name(house2), 3, make_iaa_name(house1),
                                         fee_price=1.0),), 'street', fees=1.0)
                      ])
    house1.parent = grid
    house2.parent = grid
    return grid


def test_energy_bills_accumulate_fees(grid_fees):
    constants.D3A_TEST_RUN = True
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid_fees, True)
    epb.current_market_time_slot_str = grid_fees.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid_fees)
    m_bills = MarketEnergyBills()
    m_bills._update_market_fees(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    grid_fees.children[0].past_markets = [FakeMarket([], name='house1', fees=2.0)]
    grid_fees.children[1].past_markets = []
    grid_fees.past_markets = [FakeMarket((_trade(2, make_iaa_name(grid_fees.children[0]), 3,
                                                 make_iaa_name(grid_fees.children[0]),
                                                 fee_price=4.0),), 'street', fees=4.0)]
    epb.current_market_time_slot_str = grid_fees.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid_fees)
    m_bills._update_market_fees(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    assert m_bills.market_fees['house2'] == 0.03
    assert m_bills.market_fees['street'] == 0.05
    assert m_bills.market_fees['house1'] == 0.08


def test_energy_bills_use_only_last_market_if_not_keep_past_markets(grid_fees):
    constants.D3A_TEST_RUN = False
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid_fees, True)
    epb.current_market_time_slot_str = grid_fees.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid_fees)
    m_bills = MarketEnergyBills()
    m_bills._update_market_fees(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    assert m_bills.market_fees['house2'] == 0.03
    assert m_bills.market_fees['street'] == 0.01
    assert m_bills.market_fees['house1'] == 0.06


def test_energy_bills_report_correctly_market_fees(grid_fees):
    constants.D3A_TEST_RUN = True
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid_fees, True)
    epb.current_market_time_slot_str = grid_fees.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid_fees)
    m_bills = MarketEnergyBills()
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    grid_fees.children[0].past_markets = [FakeMarket([], name='house1', fees=2.0)]
    grid_fees.children[1].past_markets = []
    grid_fees.past_markets = [FakeMarket((_trade(2, make_iaa_name(grid_fees.children[0]), 3,
                                                 make_iaa_name(grid_fees.children[0]),
                                                 fee_price=4.0),), 'street', fees=4.0)]
    epb.current_market_time_slot_str = grid_fees.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid_fees)
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    result = m_bills.bills_results
    assert result["street"]["house1"]["market_fee"] == 0.04
    assert result["street"]["house2"]["market_fee"] == 0.01
    assert result["street"]['Accumulated Trades']["market_fee"] == 0.05
    assert result["house1"]['External Trades']["market_fee"] == 0.0
    assert result["house2"]['External Trades']["market_fee"] == 0.0
