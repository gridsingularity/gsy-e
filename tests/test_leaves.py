from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.area import Area
from d3a.models.leaves import Fridge
from d3a.models.strategy.fridge import FridgeStrategy, DEFAULT_RISK


def test_fridge_leaf():
    leaf = Fridge(name="fridge1", risk=10)
    assert isinstance(leaf, Area) and not leaf.children and leaf.name == "fridge1"
    assert isinstance(leaf.strategy, FridgeStrategy) and leaf.strategy.risk == 10
    assert isinstance(leaf.appliance, FridgeAppliance)


def test_fridge_leaf_default_risk():
    leaf = Fridge(name="fridge")
    assert leaf.strategy.risk == DEFAULT_RISK
