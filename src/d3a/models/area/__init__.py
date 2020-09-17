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
from typing import List  # noqa
from cached_property import cached_property
from pendulum import DateTime, duration, today, parse
from slugify import slugify
from uuid import uuid4
from d3a.constants import TIME_ZONE
from d3a.d3a_core.exceptions import AreaException
from d3a.models.appliance.base import BaseAppliance
from d3a.models.config import SimulationConfig
from d3a.events.event_structures import TriggerMixin
from d3a.models.strategy import BaseStrategy
from d3a.d3a_core.util import TaggedLogWrapper
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.device_registry import DeviceRegistry
from d3a.constants import TIME_FORMAT
from d3a.models.area.stats import AreaStats
from d3a.models.area.event_dispatcher import DispatcherFactory
from d3a.models.area.markets import AreaMarkets
from d3a.models.area.events import Events
from d3a_interface.constants_limits import GlobalConfig
from d3a_interface.area_validator import validate_area
from d3a.models.area.redis_external_market_connection import RedisMarketExternalConnection
from d3a_interface.utils import key_in_dict_and_not_none
import d3a.constants

log = getLogger(__name__)

# TODO: As this is only used in the unittests, please remove it here and replace the usages
#       of this class with d3a-interface.constants_limits.GlobalConfig class:
DEFAULT_CONFIG = SimulationConfig(
    sim_duration=duration(hours=24),
    market_count=1,
    slot_length=duration(minutes=15),
    tick_length=duration(seconds=1),
    cloud_coverage=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE,
    start_date=today(tz=TIME_ZONE),
    max_panel_power_W=ConstSettings.PVSettings.MAX_PANEL_OUTPUT_W
)


class Area:

    def __init__(self, name: str = None, children: List["Area"] = None,
                 uuid: str = None,
                 strategy: BaseStrategy = None,
                 appliance: BaseAppliance = None,
                 config: SimulationConfig = None,
                 budget_keeper=None,
                 balancing_spot_trade_ratio=ConstSettings.BalancingSettings.SPOT_TRADE_RATIO,
                 event_list=[],
                 grid_fee_percentage: float = None,
                 grid_fee_constant: float = None,
                 external_connection_available: bool = False,
                 baseline_peak_energy_import_kWh: float = None,
                 baseline_peak_energy_export_kWh: float = None,
                 import_capacity_kVA: float = None,
                 export_capacity_kVA: float = None
                 ):
        validate_area(grid_fee_constant=grid_fee_constant,
                      grid_fee_percentage=grid_fee_percentage,
                      baseline_peak_energy_import_kWh=baseline_peak_energy_import_kWh,
                      baseline_peak_energy_export_kWh=baseline_peak_energy_export_kWh,
                      import_capacity_kVA=import_capacity_kVA,
                      export_capacity_kVA=export_capacity_kVA)
        self.balancing_spot_trade_ratio = balancing_spot_trade_ratio
        self.active = False
        self.log = TaggedLogWrapper(log, name)
        self.current_tick = 0
        self.name = name
        self.baseline_peak_energy_import_kWh = baseline_peak_energy_import_kWh
        self.baseline_peak_energy_export_kWh = baseline_peak_energy_export_kWh
        self.uuid = uuid if uuid is not None else str(uuid4())
        self.slug = slugify(name, to_lower=True)
        self.parent = None
        self.children = children if children is not None else []
        for child in self.children:
            child.parent = self

        if (len(self.children) > 0) and (strategy is not None):
            raise AreaException("A leaf area can not have children.")
        self.strategy = strategy
        self.appliance = appliance
        self._config = config
        self.events = Events(event_list, self)
        self.budget_keeper = budget_keeper
        if budget_keeper:
            self.budget_keeper.area = self
        self._bc = None
        self._markets = None
        self.dispatcher = DispatcherFactory(self)()
        self._set_grid_fees(grid_fee_constant, grid_fee_percentage)
        self._convert_area_throughput_kva_to_kwh(import_capacity_kVA, export_capacity_kVA)
        self.display_type = "Area" if self.strategy is None else self.strategy.__class__.__name__
        self._markets = AreaMarkets(self.log)
        self.stats = AreaStats(self._markets)
        log.debug(f"External connection {external_connection_available} for area {self.name}")
        self.redis_ext_conn = RedisMarketExternalConnection(self) \
            if external_connection_available is True else None
        self.schedule_grid_fee = ""

    def area_reconfigure_event(self, **kwargs):
        grid_fee_dict = {}
        if self.strategy is not None:
            self.strategy.area_reconfigure_event(**kwargs)
            return
        if 'grid_fee_constant' in kwargs or 'grid_fee_percentage' in kwargs:
            grid_fee_constant = kwargs["grid_fee_constant"] \
                if key_in_dict_and_not_none(kwargs, 'grid_fee_constant') else 0
            grid_fee_percentage = kwargs["grid_fee_percentage"] \
                if key_in_dict_and_not_none(kwargs, 'grid_fee_percentage') else 0
            grid_fee_dict['grid_fee_constant'] = grid_fee_constant
            grid_fee_dict['grid_fee_percentage'] = grid_fee_percentage
            grid_fee_dict['name'] = kwargs['name']
            grid_fee_dict['scheduled_time'] = kwargs['scheduled_time']
            self.schedule_grid_fee = grid_fee_dict
            validate_area(grid_fee_percentage=grid_fee_percentage,
                          grid_fee_constant=grid_fee_constant)
            if kwargs['scheduled_time'] is None:
                self._set_grid_fees(grid_fee_constant, grid_fee_percentage)

        if key_in_dict_and_not_none(kwargs, 'baseline_peak_energy_import_kWh'):
            self.baseline_peak_energy_import_kWh = kwargs['baseline_peak_energy_import_kWh']
            validate_area(baseline_peak_energy_import_kWh=self.baseline_peak_energy_import_kWh)
        if key_in_dict_and_not_none(kwargs, 'baseline_peak_energy_export_kWh'):
            self.baseline_peak_energy_export_kWh = kwargs['baseline_peak_energy_export_kWh']
            validate_area(baseline_peak_energy_export_kWh=self.baseline_peak_energy_export_kWh)

        if key_in_dict_and_not_none(kwargs, 'import_capacity_kVA') or \
                key_in_dict_and_not_none(kwargs, 'export_capacity_kVA'):
            import_capacity_kVA = kwargs["import_capacity_kVA"] \
                if key_in_dict_and_not_none(kwargs, 'import_capacity_kVA') else None
            export_capacity_kVA = kwargs["export_capacity_kVA"] \
                if key_in_dict_and_not_none(kwargs, 'export_capacity_kVA') else None
            validate_area(import_capacity_kVA=import_capacity_kVA,
                          export_capacity_kVA=export_capacity_kVA)
            self._convert_area_throughput_kva_to_kwh(import_capacity_kVA, export_capacity_kVA)

    def _set_grid_fees(self, transfer_fee_const, grid_fee_percentage):
        grid_fee_type = self.config.grid_fee_type \
            if self.config is not None \
            else ConstSettings.IAASettings.GRID_FEE_TYPE
        if grid_fee_type == 1:
            grid_fee_percentage = None
        elif grid_fee_type == 2:
            transfer_fee_const = None
        self.grid_fee_constant = transfer_fee_const
        self.grid_fee_percentage = grid_fee_percentage

    def _convert_area_throughput_kva_to_kwh(self, import_capacity_kVA, export_capacity_kVA):
        self.import_capacity_kWh = \
            import_capacity_kVA * self.config.slot_length.total_minutes() / 60.0 \
            if import_capacity_kVA is not None else 0.
        self.export_capacity_kWh = \
            export_capacity_kVA * self.config.slot_length.total_minutes() / 60.0 \
            if export_capacity_kVA is not None else 0.

    def set_events(self, event_list):
        self.events = Events(event_list, self)

    def activate(self, bc=None, current_tick=None):
        if current_tick is not None:
            self.current_tick = current_tick
        if bc:
            self._bc = bc
        for attr, kind in [(self.strategy, 'Strategy'), (self.appliance, 'Appliance')]:
            if attr:
                if self.parent:
                    attr.area = self.parent
                    attr.owner = self
                else:
                    raise AreaException(
                        "{kind} {attr.__class__.__name__} "
                        "on area {s} without parent!".format(
                            kind=kind,
                            attr=attr,
                            s=self
                        )
                    )

            if self.budget_keeper:
                self.budget_keeper.activate()
        if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
            self.grid_fee_percentage = 0

        # Cycle markets without triggering it's own event chain.
        self._cycle_markets(_trigger_event=False)
        if not self.strategy and self.parent is not None:
            self.log.debug("No strategy. Using inter area agent.")
        self.log.debug('Activating area')
        self.active = True
        self.dispatcher.broadcast_activate()
        if self.redis_ext_conn is not None:
            self.redis_ext_conn.sub_to_area_event()

    def deactivate(self):
        self._cycle_markets(deactivate=True)
        if self.redis_ext_conn is not None:
            self.redis_ext_conn.deactivate()
        if self.strategy:
            self.strategy.deactivate()

    def _cycle_markets(self, _trigger_event=True, _market_cycle=False, deactivate=False):
        """
        Remove markets for old time slots, add markets for new slots.
        Trigger `MARKET_CYCLE` event to allow child markets to also cycle.

        It's important for this to happen from top to bottom of the `Area` tree
        in order for the `InterAreaAgent`s to be connected correctly

        `_trigger_event` is used internally to avoid multiple event chains during
        initial area activation.
        """
        self.events.update_events(self.now)
        if self.current_market is not None and len(self.schedule_grid_fee) > 0:
            scheduled_time = parse(self.schedule_grid_fee['scheduled_time'])
            time_slot_start = self.current_market.time_slot
            time_slot_end = time_slot_start.add(minutes=GlobalConfig.slot_length.minutes)
            if time_slot_start <= scheduled_time <= time_slot_end and self.current_market.name == \
                    self.schedule_grid_fee['name']:
                self._set_grid_fees(self.schedule_grid_fee['grid_fee_constant'],
                                    self.schedule_grid_fee['grid_fee_percentage'])
                print("done:::::")

        if not self.children:
            # Since children trade in markets we only need to populate them if there are any
            return

        if self.budget_keeper and _market_cycle:
            self.budget_keeper.process_market_cycle()

        self.log.debug("Cycling markets")
        self._markets.rotate_markets(self.now, self.stats, self.dispatcher)
        self.dispatcher._delete_past_agents(self.dispatcher._inter_area_agents)

        if deactivate:
            return

        # Clear `current_market` cache
        self.__dict__.pop('current_market', None)

        # area_market_stats have to updated when cycling market of each area:
        self.stats.update_area_market_stats()
        self.stats.aggregate_exported_imported_energy(self)

        # Markets range from one slot to market_count into the future
        changed = self._markets.create_future_markets(self.now, True, self)

        if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET and \
                len(DeviceRegistry.REGISTRY.keys()) != 0:
            changed_balancing_market = self._markets.create_future_markets(self.now, False, self)
        else:
            changed_balancing_market = None

        # Force market cycle event in case this is the first market slot
        if (changed or len(self._markets.past_markets.keys()) == 0) and _trigger_event:
            self.dispatcher.broadcast_market_cycle()

        # Force balancing_market cycle event in case this is the first market slot
        if (changed_balancing_market or len(self._markets.past_balancing_markets.keys()) == 0) \
                and _trigger_event and ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            self.dispatcher.broadcast_balancing_market_cycle()

        if self.redis_ext_conn is not None:
            self.redis_ext_conn.event_market_cycle()

    def tick(self):
        if ConstSettings.IAASettings.MARKET_TYPE == 2 or \
                ConstSettings.IAASettings.MARKET_TYPE == 3:
            if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
                self.dispatcher.publish_market_clearing()
            else:
                for market in self.all_markets:
                    market.match_offers_bids()

        self.events.update_events(self.now)
        self.current_tick += 1
        if self._markets:
            for market in self._markets.markets.values():
                market.update_clock(self.current_tick_in_slot)

    def tick_and_dispatch(self):
        if d3a.constants.DISPATCH_EVENTS_BOTTOM_TO_TOP:
            self.dispatcher.broadcast_tick()
            self.tick()
        else:
            self.tick()
            self.dispatcher.broadcast_tick()

    def __repr__(self):
        return "<Area '{s.name}' markets: {markets}>".format(
            s=self,
            markets=[t.format(TIME_FORMAT) for t in self._markets.markets.keys()]
        )

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
        if self.parent:
            return self.parent.bc
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
        Return the 'current time' as a `DateTime` object.
        Can be overridden in subclasses to change the meaning of 'now'.

        In this default implementation 'current time' is defined by the number of ticks that
        have passed.
        """
        return self.config.start_date.add(
            seconds=self.config.tick_length.seconds * self.current_tick
        )

    @property
    def all_markets(self):
        return [m for m in self._markets.markets.values() if m.in_sim_duration]

    @property
    def past_markets(self):
        return list(self._markets.past_markets.values())

    def get_market(self, timeslot):
        return self._markets.markets[timeslot]

    def get_past_market(self, timeslot):
        return self._markets.past_markets[timeslot]

    def get_balancing_market(self, timeslot):
        return self._markets.balancing_markets[timeslot]

    @property
    def balancing_markets(self):
        return list(self._markets.balancing_markets.values())

    @property
    def past_balancing_markets(self):
        return list(self._markets.past_balancing_markets.values())

    @property
    def market_with_most_expensive_offer(self):
        # In case of a tie, max returns the first market occurrence in order to
        # satisfy the most recent market slot
        return max(self.all_markets,
                   key=lambda m: m.sorted_offers[0].energy_rate)

    @property
    def next_market(self):
        """Returns the 'current' market (i.e. the one currently 'running')"""
        try:
            return list(self._markets.markets.values())[0]
        except IndexError:
            return None

    @property
    def current_market(self):
        """Returns the 'most recent past market' market
        (i.e. the one that has been finished last)"""
        try:
            return list(self._markets.past_markets.values())[-1]
        except IndexError:
            return None

    @property
    def current_balancing_market(self):
        """Returns the 'current' balancing market (i.e. the one currently 'running')"""
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

    @cached_property
    def available_triggers(self):
        triggers = []
        if isinstance(self.strategy, TriggerMixin):
            triggers.extend(self.strategy.available_triggers)
        if isinstance(self.appliance, TriggerMixin):
            triggers.extend(self.appliance.available_triggers)
        return {t.name: t for t in triggers}

    def _fire_trigger(self, trigger_name, **params):
        for target in (self.strategy, self.appliance):
            if isinstance(target, TriggerMixin):
                for trigger in target.available_triggers:
                    if trigger.name == trigger_name:
                        return target.fire_trigger(trigger_name, **params)

    def update_config(self, **kwargs):
        if not self.config:
            return
        self.config.update_config_parameters(**kwargs)
        if self.strategy:
            self.strategy.read_config_event()
        for child in self.children:
            child.update_config(**kwargs)
