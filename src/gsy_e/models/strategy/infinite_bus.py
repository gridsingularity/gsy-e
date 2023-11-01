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
from gsy_framework.data_classes import TraderDetails
from gsy_framework.enums import SpotMarketTypeEnum
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import (convert_pendulum_to_str_in_dict, convert_str_to_pendulum_in_dict,
                                 find_object_of_same_weekday_and_time)

from gsy_e.gsy_e_core.exceptions import MarketException
from gsy_e.models.base import AssetType
from gsy_e.models.strategy import INF_ENERGY, BidEnabledStrategy
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.profile import EnergyProfile


# pylint: disable=missing-class-docstring, too-many-instance-attributes, too-many-arguments
class InfiniteBusStrategy(CommercialStrategy, BidEnabledStrategy):
    """Implementation for infinite bus to participate in GSy Exchange."""

    def __init__(self, energy_sell_rate=None, energy_rate_profile=None, energy_buy_rate=None,
                 buying_rate_profile=None, buying_rate_profile_uuid=None,
                 energy_rate_profile_uuid=None):
        super().__init__()
        self.energy_per_slot_kWh = INF_ENERGY
        self.energy_rate_profile_uuid = energy_rate_profile_uuid  # needed for profile_handler
        self.buying_rate_profile_uuid = buying_rate_profile_uuid  # needed for profile_handler

        # buy
        if all(arg is None for arg in [
               buying_rate_profile, buying_rate_profile_uuid, energy_buy_rate]):
            energy_buy_rate = ConstSettings.GeneralSettings.DEFAULT_FEED_IN_TARIFF
        self._buy_energy_profile = EnergyProfile(
            buying_rate_profile, buying_rate_profile_uuid, energy_buy_rate,
            profile_type=InputProfileTypes.IDENTITY)

        # sell
        if all(arg is None for arg in [
               energy_rate_profile, energy_rate_profile_uuid, energy_sell_rate]):
            energy_sell_rate = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE
        self._sell_energy_profile = EnergyProfile(
            energy_rate_profile, energy_rate_profile_uuid, energy_sell_rate,
            profile_type=InputProfileTypes.IDENTITY)

        # This is done to support the UI which handles the Infinite Bus only as a Market Maker.
        # If one plans to allow multiple Infinite Bus devices in the grid, this should be
        # amended.
        self._read_or_rotate_profiles()

    @property
    def energy_buy_rate(self):
        # This method exists for backward compatibility.
        """Return buy energy profile of the asset."""
        return self._buy_energy_profile.profile

    def serialize(self):
        return {
            # sell
            "energy_sell_rate": self._sell_energy_profile.input_energy_rate,
            "energy_rate_profile": self._sell_energy_profile.input_profile,
            "energy_rate_profile_uuid": self._sell_energy_profile.input_profile_uuid,
            # buy
            "energy_buy_rate": self._buy_energy_profile.input_energy_rate,
            "buying_rate_profile": self._buy_energy_profile.input_profile,
            "buying_rate_profile_uuid": self._buy_energy_profile.input_profile_uuid,
        }

    def _read_or_rotate_profiles(self, reconfigure=False):
        self._sell_energy_profile.read_or_rotate_profiles(reconfigure=reconfigure)
        self._buy_energy_profile.read_or_rotate_profiles(reconfigure=reconfigure)

        GlobalConfig.market_maker_rate = self._sell_energy_profile.profile
        GlobalConfig.FEED_IN_TARIFF = self._buy_energy_profile.profile

    def event_activate(self, **kwargs):
        """Event activate."""
        self._read_or_rotate_profiles()

    def buy_energy(self, market):
        """Buy energy."""
        for offer in market.sorted_offers:
            if offer.seller.name == self.owner.name:
                # Don't buy our own offer
                continue
            if offer.energy_rate <= find_object_of_same_weekday_and_time(
                    self.energy_buy_rate,
                    market.time_slot):
                try:
                    self.accept_offer(market, offer, buyer=TraderDetails(
                        self.owner.name, self.owner.uuid, self.owner.name, self.owner.uuid))
                except MarketException:
                    # Offer already gone etc., try next one.
                    continue

    def event_tick(self):
        """Buy energy on market tick. This method is triggered by the TICK event."""
        if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.ONE_SIDED.value:
            for market in self.area.all_markets:
                self.buy_energy(market)

    def event_market_cycle(self):
        super().event_market_cycle()
        if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.TWO_SIDED.value:
            for market in self.area.all_markets:
                try:
                    buy_rate = find_object_of_same_weekday_and_time(
                        self.energy_buy_rate,
                        market.time_slot)
                    self.post_bid(market,
                                  buy_rate * INF_ENERGY,
                                  INF_ENERGY)
                except MarketException:
                    pass

    def get_state(self):
        return {
            "energy_rate": convert_pendulum_to_str_in_dict(self._sell_energy_profile.profile),
            "energy_buy_rate": convert_pendulum_to_str_in_dict(self._buy_energy_profile.profile),
        }

    def restore_state(self, saved_state):
        self._buy_energy_profile.profile = convert_str_to_pendulum_in_dict(
            saved_state["energy_buy_rate"])
        self._sell_energy_profile.profile = convert_str_to_pendulum_in_dict(
            saved_state["energy_rate"])

    @property
    def asset_type(self):
        return AssetType.PROSUMER
