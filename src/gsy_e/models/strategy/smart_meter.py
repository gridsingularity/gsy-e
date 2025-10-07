# pylint: disable=fixme
"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange
This program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not,
see <http://www.gnu.org/licenses/>.
"""
from logging import getLogger
from pathlib import Path
from typing import Dict, Union

from gsy_framework.constants_limits import ConstSettings, FLOATING_POINT_TOLERANCE
from gsy_framework.data_classes import Offer, TraderDetails
from gsy_framework.read_user_profile import InputProfileTypes, UserProfileReader
from gsy_framework.utils import get_from_profile_same_weekday_and_time, limit_float_precision
from gsy_framework.validators.smart_meter_validator import SmartMeterValidator
from numpy import random
from pendulum import duration

from gsy_e import constants
from gsy_e.gsy_e_core.exceptions import GSyException, MarketException
from gsy_e.gsy_e_core.util import is_one_sided_market_simulation, is_two_sided_market_simulation
from gsy_e.models.base import AssetType
from gsy_e.models.market import MarketBase
from gsy_e.models.strategy import BidEnabledStrategy
from gsy_e.models.strategy.energy_parameters.smart_meter import SmartMeterEnergyParameters
from gsy_e.models.strategy.mixins import UseMarketMakerMixin
from gsy_e.models.strategy.state import SmartMeterState
from gsy_e.models.strategy.update_frequency import (
    TemplateStrategyBidUpdater,
    TemplateStrategyOfferUpdater,
)

log = getLogger(__name__)


class SmartMeterStrategy(BidEnabledStrategy, UseMarketMakerMixin):
    """Class defining a strategy for Smart Meter devices."""

    def serialize(self):
        return {
            # Energy parameters
            **self._energy_params.serialize(),
            # Price production parameters
            **self.offer_update.serialize(),
            # Price consumption parameters
            **self.bid_update.serialize(),
            "use_market_maker_rate": self.use_market_maker_rate,
        }

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        smart_meter_profile: Union[Path, str, Dict[int, float], Dict[str, float]] = None,
        initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
        final_selling_rate: float = ConstSettings.SmartMeterSettings.SELLING_RATE_RANGE.final,
        energy_rate_decrease_per_update: Union[float, None] = None,
        initial_buying_rate: float = (ConstSettings.SmartMeterSettings.BUYING_RATE_RANGE.initial),
        final_buying_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
        energy_rate_increase_per_update: Union[float, None] = None,
        fit_to_limit: bool = True,
        update_interval=None,
        use_market_maker_rate: bool = False,
        smart_meter_profile_uuid: str = None,
        smart_meter_measurement_uuid: str = None,
    ):
        """
        Args:
            smart_meter_profile: input profile defining the energy production/consumption of the
                Smart Meter. It can be either a CSV file path, a dict with hourly data
                (Dict[int, float]) or a dict with arbitrary time data (Dict[str, float]).
            initial_selling_rate: Starting point for offers.
            final_selling_rate: Ending point for offers.
            energy_rate_decrease_per_update: Slope of the offers' change per update.
            initial_buying_rate: Starting point for bids.
            final_buying_rate: Ending point for bids.
            energy_rate_increase_per_update: Slope of the bids' change per update.
            fit_to_limit: If `True`, derive the bid/offer behavior from a linear fitted curve.
                - For offers: `energy_rate_decrease_per_update` is ignored and the rate will
                    decrease at each update_interval, starting at `initial_selling_rate` and ending
                    at `final_selling_rate`.
                - For bids: `energy_rate_increase_per_update` is ignored and the rate will
                    increase at each update_interval, starting at `initial_buying_rate` and ending
                    at `final_buying_rate`.
            update_interval: Interval in minutes after which the Smart Meter will update its offers
                and bids.
            use_market_maker_rate: If set to True, the Smart Meter will track its final buying and
                selling rate as per utility's trading rate.
        """
        super().__init__()

        self._energy_params = SmartMeterEnergyParameters(
            smart_meter_profile, smart_meter_profile_uuid, smart_meter_measurement_uuid
        )

        # needed for profile_handler
        self.smart_meter_profile_uuid = smart_meter_profile_uuid
        self.smart_meter_measurement_uuid = smart_meter_measurement_uuid

        self.use_market_maker_rate = use_market_maker_rate
        update_interval = self._convert_update_interval_to_duration(update_interval)

        self.validator = SmartMeterValidator
        self.validator.validate(
            fit_to_limit=fit_to_limit,
            energy_rate_increase_per_update=energy_rate_increase_per_update,
            energy_rate_decrease_per_update=energy_rate_decrease_per_update,
        )

        # Instances to update the Smart Meter's bids and offers across all market slots
        self.bid_update = TemplateStrategyBidUpdater(
            initial_rate=initial_buying_rate,
            final_rate=final_buying_rate,
            fit_to_limit=fit_to_limit,
            energy_rate_change_per_update=energy_rate_increase_per_update,
            update_interval=update_interval,
            rate_limit_object=min,
        )

        self.offer_update = TemplateStrategyOfferUpdater(
            initial_rate=initial_selling_rate,
            final_rate=final_selling_rate,
            fit_to_limit=fit_to_limit,
            energy_rate_change_per_update=energy_rate_decrease_per_update,
            update_interval=update_interval,
            rate_limit_object=max,
        )
        self._reader = UserProfileReader()

    @property
    def state(self) -> SmartMeterState:
        return self._energy_params._state  # pylint: disable=protected-access

    def event_activate(self, **kwargs):
        """Activate the device."""
        self.event_activate_price()
        self.event_activate_energy()
        self.bid_update.update_and_populate_price_settings(self.area)
        self.offer_update.update_and_populate_price_settings(self.area)

    def event_activate_price(self):
        """Configure all the rates for the device (both consumption and production)."""
        # If we want to use the Market Maker rate, we must overwrite the existing rates with it.
        self._replace_rates_with_market_maker_rates()

        self._validate_consumption_rates(
            initial_rate=self.bid_update.initial_rate_profile_buffer,
            final_rate=self.bid_update.final_rate_profile_buffer,
            energy_rate_change_per_update=(
                self.bid_update.energy_rate_change_per_update_profile_buffer
            ),
            fit_to_limit=self.bid_update.fit_to_limit,
        )

        self._validate_production_rates(
            initial_rate=self.offer_update.initial_rate_profile_buffer,
            final_rate=self.offer_update.final_rate_profile_buffer,
            energy_rate_change_per_update=(
                self.offer_update.energy_rate_change_per_update_profile_buffer
            ),
            fit_to_limit=self.offer_update.fit_to_limit,
        )

    def event_activate_energy(self):
        """Read the power profile and update the energy requirements for future market slots.

        This method is triggered by the ACTIVATE event.
        """
        self._energy_params.activate(self.owner)
        time_slots = [m.time_slot for m in self.area.all_markets]
        self._energy_params.set_energy_forecast_for_future_markets(time_slots, reconfigure=True)

    def event_market_cycle(self):
        """Prepare rates and execute bids/offers when a new market slot begins.

        This method is triggered by the MARKET_CYCLE event.
        """
        super().event_market_cycle()
        self._energy_params.read_and_rotate_profiles()
        self._reset_rates_and_update_prices()
        time_slots = [m.time_slot for m in self.area.all_markets]
        self._energy_params.set_energy_forecast_for_future_markets(time_slots, reconfigure=False)
        self._set_energy_measurement_of_last_market()
        # Create bids/offers for the expected energy consumption/production in future markets
        for market in self.area.all_markets:
            self._post_offer(market)
            # Only make bids in two-sided markets
            if ConstSettings.MASettings.MARKET_TYPE != 1:
                self._post_first_bid(market)

        self._delete_past_state()

    def _set_energy_measurement_of_last_market(self):
        """Set the (simulated) actual energy of the device in the previous market slot."""
        if self.area.current_market:
            self._energy_params.set_energy_measurement_kWh(self.area.current_market.time_slot)

    def event_offer(self, *, market_id, offer):
        """Automatically react to offers (trying to buy energy) in one-sided markets.

        This method is triggered by the OFFER event.
        """
        # In two-sided markets, the device doesn't automatically react to offers (it actively bids)
        if ConstSettings.MASettings.MARKET_TYPE != 1:
            return

        market = self.area.get_spot_or_future_market_by_id(market_id)
        if self._offer_comes_from_different_seller(offer):
            self._one_sided_market_event_tick(market, offer)

    def event_tick(self):
        """Buy or offer energy on market tick. This method is triggered by the TICK event."""

        # TODO: the following methods will cycle many times on all markets and should be refactored
        self._event_tick_consumption()
        self._event_tick_production()

    def event_offer_traded(self, *, market_id, trade):
        """Validate the trade for both offers and bids. Extends the superclass method.

        This method is triggered by the MarketEvent.OFFER_TRADED event.
        """
        market = self.area.get_spot_or_future_market_by_id(market_id)
        if not market:
            return

        if self.owner.name not in (trade.seller.name, trade.buyer.name):
            return  # Only react to trades in which the device took part

        super().event_offer_traded(market_id=market_id, trade=trade)

        is_buyer = self.owner.name == trade.buyer.name
        if is_buyer:
            self.assert_if_trade_bid_price_is_too_high(market, trade)
            if ConstSettings.BalancingSettings.FLEXIBLE_LOADS_SUPPORT:
                # TODO: balancing market support not yet implemented
                # Load can put supply_balancing_offers only when there is a trade in spot_market
                # self._supply_balancing_offer(market, trade)
                pass
        else:
            self._assert_if_trade_offer_price_is_too_low(market_id, trade)
            self.state.decrement_available_energy(
                trade.traded_energy, market.time_slot, self.owner.name
            )

    def event_bid_traded(self, *, market_id, bid_trade):
        """Register the bid traded by the device. Extends the superclass method.

        This method is triggered by the MarketEvent.BID_TRADED event.
        """
        if self.owner.name != bid_trade.buyer.name:
            return

        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)

        market = self.area.get_spot_or_future_market_by_id(market_id)
        self._energy_params.decrement_energy_requirement(
            energy_kWh=bid_trade.traded_energy,
            time_slot=market.time_slot,
            area_name=self.owner.name,
        )

    def area_reconfigure_event(self, *args, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments.

        If custom profiles are provided in the `kwargs`, use them to replace the default ones
        provided by the TemplateStrategyUpdaterBase.
        """
        self._area_reconfigure_consumption_prices(**kwargs)
        self._area_reconfigure_production_prices(**kwargs)
        self.offer_update.update_and_populate_price_settings(self.area)
        self.bid_update.update_and_populate_price_settings(self.area)

        # Update the raw profile. It will be read later while setting the energy forecast.
        time_slots = [m.time_slot for m in self.area.all_markets]
        self._energy_params.reset(time_slots=time_slots, **kwargs)

    def _area_reconfigure_production_prices(self, **kwargs):
        initial_rate = (
            self._reader.read_arbitrary_profile(
                InputProfileTypes.IDENTITY, kwargs["initial_selling_rate"]
            )
            if kwargs.get("initial_selling_rate") is not None
            else self.offer_update.initial_rate_profile_buffer
        )

        final_rate = (
            self._reader.read_arbitrary_profile(
                InputProfileTypes.IDENTITY, kwargs["final_selling_rate"]
            )
            if kwargs.get("final_selling_rate") is not None
            else self.offer_update.final_rate_profile_buffer
        )

        energy_rate_change_per_update = (
            self._reader.read_arbitrary_profile(
                InputProfileTypes.IDENTITY, kwargs["energy_rate_decrease_per_update"]
            )
            if kwargs.get("energy_rate_decrease_per_update") is not None
            else self.offer_update.energy_rate_change_per_update_profile_buffer
        )

        fit_to_limit = (
            kwargs["fit_to_limit"]
            if kwargs.get("fit_to_limit") is not None
            else self.offer_update.fit_to_limit
        )

        if kwargs.get("update_interval") is not None:
            if isinstance(kwargs["update_interval"], int):
                update_interval = duration(minutes=kwargs["update_interval"])
            else:
                update_interval = kwargs["update_interval"]
        else:
            update_interval = self.offer_update.update_interval

        if kwargs.get("use_market_maker_rate") is not None:
            self.use_market_maker_rate = kwargs["use_market_maker_rate"]

        try:
            self._validate_production_rates(
                initial_rate, final_rate, energy_rate_change_per_update, fit_to_limit
            )
        except GSyException as ex:
            log.exception("SmartMeterStrategy._area_reconfigure_production_prices failed: %s", ex)
            return

        self.offer_update.set_parameters(
            initial_rate=initial_rate,
            final_rate=final_rate,
            energy_rate_change_per_update=energy_rate_change_per_update,
            fit_to_limit=fit_to_limit,
            update_interval=update_interval,
        )

    def _area_reconfigure_consumption_prices(self, **kwargs):
        initial_rate = (
            self._reader.read_arbitrary_profile(
                InputProfileTypes.IDENTITY, kwargs["initial_buying_rate"]
            )
            if kwargs.get("initial_buying_rate") is not None
            else self.bid_update.initial_rate_profile_buffer
        )

        final_rate = (
            self._reader.read_arbitrary_profile(
                InputProfileTypes.IDENTITY, kwargs["final_buying_rate"]
            )
            if kwargs.get("final_buying_rate") is not None
            else self.bid_update.final_rate_profile_buffer
        )

        energy_rate_change_per_update = (
            self._reader.read_arbitrary_profile(
                InputProfileTypes.IDENTITY, kwargs["energy_rate_increase_per_update"]
            )
            if kwargs.get("energy_rate_increase_per_update") is not None
            else self.bid_update.energy_rate_change_per_update_profile_buffer
        )

        fit_to_limit = (
            kwargs["fit_to_limit"]
            if kwargs.get("fit_to_limit") is not None
            else self.bid_update.fit_to_limit
        )

        if kwargs.get("update_interval") is not None:
            if isinstance(kwargs["update_interval"], int):
                update_interval = duration(minutes=kwargs["update_interval"])
            else:
                update_interval = kwargs["update_interval"]
        else:
            update_interval = self.bid_update.update_interval

        if kwargs.get("use_market_maker_rate") is not None:
            self.use_market_maker_rate = kwargs["use_market_maker_rate"]

        try:
            self._validate_consumption_rates(
                initial_rate, final_rate, energy_rate_change_per_update, fit_to_limit
            )
        except GSyException as ex:
            log.exception(ex)
            return

        self.bid_update.set_parameters(
            initial_rate=initial_rate,
            final_rate=final_rate,
            energy_rate_change_per_update=energy_rate_change_per_update,
            fit_to_limit=fit_to_limit,
            update_interval=update_interval,
        )

    def _reset_rates_and_update_prices(self):
        """Set the initial/final rates and update the price of all bids/offers consequently."""
        self.bid_update.update_and_populate_price_settings(self.area)
        self.bid_update.reset(self)
        self.offer_update.update_and_populate_price_settings(self.area)
        self.offer_update.reset(self)

    def _post_offer(self, market):
        offer_energy_kWh = self.state.get_available_energy_kWh(market.time_slot)
        # We need to subtract the energy from the offers that are already posted in this
        # market slot in order to validate that more offers need to be posted.
        offer_energy_kWh -= self.offers.open_offer_energy(market.id)
        if offer_energy_kWh > 0:
            offer_price = self.offer_update.initial_rate[market.time_slot] * offer_energy_kWh
            try:
                offer = market.offer(
                    offer_price,
                    offer_energy_kWh,
                    TraderDetails(
                        self.owner.name, self.owner.uuid, self.owner.name, self.owner.uuid
                    ),
                    original_price=offer_price,
                )
                self.offers.post(offer, market.id)
            except MarketException:
                pass

    def _post_first_bid(self, market):
        if not self.state.can_buy_more_energy(market.time_slot):
            return

        bid_energy = self.state.get_energy_requirement_Wh(market.time_slot)
        # TODO: balancing market support not yet implemented
        # if self._is_eligible_for_balancing_market:
        #     bid_energy -= self.state.get_desired_energy_Wh(market.time_slot) * \
        #                   self.balancing_energy_ratio.demand
        try:
            if not self.are_bids_posted(market.id):
                self.post_first_bid(
                    market, bid_energy, self.bid_update.initial_rate[market.time_slot]
                )
        except MarketException:
            pass

    @staticmethod
    def _convert_update_interval_to_duration(update_interval):
        if update_interval is None:
            return duration(minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)

        if isinstance(update_interval, int):
            return duration(minutes=update_interval)

        return None

    def _delete_past_state(self):
        if (
            constants.RETAIN_PAST_MARKET_STRATEGIES_STATE is True
            or self.area.current_market is None
        ):
            return

        # Delete past energy requirements and availability
        self.state.delete_past_state_values(self.area.current_market.time_slot)
        # Delete bid rates for previous market slots
        self.bid_update.delete_past_state_values(self.area.current_market.time_slot)
        # Delete offer rates for previous market slots
        self.offer_update.delete_past_state_values(self.area.current_market.time_slot)
        # Delete the state of the current slot from the future market cache
        self._future_market_strategy.delete_past_state_values(self.area.current_market.time_slot)

    def _validate_consumption_rates(
        self, initial_rate, final_rate, energy_rate_change_per_update, fit_to_limit
    ):
        for time_slot in initial_rate.keys():
            rate_change = (
                None
                if fit_to_limit
                else get_from_profile_same_weekday_and_time(
                    energy_rate_change_per_update, time_slot
                )
            )

            self.validator.validate_rate(
                initial_buying_rate=initial_rate[time_slot],
                energy_rate_increase_per_update=rate_change,
                final_buying_rate=get_from_profile_same_weekday_and_time(final_rate, time_slot),
                fit_to_limit=fit_to_limit,
            )

    def _validate_production_rates(
        self, initial_rate, final_rate, energy_rate_change_per_update, fit_to_limit
    ):
        for time_slot in initial_rate.keys():
            rate_change = (
                None
                if fit_to_limit
                else get_from_profile_same_weekday_and_time(
                    energy_rate_change_per_update, time_slot
                )
            )

            self.validator.validate_rate(
                initial_selling_rate=initial_rate[time_slot],
                final_selling_rate=get_from_profile_same_weekday_and_time(final_rate, time_slot),
                energy_rate_decrease_per_update=rate_change,
                fit_to_limit=fit_to_limit,
            )

    def _offer_rate_can_be_accepted(self, offer: Offer, market_slot: MarketBase):
        """Check if the offer rate is less than what the device wants to pay."""
        max_affordable_offer_rate = self.bid_update.get_updated_rate(market_slot.time_slot)
        return (
            limit_float_precision(offer.energy_rate)
            <= max_affordable_offer_rate + FLOATING_POINT_TOLERANCE
        )

    def _event_tick_consumption(self):
        for market in self.area.all_markets:
            # One-sided market (only offers are posted)
            if is_one_sided_market_simulation():
                self._one_sided_market_event_tick(market)
            # Two-sided markets (both offers and bids are posted)
            elif is_two_sided_market_simulation():
                # Update the price of existing bids to reflect the new rates
                self.bid_update.update(market, self)

        # Bid prices have been updated, so we increase the counter of the bid updates
        self.bid_update.increment_update_counter_all_markets(self)

    def _event_tick_production(self):
        for market in self.area.all_markets:
            self.offer_update.update(market, self)
        self.offer_update.increment_update_counter_all_markets(self)

    def _one_sided_market_event_tick(self, market, offer=None):
        """
        Define the behavior of the device on TICK events in one-sided markets (react to offers).
        """
        if not self.state.can_buy_more_energy(market.time_slot):
            return
        if not offer and not market.offers:
            return
        if offer and offer.id not in market.offers:
            return

        try:
            acceptable_offer = offer if offer else self._find_acceptable_offer(market)
            time_slot = market.time_slot
            if acceptable_offer and self._offer_rate_can_be_accepted(acceptable_offer, market):
                # If the device can still buy more energy
                energy_Wh = self.state.calculate_energy_to_accept(
                    acceptable_offer.energy * 1000.0, time_slot
                )
                self.accept_offer(
                    market,
                    acceptable_offer,
                    buyer=TraderDetails(
                        self.owner.name, self.owner.uuid, self.owner.name, self.owner.uuid
                    ),
                    energy=energy_Wh / 1000.0,
                )

                self._energy_params.decrement_energy_requirement(
                    energy_kWh=energy_Wh / 1000, time_slot=time_slot, area_name=self.owner.name
                )

        except MarketException:
            self.log.exception("An Error occurred while buying an offer.")

    @staticmethod
    def _find_acceptable_offer(market):
        offers = market.most_affordable_offers
        return random.choice(offers)

    def event_balancing_market_cycle(self):
        # TODO: implement
        pass

    def _offer_comes_from_different_seller(self, offer):
        return offer.seller.name not in [self.owner.name, self.area.name]

    @property
    def asset_type(self):
        return AssetType.PRODUCER
