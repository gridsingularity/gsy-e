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
from d3a.d3a_core.util import should_read_profile_from_db
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a_interface.constants_limits import GlobalConfig, ConstSettings
from d3a_interface.device_validator import validate_market_maker
from d3a_interface.read_user_profile import InputProfileTypes, \
    read_and_convert_identity_profile_to_float, convert_identity_profile_to_float
from d3a_interface.utils import key_in_dict_and_not_none


class MarketMakerStrategy(CommercialStrategy):
    parameters = ("energy_rate_profile", "energy_rate", "grid_connected",
                  "energy_rate_profile_uuid")

    def __init__(self, energy_rate_profile=None, energy_rate=None, grid_connected=True,
                 energy_rate_profile_uuid=None):
        super().__init__()
        validate_market_maker(grid_connected=grid_connected)

        self.energy_rate = None

        if should_read_profile_from_db(energy_rate_profile_uuid):
            self.energy_rate_profile = None
            self.energy_rate_input = None
            self.energy_rate_profile_uuid = energy_rate_profile_uuid
        else:
            self.energy_rate_profile = energy_rate_profile
            self.energy_rate_input = energy_rate
            self.energy_rate_profile_uuid = None

        self._grid_connected = grid_connected

        self._read_or_rotate_rate_profiles()

    def event_activate_price(self):
        pass

    def _read_or_rotate_rate_profiles(self):
        if self.energy_rate_input is None and \
                self.energy_rate_profile is None and \
                self.energy_rate_profile_uuid is None:
            self.energy_rate = read_and_convert_identity_profile_to_float(
                ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE)
        else:
            self.energy_rate = \
                convert_identity_profile_to_float(
                    self.rotate_profile(profile_type=InputProfileTypes.IDENTITY,
                                        profile=self.energy_rate if self.energy_rate
                                        else self.energy_rate_input,
                                        profile_uuid=self.energy_rate_profile_uuid))

        GlobalConfig.market_maker_rate = self.energy_rate

    def event_market_cycle(self):
        if self._grid_connected is True:
            super().event_market_cycle()

    def area_reconfigure_event(self, *args, **kwargs):
        super().area_reconfigure_event(*args, **kwargs)
        if key_in_dict_and_not_none(kwargs, "grid_connected"):
            self._grid_connected = kwargs["grid_connected"]
