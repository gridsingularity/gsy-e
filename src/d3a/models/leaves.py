from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.area import Area
from d3a.models.strategy.fridge import FridgeStrategy


class Leaf(Area):
    """
    Superclass for frequently used leaf Areas, so they can be
    instantiated and serialized in a more compact format
    """
    strategy_type = None
    appliance_type = None

    def __init__(self, name, config=None, **kwargs):
        super(Leaf, self).__init__(
            name=name,
            strategy=self.strategy_type(**{
                key: value for key, value in kwargs.items()
                if key in (self.strategy_type.parameters or []) and value is not None
            }),
            appliance=self.appliance_type(),
            config=config
        )


class Fridge(Leaf):
    strategy_type = FridgeStrategy
    appliance_type = FridgeAppliance
