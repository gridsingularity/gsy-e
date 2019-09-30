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
from d3a_interface.constants_limits import GlobalConfig


class MarketMakerStrategy(CommercialStrategy):
    parameters = ('energy_rate',)

    def __init__(self, energy_rate=None):
        GlobalConfig.market_maker_rate = read_and_convert_identity_profile_to_float(energy_rate)
        super().__init__(energy_rate)
