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

import pandapower as pp
from pandapower.plotting import to_html

from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.pv import PVStrategy
# from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.market_maker_strategy import MarketMakerStrategy


class PowerFlow:
    def __init__(self, root_area, root_voltage=400):
        """
        :param root_area: It contains tree structured hierarchical energy grid
        :param root_voltage: It contains the voltage of the top most hierarchy
        """
        self.network = pp.create_empty_network()
        self.root_voltage = root_voltage
        self._grid_forming(root_area)

    def _grid_forming(self, area):
        """
        :param area: Takes area object and convert it to specific energy device
        :return: It will return pandapower compliant connected grid
        """
        if area.strategy is None:
            area.bus = None
            area.bus = self._create_bus(area, self.root_voltage)
            if area.parent is not None:
                area.line = None
                area.line = self._add_line(area.parent, area)
        elif isinstance(area.strategy, MarketMakerStrategy):
            area.ext_grid = None
            area.ext_grid = self._add_external_grid(area)
        elif isinstance(area.strategy, LoadHoursStrategy):
            area.load_device = None
            area.load_device = self._add_load_device(area, area.strategy.avg_power_W)
        elif isinstance(area.strategy, StorageStrategy):
            area.ess_device = self._add_storage_device(area)
        elif isinstance(area.strategy, PVStrategy):
            area.pv_device = self._add_pv_device(area)
        for child in area.children:
            self._grid_forming(child)

    def _create_bus(self, area, voltage):
        """
        :param area: area node where bus bar needs to be added
        :param voltage: voltage level of bus bar
        :return: It will add a bus-bar to the specified area node
        """
        return pp.create_bus(self.network, vn_kv=voltage, name=area.name)

    def _add_external_grid(self, area):
        """
        :param area: area node where external grid element needs to be added
        :return: It will return an external grid device like MarketMaker
        """
        return pp.create_ext_grid(self.network, bus=area.parent.bus, vm_pu=1.0, name=area.name)

    def _add_load_device(self, area, avg_power_W):
        """
        :param area: Takes area that is using Load as a strategy
        :param avg_power_W: Peak power of the load device
        :return: It will add a load device to the specified area node
        """
        return pp.create_load(self.network, bus=area.parent.bus, p_mw=avg_power_W * 1e-6,
                              name=area.name)

    def _add_pv_device(self, area):
        """
        :param area: Takes area that is using PV as a strategy
        :return: It will add a PV device to the specified area node
        """
        peak_power_mw = area.strategy.panel_count * area.strategy.max_panel_power_W * 1e-6
        return pp.create_sgen(self.network, bus=area.parent.bus, p_mw=peak_power_mw,
                              name=area.name)

    def _add_storage_device(self, area):
        """
        :param area: Takes area that is using Storage as a strategy
        :return: It will add an Storage device to the specified area node
        """
        soc_ratio = area.strategy.initial_soc/100
        battery_capacity_mwh = area.strategy.state.capacity * 1e-3
        min_energy_mwh = area.strategy.state.min_allowed_soc_ratio * battery_capacity_mwh
        return pp.create_storage(self.network, bus=area.parent.bus, p_mw=battery_capacity_mwh,
                                 max_e_mwh=battery_capacity_mwh, min_e_mwh=min_energy_mwh,
                                 soc_percent=soc_ratio, name=area.name)

    def _add_line(self, source_area, target_area):
        """
        :param source_area: parent area of referenced area
        :param target_area: child area of referenced area
        :return: It will add an electrical line connecting parent and child area
        """
        line_name = str(source_area.name) + str("->") + str(target_area.name)
        return pp.create_line(self.network, from_bus=source_area.bus, to_bus=target_area.bus,
                              length_km=0.1, std_type="NAYY 4x150 SE", name=line_name)

    def run_power_flow(self):
        return pp.runpp(self.network)

    def get_results(self, dir):
        """
        :param dir: directory where results has to exported
        :return: It will export powerflow results in html format to the specified directory
        """
        filename = dir + 'powerflow.html'
        to_html(self.network, filename)
