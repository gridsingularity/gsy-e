import json
import pytest

from d3a.area_serializer import area_to_string, area_from_string
from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.area import Area
from d3a.models.strategy.fridge import FridgeStrategy
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
