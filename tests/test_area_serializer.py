import json
import pytest

from d3a.area_serializer import area_to_string, area_from_string, are_all_areas_unique
from d3a.models.appliance.pv import PVAppliance
from d3a.models.area import Area
from d3a.models.leaves import PV
from d3a.models.const import ConstSettings
from d3a.models.budget_keeper import BudgetKeeper
from d3a.models.strategy.pv import PVStrategy


def test_area_with_children_roundtrip():
    child1 = Area("child1")
    child2 = Area("child2")
    parent = Area("parent", [child1, child2])
    string = area_to_string(parent)
    recovered = area_from_string(string)
    assert recovered.name == "parent"
    assert recovered.children[0].name == "child1"
    assert recovered.children[1].name == "child2"


def test_encode_strategy_appliance():
    area = Area("child", [], PVStrategy(), PVAppliance())
    area_dict = json.loads(area_to_string(area))
    assert 'children' not in area_dict
    assert area_dict['strategy']['type'] == 'PVStrategy'
    assert area_dict['appliance']['type'] == 'PVAppliance'


def test_strategy_appliance_roundtrip():
    area = Area("child", [], PVStrategy(), PVAppliance())
    recovered = area_from_string(area_to_string(area))
    assert type(recovered.strategy) is PVStrategy
    assert type(recovered.appliance) is PVAppliance


def test_raises_unknown_class():
    with pytest.raises(ValueError):
        area_from_string("{'name':'broken','strategy':'NonexistentStrategy'}")


def test_strategy_roundtrip_with_params():
    area = Area('area', [], PVStrategy(panel_count=42, risk=1))
    area_str = area_to_string(area)
    assert json.loads(area_str)['strategy']['kwargs']['risk'] == 1
    recovered = area_from_string(area_str)
    assert recovered.strategy.panel_count == 42


def test_non_attr_param():
    area1 = Area('area1', [], PVStrategy())
    recovered1 = area_from_string(area_to_string(area1))
    assert recovered1.strategy.min_selling_rate == ConstSettings.PVSettings.MIN_SELLING_RATE


@pytest.fixture
def appliance_fixture():
    child1 = Area('child1', appliance=PVAppliance(initially_on=False))
    child2 = Area('child2', appliance=PVAppliance())
    return area_to_string(Area('parent', [child1, child2]))


def test_appliance(appliance_fixture):
    area_dict = json.loads(appliance_fixture)
    assert area_dict['children'][0]['appliance']['type'] == 'PVAppliance'


def test_appliance_roundtrip(appliance_fixture):
    recovered = area_from_string(appliance_fixture)
    assert recovered.children[1].appliance.initially_on
    assert not recovered.children[0].appliance.is_on


def test_leaf_deserialization():
    recovered = area_from_string(
        '''{
             "name": "house",
             "children":[
                 {"name": "pv1", "type": "PV", "panel_count": 4, "risk": 50},
                 {"name": "pv2", "type": "PV", "panel_count": 1, "risk": 10}
             ]
           }
        '''
    )
    pv1, pv2 = recovered.children
    assert isinstance(pv1, PV)
    assert pv1.strategy.panel_count == 4 and pv1.strategy.risk == 50
    assert isinstance(pv2, PV)
    assert pv2.strategy.panel_count == 1 and pv2.strategy.risk == 10


@pytest.fixture
def fixture_with_leaves():
    area = Area("house", [PV("pv1", panel_count=1, risk=5), PV("pv2", panel_count=4, risk=10)])
    return area_to_string(area)


def test_leaf_serialization(fixture_with_leaves):
    description = json.loads(fixture_with_leaves)
    assert description['children'][0]['type'] == 'PV'
    assert description['children'][0]['panel_count'] == 1
    assert description['children'][1]['type'] == 'PV'
    assert description['children'][1]['panel_count'] == 4


def test_roundtrip_with_leaf(fixture_with_leaves):
    recovered = area_from_string(fixture_with_leaves)
    assert isinstance(recovered.children[0].strategy, PVStrategy)
    assert isinstance(recovered.children[1].strategy, PVStrategy)


@pytest.fixture
def budget_keeper_fixture():
    child = Area('child', appliance=PVAppliance())
    budget_keeper = BudgetKeeper(budget=100.0, days_per_period=30)
    return area_to_string(Area('parent', [child], budget_keeper=budget_keeper))


def test_budget_keeper(budget_keeper_fixture):
    area_dict = json.loads(budget_keeper_fixture)
    assert area_dict['budget_keeper']['kwargs']['budget'] == 100.0
    assert area_dict['budget_keeper']['kwargs']['days_per_period'] == 30


def test_budget_keeper_roundtrip(budget_keeper_fixture):
    recovered = area_from_string(budget_keeper_fixture)
    assert recovered.budget_keeper.budget == 100.0
    assert recovered.budget_keeper.days_per_period == 30


def test_area_does_not_allow_duplicate_subarea_names():
    area = Area(
        'Grid',
        [Area('House 1', children=[Area('H1 General Load'), Area('H1 PV1')]),
         Area('House 1', children=[Area('H2 General Load'), Area('H2 PV1')])],
    )

    with pytest.raises(AssertionError):
        are_all_areas_unique(area, set())

    area = Area(
        'Grid',
        [Area('House 1', children=[Area('H1 General Load'), Area('H1 PV1')]),
         Area('House 2', children=[Area('H1 General Load'), Area('H2 PV1')])],
    )

    with pytest.raises(AssertionError):
        are_all_areas_unique(area, set())

    area = Area(
        'Grid',
        [Area('House 1', children=[Area('H1 General Load'), Area('H1 PV1')]),
         Area('House 2', children=[Area('H2 General Load'), Area('H2 PV1')])],
    )

    # Does not raise an assertion
    are_all_areas_unique(area, set())
