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
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.d3a_core.sim_results.area_statistics import _is_load_node, _is_prosumer_node
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy


class KPI:
    def __init__(self):
        self.performance_indices = dict()
        self.producer_list = list()
        self.consumer_list = list()
        self.consumer_area_list = list()
        self.ess_list = list()
        self.buffer_list = list()
        self.total_energy_demanded_wh = 0
        self.total_energy_produced_wh = 0
        self.total_self_consumption_wh = 0
        self.self_consumption_buffer_wh = 0

    def __repr__(self):
        return f"KPI: {self.performance_indices}"

    def _accumulate_devices(self, area):
        for child in area.children:
            if type(child.strategy) in [PVStrategy, PVUserProfileStrategy,
                                        PVPredefinedStrategy, CommercialStrategy]:
                self.producer_list.append(child.name)
            elif _is_load_node(child):
                self.consumer_list.append(child.name)
                self.consumer_area_list.append(child.parent)
                self.total_energy_demanded_wh += child.strategy.state.total_energy_demanded_wh
            elif _is_prosumer_node(child):
                self.ess_list.append(child.name)
            elif isinstance(child.strategy, InfiniteBusStrategy):
                self.buffer_list.append(child.name)
            if child.children:
                self._accumulate_devices(child)

    def _accumulate_self_production(self, trade):
        if trade.seller_origin in self.producer_list:
            self.total_energy_produced_wh += trade.offer.energy * 1000

    def _accumulate_self_consumption(self, trade):
        if trade.seller_origin in self.producer_list and trade.buyer_origin in self.consumer_list:
            self.total_self_consumption_wh += trade.offer.energy * 1000

    def _accumulate_self_consumption_buffer(self, trade):
        if trade.seller_origin in self.producer_list and trade.buyer_origin in self.ess_list:
            self.self_consumption_buffer_wh += trade.offer.energy * 1000

    def _dissipate_self_consumption_buffer(self, trade):
        if trade.seller_origin in self.ess_list:
            # self_consumption_buffer needs to be exhausted to total_self_consumption
            # if sold to internal consumer
            if trade.buyer_origin in self.consumer_list and self.self_consumption_buffer_wh > 0:
                if (self.self_consumption_buffer_wh - trade.offer.energy * 1000) > 0:
                    self.self_consumption_buffer_wh -= trade.offer.energy * 1000
                    self.total_self_consumption_wh += trade.offer.energy * 1000
                else:
                    self.total_self_consumption_wh += self.self_consumption_buffer_wh
                    self.self_consumption_buffer_wh = 0
            # self_consumption_buffer needs to be exhausted if sold to any external agent
            elif trade.buyer_origin not in [*self.ess_list, *self.consumer_list] and \
                    self.self_consumption_buffer_wh > 0:
                if (self.self_consumption_buffer_wh - trade.offer.energy * 1000) > 0:
                    self.self_consumption_buffer_wh -= trade.offer.energy * 1000
                else:
                    self.self_consumption_buffer_wh = 0

    def _accumulate_infinite_consumption(self, trade):
        if trade.seller_origin in self.buffer_list and trade.buyer_origin in self.consumer_list:
            self.total_self_consumption_wh += trade.offer.energy * 1000

    def _dissipate_infinite_consumption(self, trade):
        if trade.buyer_origin in self.buffer_list and trade.seller_origin in self.producer_list:
            self.total_self_consumption_wh += trade.offer.energy * 1000

    def _accumulate_energy_trace(self):
        for c_area in self.consumer_area_list:
            for market in c_area.past_markets:
                for trade in market.trades:
                    self._accumulate_self_consumption(trade)
                    self._accumulate_self_production(trade)
                    self._accumulate_self_consumption_buffer(trade)
                    self._dissipate_self_consumption_buffer(trade)
                    self._accumulate_infinite_consumption(trade)
                    self._dissipate_infinite_consumption(trade)

    def area_performance_indices(self, area):
        self.producer_list = []
        self.consumer_list = []
        self.consumer_area_list = []
        self.ess_list = []
        self.buffer_list = []
        self.total_energy_demanded_wh = 0
        self.total_energy_produced_wh = 0
        self.total_self_consumption_wh = 0
        self.self_consumption_buffer_wh = 0

        self._accumulate_devices(area)

        self._accumulate_energy_trace()

        # in case when the area doesn't have any load demand
        if self.total_energy_demanded_wh <= 0:
            self_sufficiency = None
        elif self.total_self_consumption_wh >= self.total_energy_demanded_wh:
            self_sufficiency = 1.0
        else:
            self_sufficiency = self.total_self_consumption_wh / self.total_energy_demanded_wh

        # in case when the area doesn't have any producing devices
        if self.total_energy_produced_wh <= 0:
            self_consumption = None
        elif self.total_self_consumption_wh >= self.total_energy_produced_wh:
            self_consumption = 1.0
        else:
            self_consumption = self.total_self_consumption_wh / self.total_energy_produced_wh
        return {"self_sufficiency": self_sufficiency, "self_consumption": self_consumption}

    def update_kpis_from_area(self, area):
        self.performance_indices[area.name] = \
            self.area_performance_indices(area)

        for child in area.children:
            if len(child.children) > 0:
                self.update_kpis_from_area(child)
