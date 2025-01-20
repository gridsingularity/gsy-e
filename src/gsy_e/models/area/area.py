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
from typing import TYPE_CHECKING, Dict, List, Optional, Union

from gsy_framework.area_validator import validate_area
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.exceptions import GSyAreaException, GSyDeviceException
from gsy_framework.utils import key_in_dict_and_not_none
from pendulum import DateTime

import gsy_e.constants
from gsy_e.gsy_e_core.blockchain_interface import blockchain_interface_factory
from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.gsy_e_core.exceptions import AreaException
from gsy_e.gsy_e_core.matching_engine_singleton import bid_offer_matcher
from gsy_e.gsy_e_core.util import is_external_matching_enabled, is_two_sided_market_simulation
from gsy_e.models.area.area_base import AreaBase
from gsy_e.models.area.event_dispatcher import DispatcherFactory
from gsy_e.models.area.events import Events
from gsy_e.models.area.markets import AreaMarkets
from gsy_e.models.area.redis_external_market_connection import RedisMarketExternalConnection
from gsy_e.models.area.stats import AreaStats
from gsy_e.models.area.throughput_parameters import ThroughputParameters
from gsy_e.models.config import SimulationConfig
from gsy_e.models.market.forward import ForwardMarketBase
from gsy_e.models.market.future import FutureMarkets

from gsy_e.models.strategy.external_strategies import ExternalMixin

log = getLogger(__name__)

if TYPE_CHECKING:
    from gsy_e.models.market import MarketBase
    from gsy_e.models.strategy import BaseStrategy
    from gsy_e.models.strategy.trading_strategy_base import TradingStrategyBase


class Area(AreaBase):
    # pylint: disable=too-many-public-methods
    """Generic class to define both market areas and devices.

    Important: this class should not be used in setup files. Please use Market or Asset instead.
    """

    # pylint: disable=too-many-arguments,too-many-instance-attributes
    def __init__(
        self,
        name: str = None,
        children: List["Area"] = None,
        uuid: str = None,
        strategy: Optional[Union["BaseStrategy", "TradingStrategyBase"]] = None,
        config: SimulationConfig = None,
        balancing_spot_trade_ratio=ConstSettings.BalancingSettings.SPOT_TRADE_RATIO,
        event_list=None,
        grid_fee_percentage: float = None,
        grid_fee_constant: float = None,
        external_connection_available: bool = False,
        throughput: ThroughputParameters = ThroughputParameters(),
        min_offer_age: int = None,
        min_bid_age: int = None,
    ):
        super().__init__(
            name, children, uuid, strategy, config, grid_fee_percentage, grid_fee_constant
        )
        self.display_type = "Area" if self.strategy is None else self.strategy.__class__.__name__
        self.current_tick = 0
        self.throughput = throughput
        event_list = event_list if event_list is not None else []
        self.events = Events(event_list, self)
        self._bc = None
        self.dispatcher = DispatcherFactory(self)()
        self._markets = AreaMarkets(self.log)
        self.stats = AreaStats(self._markets, self)
        log.debug("External connection %s for area %s", external_connection_available, self.name)
        self.redis_ext_conn = (
            RedisMarketExternalConnection(self)
            if external_connection_available and self.strategy is None
            else None
        )
        self.external_connection_available = external_connection_available
        self.balancing_spot_trade_ratio = balancing_spot_trade_ratio
        self._min_offer_age = (
            min_offer_age if min_offer_age is not None else ConstSettings.MASettings.MIN_OFFER_AGE
        )
        self._min_bid_age = (
            min_bid_age if min_bid_age is not None else ConstSettings.MASettings.MIN_BID_AGE
        )

    def get_state(self):
        """Get the current state of the area."""
        state = super().get_state()
        state.update({"current_tick": self.current_tick})
        if not self.strategy:
            state.update(**self.stats.get_state())
        return state

    def restore_state(self, saved_state):
        """Restore a previously-saved state."""
        self.current_tick = saved_state["current_tick"]
        self.stats.restore_state(saved_state)
        super().restore_state(saved_state)

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

        baseline_peak_energy_import_kWh = (
            kwargs["baseline_peak_energy_import_kWh"]
            if key_in_dict_and_not_none(kwargs, "baseline_peak_energy_import_kWh")
            else self.throughput.baseline_peak_energy_import_kWh
        )

        baseline_peak_energy_export_kWh = (
            kwargs["baseline_peak_energy_export_kWh"]
            if key_in_dict_and_not_none(kwargs, "baseline_peak_energy_export_kWh")
            else self.throughput.baseline_peak_energy_export_kWh
        )

        import_capacity_kVA = (
            kwargs["import_capacity_kVA"]
            if key_in_dict_and_not_none(kwargs, "import_capacity_kVA")
            else self.throughput.import_capacity_kVA
        )

        export_capacity_kVA = (
            kwargs["export_capacity_kVA"]
            if key_in_dict_and_not_none(kwargs, "export_capacity_kVA")
            else self.throughput.import_capacity_kVA
        )

        try:
            validate_area(
                grid_fee_constant=grid_fee_constant, grid_fee_percentage=grid_fee_percentage
            )
            throughput = ThroughputParameters(
                baseline_peak_energy_import_kWh=baseline_peak_energy_import_kWh,
                baseline_peak_energy_export_kWh=baseline_peak_energy_export_kWh,
                import_capacity_kVA=import_capacity_kVA,
                export_capacity_kVA=export_capacity_kVA,
            )

        except (GSyAreaException, GSyDeviceException) as ex:
            log.error(ex)
            return None

        self._set_grid_fees(grid_fee_constant, grid_fee_percentage)
        self.throughput = throughput
        self.update_descendants_strategy_prices()

        return None

    def set_events(self, event_list):
        """Set events for the area."""
        self.events = Events(event_list, self)

    def activate(self, bc=None, current_tick=None, simulation_id=None):
        """Activate the area and broadcast the activation event."""
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

        # Cycle markets without triggering it's own event chain.
        self.cycle_markets(_trigger_event=False)

        if not self.strategy and self.parent is not None:
            self.log.debug("No strategy. Using inter area agent.")
        self.log.debug("Activating area")
        self.active = True
        self.dispatcher.broadcast_activate(
            bc=bc, current_tick=self.current_tick, simulation_id=simulation_id
        )
        if self.redis_ext_conn is not None:
            self.redis_ext_conn.sub_to_external_channels()

    def deactivate(self):
        """Deactivate the area."""
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
        in order for the `MarketAgent`s to be connected correctly

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

        self.log.debug("Cycling markets")
        self._markets.rotate_markets(now_value)

        # create new future markets:
        if self.future_markets:
            self.future_markets.create_future_market_slots(now_value, self.config)

        # create new day ahead markets:
        if self.forward_markets:
            for forward_market in self.forward_markets.values():
                forward_market.create_future_market_slots(now_value, self.config)

        self.dispatcher.event_market_cycle()

        # area_market_stats have to updated when cycling market of each area:
        self.stats.update_area_market_stats()

        if deactivate:
            return

        # pylint: disable=fixme
        # TODO: Refactor and port the future, spot, settlement and balancing market creation to
        # AreaMarkets class, in order to create all necessary markets with one call.
        changed = self._markets.create_new_spot_market(now_value, AvailableMarketTypes.SPOT, self)

        # create new settlement market
        if (
            self.last_past_market
            and ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS
        ):
            self._markets.create_settlement_market(self.last_past_market.time_slot, self)

        if (
            ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET
            and len(DeviceRegistry.REGISTRY.keys()) != 0
        ):
            changed_balancing_market = self._markets.create_new_spot_market(
                now_value, AvailableMarketTypes.BALANCING, self
            )
        else:
            changed_balancing_market = None

        self._markets.update_area_market_id_lists()

        # Force market cycle event in case this is the first market slot
        if (changed or len(self._markets.past_markets.keys()) == 0) and _trigger_event:
            self.dispatcher.broadcast_market_cycle()

        # Force balancing_market cycle event in case this is the first market slot
        if (
            (changed_balancing_market or len(self._markets.past_balancing_markets.keys()) == 0)
            and _trigger_event
            and ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET
        ):
            self.dispatcher.broadcast_balancing_market_cycle()
        self.stats.calculate_energy_deviances()

    def publish_market_cycle_to_external_clients(self):
        """Recursively notify children and external clients about the market cycle event."""
        if self.strategy and isinstance(self.strategy, ExternalMixin):
            self.strategy.publish_market_cycle()
        elif not self.strategy and self.external_connection_available:
            self.redis_ext_conn.publish_market_cycle()
        for child in self.children:
            child.publish_market_cycle_to_external_clients()

    def _consume_commands_from_aggregator(self):
        if self.redis_ext_conn is not None and self.redis_ext_conn.is_aggregator_controlled:
            (
                self.redis_ext_conn.aggregator.consume_all_area_commands(
                    self.uuid, self.redis_ext_conn.trigger_aggregator_commands
                )
            )
        elif self.strategy and getattr(self.strategy, "is_aggregator_controlled", False):
            (
                self.strategy.redis.aggregator.consume_all_area_commands(
                    self.uuid, self.strategy.trigger_aggregator_commands
                )
            )

    def tick(self):
        """Tick event handler.

        Invoke aggregator commands consumer, publish market clearing, update events,
        update cached matching engine matcher markets and match trades recommendations.
        """
        if is_two_sided_market_simulation() and not self.strategy:
            if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
                self.dispatcher.publish_market_clearing()
            elif is_external_matching_enabled():
                # If external matching is enabled, clear before placing orders
                bid_offer_matcher.match_recommendations()
                self._update_matching_engine_matcher()
            else:
                # If internal matching is enabled, place orders before clearing
                self._update_matching_engine_matcher()
                bid_offer_matcher.match_recommendations()

        self.events.update_events(self.now)

    def _update_matching_engine_matcher(self) -> None:
        """Update the markets cache that the matching engine matcher will request"""
        markets_mapping = {
            "current_time": self.now,
            AvailableMarketTypes.SPOT: [self.spot_market],
            AvailableMarketTypes.SETTLEMENT: list(self.settlement_markets.values()),
            AvailableMarketTypes.FUTURE: self.future_markets,
        }

        bid_offer_matcher.update_area_uuid_spot_markets_mapping(
            area_uuid_markets_mapping={self.uuid: markets_mapping}
        )

        if not ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS:
            return

        forward_markets_mapping = {
            "current_time": self.now,
            AvailableMarketTypes.INTRADAY: self.forward_markets.get(AvailableMarketTypes.INTRADAY),
            AvailableMarketTypes.DAY_FORWARD: self.forward_markets.get(
                AvailableMarketTypes.DAY_FORWARD
            ),
            AvailableMarketTypes.WEEK_FORWARD: self.forward_markets.get(
                AvailableMarketTypes.WEEK_FORWARD
            ),
            AvailableMarketTypes.MONTH_FORWARD: self.forward_markets.get(
                AvailableMarketTypes.MONTH_FORWARD
            ),
            AvailableMarketTypes.YEAR_FORWARD: self.forward_markets.get(
                AvailableMarketTypes.YEAR_FORWARD
            ),
        }
        bid_offer_matcher.update_area_uuid_forward_markets_mapping(
            area_uuid_markets_mapping={self.uuid: forward_markets_mapping}
        )

    def execute_actions_after_tick_event(self) -> None:
        """
        Execute actions that are needed after the tick event has been processed and dispatched
        to all areas. The actions performed for now is consuming the aggregator commands, and
        updating the clock on markets with self.now member
        Returns: None

        """
        self.current_tick += 1
        self._consume_commands_from_aggregator()
        if self.children:
            self.spot_market.update_clock(self.now)
            self.future_markets.update_clock(self.now)
            for market in self._markets.settlement_markets.values():
                market.update_clock(self.now)
            for market in self._markets.forward_markets.values():
                market.update_clock(self.now)
        for child in self.children:
            child.execute_actions_after_tick_event()

    def tick_and_dispatch(self):
        """Invoke tick handler and broadcast the event to children."""
        if gsy_e.constants.DISPATCH_EVENTS_BOTTOM_TO_TOP:
            self.dispatcher.broadcast_tick()
            self.tick()
        else:
            self.tick()
            self.dispatcher.broadcast_tick()

    def __repr__(self):
        return (
            f"<Area '{self.name}' markets: "
            f"{[t.format(gsy_e.constants.TIME_FORMAT) for t in self._markets.markets]}>"
        )

    @property
    def all_markets(self):
        """Return all markets that the area is involved with."""
        return [market for market in self._markets.markets.values() if market.in_sim_duration]

    @property
    def current_slot(self) -> int:
        """Return the number of the current market slot."""
        return self.current_tick // self.config.ticks_per_slot

    @property
    def current_tick_in_slot(self):
        """Return the number of the current tick in the current market slot."""
        return self.current_tick % self.config.ticks_per_slot

    @property
    def bc(self):
        """Return the blockchain interface used by the area."""
        if self._bc is not None:
            return self._bc
        return None

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
        """Return the past markets of the area."""
        return list(self._markets.past_markets.values())

    def get_market(self, time_slot):
        """Return the market of the area that occurred at the specified time slot."""
        return self._markets.markets.get(time_slot)

    def get_balancing_market(self, time_slot):
        """Return the balancing market of the area that occurred at the specified time slot."""
        return self._markets.balancing_markets[time_slot]

    @property
    def balancing_markets(self) -> List:
        """Return the balancing markets of the area."""
        return list(self._markets.balancing_markets.values())

    @property
    def past_balancing_markets(self) -> List:
        """Return the past balancing markets of the area."""
        return list(self._markets.past_balancing_markets.values())

    @property
    def spot_market(self):
        """Return the "current" market (i.e. the one currently "running")."""
        try:
            return self.all_markets[-1]
        except IndexError:
            return None

    @property
    def current_market(self):
        """Return the "most recent past market" (the one that has been finished last)."""
        try:
            return list(self._markets.past_markets.values())[-1]
        except IndexError:
            return None

    @property
    def current_balancing_market(self):
        """Return the "current" balancing market (i.e. the one currently "running")"""
        try:
            return list(self._markets.past_balancing_markets.values())[-1]
        except IndexError:
            return None

    def get_future_market_from_id(self, _id):
        """Return the future market that corresponds to the provided ID."""
        return self._markets.indexed_future_markets.get(_id, None)

    def get_spot_or_future_market_by_id(self, market_id: str) -> Optional["MarketBase"]:
        """Retrieve a spot or future market from its ID."""
        if self.is_market_spot(market_id):
            return self.spot_market
        if self.is_market_future(market_id):
            return self.future_markets
        return None

    def is_market_spot_or_future(self, market_id):
        """Return True if the market is a spot or future market."""
        return self.is_market_spot(market_id) or self.is_market_future(market_id)

    @property
    def last_past_market(self):
        """Return the most recent of the area's past markets."""
        try:
            return list(self._markets.past_markets.values())[-1]
        except IndexError:
            return None

    @property
    def future_market_time_slots(self) -> List[DateTime]:
        """Return the future markets time slots of the area."""
        if not self._markets.future_markets:
            return []
        return self._markets.future_markets.market_time_slots

    @property
    def future_markets(self) -> FutureMarkets:
        """Return the future markets of the area."""
        return self._markets.future_markets

    @property
    def forward_markets(self) -> Optional[Dict[AvailableMarketTypes, ForwardMarketBase]]:
        """Return the day ahead markets of the area."""
        return self._markets.forward_markets

    @property
    def settlement_markets(self) -> Dict:
        """Return the settlement markets of the area."""
        return self._markets.settlement_markets

    @property
    def last_past_settlement_market(self):
        """Return the most recent of the area's past settlement markets."""
        try:
            return list(self._markets.past_settlement_markets.items())[-1]
        except IndexError:
            return None

    @property
    def past_settlement_markets(self) -> Dict:
        """Return the past settlement markets of the area."""
        return self._markets.past_settlement_markets

    def get_settlement_market(self, time_slot):
        """Return the settlement market of the area that occurred at the specified time slot."""
        return self._markets.settlement_markets.get(time_slot)

    def get_market_instances_from_class_type(self, market_type: AvailableMarketTypes) -> Dict:
        """
        Return market dicts for the selected market type
        Args:
            market_type: Selected market type (spot/balancing/settlement/future)

        Returns: Dicts with market objects for the selected market type
        """
        return self._markets.get_market_instances_from_class_type(market_type)

    def is_market_spot(self, market_id: str) -> bool:
        """Return True if market_id belongs to a SPOT market."""
        return market_id in self._markets.spot_market_ids

    def is_market_settlement(self, market_id: str) -> bool:
        """Return True if market_id belongs to a SETTLEMENT market."""
        return market_id in self._markets.settlement_market_ids

    def is_market_balancing(self, market_id: str) -> bool:
        """Return True if market_id belongs to a BALANCING market."""
        return market_id in self._markets.balancing_market_ids

    def is_market_future(self, market_id: str) -> bool:
        """Return True if market_id belongs to a FUTURE market."""
        return market_id == self.future_markets.id

    def get_results_dict(self) -> dict:
        """
        Compose the results dict for the respective area. For non-strategy areas the area stats
        are used, while in the strategy areas the respective state class method is used.
        """
        if self.strategy is not None:
            current_time_slot = None
            if self.spot_market:
                current_time_slot = self.spot_market.time_slot
            elif self.parent.spot_market:
                current_time_slot = self.parent.spot_market.time_slot
            return self.strategy.state.get_results_dict(current_time_slot)
        return {
            "area_throughput": {
                "baseline_peak_energy_import_kWh": self.throughput.baseline_peak_energy_import_kWh,
                "baseline_peak_energy_export_kWh": self.throughput.baseline_peak_energy_export_kWh,
                "import_capacity_kWh": self.throughput.import_capacity_kWh,
                "export_capacity_kWh": self.throughput.export_capacity_kWh,
                "imported_energy_kWh": (
                    self.stats.imported_traded_energy_kwh.get(self.current_market.time_slot, 0.0)
                    if self.current_market is not None
                    else 0.0
                ),
                "exported_energy_kWh": (
                    self.stats.exported_traded_energy_kwh.get(self.current_market.time_slot, 0.0)
                    if self.current_market is not None
                    else 0.0
                ),
            },
            "grid_fee_constant": (
                self.current_market.const_fee_rate if self.current_market is not None else 0.0
            ),
        }


class Market(Area):
    """Class to define geographical market areas that can contain children (areas or assets)."""


class Asset(Area):
    """Class to define assets (devices). These instances cannot contain children."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.children:
            raise ValueError(f"{self.__class__.__name__} instances can't have children.")
