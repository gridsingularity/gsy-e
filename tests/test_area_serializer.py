import json
import pytest

from d3a.area_serializer import area_to_string, area_from_string
from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.area import Area
from d3a.models.leaves import Fridge, PV
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.const import ConstSettings
from d3a.models.budget_keeper import BudgetKeeper
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.simple import OfferStrategy


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
    area = Area("child", [], FridgeStrategy(), FridgeAppliance())
    area_dict = json.loads(area_to_string(area))
    assert 'children' not in area_dict
    assert area_dict['strategy']['type'] == 'FridgeStrategy'
    assert area_dict['appliance']['type'] == 'FridgeAppliance'


def test_strategy_appliance_roundtrip():
    area = Area("child", [], FridgeStrategy(), FridgeAppliance())
    recovered = area_from_string(area_to_string(area))
    assert type(recovered.strategy) is FridgeStrategy
    assert type(recovered.appliance) is FridgeAppliance


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
    area1 = Area('area1', [], OfferStrategy(price_fraction_choice=(1, 10)))
    recovered1 = area_from_string(area_to_string(area1))
    assert recovered1.strategy.price_fraction == [1, 10]


@pytest.fixture
def appliance_fixture():
    child1 = Area('child1', appliance=FridgeAppliance(initially_on=False))
    child2 = Area('child2', appliance=PVAppliance())
    return area_to_string(Area('parent', [child1, child2]))


def test_appliance(appliance_fixture):
    area_dict = json.loads(appliance_fixture)
    assert area_dict['children'][0]['appliance']['type'] == 'FridgeAppliance'
    assert area_dict['children'][1]['appliance']['kwargs']['initially_on']


def test_appliance_roundtrip(appliance_fixture):
    recovered = area_from_string(appliance_fixture)
    assert recovered.children[1].appliance.initially_on
    assert not recovered.children[0].appliance.is_on


def test_leaf_deserialization():
    recovered = area_from_string(
        '''{
             "name": "house",
             "children":[
                 {"name": "fridge", "type": "Fridge"},
                 {"name": "pv", "type": "PV", "panel_count": 4, "risk": 50}
             ]
           }
        '''
    )
    fridge, pv = recovered.children
    assert isinstance(fridge, Fridge) and isinstance(pv, PV)
    assert pv.strategy.panel_count == 4 and pv.strategy.risk == 50
    assert fridge.strategy.risk == ConstSettings.GeneralSettings.DEFAULT_RISK


@pytest.fixture
def fixture_with_leaves():
    area = Area("house", [Fridge("fridge"), PV("pv", panel_count=4, risk=10)])
    return area_to_string(area)


def test_leaf_serialization(fixture_with_leaves):
    description = json.loads(fixture_with_leaves)
    assert description['children'][0]['type'] == 'Fridge'
    assert description['children'][1]['panel_count'] == 4


def test_roundtrip_with_leaf(fixture_with_leaves):
    recovered = area_from_string(fixture_with_leaves)
    assert isinstance(recovered.children[0], Fridge)
    assert isinstance(recovered.children[1].strategy, PVStrategy)


@pytest.fixture
def budget_keeper_fixture():
    child = Area('child', appliance=FridgeAppliance())
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
