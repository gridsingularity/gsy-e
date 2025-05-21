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
import traceback
from logging import getLogger

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import TraderDetails
from gsy_framework.exceptions import GSyException
from gsy_framework.read_user_profile import read_arbitrary_profile, InputProfileTypes
from gsy_framework.utils import key_in_dict_and_not_none
from gsy_framework.validators import PVValidator
from pendulum import duration

from gsy_e import constants
from gsy_e.gsy_e_core.exceptions import MarketException
from gsy_e.models.base import AssetType
from gsy_e.models.strategy import BidEnabledStrategy
from gsy_e.models.strategy.energy_parameters.pv import PVEnergyParameters
from gsy_e.models.strategy.future.strategy import future_market_strategy_factory
from gsy_e.models.strategy.mixins import UseMarketMakerMixin
from gsy_e.models.strategy.settlement.strategy import settlement_market_strategy_factory
from gsy_e.models.strategy.state import PVState
from gsy_e.models.strategy.update_frequency import TemplateStrategyOfferUpdater

log = getLogger(__name__)


class PVStrategy(BidEnabledStrategy, UseMarketMakerMixin):
    """PV Strategy class for gaussian generation profile."""

    # pylint: disable=too-many-arguments
    def __init__(self, panel_count: int = 1,
                 initial_selling_rate:
                 float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
                 final_selling_rate:
                 float = ConstSettings.PVSettings.SELLING_RATE_RANGE.final,
                 fit_to_limit: bool = True,
                 update_interval=None,
                 energy_rate_decrease_per_update=None,
                 capacity_kW: float = None,
                 use_market_maker_rate: bool = False):
        """
        Args:
             panel_count: Number of solar panels for this PV plant
             initial_selling_rate: Upper Threshold for PV offers
             final_selling_rate: Lower Threshold for PV offers
             fit_to_limit: Linear curve following initial_selling_rate & initial_selling_rate
             update_interval: Interval after which PV will update its offer
             energy_rate_decrease_per_update: Slope of PV Offer change per update
             capacity_kW: power rating of the predefined profiles
        """
        super().__init__()
        self._energy_params = PVEnergyParameters(panel_count, capacity_kW)
        self.use_market_maker_rate = use_market_maker_rate
        self._init_price_update(update_interval, initial_selling_rate, final_selling_rate,
                                fit_to_limit, energy_rate_decrease_per_update)

    def serialize(self):
        """Return dict with the current strategy parameter values."""
        return {
            **self._energy_params.serialize(),
            **self.offer_update.serialize(),
            "use_market_maker_rate": self.use_market_maker_rate
        }

    @classmethod
    def _create_settlement_market_strategy(cls):
        return settlement_market_strategy_factory()

    def _create_future_market_strategy(self):
        return future_market_strategy_factory(self.asset_type)

    @property
    def state(self) -> PVState:
        return self._energy_params._state  # pylint: disable=protected-access

    # pylint: disable=too-many-arguments
    def _init_price_update(self, update_interval, initial_selling_rate, final_selling_rate,
                           fit_to_limit, energy_rate_decrease_per_update):

        # Instantiate instance variables that should not be shared with child classes
        self.final_selling_rate = final_selling_rate

        if update_interval is None:
            update_interval = \
                duration(minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)

        if isinstance(update_interval, int):
            update_interval = duration(minutes=update_interval)

        PVValidator.validate_rate(
            fit_to_limit=fit_to_limit,
            energy_rate_decrease_per_update=energy_rate_decrease_per_update)

        self.offer_update = TemplateStrategyOfferUpdater(initial_selling_rate, final_selling_rate,
                                                         fit_to_limit,
                                                         energy_rate_decrease_per_update,
                                                         update_interval)

    def area_reconfigure_event(self, *args, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        self._area_reconfigure_prices(**kwargs)
        self.offer_update.update_and_populate_price_settings(self.area)
        self._energy_params.reset(**kwargs)
        self.set_produced_energy_forecast_in_state(reconfigure=True)

    def _area_reconfigure_prices(self, **kwargs):

        initial_rate = (
            read_arbitrary_profile(InputProfileTypes.IDENTITY, kwargs["initial_selling_rate"])
            if kwargs.get("initial_selling_rate") is not None
            else self.offer_update.initial_rate_profile_buffer)

        final_rate = (
            read_arbitrary_profile(InputProfileTypes.IDENTITY, kwargs["final_selling_rate"])
            if kwargs.get("final_selling_rate") is not None
            else self.offer_update.final_rate_profile_buffer)

        energy_rate_change_per_update = (
            read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                   kwargs["energy_rate_decrease_per_update"])
            if kwargs.get("energy_rate_decrease_per_update") is not None
            else self.offer_update.energy_rate_change_per_update_profile_buffer)

        fit_to_limit = (
            kwargs["fit_to_limit"]
            if kwargs.get("fit_to_limit") is not None
            else self.offer_update.fit_to_limit)

        if key_in_dict_and_not_none(kwargs, "update_interval"):
            if isinstance(kwargs["update_interval"], int):
                update_interval = duration(minutes=kwargs["update_interval"])
            else:
                update_interval = kwargs["update_interval"]
        else:
            update_interval = self.offer_update.update_interval

        if key_in_dict_and_not_none(kwargs, "use_market_maker_rate"):
            self.use_market_maker_rate = kwargs["use_market_maker_rate"]

        try:
            self._validate_rates(initial_rate, final_rate, energy_rate_change_per_update,
                                 fit_to_limit)
        except GSyException as e:  # pylint: disable=broad-except
            log.error("PVStrategy._area_reconfigure_prices failed. Exception: %s. "
                      "Traceback: %s", e, traceback.format_exc())
            return

        self.offer_update.set_parameters(
            initial_rate=initial_rate,
            final_rate=final_rate,
            energy_rate_change_per_update=energy_rate_change_per_update,
            fit_to_limit=fit_to_limit,
            update_interval=update_interval
        )

    def _validate_rates(self, initial_rate: dict, final_rate: dict, energy_rate_change_per_update: dict,
                        fit_to_limit):
        # all parameters have to be validated for each time slot here
        for time_slot in initial_rate.keys():
            if self.area and self.area.current_market \
                    and time_slot < self.area.current_market.time_slot:
                continue
            rate_change = None if fit_to_limit else energy_rate_change_per_update.get(time_slot)
            PVValidator.validate_rate(
                initial_selling_rate=initial_rate.get(time_slot),
                final_selling_rate=final_rate.get(time_slot),
                energy_rate_decrease_per_update=rate_change,
                fit_to_limit=fit_to_limit)

    def event_activate(self, **kwargs):
        self.event_activate_price()
        self.event_activate_energy()
        self.offer_update.update_and_populate_price_settings(self.area)
        self._future_market_strategy.update_and_populate_price_settings(self)

    def event_activate_price(self):
        self._replace_rates_with_market_maker_rates()

        self._validate_rates(self.offer_update.initial_rate_profile_buffer.profile,
                             self.offer_update.final_rate_profile_buffer.profile,
                             self.offer_update.energy_rate_change_per_update_profile_buffer.profile,
                             self.offer_update.fit_to_limit)

    def event_activate_energy(self):
        """Activate energy parameters of the PV."""
        self._energy_params.activate(self.simulation_config)
        self.set_produced_energy_forecast_in_state(reconfigure=True)

    def event_tick(self):
        """Update the prices of existing offers on market tick.

        This method is triggered by the TICK event.
        """
        self.offer_update.update(self.area.spot_market, self)
        self.offer_update.increment_update_counter_all_markets(self)

        self._settlement_market_strategy.event_tick(self)
        self._future_market_strategy.event_tick(self)

    # pylint: disable=unused-argument
    def set_produced_energy_forecast_in_state(self, reconfigure=True):
        """Set the produced energy forecast for desired timeslot."""
        # This forecast is based on the real PV system data provided by enphase
        # They can be found in the tools folder
        # A fit of a gaussian function to those data results in a formula Energy(time)
        if not self.area or not self.area.spot_market:
            return
        time_slots = [self.area.spot_market.time_slot]
        if ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS:
            time_slots.extend(self.area.future_market_time_slots)
        for time_slot in time_slots:
            self._energy_params.set_produced_energy_forecast(
                time_slot, self.simulation_config.slot_length)

    def event_market_cycle(self):
        super().event_market_cycle()
        # Provide energy values for the past market slot, to be used in the settlement market
        self._set_energy_measurement_of_last_market()
        self.set_produced_energy_forecast_in_state(reconfigure=False)
        self.event_market_cycle_price()
        self._delete_past_state()
        self._settlement_market_strategy.event_market_cycle(self)
        self._future_market_strategy.event_market_cycle(self)

    def _set_energy_measurement_of_last_market(self):
        """Set the (simulated) actual energy of the device in the previous market slot."""
        if self.area.current_market:
            self._energy_params.set_energy_measurement_kWh(self.area.current_market.time_slot)

    def _delete_past_state(self):
        if (constants.RETAIN_PAST_MARKET_STRATEGIES_STATE is True or
                self.area.current_market is None):
            return

        self.state.delete_past_state_values(self.area.current_market.time_slot)
        self.offer_update.delete_past_state_values(self.area.current_market.time_slot)
        self._future_market_strategy.delete_past_state_values(
            self.area.current_market.time_slot)

    def event_market_cycle_price(self):
        """Manage price parameters during the market cycle event."""
        self.offer_update.update_and_populate_price_settings(self.area)
        self.offer_update.reset(self)

        market = self.area.spot_market
        offer_energy_kWh = self.state.get_available_energy_kWh(market.time_slot)
        # We need to subtract the energy from the offers that are already posted in this
        # market in order to validate that more offers need to be posted.
        offer_energy_kWh -= self.offers.open_offer_energy(market.id)
        if offer_energy_kWh > 0:
            offer_price = \
                self.offer_update.initial_rate[market.time_slot] * offer_energy_kWh
            try:
                offer = market.offer(
                    offer_price,
                    offer_energy_kWh,
                    TraderDetails(self.owner.name, self.owner.uuid, self.owner.name,
                                  self.owner.uuid),
                    original_price=offer_price,
                    time_slot=market.time_slot
                )
                self.offers.post(offer, market.id)
            except MarketException:
                pass

    def event_offer_traded(self, *, market_id, trade):
        super().event_offer_traded(market_id=market_id, trade=trade)
        self._settlement_market_strategy.event_offer_traded(self, market_id, trade)

        if not self.area.is_market_spot_or_future(market_id):
            return

        self._assert_if_trade_offer_price_is_too_low(market_id, trade)

        if trade.seller.name == self.owner.name:
            self.state.decrement_available_energy(
                trade.traded_energy, trade.time_slot, self.owner.name)

    def event_bid_traded(self, *, market_id, bid_trade):
        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)
        self._settlement_market_strategy.event_bid_traded(self, market_id, bid_trade)

    @property
    def asset_type(self):
        return AssetType.PRODUCER
