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
from d3a.d3a_core.util import find_object_of_same_weekday_and_time
from d3a.d3a_core.util import get_market_maker_rate_from_config, ExternalTickCounter
from d3a.d3a_core.user_profile_handler import ProfileDBConnectionHandler


class ExternalConnectionGlobalStatistics:

    def __init__(self):
        self.area_stats_tree_dict = {}
        self.root_area = None
        self.external_tick_counter = None
        self.current_feed_in_tariff = None
        self.current_market_maker_rate = None

    def __call__(self, root_area, ticks_per_slot):
        self.root_area = root_area
        self.external_tick_counter = ExternalTickCounter(ticks_per_slot)

    def _buffer_feed_in_tariff(self, area, current_market_slot):
        """
        This simplified recursion is sufficient as the infinite bus is expected to be in the
        uppermost level of the tree
        """
        # the lazy import is needed in order to avoid circular imports
        from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
        for child in area.children:
            if isinstance(child.strategy, InfiniteBusStrategy):
                self.current_feed_in_tariff = \
                    find_object_of_same_weekday_and_time(child.strategy.energy_buy_rate,
                                                         current_market_slot)
                return

    def buffer_market_maker_rate(self):
        if self.root_area.current_market:
            self.current_market_maker_rate = get_market_maker_rate_from_config(
                                                      self.root_area.current_market)

    def update(self, market_cycle=False):
        if self.root_area.current_market is None:
            return
        self._create_grid_tree_dict(self.root_area, self.area_stats_tree_dict)
        if market_cycle:
            self._buffer_feed_in_tariff(self.root_area, self.root_area.current_market.time_slot)
            self.buffer_market_maker_rate()

    def is_it_time_for_external_tick(self, current_tick_in_slot):
        return self.external_tick_counter.is_it_time_for_external_tick(current_tick_in_slot)

    def _create_grid_tree_dict(self, area, outdict):
        # the lazy import is needed in order to avoid circular imports
        from d3a.models.strategy.external_strategies import ExternalMixin
        outdict[area.uuid] = {}
        if area.children:
            if area.current_market:
                area_dict = {'last_market_bill': area.stats.get_last_market_stats_for_grid_tree(),
                             'last_market_stats': area.stats.get_price_stats_current_market(),
                             'last_market_fee': area.current_market.fee_class.grid_fee_rate,
                             'current_market_fee': area.get_grid_fee(),
                             'area_name': area.name,
                             'children': {}}
            else:
                area_dict = {'children': {},
                             'area_name': area.name}
            outdict[area.uuid].update(area_dict)
            for child in area.children:
                self._create_grid_tree_dict(child, outdict[area.uuid]['children'])
        else:
            outdict[area.uuid] = area.strategy.market_info_dict \
                if isinstance(area.strategy, ExternalMixin) else {}
            outdict[area.uuid].update({'area_name': area.name})


class GlobalObjects:
    profile_db_connection = ProfileDBConnectionHandler()
    external_global_stats = ExternalConnectionGlobalStatistics()
