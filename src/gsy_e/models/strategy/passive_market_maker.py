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
from collections import namedtuple
from enum import Enum
from logging import getLogger
from typing import Union

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import SpotMarketTypeEnum
from gsy_framework.utils import key_in_dict_and_not_none

from gsy_e import constants
from gsy_e.gsy_e_core.exceptions import MarketException
from gsy_e.models.base import AssetType
from gsy_e.models.state import ESSEnergyOrigin, StorageState
from gsy_e.models.strategy import BidEnabledStrategy
from gsy_e.models.strategy.update_frequency import (
    MarketMakerStrategyBidUpdater, MarketMakerStrategyOfferUpdater)

log = getLogger(__name__)

BalancingRatio = namedtuple("BalancingRatio", ("demand", "supply"))

StorageSettings = ConstSettings.StorageSettings
PassiveMarketMakerSettings = ConstSettings.PassiveMarketMakerSettings
GeneralSettings = ConstSettings.GeneralSettings
BalancingSettings = ConstSettings.BalancingSettings


class PassiveMarketMakerStrategy(BidEnabledStrategy):
    """Template strategy for flexible market maker agent."""

    def serialize(self):
        return {
            "initial_soc": self.state.initial_soc,
            "min_allowed_soc": self.state.min_allowed_soc_ratio * 100.0,
            "battery_capacity_kWh": self.state.capacity,
            "max_abs_battery_power_kW": self.state.max_abs_battery_power_kW,
            "initial_energy_origin": self.state.initial_energy_origin,
            "initial_middle_price": self.initial_middle_price,
            "spread": self.spread,
            "fixed_order_size": self.fixed_order_size,
            "enable_inventory": self.enable_inventory,
            **self.bid_update.serialize(),
            **self.offer_update.serialize(),
        }

    def __init__(  # pylint: disable=too-many-arguments, too-many-locals
        self, initial_soc: float = StorageSettings.MIN_ALLOWED_SOC,
        min_allowed_soc=StorageSettings.MIN_ALLOWED_SOC,
        battery_capacity_kWh: float = StorageSettings.CAPACITY,
        max_abs_battery_power_kW: float = StorageSettings.MAX_ABS_POWER,
        initial_energy_origin: Enum = ESSEnergyOrigin.EXTERNAL,
        initial_middle_price: float =
        PassiveMarketMakerSettings.INITIAL_MIDDLE_PRICE,
        spread: float =
        PassiveMarketMakerSettings.SPREAD,
        fixed_order_size: float =
        PassiveMarketMakerSettings.FIXED_ORDER_SIZE,
        enable_inventory: bool =
        PassiveMarketMakerSettings.ENABLE_INVENTORY):

        self.fixed_order_size = fixed_order_size

        super().__init__()

        self.offer_update = MarketMakerStrategyOfferUpdater(
            initial_mid_price=initial_middle_price, spread=spread,
            enable_inventory=enable_inventory)
        self.bid_update = MarketMakerStrategyBidUpdater(
            initial_mid_price=initial_middle_price, spread=spread,
            enable_inventory=enable_inventory)
        self._state = StorageState(
            initial_soc=initial_soc, initial_energy_origin=initial_energy_origin,
            capacity=battery_capacity_kWh, max_abs_battery_power_kW=max_abs_battery_power_kW,
            min_allowed_soc=min_allowed_soc)

    @property
    def state(self) -> StorageState:
        return self._state

    def _area_reconfigure_prices(self, **kwargs):  # pylint: disable=too-many-branches
        if key_in_dict_and_not_none(kwargs, "initial_mid_price"):
            initial_mid_price = kwargs["initial_mid_price"]
        else:
            initial_mid_price = self.offer_update.initial_mid_price_input
        if key_in_dict_and_not_none(kwargs, "spread"):
            spread = kwargs["spread"]
        else:
            spread = self.offer_update.spread_input
        if key_in_dict_and_not_none(kwargs, "enable_inventory"):
            enable_inventory = kwargs["enable_inventory"]
        else:
            enable_inventory = self.bid_update.enable_inventory

        self.offer_update.set_parameters(
            initial_mid_price=initial_mid_price,
            spread=spread,
            enable_inventory=enable_inventory
        )
        self.bid_update.set_parameters(
            initial_mid_price=initial_mid_price,
            spread=spread,
            enable_inventory=enable_inventory
        )

    def area_reconfigure_event(self, *args, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        self._area_reconfigure_prices(**kwargs)

    def event_on_disabled_area(self):
        self.state.check_state(self.area.spot_market.time_slot)

    def event_activate_energy(self):
        """Set the battery energy for each slot when the ACTIVATE event is triggered."""
        self.state.activate(
            self.simulation_config.slot_length,
            self.area.current_market.time_slot
            if self.area.current_market else self.area.config.start_date)

    def event_activate(self, **kwargs):
        self.event_activate_energy()

    def event_tick(self):
        """Post bids or update existing bid prices on market tick.

        This method is triggered by the TICK event.
        """

        #market = self.area.spot_market
        self._buy_energy_two_sided_spot_market()
        self._sell_energy_to_spot_market()

        #self.state.check_state(market.time_slot)
        #self.offer_update.update(market, self)
        #self.bid_update.update(market, self)

    def event_offer_traded(self, *, market_id, trade):

        super().event_offer_traded(market_id=market_id, trade=trade)

        market = self.area.get_spot_or_future_market_by_id(market_id)
        if not market:
            return

        self.assert_if_trade_bid_price_is_too_high(market, trade)
        self._assert_if_trade_offer_price_is_too_low(market_id, trade)

    def _track_bought_energy_origin(self, seller):
        if seller == self.area.name:
            return ESSEnergyOrigin.EXTERNAL
        if self.area.children and seller in [child.name for child in self.area.children]:
            return ESSEnergyOrigin.LOCAL
        return ESSEnergyOrigin.UNKNOWN

    def event_bid_traded(self, *, market_id, bid_trade):
        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)

        if not self.area.is_market_spot_or_future(market_id):
            return

    def _cycle_state(self):
        current_market = self.area.spot_market
        past_market = self.area.last_past_market

        self.state.market_cycle(
            past_market.time_slot if past_market else None,
            current_market.time_slot,
            self.area.future_market_time_slots
        )

    def event_market_cycle(self):
        super().event_market_cycle()
        self.offer_update.reset(self)

        #self._cycle_state()

        self._sell_energy_to_spot_market()
        self._buy_energy_two_sided_spot_market()
        self._delete_past_state()

    def _sell_energy_to_spot_market(self):
        market = self.area.spot_market
        selling_rate = self.offer_update.get_updated_offer_rate(self.area)
        if self.are_offers_posted(market.id):
            self.offer_update.update(market, self)
            return

        offer = self.post_first_offer(
            self.area.spot_market, self.fixed_order_size, selling_rate
        )
        #self.state.register_energy_from_posted_offer(offer.energy, time_slot)

    def _buy_energy_two_sided_spot_market(self):
        market = self.area.spot_market
        time_slot = self.spot_market_time_slot
        if self.are_bids_posted(market.id):
            self.bid_update.update(market, self)
            return

        #self.bid_update.reset(self)

        energy_rate = self.bid_update.get_updated_bid_rate(self.area)
        try:
            first_bid = self.post_first_bid(market, self.fixed_order_size * 1000.0, energy_rate)
            #if first_bid is not None:
                #self.state.register_energy_from_posted_bid(first_bid.energy, time_slot)
        except MarketException:
            pass

    def _delete_past_state(self):
        if (constants.RETAIN_PAST_MARKET_STRATEGIES_STATE is True or
                self.area.current_market is None):
            return

        self.offer_update.reset(self)
        self.bid_update.reset(self)
        self.state.delete_past_state_values(self.area.current_market.time_slot)