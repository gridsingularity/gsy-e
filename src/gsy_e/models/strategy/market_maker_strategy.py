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
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.utils import key_in_dict_and_not_none
from gsy_framework.validators import MarketMakerValidator

from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.strategy_profile import StrategyProfile


class MarketMakerStrategy(CommercialStrategy):
    """
    Market Maker trading strategy. According to the grid_connected parameter, it either operates
    as a usual strategy by posting offers, or it only sets up the market maker rate configuration
    in order to be used as the reference market maker price by other strategies.
    """

    def __init__(self, energy_rate_profile=None, energy_rate=None, grid_connected=True,
                 energy_rate_profile_uuid=None):
        super().__init__()
        MarketMakerValidator.validate(grid_connected=grid_connected)
        self._grid_connected = grid_connected
        self.energy_rate_profile_uuid = energy_rate_profile_uuid  # needed for profile_handler

        if all(arg is None for arg in [
               energy_rate_profile, energy_rate_profile_uuid, energy_rate]):
            energy_rate = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE

        self._sell_energy_profile = StrategyProfile(
            energy_rate_profile, energy_rate_profile_uuid, energy_rate)
        self._read_or_rotate_profiles()

    def serialize(self):
        return {
            "grid_connected": self._grid_connected,
            "energy_rate": self._sell_energy_profile.input_energy_rate,
            "energy_rate_profile": self._sell_energy_profile.input_profile,
            "energy_rate_profile_uuid": self._sell_energy_profile.input_profile_uuid
        }

    def _read_or_rotate_profiles(self, reconfigure=False):
        self._sell_energy_profile.read_or_rotate_profiles(reconfigure=reconfigure)
        GlobalConfig.market_maker_rate = self._sell_energy_profile.profile

    def event_market_cycle(self):
        if self._grid_connected is True:
            super().event_market_cycle()

    def area_reconfigure_event(self, *args, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        super().area_reconfigure_event(*args, **kwargs)
        if key_in_dict_and_not_none(kwargs, "grid_connected"):
            self._grid_connected = kwargs["grid_connected"]
