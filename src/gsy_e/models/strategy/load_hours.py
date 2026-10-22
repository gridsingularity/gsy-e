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
from typing import Union, Dict

from gsy_framework.constants_limits import ConstSettings, FLOATING_POINT_TOLERANCE
from gsy_framework.data_classes import Offer, TraderDetails
from gsy_framework.exceptions import GSyDeviceException
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import (
    limit_float_precision,
    is_time_slot_in_simulation_duration,
)
from gsy_framework.validators.load_validator import LoadValidator
from numpy import random
from pendulum import duration

from gsy_e import constants
from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.gsy_e_core.exceptions import MarketException
from gsy_e.gsy_e_core.util import is_two_sided_market_simulation, is_one_sided_market_simulation
from gsy_e.models.base import AssetType
from gsy_e.models.market import MarketBase
from gsy_e.models.strategy import BidEnabledStrategy
from gsy_e.models.strategy.energy_parameters.load import LoadHoursEnergyParameters
from gsy_e.models.strategy.future.strategy import future_market_strategy_factory
from gsy_e.models.strategy.mixins import UseMarketMakerMixin
from gsy_e.models.strategy.settlement.strategy import settlement_market_strategy_factory
from gsy_e.models.strategy.state import LoadState
from gsy_e.models.strategy.update_frequency import TemplateStrategyBidUpdater
from gsy_e.models.strategy.strategy_profile import profile_factory, StrategyProfileBase

BalancingRatio = namedtuple("BalancingRatio", ("demand", "supply"))


# pylint: disable=too-many-instance-attributes
class LoadHoursStrategy(BidEnabledStrategy, UseMarketMakerMixin):
    """Strategy for the load assets that can consume energy in predefined hrs of day."""

    def serialize(self):
        return {
            **self._energy_params.serialize(),
            **self.bid_update.serialize(),
            "balancing_energy_ratio": self.balancing_energy_ratio,
            "use_market_maker_rate": self.use_market_maker_rate,
        }

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        avg_power_W,
        hrs_of_day=None,
        fit_to_limit=True,
        energy_rate_increase_per_update=None,
        update_interval=None,
        initial_buying_rate: Union[
            float, Dict, str
        ] = ConstSettings.LoadSettings.BUYING_RATE_RANGE.initial,
        final_buying_rate: Union[
            float, Dict, str
        ] = ConstSettings.LoadSettings.BUYING_RATE_RANGE.final,
        balancing_energy_ratio: tuple = (
            ConstSettings.BalancingSettings.OFFER_DEMAND_RATIO,
            ConstSettings.BalancingSettings.OFFER_SUPPLY_RATIO,
        ),
        use_market_maker_rate: bool = False,
    ):
        """
        Constructor of LoadHoursStrategy
        :param avg_power_W: Power rating of load device
        :param hrs_of_day: hours of day energy is needed
        :param fit_to_limit: if set to True, it will make a linear curve
        following following initial_buying_rate & final_buying_rate
        :param energy_rate_increase_per_update: Slope of Load bids change per update
        :param update_interval: Interval after which Load will update its offer
        :param initial_buying_rate: Starting point of load's preferred buying rate
        :param final_buying_rate: Ending point of load's preferred buying rate
        :param use_market_maker_rate: If set to True, Load would track its final buying rate
        as per utility's trading rate
        """
        super().__init__()
        self._energy_params = LoadHoursEnergyParameters(avg_power_W, hrs_of_day)

        self.balancing_energy_ratio = BalancingRatio(*balancing_energy_ratio)
        self.use_market_maker_rate = use_market_maker_rate
        self._init_price_update(
            fit_to_limit,
            energy_rate_increase_per_update,
            update_interval,
            initial_buying_rate,
            final_buying_rate,
        )

        self._calculate_active_markets()
        self._cycled_market = set()
        self._simulation_start_timestamp = None

    @property
    def state(self) -> LoadState:
        return self._energy_params.state

    @classmethod
    def _create_settlement_market_strategy(cls):
        return settlement_market_strategy_factory()

    def _create_future_market_strategy(self):
        return future_market_strategy_factory(self.asset_type)

    def _init_price_update(
        self,
        fit_to_limit,
        energy_rate_increase_per_update,
        update_interval,
        initial_buying_rate,
        final_buying_rate,
    ):

        LoadValidator.validate_rate(
            fit_to_limit=fit_to_limit,
            energy_rate_increase_per_update=energy_rate_increase_per_update,
        )

        if update_interval is None:
            update_interval = duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL
            )

        if isinstance(update_interval, int):
            update_interval = duration(minutes=update_interval)

        BidEnabledStrategy.__init__(self)
        self.bid_update = TemplateStrategyBidUpdater(
            initial_rate=initial_buying_rate,
            final_rate=final_buying_rate,
            fit_to_limit=fit_to_limit,
            energy_rate_change_per_update=energy_rate_increase_per_update,
            update_interval=update_interval,
            rate_limit_object=min,
        )

    def _validate_rates(
        self,
        initial_rate: StrategyProfileBase,
        final_rate: StrategyProfileBase,
        energy_rate_change_per_update: StrategyProfileBase,
        fit_to_limit: bool,
    ):
        # all parameters have pvto be validated for each time slot starting from the current time
        for time_slot in initial_rate.profile.keys():
            if not is_time_slot_in_simulation_duration(time_slot, self.area.config):
                continue

            if (
                self.area
                and self.area.current_market
                and time_slot < self.area.current_market.time_slot
            ):
                continue
            rate_change = (
                None if fit_to_limit else energy_rate_change_per_update.get_value(time_slot)
            )
            LoadValidator.validate_rate(
                initial_buying_rate=initial_rate.get_value(time_slot),
                energy_rate_increase_per_update=rate_change,
                final_buying_rate=final_rate.get_value(time_slot),
                fit_to_limit=fit_to_limit,
            )

    def event_activate(self, **kwargs):
        self._energy_params.event_activate_energy(self.area)
        self._calculate_active_markets()
        self.event_activate_price()
        self.bid_update.update_and_populate_price_settings(self.area)
        self._future_market_strategy.update_and_populate_price_settings(self)

    def _cycle_energy_parameters(self):
        self._calculate_active_markets()
        self._update_energy_requirement_in_state()
        # Provide energy values for the past market slot, to be used in the settlement market
        self._set_energy_measurement_of_last_market()
        self.update_state()

    def event_market_cycle(self):
        super().event_market_cycle()
        self._cycle_energy_parameters()
        self.bid_update.update_and_populate_price_settings(self.area)
        if is_one_sided_market_simulation():
            self.bid_update.reset(self)
        self._post_first_bid()
        self._settlement_market_strategy.event_market_cycle(self)
        self._future_market_strategy.event_market_cycle(self)

    def update_state(self):
        """Update the state of the strategy."""
        if self.area.current_market:
            self._cycled_market = {self.area.current_market.time_slot}

        self._delete_past_state()

    def _set_energy_measurement_of_last_market(self):
        """Set the (simulated) actual energy of the device in the previous market slot."""
        if self.area.current_market:
            self._energy_params.set_energy_measurement_kWh(self.area.current_market.time_slot)

    def _delete_past_state(self):
        if (
            constants.RETAIN_PAST_MARKET_STRATEGIES_STATE is True
            or self.area.current_market is None
        ):
            return

        self.state.delete_past_state_values(self.area.current_market.time_slot)
        self.bid_update.delete_past_state_values(self.area.current_market.time_slot)
        self._future_market_strategy.delete_past_state_values(self.area.current_market.time_slot)

    def _area_reconfigure_prices(self, **kwargs):
        if kwargs.get("initial_buying_rate") is not None:
            initial_rate = profile_factory(
                profile_type=InputProfileTypes.IDENTITY,
                input_profile=kwargs["initial_buying_rate"],
            )
            initial_rate.read_or_rotate_profiles()
        else:
            initial_rate = self.bid_update.initial_rate_profile_buffer
        if kwargs.get("final_buying_rate") is not None:
            final_rate = profile_factory(
                profile_type=InputProfileTypes.IDENTITY, input_profile=kwargs["final_buying_rate"]
            )
            final_rate.read_or_rotate_profiles()
        else:
            final_rate = self.bid_update.final_rate_profile_buffer
        if kwargs.get("energy_rate_increase_per_update") is not None:
            energy_rate_change_per_update = profile_factory(
                profile_type=InputProfileTypes.IDENTITY,
                input_profile=kwargs["energy_rate_increase_per_update"],
            )
            energy_rate_change_per_update.read_or_rotate_profiles()
        else:
            energy_rate_change_per_update = (
                self.bid_update.energy_rate_change_per_update_profile_buffer
            )
        if kwargs.get("fit_to_limit") is not None:
            fit_to_limit = kwargs["fit_to_limit"]
        else:
            fit_to_limit = self.bid_update.fit_to_limit
        if kwargs.get("update_interval") is not None:
            update_interval = (
                duration(minutes=kwargs["update_interval"])
                if isinstance(kwargs["update_interval"], int)
                else kwargs["update_interval"]
            )
        else:
            update_interval = self.bid_update.update_interval

        if kwargs.get("use_market_maker_rate") is not None:
            self.use_market_maker_rate = kwargs["use_market_maker_rate"]

        try:
            self._validate_rates(
                initial_rate, final_rate, energy_rate_change_per_update, fit_to_limit
            )
        except GSyDeviceException:
            self.log.exception("LoadHours._area_reconfigure_prices failed. Exception: ")
            return

        self.bid_update.set_parameters(
            initial_rate=initial_rate.profile,
            final_rate=final_rate.profile,
            energy_rate_change_per_update=energy_rate_change_per_update.profile,
            fit_to_limit=fit_to_limit,
            update_interval=update_interval,
        )
        self.bid_update.update_and_populate_price_settings(self.area)

    def area_reconfigure_event(self, *args, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        self._energy_params.reset(self.area.spot_market.time_slot, **kwargs)
        self._update_energy_requirement_in_state()
        self._area_reconfigure_prices(**kwargs)

    def event_activate_price(self):
        """Update the strategy prices upon the activation and validate them afterwards."""
        self._replace_rates_with_market_maker_rates()

        self._validate_rates(
            self.bid_update.initial_rate_profile_buffer,
            self.bid_update.final_rate_profile_buffer,
            self.bid_update.energy_rate_change_per_update_profile_buffer,
            self.bid_update.fit_to_limit,
        )

    @staticmethod
    def _find_acceptable_offer(market):
        offers = market.most_affordable_offers
        return random.choice(offers)

    def _offer_rate_can_be_accepted(self, offer: Offer, market_slot: MarketBase):
        """Check if the offer rate is less than what the device wants to pay."""
        max_affordable_offer_rate = self.bid_update.get_updated_rate(market_slot.time_slot)
        return (
            limit_float_precision(offer.energy_rate)
            <= max_affordable_offer_rate + FLOATING_POINT_TOLERANCE
        )

    def _one_sided_market_event_tick(self, market, offer=None):
        if not self.state.can_buy_more_energy(market.time_slot):
            return

        try:
            if offer is None:
                if not market.offers:
                    return
                acceptable_offer = self._find_acceptable_offer(market)
            else:
                if offer.id not in market.offers:
                    return
                acceptable_offer = offer

            time_slot = market.time_slot
            if (
                acceptable_offer
                and self._energy_params.allowed_operating_hours(time_slot)
                and self._offer_rate_can_be_accepted(acceptable_offer, market)
            ):
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
            self.log.exception("An Error occurred while buying an offer")

    def _two_sided_market_event_tick(self, market):
        self.bid_update.update(market, self)

    def event_tick(self):
        """Post bids on market tick. This method is triggered by the TICK event."""
        for market in self.active_markets:
            if is_one_sided_market_simulation():
                self._one_sided_market_event_tick(market)
            elif is_two_sided_market_simulation():
                self._two_sided_market_event_tick(market)

        self.bid_update.increment_update_counter_all_markets(self)
        self._settlement_market_strategy.event_tick(self)
        self._future_market_strategy.event_tick(self)

    def event_offer(self, *, market_id, offer):
        """Automatically react to offers in single-sided markets.

        This method is triggered by the OFFER event.
        """
        super().event_offer(market_id=market_id, offer=offer)
        # In two-sided markets, the device doesn't automatically react to offers (it actively bids)
        if ConstSettings.MASettings.MARKET_TYPE != 1:
            return

        market = self.area.get_spot_or_future_market_by_id(market_id)
        if not market:
            return
        if market.time_slot not in self._cycled_market:
            # Blocking _one_sided_market_event_tick before self.event_market_cycle was called
            return

        if self._can_buy_in_market(market) and self._offer_comes_from_different_seller(offer):
            self._one_sided_market_event_tick(market, offer)

    def _can_buy_in_market(self, market):
        return self._is_market_active(market) and self.state.can_buy_more_energy(market.time_slot)

    def _offer_comes_from_different_seller(self, offer):
        return offer.seller.name not in [self.owner.name, self.area.name]

    def _post_first_bid(self):
        if is_one_sided_market_simulation():
            return
        for market in self.active_markets:
            if (
                self.state.can_buy_more_energy(market.time_slot)
                and self._energy_params.allowed_operating_hours(market.time_slot)
                and not self.are_bids_posted(market.id)
            ):
                bid_energy = self.state.get_energy_requirement_Wh(market.time_slot)
                if self._is_eligible_for_balancing_market:
                    bid_energy -= (
                        self.state.get_desired_energy_Wh(market.time_slot)
                        * self.balancing_energy_ratio.demand
                    )
                try:
                    self.post_first_bid(
                        market, bid_energy, self.bid_update.initial_rate[market.time_slot]
                    )
                except MarketException:
                    pass

    def event_balancing_market_cycle(self):
        for market in self.active_markets:
            self._demand_balancing_offer(market)

    def event_bid_traded(self, *, market_id, bid_trade):
        """Register the bid traded by the device and its effects. Extends the superclass method.

        This method is triggered by the MarketEvent.BID_TRADED event.
        """
        # settlement market event_bid_traded has to be triggered before the early return:
        self._settlement_market_strategy.event_bid_traded(self, market_id, bid_trade)

        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)

        if not self.area.is_market_spot_or_future(market_id):
            return
        if bid_trade.match_details["bid"].buyer.name == self.owner.name:
            self._energy_params.decrement_energy_requirement(
                energy_kWh=bid_trade.traded_energy,
                time_slot=bid_trade.time_slot,
                area_name=self.owner.name,
            )

    def event_offer_traded(self, *, market_id, trade):
        """Register the offer traded by the device and its effects. Extends the superclass method.

        This method is triggered by the MarketEvent.OFFER_TRADED event.
        """
        # settlement market event_trade has to be triggered before the early return:
        self._settlement_market_strategy.event_offer_traded(self, market_id, trade)

        market = self.area.get_spot_or_future_market_by_id(market_id)
        if not market:
            return

        self.assert_if_trade_bid_price_is_too_high(market, trade)

        if ConstSettings.BalancingSettings.FLEXIBLE_LOADS_SUPPORT:
            # Load can only put supply_balancing_offers only when there is a trade in spot_market
            self._supply_balancing_offer(market, trade)
        super().event_offer_traded(market_id=market_id, trade=trade)

    # committing to increase its consumption when required
    def _demand_balancing_offer(self, market):
        if not self._is_eligible_for_balancing_market:
            return

        ramp_up_energy = self.balancing_energy_ratio.demand * self.state.get_desired_energy_Wh(
            market.time_slot
        )

        self._energy_params.decrement_energy_requirement(
            energy_kWh=ramp_up_energy / 1000, time_slot=market.time_slot, area_name=self.owner.name
        )

        ramp_up_price = DeviceRegistry.REGISTRY[self.owner.name][0] * ramp_up_energy
        if ramp_up_energy != 0 and ramp_up_price != 0:
            self.area.get_balancing_market(market.time_slot).balancing_offer(
                ramp_up_price,
                -ramp_up_energy,
                TraderDetails(self.owner.name, self.owner.uuid, self.owner.name, self.owner.uuid),
            )

    # committing to reduce its consumption when required
    def _supply_balancing_offer(self, market, trade):
        if not self._is_eligible_for_balancing_market:
            return
        if trade.buyer.name != self.owner.name:
            return
        ramp_down_energy = self.balancing_energy_ratio.supply * trade.traded_energy
        ramp_down_price = DeviceRegistry.REGISTRY[self.owner.name][1] * ramp_down_energy
        self.area.get_balancing_market(market.time_slot).balancing_offer(
            ramp_down_price,
            ramp_down_energy,
            TraderDetails(self.owner.name, self.owner.uuid, self.owner.name, self.owner.uuid),
        )

    @property
    def active_markets(self):
        """Return market slots in which the load device is active.

        Active market slots are specific to the LoadHoursStrategy and depend on the hours of day
        in which the device will be active (selected by the user).
        """
        return self._active_markets

    def _calculate_active_markets(self):
        self._active_markets = (
            [market for market in self.area.all_markets if self._is_market_active(market)]
            if self.area
            else []
        )

    def _is_market_active(self, market):
        return (
            self._energy_params.allowed_operating_hours(market.time_slot)
            and market.in_sim_duration
            and (
                not self.area.current_market
                or market.time_slot >= self.area.current_market.time_slot
            )
        )

    def _update_energy_requirement_future_markets(self):
        if not ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS:
            return
        for time_slot in self.area.future_market_time_slots:
            self._energy_params.update_energy_requirement(time_slot)

    def _update_energy_requirement_in_state(self):
        self._update_energy_requirement_spot_market()
        self._update_energy_requirement_future_markets()

    def _update_energy_requirement_spot_market(self):
        if self.area and self.area.spot_market:
            self._energy_params.update_energy_requirement(self.area.spot_market.time_slot)

        for market in self.active_markets:
            if not self._energy_params.allowed_operating_hours(market.time_slot):
                self.state.set_desired_energy(0.0, market.time_slot, True)
        if self.area.current_market:
            self.state.update_total_demanded_energy(self.area.current_market.time_slot)
        self._update_energy_requirement_future_markets()

    @property
    def asset_type(self):
        return AssetType.CONSUMER
