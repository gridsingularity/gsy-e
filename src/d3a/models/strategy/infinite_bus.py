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
import d3a.constants
from d3a.d3a_core.exceptions import MarketException
from d3a.models.strategy import BidEnabledStrategy, INF_ENERGY
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from d3a_interface.read_user_profile import read_arbitrary_profile, InputProfileTypes, \
    read_and_convert_identity_profile_to_float, convert_identity_profile_to_float
from d3a_interface.utils import convert_str_to_pendulum_in_dict, convert_pendulum_to_str_in_dict
from d3a_interface.utils import find_object_of_same_weekday_and_time


class InfiniteBusStrategy(CommercialStrategy, BidEnabledStrategy):
    parameters = ("energy_sell_rate", "energy_rate_profile", "energy_buy_rate",
                  "buying_rate_profile", "buying_rate_profile_uuid", "energy_rate_profile_uuid")

    def __init__(self, energy_sell_rate=None, energy_rate_profile=None, energy_buy_rate=None,
                 buying_rate_profile=None, buying_rate_profile_uuid=None,
                 energy_rate_profile_uuid=None):
        super().__init__()
        self.energy_per_slot_kWh = INF_ENERGY
        self.energy_buy_rate = None

        if d3a.constants.CONNECT_TO_PROFILES_DB and buying_rate_profile_uuid:
            self.energy_buy_rate_input = None
            self.buying_rate_profile = None
            self.buying_rate_profile_uuid = buying_rate_profile_uuid
        else:
            self.energy_buy_rate_input = energy_buy_rate
            self.buying_rate_profile = buying_rate_profile
            self.buying_rate_profile_uuid = None

        if d3a.constants.CONNECT_TO_PROFILES_DB and energy_rate_profile_uuid:
            self.energy_rate_input = None
            self.energy_rate_profile = None
            self.energy_rate_profile_uuid = energy_rate_profile_uuid
        else:
            self.energy_rate_input = energy_sell_rate
            self.energy_rate_profile = energy_rate_profile
            self.energy_rate_profile_uuid = None

        # This is done to support the UI which handles the Infinite Bus only as a Market Maker.
        # If one plans to allow multiple Infinite Bus devices in the grid, this should be
        # amended.
        self._set_market_maker_rate()

    def _set_market_maker_rate(self):
        if self.energy_rate_profile is not None:
            GlobalConfig.market_maker_rate = \
                read_and_convert_identity_profile_to_float(self.energy_rate_profile)
        elif isinstance(self.energy_rate, (int, float)):
            GlobalConfig.market_maker_rate = self.energy_rate
        elif isinstance(self.energy_rate, (str, dict)):
            GlobalConfig.market_maker_rate = \
                read_arbitrary_profile(InputProfileTypes.IDENTITY, self.energy_rate)
        else:
            GlobalConfig.market_maker_rate = \
                ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE

    def _read_or_rotate_rate_profiles(self):
        if self.energy_buy_rate_input is None and \
                self.buying_rate_profile is None and \
                self.buying_rate_profile_uuid is None:
            self.energy_buy_rate = self.area.config.market_maker_rate
        else:
            self.energy_buy_rate = \
                convert_identity_profile_to_float(
                    self.rotate_profile(profile_type=InputProfileTypes.IDENTITY,
                                        profile=self.energy_buy_rate if self.energy_buy_rate
                                        else self.energy_buy_rate_input,
                                        profile_uuid=self.buying_rate_profile_uuid))

        if self.energy_rate_input is None and \
                self.energy_rate_profile is None and \
                self.energy_rate_profile_uuid is None:
            self.energy_rate = self.area.config.market_maker_rate
        else:
            self.energy_rate = \
                convert_identity_profile_to_float(
                    self.rotate_profile(profile_type=InputProfileTypes.IDENTITY,
                                        profile=self.energy_rate if self.energy_rate
                                        else self.energy_rate_input,
                                        profile_uuid=self.energy_rate_profile_uuid))

    def buy_energy(self, market):
        for offer in market.sorted_offers:
            if offer.seller == self.owner.name:
                # Don't buy our own offer
                continue
            if offer.energy_rate <= find_object_of_same_weekday_and_time(self.energy_buy_rate,
                                                                         market.time_slot):
                try:
                    self.accept_offer(market, offer, buyer_origin=self.owner.name,
                                      buyer_origin_id=self.owner.uuid,
                                      buyer_id=self.owner.uuid)
                except MarketException:
                    # Offer already gone etc., try next one.
                    continue

    def event_tick(self):
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            for market in self.area.all_markets:
                self.buy_energy(market)

    def event_market_cycle(self):
        super().event_market_cycle()
        if ConstSettings.IAASettings.MARKET_TYPE == 2 or \
           ConstSettings.IAASettings.MARKET_TYPE == 3:
            for market in self.area.all_markets:
                try:
                    buy_rate = find_object_of_same_weekday_and_time(self.energy_buy_rate,
                                                                    market.time_slot)
                    self.post_bid(market,
                                  buy_rate * INF_ENERGY,
                                  INF_ENERGY)
                except MarketException:
                    pass

    def get_state(self):
        return {
            "energy_rate": convert_pendulum_to_str_in_dict(self.energy_rate),
            "energy_buy_rate": convert_pendulum_to_str_in_dict(self.energy_buy_rate),
        }

    def restore_state(self, saved_state):
        self.energy_buy_rate.update(convert_str_to_pendulum_in_dict(
            saved_state["energy_buy_rate"]))
        self.energy_rate.update(convert_str_to_pendulum_in_dict(
            saved_state["energy_rate"]))
