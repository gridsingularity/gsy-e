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

from abc import ABC, abstractmethod

from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy


class PowerFlowBase(ABC):
    def __init__(self, root_area, root_voltage):
        """
        :param root_area: contains tree structured hierarchical energy grid
        :param root_voltage: contains the voltage of the top most hierarchy
        """
        self.root_voltage = root_voltage
        self._grid_forming(root_area)

    def _grid_forming(self, area):
        """
        :param area: takes area object and convert it to specific energy device
        :return: electrical network compliant connected grid
        """
        if area.strategy is None:
            area.bus = self.create_bus(area, self.root_voltage)
            if area.parent is not None:
                area.line = self.add_line(area.parent, area)
        elif isinstance(area.strategy, InfiniteBusStrategy):
            area.ext_grid = self.add_external_grid(area)
        elif isinstance(area.strategy, LoadHoursStrategy):
            area.load_device = self.add_load_device(area, area.strategy.avg_power_W)
        elif isinstance(area.strategy, StorageStrategy):
            area.ess_device = self.add_storage_device(area)
        elif isinstance(area.strategy, PVStrategy):
            area.pv_device = \
                self.add_generation_device(area, area.strategy.max_panel_power_W * 1e-3)
        elif isinstance(area.strategy, FinitePowerPlant):
            area.power_plant = \
                self.add_generation_device(area, area.strategy.max_available_power_kW)
        for child in area.children:
            self._grid_forming(child)

    @abstractmethod
    def create_bus(self, area, voltage):
        """
        :param area: area node where bus bar needs to be added
        :param voltage: voltage level of bus bar
        :return: add a bus-bar to the specified area node
        """
        pass

    @abstractmethod
    def add_external_grid(self, area):
        """
        :param area: area node where external grid element needs to be added
        :return: an external grid device like MarketMaker
        """
        pass

    @abstractmethod
    def add_load_device(self, area, avg_power_w):
        """
        :param area: Takes area that is using Load as a strategy
        :param avg_power_w: Peak power of the load device
        :return: add a load device to the specified area node
        """
        pass

    @abstractmethod
    def add_generation_device(self, area, peak_power_kw):
        """
        :param area: Takes area that is using generating strategy
        :param peak_power_kw: Takes into account power rating of the generating device
        :return: add a generating device to the specified area node
        """
        pass

    @abstractmethod
    def add_storage_device(self, area):
        """
        :param area: Takes area that is using Storage as a strategy
        :return: add an Storage device to the specified area node
        """
        pass

    @abstractmethod
    def add_line(self, source_area, target_area):
        """
        :param source_area: parent area of referenced area
        :param target_area: child area of referenced area
        :return: add an electrical line connecting parent and child area
        """
        pass

    @abstractmethod
    def run_power_flow(self):
        pass

    @abstractmethod
    def export_powerflow_results(self, dir):
        """
        :param dir: directory where results has to exported
        :return: export powerflow results in html format to the specified directory
        """
        pass
