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
import warnings
from logging import getLogger
from typing import List, Optional  # noqa

from cached_property import cached_property
from pendulum import duration
from pendulum import DateTime
from slugify import slugify

from d3a.blockchain import BlockChainInterface
from d3a.constants import TIME_ZONE
from d3a.d3a_core.exceptions import AreaException
from d3a.models.appliance.base import BaseAppliance
from d3a.models.config import SimulationConfig
from d3a.events.event_structures import TriggerMixin
from d3a.models.strategy import BaseStrategy
from d3a.d3a_core.util import TaggedLogWrapper
from d3a.models.const import ConstSettings
from d3a.d3a_core.device_registry import DeviceRegistry
from d3a.constants import TIME_FORMAT
from d3a.models.area.stats import AreaStats
from d3a.models.area.event_dispatcher import AreaDispatcher
from d3a.models.area.markets import AreaMarkets
from d3a.models.area.events import Events

log = getLogger(__name__)


DEFAULT_CONFIG = SimulationConfig(
    duration=duration(hours=24),
    market_count=1,
    slot_length=duration(minutes=15),
    tick_length=duration(seconds=1),
    cloud_coverage=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE,
    market_maker_rate=str(ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE),
    iaa_fee=ConstSettings.IAASettings.FEE_PERCENTAGE
)


class Area:
    _area_id_counter = 1

    def __init__(self, name: str = None, children: List["Area"] = None,
                 strategy: BaseStrategy = None,
                 appliance: BaseAppliance = None,
                 config: SimulationConfig = None,
                 budget_keeper=None,
                 balancing_spot_trade_ratio=ConstSettings.BalancingSettings.SPOT_TRADE_RATIO,
                 event_list=[]):
        self.balancing_spot_trade_ratio = balancing_spot_trade_ratio
        self.active = False
        self.log = TaggedLogWrapper(log, name)
        self.current_tick = 0
        self.name = name
        self.slug = slugify(name, to_lower=True)
        self.area_id = Area._area_id_counter
        Area._area_id_counter += 1
        self.parent = None
        self.children = children if children is not None else []
        for child in self.children:
            child.parent = self
        self.strategy = strategy
        self.appliance = appliance
        self._config = config
        self.events = Events(event_list, self)
        self.budget_keeper = budget_keeper
        if budget_keeper:
            self.budget_keeper.area = self
        self._bc = None  # type: BlockChainInterface
        self._markets = AreaMarkets(self.log)
        self.stats = AreaStats(self._markets)
        self.dispatcher = AreaDispatcher(self)

    def activate(self, bc=None):
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

        # Cycle markets without triggering it's own event chain.
        self._cycle_markets(_trigger_event=False)

        if not self.strategy and self.parent is not None:
            self.log.warning("No strategy. Using inter area agent.")
        self.log.info('Activating area')
        self.active = True
        self.dispatcher.broadcast_activate()

    def _cycle_markets(self, _trigger_event=True, _market_cycle=False):
        """
        Remove markets for old time slots, add markets for new slots.
        Trigger `MARKET_CYCLE` event to allow child markets to also cycle.

        It's important for this to happen from top to bottom of the `Area` tree
        in order for the `InterAreaAgent`s to be connected correctly

        `_trigger_event` is used internally to avoid multiple event chains during
        initial area activation.
        """

        self.events.update_events(self.now)

        if not self.children:
            # Since children trade in markets we only need to populate them if there are any
            return

        if self.budget_keeper and _market_cycle:
            self.budget_keeper.process_market_cycle()

        now = self.now
        time_in_hour = duration(minutes=now.minute, seconds=now.second)
        now = now.at(now.hour, minute=0, second=0) + \
            ((time_in_hour // self.config.slot_length) * self.config.slot_length)

        self.log.info("Cycling markets")
        self._markets.rotate_markets(now, self.stats, self.dispatcher)

        # Clear `current_market` cache
        self.__dict__.pop('current_market', None)

        # Markets range from one slot to market_count into the future
        changed = self._markets.create_future_markets(now, True, self)

        if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET and \
                len(DeviceRegistry.REGISTRY.keys()) != 0:
            changed_balancing_market = self._markets.create_future_markets(now, False, self)
        else:
            changed_balancing_market = None

        # Force market cycle event in case this is the first market slot
        if (changed or len(self._markets.past_markets.keys()) == 0) and _trigger_event:
            self.dispatcher.broadcast_market_cycle()

        # Force balancing_market cycle event in case this is the first market slot
        if (changed_balancing_market or len(self._markets.past_balancing_markets.keys()) == 0) \
                and _trigger_event and ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            self.dispatcher.broadcast_balancing_market_cycle()

    def tick(self, is_root_area=False):
        self.events.update_events(self.now)
        if self.current_tick % self.config.ticks_per_slot == 0 and is_root_area:
            self._cycle_markets()
        self.dispatcher.broadcast_tick(area=self)
        self.current_tick += 1

    def __repr__(self):
        return "<Area '{s.name}' markets: {markets}>".format(
            s=self,
            markets=[t.strftime(TIME_FORMAT) for t in self._markets.markets.keys()]
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
        return DEFAULT_CONFIG

    @property
    def bc(self) -> Optional[BlockChainInterface]:
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

    def get_now(self) -> DateTime:
        """Compatibility wrapper"""
        warnings.warn("The '.get_now()' method has been replaced by the '.now' property. "
                      "Please use that in the future.")
        return self.now

    @property
    def now(self) -> DateTime:
        """
        Return the 'current time' as a `DateTime` object.
        Can be overridden in subclasses to change the meaning of 'now'.

        In this default implementation 'current time' is defined by the number of ticks that
        have passed.
        """
        return DateTime.now(tz=TIME_ZONE).start_of('day').add(
            seconds=self.config.tick_length.seconds * self.current_tick
        )

    @property
    def all_markets(self):
        return list(self._markets.markets.values())

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
                   key=lambda m: m.sorted_offers[0].price / m.sorted_offers[0].energy)

    @property
    def next_market(self):
        """Returns the 'current' market (i.e. the one currently 'running')"""
        try:
            return list(self._markets.markets.values())[0]
        except IndexError:
            return None

    @cached_property
    def current_market(self):
        """Returns the 'current' market (i.e. the one currently 'running')"""
        try:
            return list(self._markets.past_markets.values())[-1]
        except IndexError:
            return None

    def get_future_market_from_id(self, _id):
        try:
            return [m for m in self._markets.markets.values() if m.id == _id][0]
        except IndexError:
            return None

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
        self.config.event_update(**kwargs)
        if self.strategy:
            self.strategy.read_config_event()
        for child in self.children:
            child.update_config(**kwargs)
