"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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

from logging import getLogger
from typing import TYPE_CHECKING, List, Union, Optional
from uuid import uuid4

from gsy_framework.area_validator import validate_area
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.exceptions import GSyAreaException, GSyDeviceException
from gsy_framework.utils import key_in_dict_and_not_none
from pendulum import DateTime
from slugify import slugify

from gsy_e.gsy_e_core.exceptions import AreaException, GSyException
from gsy_e.gsy_e_core.util import TaggedLogWrapper
from gsy_e.models.config import SimulationConfig


log = getLogger(__name__)

if TYPE_CHECKING:
    from gsy_e.models.area import Area
    from gsy_framework.data_classes import Trade
    from gsy_e.models.strategy import BaseStrategy
    from gsy_e.models.strategy.trading_strategy_base import TradingStrategyBase


def check_area_name_exists_in_parent_area(parent_area, name):
    """
    Check the children of parent area , iterate through its children and
        check if the name to be appended does not exist
    Note: this check is to be called before adding a new area of changing its name
    :param parent_area: Parent Area
    :param name: New name of area
    :return: boolean
    """
    for child in parent_area.children:
        if child.name == name:
            return True
    return False


class AreaChildrenList(list):
    """Class to define the children of an area."""

    def __init__(self, parent_area, *args, **kwargs):
        self.parent_area = parent_area
        super().__init__(*args, **kwargs)

    def _validate_before_insertion(self, item):
        if check_area_name_exists_in_parent_area(self.parent_area, item.name):
            raise AreaException("Area name should be unique inside the same Parent Area")

    def append(self, item: "Area") -> None:
        self._validate_before_insertion(item)
        super().append(item)

    def insert(self, index, item):
        self._validate_before_insertion(item)
        super().insert(index, item)


class AreaBase:
    """
    Base class for the Area model. Contains common behavior for both coefficient trading and
    market trading.
    """

    # pylint: disable=too-many-arguments,too-many-instance-attributes
    def __init__(
        self,
        name: str = None,
        children: List["Area"] = None,
        uuid: str = None,
        strategy: Optional[Union["BaseStrategy", "TradingStrategyBase"]] = None,
        config: SimulationConfig = None,
        grid_fee_percentage: float = None,
        grid_fee_constant: float = None,
    ):
        validate_area(grid_fee_constant=grid_fee_constant, grid_fee_percentage=grid_fee_percentage)
        self.active = False
        self.log = TaggedLogWrapper(log, name)
        self.__name = name
        self.uuid = uuid if uuid is not None else str(uuid4())
        self.slug = slugify(name, to_lower=True)
        self.parent = None
        if not children:
            children = []
        children = [child for child in children if child is not None]
        self.children = (
            AreaChildrenList(self, children) if children is not None else AreaChildrenList(self)
        )
        for child in self.children:
            child.parent = self

        if (len(self.children) > 0) and (strategy is not None):
            raise AreaException("A leaf area can not have children.")
        self.strategy = strategy
        self._config = config
        self._set_grid_fees(grid_fee_constant, grid_fee_percentage)
        self.current_market_time_slot = None

    @property
    def now(self) -> DateTime:
        """Get the current time of the simulation."""
        return self.current_market_time_slot

    @property
    def trades(self) -> List["Trade"]:
        """Get a list of trades that this area performed during the last market."""
        return self.strategy.trades

    def _set_grid_fees(self, grid_fee_const, grid_fee_percentage):
        grid_fee_type = (
            self.config.grid_fee_type
            if self.config is not None
            else ConstSettings.MASettings.GRID_FEE_TYPE
        )
        if grid_fee_type == 1:
            grid_fee_percentage = None
        elif grid_fee_type == 2:
            grid_fee_const = None
        self.grid_fee_constant = grid_fee_const
        self.grid_fee_percentage = grid_fee_percentage

    @property
    def config(self) -> Union[SimulationConfig, GlobalConfig]:
        """Return the configuration used by the area."""
        if self._config:
            return self._config
        if self.parent:
            return self.parent.config
        return GlobalConfig

    @property
    def name(self):
        """Return the name of the area."""
        return self.__name

    @name.setter
    def name(self, new_name):
        if check_area_name_exists_in_parent_area(self.parent, new_name):
            raise AreaException("Area name should be unique inside the same Parent Area")

        self.__name = new_name

    def get_path_to_root_fees(self) -> float:
        """Return the cumulative fees value from the current area to its root."""
        if self.parent is not None:
            grid_fee_constant = self.grid_fee_constant if self.grid_fee_constant else 0
            return grid_fee_constant + self.parent.get_path_to_root_fees()
        return self.grid_fee_constant if self.grid_fee_constant else 0

    def get_grid_fee(self):
        """Return the current grid fee for the area."""
        grid_fee_type = (
            self.config.grid_fee_type
            if self.config is not None
            else ConstSettings.MASettings.GRID_FEE_TYPE
        )

        return self.grid_fee_constant if grid_fee_type == 1 else self.grid_fee_percentage

    def update_config(self, **kwargs):
        """Update the configuration of the area using the provided arguments."""
        if not self.config:
            return
        self.config.update_config_parameters(**kwargs)
        if self.strategy:
            self.strategy.read_config_event()
        for child in self.children:
            child.update_config(**kwargs)

    def get_state(self):
        """Get the current state of the area."""
        state = {}
        if self.strategy is not None:
            state = self.strategy.get_state()

        return state

    def restore_state(self, saved_state):
        """Restore a previously-saved state."""
        if self.strategy is not None:
            self.strategy.restore_state(saved_state)

    def area_reconfigure_event(self, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        if self.strategy is not None:
            self.strategy.area_reconfigure_event(**kwargs)
            return True

        grid_fee_constant = (
            kwargs["grid_fee_constant"]
            if key_in_dict_and_not_none(kwargs, "grid_fee_constant")
            else self.grid_fee_constant
        )
        grid_fee_percentage = (
            kwargs["grid_fee_percentage"]
            if key_in_dict_and_not_none(kwargs, "grid_fee_percentage")
            else self.grid_fee_percentage
        )

        try:
            validate_area(
                grid_fee_constant=grid_fee_constant, grid_fee_percentage=grid_fee_percentage
            )

        except (GSyAreaException, GSyDeviceException) as ex:
            log.error(ex)
            return None

        self.update_descendants_strategy_prices()
        return None

    def update_descendants_strategy_prices(self):
        """Recursively update the strategy prices of all descendants of the area."""
        try:
            if self.strategy is not None:
                self.strategy.event_activate_price()
            for child in self.children:
                child.update_descendants_strategy_prices()
        except GSyException:
            log.exception("area.update_descendants_strategy_prices failed.")

    def get_results_dict(self):
        """Calculate the results dict for the coefficients trading."""
        if self.strategy is not None:
            return self.strategy.state.get_results_dict(self.current_market_time_slot)
        return {}

    @property
    def is_home_area(self):
        "Return if the area is a home area."
        return self.children and all(child.strategy for child in self.children)
