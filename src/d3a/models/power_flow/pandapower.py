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
import os
import platform

from d3a.models.power_flow import PowerFlowBase
from d3a.d3a_core.util import convert_unit_to_mega, convert_kilo_to_mega, convert_percent_to_ratio
from d3a.d3a_core.export import mkdir_from_str
from d3a_interface.constants_limits import GlobalConfig
if platform.python_implementation() != "PyPy" and GlobalConfig.POWER_FLOW is True:
    import pandapower as pp
    from pandapower.plotting import to_html


class PandaPowerFlow(PowerFlowBase):
    def __init__(self, root_area, root_voltage=400):
        self.network = pp.create_empty_network()
        super().__init__(root_area, root_voltage)

    def create_bus(self, area, voltage):
        return pp.create_bus(self.network, vn_kv=voltage, name=area.name)

    def add_external_grid(self, area):
        return pp.create_ext_grid(self.network, bus=area.parent.bus, vm_pu=1.0, name=area.name)

    def add_load_device(self, area, avg_power_w):
        return pp.create_load(self.network, bus=area.parent.bus,
                              p_mw=convert_unit_to_mega(avg_power_w),
                              name=area.name)

    def add_generation_device(self, area, peak_power_kw):
        return pp.create_gen(self.network, bus=area.parent.bus,
                             p_mw=convert_kilo_to_mega(peak_power_kw),
                             name=area.name)

    def add_storage_device(self, area):
        soc_ratio = convert_percent_to_ratio(area.strategy.initial_soc)
        battery_capacity_mwh = convert_kilo_to_mega(area.strategy.state.capacity)
        min_energy_mwh = area.strategy.state.min_allowed_soc_ratio * battery_capacity_mwh
        return pp.create_storage(self.network, bus=area.parent.bus, p_mw=battery_capacity_mwh,
                                 max_e_mwh=battery_capacity_mwh, min_e_mwh=min_energy_mwh,
                                 soc_percent=soc_ratio, name=area.name)

    def add_line(self, source_area, target_area):
        line_name = str(source_area.name) + str("->") + str(target_area.name)
        return pp.create_line(self.network, from_bus=source_area.bus, to_bus=target_area.bus,
                              length_km=0.1, std_type="NAYY 4x150 SE", name=line_name)

    def run_power_flow(self):
        return pp.runpp(self.network)

    def export_power_flow_results(self, directory: dir):
        mkdir_from_str(directory)
        filename = os.path.join(directory, 'power_flow.html')
        to_html(self.network, filename)
