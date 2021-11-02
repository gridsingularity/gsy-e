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
from logging import getLogger
from typing import List, Dict
from uuid import uuid4

from gsy_framework.area_validator import validate_area
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.enums import SpotMarketTypeEnum
from gsy_framework.utils import key_in_dict_and_not_none
from pendulum import DateTime, duration, today
from slugify import slugify

import d3a.constants
from cached_property import cached_property
from d3a.gsy_e_core.blockchain_interface import blockchain_interface_factory
from d3a.gsy_e_core.device_registry import DeviceRegistry
from d3a.gsy_e_core.exceptions import AreaException
from d3a.gsy_e_core.myco_singleton import bid_offer_matcher
from d3a.gsy_e_core.util import TaggedLogWrapper, is_external_matching_enabled
from d3a.models.area.event_dispatcher import DispatcherFactory
from d3a.models.area.events import Events
from d3a.models.area.markets import AreaMarkets
from d3a.models.area.redis_external_market_connection import RedisMarketExternalConnection
from d3a.models.area.stats import AreaStats
from d3a.models.area.throughput_parameters import ThroughputParameters
from d3a.models.config import SimulationConfig
from d3a.models.market.market_structures import AvailableMarketTypes
from d3a.models.strategy import BaseStrategy
from d3a.models.strategy.external_strategies import ExternalMixin
from d3a.models.market.future import FutureMarkets
log = getLogger(__name__)


# TODO: As this is only used in the unittests, please remove it here and replace the usages
#       of this class with d3a-interface.constants_limits.GlobalConfig class:
DEFAULT_CONFIG = SimulationConfig(
    sim_duration=duration(hours=24),
    slot_length=duration(minutes=15),
    tick_length=duration(seconds=1),
    cloud_coverage=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE,
    start_date=today(tz=d3a.constants.TIME_ZONE),
    capacity_kW=ConstSettings.PVSettings.DEFAULT_CAPACITY_KW
)


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


class Area:

    def __init__(self, name: str = None, children: List["Area"] = None,
                 uuid: str = None,
                 strategy: BaseStrategy = None,
                 config: SimulationConfig = None,
                 budget_keeper=None,
                 balancing_spot_trade_ratio=ConstSettings.BalancingSettings.SPOT_TRADE_RATIO,
                 event_list=[],
                 grid_fee_percentage: float = None,
                 grid_fee_constant: float = None,
                 external_connection_available: bool = False,
                 throughput: ThroughputParameters = ThroughputParameters()
                 ):
        validate_area(grid_fee_constant=grid_fee_constant,
                      grid_fee_percentage=grid_fee_percentage)
        self.balancing_spot_trade_ratio = balancing_spot_trade_ratio
        self.active = False
        self.log = TaggedLogWrapper(log, name)
        self.current_tick = 0
        self.__name = name
        self.throughput = throughput
        self.uuid = uuid if uuid is not None else str(uuid4())
        self.slug = slugify(name, to_lower=True)
        self.parent = None
        self.children = AreaChildrenList(self, children) if children is not None\
            else AreaChildrenList(self)
        for child in self.children:
            child.parent = self

        if (len(self.children) > 0) and (strategy is not None):
            raise AreaException("A leaf area can not have children.")
        self.strategy = strategy
        self._config = config
        self.events = Events(event_list, self)
        self.budget_keeper = budget_keeper
        if budget_keeper:
            self.budget_keeper.area = self
        self._bc = None
        self._markets = None
        self.dispatcher = DispatcherFactory(self)()
        self._set_grid_fees(grid_fee_constant, grid_fee_percentage)
        self.display_type = "Area" if self.strategy is None else self.strategy.__class__.__name__
        self._markets = AreaMarkets(self.log)
        self.stats = AreaStats(self._markets, self)
        log.debug("External connection %s for area %s", external_connection_available, self.name)
        self.redis_ext_conn = RedisMarketExternalConnection(self) \
            if external_connection_available and self.strategy is None else None
        self.should_update_child_strategies = False
        self.external_connection_available = external_connection_available

    @property
    def name(self):
        return self.__name

    @name.setter
    def name(self, new_name):
        if check_area_name_exists_in_parent_area(self.parent, new_name):
            raise AreaException("Area name should be unique inside the same Parent Area")

        self.__name = new_name

    def get_state(self):
        state = {}
        if self.strategy is not None:
            state = self.strategy.get_state()

        state.update(**{
            "current_tick": self.current_tick,
            "area_stats": self.stats.get_state()
        })
        return state

    def restore_state(self, saved_state):
        self.current_tick = saved_state["current_tick"]
        self.stats.restore_state(saved_state["area_stats"])
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
            else self.grid_fee_constant)
        grid_fee_percentage = (
            kwargs["grid_fee_percentage"]
            if key_in_dict_and_not_none(kwargs, "grid_fee_percentage")
            else self.grid_fee_percentage)

        baseline_peak_energy_import_kWh = (
            kwargs["baseline_peak_energy_import_kWh"]
            if key_in_dict_and_not_none(
                kwargs, "baseline_peak_energy_import_kWh")
            else self.throughput.baseline_peak_energy_import_kWh)

        baseline_peak_energy_export_kWh = (
            kwargs["baseline_peak_energy_export_kWh"]
            if key_in_dict_and_not_none(
                kwargs, "baseline_peak_energy_export_kWh")
            else self.throughput.baseline_peak_energy_export_kWh)

        import_capacity_kVA = (
            kwargs["import_capacity_kVA"]
            if key_in_dict_and_not_none(kwargs, "import_capacity_kVA")
            else self.throughput.import_capacity_kVA)

        export_capacity_kVA = (
            kwargs["export_capacity_kVA"]
            if key_in_dict_and_not_none(kwargs, "export_capacity_kVA")
            else self.throughput.import_capacity_kVA)

        try:
            validate_area(grid_fee_constant=grid_fee_constant,
                          grid_fee_percentage=grid_fee_percentage)
            throughput = ThroughputParameters(
                            baseline_peak_energy_import_kWh=baseline_peak_energy_import_kWh,
                            baseline_peak_energy_export_kWh=baseline_peak_energy_export_kWh,
                            import_capacity_kVA=import_capacity_kVA,
                            export_capacity_kVA=export_capacity_kVA
                        )

        except Exception as ex:
            log.error(ex)
            return

        self._set_grid_fees(grid_fee_constant, grid_fee_percentage)
        self.throughput = throughput
        self._update_descendants_strategy_prices()

    def _update_descendants_strategy_prices(self):
        try:
            if self.strategy is not None:
                self.strategy.event_activate_price()
            for child in self.children:
                child._update_descendants_strategy_prices()
        except Exception:
            log.exception("area._update_descendants_strategy_prices failed.")
            return

    def _set_grid_fees(self, grid_fee_const, grid_fee_percentage):
        grid_fee_type = self.config.grid_fee_type \
            if self.config is not None \
            else ConstSettings.IAASettings.GRID_FEE_TYPE
        if grid_fee_type == 1:
            grid_fee_percentage = None
        elif grid_fee_type == 2:
            grid_fee_const = None
        self.grid_fee_constant = grid_fee_const
        self.grid_fee_percentage = grid_fee_percentage

    def get_path_to_root_fees(self):
        if self.parent is not None:
            grid_fee_constant = self.grid_fee_constant if self.grid_fee_constant else 0
            return grid_fee_constant + self.parent.get_path_to_root_fees()
        return self.grid_fee_constant if self.grid_fee_constant else 0

    def get_grid_fee(self):
        grid_fee_type = self.config.grid_fee_type \
            if self.config is not None \
            else ConstSettings.IAASettings.GRID_FEE_TYPE
        return self.grid_fee_constant if grid_fee_type == 1 else self.grid_fee_percentage

    def set_events(self, event_list):
        self.events = Events(event_list, self)

    def activate(self, bc=None, current_tick=None, simulation_id=None):
        if current_tick is not None:
            self.current_tick = current_tick

        self._bc = blockchain_interface_factory(bc, self.uuid, simulation_id)

        if self.strategy:
            if self.parent:
                self.strategy.area = self.parent
                self.strategy.owner = self
            else:
                raise AreaException(
                    f"Strategy {self.strategy.__class__.__name__} on area {self} without parent!"
                    )
        else:
            self._markets.activate_future_markets(self)
            self._markets.activate_market_rotators()

        if self.budget_keeper:
            self.budget_keeper.activate()
        if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
            self._set_grid_fees(0, 0)

        # Cycle markets without triggering it's own event chain.
        self.cycle_markets(_trigger_event=False)

        if not self.strategy and self.parent is not None:
            self.log.debug("No strategy. Using inter area agent.")
        self.log.debug("Activating area")
        self.active = True
        self.dispatcher.broadcast_activate(bc=bc, current_tick=self.current_tick,
                                           simulation_id=simulation_id)
        if self.redis_ext_conn is not None:
            self.redis_ext_conn.sub_to_external_channels()

    def deactivate(self):
        self.cycle_markets(deactivate=True)
        if self.redis_ext_conn is not None:
            self.redis_ext_conn.deactivate()
        if self.strategy:
            self.strategy.deactivate()

    def cycle_markets(self, _trigger_event=True, _market_cycle=False, deactivate=False):
        """
        Remove markets for old time slots, add markets for new slots.
        Trigger `MARKET_CYCLE` event to allow child markets to also cycle.

        It's important for this to happen from top to bottom of the `Area` tree
        in order for the `InterAreaAgent`s to be connected correctly

        `_trigger_event` is used internally to avoid multiple event chains during
        initial area activation.
        """

        current_tick_in_slot = int(self.current_tick % self.config.ticks_per_slot)
        tick_at_the_slot_start = self.current_tick - current_tick_in_slot
        if tick_at_the_slot_start == 0:
            now_value = self.now
        else:
            datetime_at_the_slot_start = self.config.start_date.add(
                seconds=self.config.tick_length.seconds * tick_at_the_slot_start
            )

            now_value = datetime_at_the_slot_start

        self.events.update_events(now_value)

        if not self.children:
            self.stats.calculate_energy_deviances()
            # Since children trade in markets we only need to populate them if there are any
            return

        if self.budget_keeper and _market_cycle:
            self.budget_keeper.process_market_cycle()

        self.log.debug("Cycling markets")
        self._markets.rotate_markets(now_value)

        # create new future markets:
        if self.future_markets:
            self.future_markets.create_future_markets(now_value, self.config.slot_length)

        self.dispatcher.event_market_cycle()

        # area_market_stats have to updated when cycling market of each area:
        self.stats.update_area_market_stats()

        if deactivate:
            return

        if self.should_update_child_strategies is True:
            self._update_descendants_strategy_prices()
            self.should_update_child_strategies = False

        # TODO: Refactor and port the future, spot, settlement and balancing market creation to
        # AreaMarkets class, in order to create all necessary markets with one call.

        changed = self._markets.create_new_spot_market(now_value, AvailableMarketTypes.SPOT, self)

        # create new settlement market
        if (self.last_past_market and
                ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS):
            self._markets.create_settlement_market(self.last_past_market.time_slot, self)

        if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET and \
                len(DeviceRegistry.REGISTRY.keys()) != 0:
            changed_balancing_market = self._markets.create_new_spot_market(
                now_value, AvailableMarketTypes.BALANCING, self)
        else:
            changed_balancing_market = None

        # Force market cycle event in case this is the first market slot
        if (changed or len(self._markets.past_markets.keys()) == 0) and _trigger_event:
            self.dispatcher.broadcast_market_cycle()

        # Force balancing_market cycle event in case this is the first market slot
        if (changed_balancing_market or len(self._markets.past_balancing_markets.keys()) == 0) \
                and _trigger_event and ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            self.dispatcher.broadcast_balancing_market_cycle()
        self.stats.calculate_energy_deviances()

    def publish_market_cycle_to_external_clients(self):
        if self.strategy and isinstance(self.strategy, ExternalMixin):
            self.strategy.publish_market_cycle()
        elif not self.strategy and self.external_connection_available:
            self.redis_ext_conn.publish_market_cycle()
        for child in self.children:
            child.publish_market_cycle_to_external_clients()

    def _consume_commands_from_aggregator(self):
        if self.redis_ext_conn is not None and self.redis_ext_conn.is_aggregator_controlled:
            (self.redis_ext_conn.aggregator.
             consume_all_area_commands(self.uuid,
                                       self.redis_ext_conn.trigger_aggregator_commands))
        elif (self.strategy
              and getattr(self.strategy, "is_aggregator_controlled", False)):
            (self.strategy.redis.aggregator.
             consume_all_area_commands(self.uuid,
                                       self.strategy.trigger_aggregator_commands))

    def tick(self):
        """Tick event handler.

        Invoke aggregator commands consumer, publish market clearing, update events,
        update cached myco matcher markets and match trades recommendations.
        """
        if (ConstSettings.IAASettings.MARKET_TYPE == SpotMarketTypeEnum.TWO_SIDED.value
                and not self.strategy):
            if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
                self._consume_commands_from_aggregator()
                self.dispatcher.publish_market_clearing()
            elif is_external_matching_enabled():
                # If external matching is enabled, clear before placing orders
                bid_offer_matcher.match_recommendations()
                self._consume_commands_from_aggregator()
                self._update_myco_matcher()
            else:
                # If internal matching is enabled, place orders before clearing
                self._consume_commands_from_aggregator()
                self._update_myco_matcher()
                bid_offer_matcher.match_recommendations()
        else:
            self._consume_commands_from_aggregator()

        self.events.update_events(self.now)

    def _update_myco_matcher(self) -> None:
        """Update the markets cache that the myco matcher will request"""
        bid_offer_matcher.update_area_uuid_markets_mapping(
            area_uuid_markets_mapping={
                self.uuid: {"markets": [self.spot_market],
                            "settlement_markets": self.settlement_markets.values(),
                            "future_markets": self.future_markets,
                            "current_time": self.now}})

    def update_clock_on_markets(self) -> None:
        """
        Update clock on markets with self.now member.
        Returns:

        """
        self.current_tick += 1
        if self.children:
            self.spot_market.update_clock(self.now)

            for market in self._markets.settlement_markets.values():
                market.update_clock(self.now)
        for child in self.children:
            child.update_clock_on_markets()

    def tick_and_dispatch(self):
        """Invoke tick handler and broadcast the event to children."""
        if d3a.constants.DISPATCH_EVENTS_BOTTOM_TO_TOP:
            self.dispatcher.broadcast_tick()
            self.tick()
        else:
            self.tick()
            self.dispatcher.broadcast_tick()

    def __repr__(self):
        return "<Area '{s.name}' markets: {markets}>".format(
            s=self,
            markets=[t.format(d3a.constants.TIME_FORMAT) for t in self._markets.markets.keys()]
        )

    @property
    def all_markets(self):
        return [m for m in self._markets.markets.values() if m.in_sim_duration]

    @property
    def current_slot(self):
        return self.current_tick // self.config.ticks_per_slot

    @property
    def current_tick_in_slot(self):
        return self.current_tick % self.config.ticks_per_slot

    @property
    def config(self):
        if self._config:
            return self._config
        if self.parent:
            return self.parent.config
        return GlobalConfig

    @property
    def bc(self):
        if self._bc is not None:
            return self._bc
        return None

    @cached_property
    def child_by_slug(self):
        slug_map = {}
        areas = [self]
        while areas:
            for area in list(areas):
                slug_map[area.slug] = area
                areas.remove(area)
                areas.extend(area.children)
        return slug_map

    @property
    def now(self) -> DateTime:
        """
        Return the "current time" as a "DateTime" object.
        Can be overridden in subclasses to change the meaning of "now".

        In this default implementation "current time" is defined by the number of ticks that
        have passed.
        """
        return self.config.start_date.add(
            seconds=self.config.tick_length.seconds * self.current_tick
        )

    @property
    def past_markets(self) -> List:
        return list(self._markets.past_markets.values())

    def get_market(self, time_slot):
        return self._markets.markets.get(time_slot)

    def get_past_market(self, time_slot):
        return self._markets.past_markets[time_slot]

    def get_balancing_market(self, time_slot):
        return self._markets.balancing_markets[time_slot]

    @property
    def balancing_markets(self) -> List:
        return list(self._markets.balancing_markets.values())

    @property
    def past_balancing_markets(self) -> List:
        return list(self._markets.past_balancing_markets.values())

    @property
    def spot_market(self):
        """Returns the "current" market (i.e. the one currently "running")"""
        try:
            return self.all_markets[-1]
        except IndexError:
            return None

    @property
    def current_market(self):
        """Returns the "most recent past market" market
        (i.e. the one that has been finished last)"""
        try:
            return list(self._markets.past_markets.values())[-1]
        except IndexError:
            return None

    @property
    def current_balancing_market(self):
        """Returns the "current" balancing market (i.e. the one currently "running")"""
        try:
            return list(self._markets.past_balancing_markets.values())[-1]
        except IndexError:
            return None

    def get_future_market_from_id(self, _id):
        return self._markets.indexed_future_markets.get(_id, None)

    @property
    def last_past_market(self):
        try:
            return list(self._markets.past_markets.values())[-1]
        except IndexError:
            return None

    @property
    def future_market_time_slots(self) -> List[DateTime]:
        return self._markets.future_markets.market_time_slots

    @property
    def future_markets(self) -> FutureMarkets:
        return self._markets.future_markets

    @property
    def settlement_markets(self) -> Dict:
        return self._markets.settlement_markets

    @property
    def last_past_settlement_market(self):
        try:
            return list(self._markets.past_settlement_markets.items())[-1]
        except IndexError:
            return None

    @property
    def past_settlement_markets(self) -> Dict:
        return self._markets.past_settlement_markets

    def get_settlement_market(self, time_slot):
        return self._markets.settlement_markets.get(time_slot)

    def get_market_instances_from_class_type(self, market_type: AvailableMarketTypes) -> Dict:
        """
        Return market dicts for the selected market type
        Args:
            market_type: Selected market type (spot/balancing/settlement/future)

        Returns: Dicts with market objects for the selected market type

        """
        return self._markets.get_market_instances_from_class_type(market_type)

    def update_config(self, **kwargs):
        if not self.config:
            return
        self.config.update_config_parameters(**kwargs)
        if self.strategy:
            self.strategy.read_config_event()
        for child in self.children:
            child.update_config(**kwargs)
