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
from unittest.mock import MagicMock, Mock
from math import isclose
from uuid import uuid4
import pytest
from pendulum import today, now
from gsy_framework.unit_test_utils import assert_dicts_identical, \
    assert_lists_contain_same_elements
from gsy_framework.sim_results.bills import MarketEnergyBills
from gsy_framework.data_classes import Trade
from d3a.gsy_e_core.sim_results.endpoint_buffer import SimulationEndpointBuffer
from d3a.gsy_e_core.util import make_iaa_name
from d3a import constants
from d3a.models.area.throughput_parameters import ThroughputParameters


@pytest.fixture(scope="function", autouse=True)
def auto_fixture():
    yield
    constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = False


class FakeArea:
    def __init__(self, name, children=[], past_markets=[]):
        self.name = name
        self.display_type = "Area"
        self.children = children
        self.past_markets = past_markets
        self.strategy = None
        self.uuid = str(uuid4())
        self.parent = None
        self.throughput = ThroughputParameters()
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
        self.offer_history = []
        self.bid_history = []


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
    grid.name_uuid_mapping = {
        "grid": grid.uuid,
        "house1": house1.uuid,
        "house2": house2.uuid,
        "commercial": commercial.uuid,
        "fridge": fridge.uuid,
        "pv": pv.uuid,
        "e-car": e_car.uuid
    }
    return grid


def test_energy_bills(grid):
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid, True)
    epb.current_market_time_slot_str = grid.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid)
    m_bills = MarketEnergyBills(should_export_plots=True)
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict,
                   epb.current_market_time_slot_str)
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
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict,
                   epb.current_market_time_slot_str)
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
    m_bills = MarketEnergyBills(should_export_plots=True)
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict,
                   epb.current_market_time_slot_str)
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


def test_energy_bills_redis(grid):
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid, True)
    epb.current_market_time_slot_str = grid.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid)
    m_bills = MarketEnergyBills(should_export_plots=True)
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict,
                   epb.current_market_time_slot_str)
    result = m_bills.bills_results
    result_redis = m_bills.bills_redis_results
    for house in grid.children:
        assert_dicts_identical(result[house.name], result_redis[house.uuid])
        for device in house.children:
            assert_dicts_identical(result[device.name], result_redis[device.uuid])


def test_calculate_raw_energy_bills(grid):
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid, True)
    epb.current_market_time_slot_str = grid.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid)
    m_bills = MarketEnergyBills(should_export_plots=True)
    m_bills._update_market_fees(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    bills = m_bills._energy_bills(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    grid_children_uuids = [c.uuid for c in grid.children]
    assert all(h in bills for h in grid_children_uuids)
    commercial_uuid = grid.name_uuid_mapping["commercial"]
    assert 'children' not in bills[commercial_uuid]
    house1_uuid = grid.name_uuid_mapping["house1"]
    assert grid.name_uuid_mapping["pv"] in bills[house1_uuid]["children"]
    pv_bills = [v for k, v in bills[house1_uuid]["children"].items()
                if k == grid.name_uuid_mapping["pv"]][0]
    assert pv_bills['sold'] == 2.0 and isclose(pv_bills['earned'], 0.01)
    assert grid.name_uuid_mapping["fridge"] in bills[house1_uuid]["children"]
    house2_uuid = grid.name_uuid_mapping["house2"]
    assert grid.name_uuid_mapping["e-car"] in bills[house2_uuid]["children"]


def _compare_bills(bill1, bill2):
    key_list = ["spent", "earned", "bought", "sold", "total_energy", "total_cost",
                "market_fee", "type"]
    for k in key_list:
        assert bill1[k] == bill2[k]


def test_flatten_energy_bills(grid):
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid, True)
    epb.current_market_time_slot_str = grid.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid)
    m_bills = MarketEnergyBills(should_export_plots=True)
    m_bills._update_market_fees(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    bills = m_bills._energy_bills(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    flattened = {}
    m_bills._flatten_energy_bills(bills, flattened)
    assert all("children" not in v for _, v in flattened.items())
    name_list = ['house1', 'house2', 'pv', 'fridge', 'e-car', 'commercial']
    uuid_list = [grid.name_uuid_mapping[k] for k in name_list]
    assert_lists_contain_same_elements(uuid_list, flattened.keys())
    house1_uuid = grid.name_uuid_mapping["house1"]
    _compare_bills(flattened[house1_uuid], bills[house1_uuid])
    house2_uuid = grid.name_uuid_mapping["house2"]
    _compare_bills(flattened[house2_uuid], bills[house2_uuid])
    commercial_uuid = grid.name_uuid_mapping["commercial"]
    _compare_bills(flattened[commercial_uuid], bills[commercial_uuid])
    pv_uuid = grid.name_uuid_mapping["pv"]
    pv = [v for k, v in bills[house1_uuid]["children"].items() if k == pv_uuid][0]
    _compare_bills(flattened[pv_uuid], pv)
    fridge_uuid = grid.name_uuid_mapping["fridge"]
    fridge = [v for k, v in bills[house1_uuid]["children"].items() if k == fridge_uuid][0]
    _compare_bills(flattened[fridge_uuid], fridge)
    ecar_uuid = grid.name_uuid_mapping["e-car"]
    ecar = [v for k, v in bills[house2_uuid]["children"].items() if k == ecar_uuid][0]
    _compare_bills(flattened[ecar_uuid], ecar)


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
    m_bills = MarketEnergyBills(should_export_plots=True)
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict,
                   epb.current_market_time_slot_str)
    result = m_bills.bills_results
    assert result['house1']['bought'] == result['house2']['sold'] == 3


def test_energy_bills_ensure_device_types_are_populated(grid2):
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid2, True)
    epb.current_market_time_slot_str = grid2.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid2)
    m_bills = MarketEnergyBills(should_export_plots=True)
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict,
                   epb.current_market_time_slot_str)
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
    grid.name_uuid_mapping = {
        "street": grid.uuid,
        "house1": house1.uuid,
        "house2": house2.uuid,
    }
    return grid


def test_energy_bills_accumulate_fees(grid_fees):
    constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = True
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid_fees, True)
    epb.current_market_time_slot_str = grid_fees.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid_fees)
    m_bills = MarketEnergyBills(should_export_plots=True)
    m_bills._update_market_fees(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    grid_fees.children[0].past_markets = [FakeMarket([], name='house1', fees=2.0)]
    grid_fees.children[1].past_markets = []
    grid_fees.past_markets = [FakeMarket((_trade(2, make_iaa_name(grid_fees.children[0]), 3,
                                                 make_iaa_name(grid_fees.children[0]),
                                                 fee_price=4.0),), 'street', fees=4.0)]
    epb.current_market_time_slot_str = grid_fees.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid_fees)
    m_bills._update_market_fees(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    assert m_bills.market_fees[grid_fees.name_uuid_mapping['house2']] == 0.03
    assert m_bills.market_fees[grid_fees.name_uuid_mapping['street']] == 0.05
    assert m_bills.market_fees[grid_fees.name_uuid_mapping['house1']] == 0.08


def test_energy_bills_use_only_last_market_if_not_keep_past_markets(grid_fees):
    constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = False

    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid_fees, True)
    epb.current_market_time_slot_str = grid_fees.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid_fees)
    m_bills = MarketEnergyBills(should_export_plots=True)
    m_bills._update_market_fees(epb.area_result_dict, epb.flattened_area_core_stats_dict)
    assert m_bills.market_fees[grid_fees.name_uuid_mapping['house2']] == 0.03
    assert m_bills.market_fees[grid_fees.name_uuid_mapping['street']] == 0.01
    assert m_bills.market_fees[grid_fees.name_uuid_mapping['house1']] == 0.06


def test_energy_bills_report_correctly_market_fees(grid_fees):
    constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = True
    epb = SimulationEndpointBuffer("1", {"seed": 0}, grid_fees, True)
    epb.current_market_time_slot_str = grid_fees.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid_fees)
    m_bills = MarketEnergyBills(should_export_plots=True)
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict,
                   epb.current_market_time_slot_str)
    grid_fees.children[0].past_markets = [FakeMarket([], name='house1', fees=2.0)]
    grid_fees.children[1].past_markets = []
    grid_fees.past_markets = [FakeMarket((_trade(2, make_iaa_name(grid_fees.children[0]), 3,
                                                 make_iaa_name(grid_fees.children[0]),
                                                 fee_price=4.0),), 'street', fees=4.0)]
    epb.current_market_time_slot_str = grid_fees.current_market.time_slot_str
    epb._populate_core_stats_and_sim_state(grid_fees)
    m_bills.update(epb.area_result_dict, epb.flattened_area_core_stats_dict,
                   epb.current_market_time_slot_str)
    result = m_bills.bills_results
    assert result["street"]["house1"]["market_fee"] == 0.04
    assert result["street"]["house2"]["market_fee"] == 0.01
    assert result["street"]['Accumulated Trades']["market_fee"] == 0.05
    assert result["house1"]['External Trades']["market_fee"] == 0.0
    assert result["house2"]['External Trades']["market_fee"] == 0.0
