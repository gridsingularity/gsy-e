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
from typing import Union, Optional

from gsy_framework.constants_limits import ConstSettings, FLOATING_POINT_TOLERANCE
from gsy_framework.data_classes import TraderDetails
from gsy_framework.exceptions import GSyException
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import key_in_dict_and_not_none
from gsy_framework.validators import StorageValidator
from pendulum import duration

from gsy_e import constants
from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.gsy_e_core.exceptions import MarketException
from gsy_e.gsy_e_core.util import is_one_sided_market_simulation, is_two_sided_market_simulation
from gsy_e.models.base import AssetType
from gsy_e.models.strategy.state import ESSEnergyOrigin, StorageState, StorageLosses
from gsy_e.models.strategy import BidEnabledStrategy
from gsy_e.models.strategy.future.strategy import future_market_strategy_factory
from gsy_e.models.strategy.update_frequency import (
    TemplateStrategyBidUpdater,
    TemplateStrategyOfferUpdater,
)
from gsy_e.models.strategy.strategy_profile import profile_factory, StrategyProfileBase

log = getLogger(__name__)

BalancingRatio = namedtuple("BalancingRatio", ("demand", "supply"))

StorageSettings = ConstSettings.StorageSettings
GeneralSettings = ConstSettings.GeneralSettings
BalancingSettings = ConstSettings.BalancingSettings


class StorageStrategy(BidEnabledStrategy):
    """Template strategy for storage assets."""

    def serialize(self):
        return {
            "initial_soc": self.state.initial_soc,
            "min_allowed_soc": self.state.min_allowed_soc_ratio * 100.0,
            "battery_capacity_kWh": self.state.capacity,
            "max_abs_battery_power_kW": self.state.max_abs_battery_power_kW,
            "cap_price_strategy": self.cap_price_strategy,
            "initial_energy_origin": self.state.initial_energy_origin.value,
            "balancing_energy_ratio": self.balancing_energy_ratio,
            **self.bid_update.serialize(),
            **self.offer_update.serialize(),
        }

    def __init__(  # pylint: disable=too-many-arguments, too-many-locals
        self,
        initial_soc: float = StorageSettings.MIN_ALLOWED_SOC,
        min_allowed_soc=StorageSettings.MIN_ALLOWED_SOC,
        battery_capacity_kWh: float = StorageSettings.CAPACITY,
        max_abs_battery_power_kW: float = StorageSettings.MAX_ABS_POWER,
        cap_price_strategy: bool = False,
        initial_selling_rate: Union[float, dict] = StorageSettings.SELLING_RATE_RANGE.initial,
        final_selling_rate: Union[float, dict] = StorageSettings.SELLING_RATE_RANGE.final,
        initial_buying_rate: Union[float, dict] = StorageSettings.BUYING_RATE_RANGE.initial,
        final_buying_rate: Union[float, dict] = StorageSettings.BUYING_RATE_RANGE.final,
        fit_to_limit=True,
        energy_rate_increase_per_update=None,
        energy_rate_decrease_per_update=None,
        update_interval=None,
        initial_energy_origin: Enum = ESSEnergyOrigin.EXTERNAL,
        losses: Optional[StorageLosses] = None,
        balancing_energy_ratio: tuple = (
            BalancingSettings.OFFER_DEMAND_RATIO,
            BalancingSettings.OFFER_SUPPLY_RATIO,
        ),
    ):

        if update_interval is None:
            update_interval = duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL
            )

        if min_allowed_soc is None:
            min_allowed_soc = StorageSettings.MIN_ALLOWED_SOC
        self.initial_soc = initial_soc

        StorageValidator.validate(
            initial_soc=initial_soc,
            min_allowed_soc=min_allowed_soc,
            battery_capacity_kWh=battery_capacity_kWh,
            max_abs_battery_power_kW=max_abs_battery_power_kW,
            fit_to_limit=fit_to_limit,
            energy_rate_increase_per_update=energy_rate_increase_per_update,
            energy_rate_decrease_per_update=energy_rate_decrease_per_update,
        )

        if isinstance(update_interval, int):
            update_interval = duration(minutes=update_interval)

        super().__init__()

        self.offer_update = TemplateStrategyOfferUpdater(
            initial_rate=initial_selling_rate,
            final_rate=final_selling_rate,
            fit_to_limit=fit_to_limit,
            energy_rate_change_per_update=energy_rate_decrease_per_update,
            update_interval=update_interval,
        )
        for time_slot in self.offer_update.initial_rate_profile_buffer.profile.keys():
            StorageValidator.validate(
                initial_selling_rate=self.offer_update.initial_rate_profile_buffer.get_value(
                    time_slot
                ),
                final_selling_rate=self.offer_update.final_rate_profile_buffer.get_value(
                    time_slot
                ),
            )
        self.bid_update = TemplateStrategyBidUpdater(
            initial_rate=initial_buying_rate,
            final_rate=final_buying_rate,
            fit_to_limit=fit_to_limit,
            energy_rate_change_per_update=energy_rate_increase_per_update,
            update_interval=update_interval,
            rate_limit_object=min,
        )
        for time_slot in self.bid_update.initial_rate_profile_buffer.profile.keys():
            StorageValidator.validate(
                initial_buying_rate=self.bid_update.initial_rate_profile_buffer.get_value(
                    time_slot
                ),
                final_buying_rate=self.bid_update.final_rate_profile_buffer.get_value(time_slot),
            )
        self._state = StorageState(
            initial_soc=initial_soc,
            initial_energy_origin=initial_energy_origin,
            capacity=battery_capacity_kWh,
            max_abs_battery_power_kW=max_abs_battery_power_kW,
            min_allowed_soc=min_allowed_soc,
            losses=losses,
        )
        self.cap_price_strategy = cap_price_strategy
        self.balancing_energy_ratio = BalancingRatio(*balancing_energy_ratio)

    def _create_future_market_strategy(self):
        return future_market_strategy_factory(self.asset_type)

    @property
    def state(self) -> StorageState:
        return self._state

    def _area_reconfigure_prices(self, **kwargs):  # pylint: disable=too-many-branches
        if key_in_dict_and_not_none(kwargs, "initial_selling_rate"):
            initial_selling_rate = profile_factory(
                profile_type=InputProfileTypes.IDENTITY,
                input_profile=kwargs["initial_selling_rate"],
            )
            initial_selling_rate.read_or_rotate_profiles()
        else:
            initial_selling_rate = self.offer_update.initial_rate_profile_buffer
        if key_in_dict_and_not_none(kwargs, "final_selling_rate"):
            final_selling_rate = profile_factory(
                profile_type=InputProfileTypes.IDENTITY, input_profile=kwargs["final_selling_rate"]
            )
            final_selling_rate.read_or_rotate_profiles()
        else:
            final_selling_rate = self.offer_update.final_rate_profile_buffer
        if key_in_dict_and_not_none(kwargs, "initial_buying_rate"):
            initial_buying_rate = profile_factory(
                profile_type=InputProfileTypes.IDENTITY,
                input_profile=kwargs["initial_buying_rate"],
            )
            initial_buying_rate.read_or_rotate_profiles()
        else:
            initial_buying_rate = self.bid_update.initial_rate_profile_buffer
        if key_in_dict_and_not_none(kwargs, "final_buying_rate"):
            final_buying_rate = profile_factory(
                profile_type=InputProfileTypes.IDENTITY, input_profile=kwargs["final_buying_rate"]
            )
            final_buying_rate.read_or_rotate_profiles()
        else:
            final_buying_rate = self.bid_update.final_rate_profile_buffer
        if key_in_dict_and_not_none(kwargs, "energy_rate_decrease_per_update"):
            energy_rate_decrease_per_update = profile_factory(
                profile_type=InputProfileTypes.IDENTITY,
                input_profile=kwargs["energy_rate_decrease_per_update"],
            )
            energy_rate_decrease_per_update.read_or_rotate_profiles()
        else:
            energy_rate_decrease_per_update = (
                self.offer_update.energy_rate_change_per_update_profile_buffer
            )
        if key_in_dict_and_not_none(kwargs, "energy_rate_increase_per_update"):
            energy_rate_increase_per_update = profile_factory(
                profile_type=InputProfileTypes.IDENTITY,
                input_profile=kwargs["energy_rate_increase_per_update"],
            )
            energy_rate_increase_per_update.read_or_rotate_profiles()
        else:
            energy_rate_increase_per_update = (
                self.bid_update.energy_rate_change_per_update_profile_buffer
            )
        if key_in_dict_and_not_none(kwargs, "fit_to_limit"):
            bid_fit_to_limit = kwargs["fit_to_limit"]
            offer_fit_to_limit = kwargs["fit_to_limit"]
        else:
            bid_fit_to_limit = self.bid_update.fit_to_limit
            offer_fit_to_limit = self.offer_update.fit_to_limit
        if key_in_dict_and_not_none(kwargs, "update_interval"):
            if isinstance(kwargs["update_interval"], int):
                update_interval = duration(minutes=kwargs["update_interval"])
            else:
                update_interval = kwargs["update_interval"]
        else:
            update_interval = self.bid_update.update_interval

        try:
            self._validate_rates(
                initial_selling_rate,
                final_selling_rate,
                initial_buying_rate,
                final_buying_rate,
                energy_rate_increase_per_update,
                energy_rate_decrease_per_update,
                bid_fit_to_limit,
                offer_fit_to_limit,
            )
        except GSyException as ex:
            log.exception("StorageStrategy._area_reconfigure_prices failed. Exception: %s.", ex)
            return

        self.offer_update.set_parameters(
            initial_rate=initial_selling_rate.profile,
            final_rate=final_selling_rate.profile,
            energy_rate_change_per_update=energy_rate_decrease_per_update.profile,
            fit_to_limit=offer_fit_to_limit,
            update_interval=update_interval,
        )
        self.offer_update.update_and_populate_price_settings(self.area)

        self.bid_update.set_parameters(
            initial_rate=initial_buying_rate.profile,
            final_rate=final_buying_rate.profile,
            energy_rate_change_per_update=energy_rate_increase_per_update.profile,
            fit_to_limit=bid_fit_to_limit,
            update_interval=update_interval,
        )
        self.bid_update.update_and_populate_price_settings(self.area)

    def area_reconfigure_event(self, *args, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        self._area_reconfigure_prices(**kwargs)
        self._update_profiles_with_default_values()

    def _validate_rates(  # pylint: disable=too-many-arguments
        self,
        initial_selling_rate: StrategyProfileBase,
        final_selling_rate: StrategyProfileBase,
        initial_buying_rate: StrategyProfileBase,
        final_buying_rate: StrategyProfileBase,
        energy_rate_increase_per_update,
        energy_rate_decrease_per_update,
        bid_fit_to_limit,
        offer_fit_to_limit,
    ):

        for time_slot in initial_selling_rate.profile.keys():
            if (
                self.area
                and self.area.current_market
                and time_slot < self.area.current_market.time_slot
            ):
                continue

            bid_rate_change = (
                None if bid_fit_to_limit else energy_rate_increase_per_update.get_value(time_slot)
            )
            offer_rate_change = (
                None
                if offer_fit_to_limit
                else energy_rate_decrease_per_update.get_value(time_slot)
            )
            StorageValidator.validate(
                initial_selling_rate=initial_selling_rate.get_value(time_slot),
                final_selling_rate=final_selling_rate.get_value(time_slot),
                initial_buying_rate=initial_buying_rate.get_value(time_slot),
                final_buying_rate=final_buying_rate.get_value(time_slot),
                energy_rate_increase_per_update=bid_rate_change,
                energy_rate_decrease_per_update=offer_rate_change,
            )

    def event_on_disabled_area(self):
        self.state.check_state(self.area.spot_market.time_slot)

    def event_activate_price(self):
        """Validate rates of offers and bids when the ACTIVATE event is triggered."""
        self._validate_rates(
            self.offer_update.initial_rate_profile_buffer,
            self.offer_update.final_rate_profile_buffer,
            self.bid_update.initial_rate_profile_buffer,
            self.bid_update.final_rate_profile_buffer,
            self.bid_update.energy_rate_change_per_update_profile_buffer,
            self.offer_update.energy_rate_change_per_update_profile_buffer,
            self.bid_update.fit_to_limit,
            self.offer_update.fit_to_limit,
        )

    def event_activate_energy(self):
        """Set the battery energy for each slot when the ACTIVATE event is triggered."""
        self.state.activate(
            self.simulation_config.slot_length,
            (
                self.area.current_market.time_slot
                if self.area.current_market
                else self.area.config.start_date
            ),
        )

    def event_activate(self, **kwargs):
        self._update_profiles_with_default_values()
        self.event_activate_energy()
        self.event_activate_price()

    def event_tick(self):
        """Post bids or update existing bid prices on market tick.

        This method is triggered by the TICK event.
        """

        market = self.area.spot_market
        self._buy_energy_two_sided_spot_market()

        self.state.check_state(market.time_slot)
        if self.cap_price_strategy is False:
            self.offer_update.update(market, self)

        self.bid_update.increment_update_counter_all_markets(self)
        self.offer_update.increment_update_counter_all_markets(self)

        self._buy_energy_one_sided_spot_market(market)

        self._future_market_strategy.event_tick(self)

    def event_offer_traded(self, *, market_id, trade):

        super().event_offer_traded(market_id=market_id, trade=trade)

        market = self.area.get_spot_or_future_market_by_id(market_id)
        if not market:
            return

        self.assert_if_trade_bid_price_is_too_high(market, trade)
        self._assert_if_trade_offer_price_is_too_low(market_id, trade)

        if trade.seller.name == self.owner.name:
            self.state.register_energy_from_offer_trade(trade.traded_energy, trade.time_slot)

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

        if bid_trade.buyer.name == self.owner.name:
            self.state.register_energy_from_bid_trade(
                bid_trade.traded_energy,
                bid_trade.time_slot,
                self._track_bought_energy_origin(bid_trade.seller.name),
            )

    def _cycle_state(self):
        current_market = self.area.spot_market
        past_market = self.area.last_past_market

        self.state.market_cycle(
            past_market.time_slot if past_market else None,
            current_market.time_slot,
            self.area.future_market_time_slots,
        )

    def event_market_cycle(self):
        super().event_market_cycle()
        self._update_profiles_with_default_values()
        self.offer_update.reset(self)

        self._cycle_state()

        self._sell_energy_to_spot_market()
        self._buy_energy_two_sided_spot_market()
        self._future_market_strategy.event_market_cycle(self)
        self._delete_past_state()

    def event_balancing_market_cycle(self):
        if not self._is_eligible_for_balancing_market:
            return

        current_market = self.area.spot_market
        free_storage = self.state.free_storage(current_market.time_slot)
        seller_details = TraderDetails(
            self.owner.name, self.owner.uuid, self.owner.name, self.owner.uuid
        )
        if free_storage > 0:
            charge_energy = self.balancing_energy_ratio.demand * free_storage
            charge_price = DeviceRegistry.REGISTRY[self.owner.name][0] * charge_energy
            if charge_energy != 0 and charge_price != 0:
                # committing to start charging when required
                self.area.get_balancing_market(self.area.now).balancing_offer(
                    charge_price, -charge_energy, seller_details
                )
        if self.state.used_storage > 0:
            discharge_energy = self.balancing_energy_ratio.supply * self.state.used_storage
            discharge_price = DeviceRegistry.REGISTRY[self.owner.name][1] * discharge_energy
            # committing to start discharging when required
            if discharge_energy != 0 and discharge_price != 0:
                self.area.get_balancing_market(self.area.now).balancing_offer(
                    discharge_price, discharge_energy, seller_details
                )

    def _try_to_buy_offer(self, offer, market, max_affordable_offer_rate):
        if offer.seller.name == self.owner.name:
            # Don't buy our own offer
            return None
        # Check if the price is cheap enough
        if offer.energy_rate > max_affordable_offer_rate:
            # Can early return here, because the offers are sorted according to energy rate
            # therefore the following offers will be more expensive
            return True

        try:
            max_energy = self.state.get_available_energy_to_buy_kWh(market.time_slot)
            max_energy = min(offer.energy, max_energy)
            if max_energy > FLOATING_POINT_TOLERANCE:
                self.state.register_energy_from_one_sided_market_accept_offer(
                    max_energy,
                    market.time_slot,
                    self._track_bought_energy_origin(offer.seller.name),
                )
                self.accept_offer(
                    market,
                    offer,
                    buyer=TraderDetails(
                        self.owner.name, self.owner.uuid, self.owner.name, self.owner.uuid
                    ),
                    energy=max_energy,
                )
            return None
        except MarketException:
            # Offer already gone etc., try next one.
            return None

    def _buy_energy_one_sided_spot_market(self, market, offer=None):
        if not market:
            return
        if not is_one_sided_market_simulation():
            return
        max_affordable_offer_rate = self.bid_update.get_updated_rate(market.time_slot)

        if offer:
            self._try_to_buy_offer(offer, market, max_affordable_offer_rate)
        else:
            for market_offer in market.sorted_offers:
                if (
                    self._try_to_buy_offer(market_offer, market, max_affordable_offer_rate)
                    is False
                ):
                    return

    def _sell_energy_to_spot_market(self):
        time_slot = self.area.spot_market.time_slot
        selling_rate = self.calculate_selling_rate(self.area.spot_market)
        energy_kWh = self.state.get_available_energy_to_sell_kWh(time_slot)
        if energy_kWh > FLOATING_POINT_TOLERANCE:
            offer = self.post_first_offer(self.area.spot_market, energy_kWh, selling_rate)
            self.state.register_energy_from_posted_offer(offer.energy, time_slot)

    def _buy_energy_two_sided_spot_market(self):
        if not is_two_sided_market_simulation():
            return
        market = self.area.spot_market
        time_slot = self.spot_market_time_slot
        if self.are_bids_posted(market.id):
            self.bid_update.update(market, self)
            return

        self.bid_update.reset(self)

        energy_kWh = self.state.get_available_energy_to_buy_kWh(time_slot)
        energy_rate = self.bid_update.initial_rate[time_slot]
        if energy_kWh > FLOATING_POINT_TOLERANCE:
            try:
                first_bid = self.post_first_bid(market, energy_kWh * 1000.0, energy_rate)
                if first_bid is not None:
                    self.state.register_energy_from_posted_bid(first_bid.energy, time_slot)
            except MarketException:
                pass

    def calculate_selling_rate(self, market):
        """Calculate the selling rate."""
        if self.cap_price_strategy is True:
            return self._capacity_dependant_sell_rate(market)

        return self.offer_update.initial_rate[market.time_slot]

    def _capacity_dependant_sell_rate(self, market):
        soc = self.state.get_soc_level(market.time_slot)
        max_selling_rate = self.offer_update.initial_rate[market.time_slot]
        min_selling_rate = self.offer_update.final_rate[market.time_slot]
        if max_selling_rate < min_selling_rate:
            return min_selling_rate

        return max_selling_rate - (max_selling_rate - min_selling_rate) * soc

    def _update_profiles_with_default_values(self):
        self.offer_update.update_and_populate_price_settings(self.area)
        self.bid_update.update_and_populate_price_settings(self.area)
        self.state.add_default_values_to_state_profiles(
            [self.spot_market_time_slot, *self.area.future_market_time_slots]
        )
        self._future_market_strategy.update_and_populate_price_settings(self)

    def event_offer(self, *, market_id, offer):
        super().event_offer(market_id=market_id, offer=offer)
        if is_one_sided_market_simulation() and not self.area.is_market_future(market_id):
            market = self.area.get_spot_or_future_market_by_id(market_id)
            if not market:
                return
            # sometimes the offer event arrives earlier than the market_cycle event,
            # so the default values have to be written here too:
            self._update_profiles_with_default_values()
            if (
                offer.id in market.offers
                and offer.seller.name != self.owner.name
                and offer.seller.name != self.area.name
            ):
                self._buy_energy_one_sided_spot_market(market, offer)

    def _delete_past_state(self):
        if (
            constants.RETAIN_PAST_MARKET_STRATEGIES_STATE is True
            or self.area.current_market is None
        ):
            return

        self.offer_update.delete_past_state_values(self.area.current_market.time_slot)
        self.bid_update.delete_past_state_values(self.area.current_market.time_slot)
        self.state.delete_past_state_values(self.area.current_market.time_slot)

        # Delete the state of the current slot from the future market cache
        self._future_market_strategy.delete_past_state_values(self.area.current_market.time_slot)

    @property
    def asset_type(self):
        return AssetType.PROSUMER
