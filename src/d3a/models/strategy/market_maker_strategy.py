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
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.read_user_profile import read_and_convert_identity_profile_to_float
from d3a_interface.constants_limits import GlobalConfig, ConstSettings
from d3a_interface.device_validator import validate_market_maker


class MarketMakerStrategy(CommercialStrategy):
    parameters = ('energy_rate', 'grid_connected')

    def __init__(self, energy_rate=None, grid_connected=True):
        validate_market_maker(grid_connected=grid_connected)
        energy_rate = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE \
            if energy_rate is None else read_and_convert_identity_profile_to_float(energy_rate)
        GlobalConfig.market_maker_rate = energy_rate
        self._grid_connected = grid_connected
        super().__init__(energy_rate)

    def event_market_cycle(self):
        if self._grid_connected is True:
            super().event_market_cycle()

    def event_activate(self):
        pass
