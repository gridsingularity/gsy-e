"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange

This program is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If
not, see <http://www.gnu.org/licenses/>.
"""
import unittest
import uuid
from collections import OrderedDict
from unittest.mock import Mock, patch, call, create_autospec

from gsy_framework.exceptions import GSyException
from gsy_framework.validators.smart_meter_validator import SmartMeterValidator
from pendulum import datetime, duration

from gsy_e import constants
from gsy_e.models.area import Area
from gsy_e.models.market.one_sided import OneSidedMarket
from gsy_e.models.strategy.state import SmartMeterState
from gsy_e.models.strategy.smart_meter import SmartMeterStrategy


# pylint: disable=protected-access
class SmartMeterStrategyTest(unittest.TestCase):
    """Tests for the SmartMeterStrategy behaviour."""

    @classmethod
    def setUpClass(cls) -> None:
        """Instantiate slot times that will be shared by energy profiles and market slots mocks."""
        cls.slot_times = [
            datetime(2021, 6, 15, 0, 0, 0),
            datetime(2021, 6, 15, 0, 15, 0),
            datetime(2021, 6, 15, 0, 30, 0)]
        constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = False

    @classmethod
    def tearDownClass(cls) -> None:
        constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = True

    def setUp(self) -> None:
        """Instantiate the strategy used throughout the tests"""
        self.strategy = SmartMeterStrategy(
            initial_selling_rate=30, final_selling_rate=5, smart_meter_profile="some_path.csv")
        self.area_mock = create_autospec(Area)
        self.strategy.area = self.area_mock
        self.strategy.owner = Mock()
        self.strategy.validator = create_autospec(SmartMeterValidator)

    @staticmethod
    @patch.object(SmartMeterValidator, "validate")
    def test_init(validate_mock):
        """Test the side-effects of the init function of the smart meter strategy."""
        strategy = SmartMeterStrategy(
            initial_selling_rate=30, final_selling_rate=5, smart_meter_profile="some_path.csv",
            update_interval=1, energy_rate_increase_per_update=2,
            energy_rate_decrease_per_update=4)

        assert strategy.offer_update.update_interval == duration(minutes=1)
        assert strategy.bid_update.update_interval == duration(minutes=1)
        validate_mock.assert_called_once_with(
            fit_to_limit=True, energy_rate_increase_per_update=2,
            energy_rate_decrease_per_update=4)

    def test_event_activate(self):
        """event_activate calls the expected interface methods."""
        self.strategy.event_activate_price = Mock()
        self.strategy.event_activate_energy = Mock()
        self.strategy.bid_update = Mock()
        self.strategy.offer_update = Mock()

        self.strategy.event_activate()
        self.strategy.bid_update.update_and_populate_price_settings.assert_called_with(
            self.area_mock)
        self.strategy.offer_update.update_and_populate_price_settings.assert_called_with(
            self.area_mock)

        self.strategy.event_activate_energy.assert_called_with()
        self.strategy.event_activate_price.assert_called_with()

    @patch("gsy_e.models.strategy.mixins.get_market_maker_rate_from_config")
    def test_event_activate_price_with_market_maker_rate(
            self, get_market_maker_rate_from_config_mock):
        """If the market maker rate is used, call bid/offer updaters to replace existing rates."""
        self.strategy.use_market_maker_rate = True
        get_market_maker_rate_from_config_mock.return_value = 15
        self.strategy.owner.get_path_to_root_fees.return_value = 1
        self.strategy.bid_update.set_parameters = Mock()
        self.strategy.offer_update.set_parameters = Mock()

        self.strategy.event_activate_price()
        self.strategy.bid_update.set_parameters.assert_called_once()
        call_args = self.strategy.bid_update.set_parameters.call_args
        # The final buying rate is the sum of the market maker rate and the fees
        assert set(call_args.kwargs["final_rate"].values()) == {16}

        self.strategy.offer_update.set_parameters.assert_called_once()
        call_args = self.strategy.offer_update.set_parameters.call_args
        # The initial selling rate is the difference between the market maker rate and the fees
        assert set(call_args.kwargs["initial_rate"].values()) == {14}

        self.strategy.validator.validate_rate.assert_called()

    def test_event_activate_price_without_market_maker_rate(self):
        """If the market maker rate is not used, bid/offer updaters' methods are not called."""
        self.strategy.use_market_maker_rate = False
        self.strategy.bid_update.set_parameters = Mock()
        self.strategy.offer_update.set_parameters = Mock()

        self.strategy.event_activate_price()
        self.strategy.bid_update.set_parameters.assert_not_called()
        self.strategy.offer_update.set_parameters.assert_not_called()

    @patch(
        "gsy_e.gsy_e_core.global_objects_singleton.global_objects.profiles_handler.rotate_profile")
    def test_set_energy_forecast_for_future_markets(self, rotate_profile_mock):
        """The consumption/production expectations for the upcoming market slots are correctly set.

        This method is private, but we test it to avoid duplication and because of its complexity.
        """
        rotate_profile_mock.return_value = self._create_profile_mock()
        # We want to iterate over some area markets, so we create mocks for them
        market_mocks = self._create_market_mocks(3)
        self.strategy.area.all_markets = market_mocks
        self.strategy._energy_params._state = create_autospec(SmartMeterState)
        self.strategy._energy_params.read_and_rotate_profiles()
        time_slots = [m.time_slot for m in self.strategy.area.all_markets]
        self.strategy._energy_params.set_energy_forecast_for_future_markets(
            time_slots, reconfigure=True)

        assert self.strategy.state.set_desired_energy.call_count == 3  # One call for each slot
        self.strategy.state.set_desired_energy.assert_has_calls([
            call(1 * 1000, market_mocks[0].time_slot, overwrite=False),
            call(0, market_mocks[1].time_slot, overwrite=False),
            call(0, market_mocks[2].time_slot, overwrite=False)])

        assert self.strategy.state.set_available_energy.call_count == 3
        self.strategy.state.set_available_energy.assert_has_calls([
            call(0, market_mocks[0].time_slot, True),
            call(0.5, market_mocks[1].time_slot, True),
            call(0.1, market_mocks[2].time_slot, True)])

        assert self.strategy.state.update_total_demanded_energy.call_count == 3
        self.strategy.state.update_total_demanded_energy.assert_has_calls([
            call(market_slot.time_slot) for market_slot in market_mocks])

    @patch(
        "gsy_e.gsy_e_core.global_objects_singleton.global_objects.profiles_handler.rotate_profile")
    def test_set_energy_forecast_for_future_markets_no_profile(self, rotate_profile_mock):
        """Consumption/production expectations can't be set without an energy profile."""
        rotate_profile_mock.return_value = None
        self.strategy._energy_params.activate(self.strategy.area)
        with self.assertRaises(GSyException):
            time_slots = [m.time_slot for m in self.strategy.area.all_markets]
            self.strategy._energy_params.set_energy_forecast_for_future_markets(
                time_slots, reconfigure=True)

    @patch(
        "gsy_e.gsy_e_core.global_objects_singleton.global_objects.profiles_handler.rotate_profile")
    def test_event_activate_energy(self, rotate_profile_mock):
        """event_activate_energy calls the expected state interface methods."""
        rotate_profile_mock.return_value = self._create_profile_mock()
        self.strategy._energy_params.set_energy_forecast_for_future_markets = Mock()

        self.strategy.event_activate_energy()
        time_slots = [m.time_slot for m in self.strategy.area.all_markets]
        self.strategy._energy_params.set_energy_forecast_for_future_markets.\
            assert_called_once_with(time_slots, reconfigure=True)

    @patch("gsy_e.models.strategy.BidEnabledStrategy.event_market_cycle")
    def test_event_market_cycle(self, super_method_mock):
        """event_market_cycle calls the expected interfaces."""
        self.strategy.bid_update.update_and_populate_price_settings = Mock()
        self.strategy.offer_update.update_and_populate_price_settings = Mock()
        self.strategy.bid_update.reset = Mock()
        self.strategy.offer_update.reset = Mock()
        self.strategy.state.delete_past_state_values = Mock()
        self.strategy.bid_update.delete_past_state_values = Mock()
        self.strategy.offer_update.delete_past_state_values = Mock()
        self.strategy._energy_params.set_energy_forecast_for_future_markets = Mock()
        self.strategy._energy_params.read_and_rotate_profiles = Mock()
        self.strategy._set_energy_measurement_of_last_market = Mock()
        self.strategy._post_offer = Mock()
        market_mocks = self._create_market_mocks(3)
        self.strategy.area.all_markets = market_mocks

        self.strategy.event_market_cycle()
        super_method_mock.assert_called_once()
        self.strategy.bid_update.update_and_populate_price_settings.assert_called_with(
            self.area_mock)
        self.strategy.offer_update.update_and_populate_price_settings.assert_called_with(
            self.area_mock)
        self.strategy.bid_update.reset.assert_called_with(self.strategy)
        self.strategy.offer_update.reset.assert_called_with(self.strategy)

        # We just assert calls to private methods, because we have separate unittests for them
        time_slots = [m.time_slot for m in self.strategy.area.all_markets]
        self.strategy._energy_params.set_energy_forecast_for_future_markets.\
            assert_called_once_with(time_slots, reconfigure=False)
        assert self.strategy._post_offer.call_count == 3
        self.strategy._set_energy_measurement_of_last_market.assert_called_once()

        self.strategy.state.delete_past_state_values.assert_called_once_with(
            self.area_mock.current_market.time_slot)
        self.strategy.bid_update.delete_past_state_values.assert_called_once_with(
            self.area_mock.current_market.time_slot)
        self.strategy.offer_update.delete_past_state_values.assert_called_once_with(
            self.area_mock.current_market.time_slot)

    @patch("gsy_e.models.strategy.energy_parameters.smart_meter.utils")
    def test_set_energy_measurement_of_last_market(self, utils_mock):
        """The real energy of the last market is set when necessary."""
        # If we are in the first market slot, the real energy is not set
        self.strategy.area.current_market = None
        self.strategy.state.set_energy_measurement_kWh = Mock()
        self.strategy._set_energy_measurement_of_last_market()
        self.strategy.state.set_energy_measurement_kWh.assert_not_called()

        # When there is at least one past market, the real energy is set
        self.strategy.state.set_energy_measurement_kWh.reset_mock()
        self.strategy.area.current_market = Mock()
        utils_mock.compute_altered_energy.return_value = 100

        self.strategy._set_energy_measurement_of_last_market()
        self.strategy.state.set_energy_measurement_kWh.assert_called_once_with(
            100, self.strategy.area.current_market.time_slot)

    @patch("gsy_framework.constants_limits.ConstSettings.MASettings")
    def test_event_offer_two_sided_market(self, ma_settings_mock):
        """The device does not automatically react to offers in two-sided markets."""
        ma_settings_mock.MARKET_TYPE = 2
        self.strategy.event_offer(market_id="some_market_id", offer="some_offer")
        # Make sure that the method is returning immediately and not executing further logic
        self.strategy.area.get_future_market_from_id.assert_not_called()

    def test_post_offer(self):
        """Offers are generated and sent to the offers class to be posted.

        This method is private, but we test it to avoid duplication and because of its complexity.
        """
        self.strategy.state.get_available_energy_kWh = Mock(return_value=12)
        market_mock = self._create_market_mocks(1)[0]
        offer_mock = Mock()
        market_mock.offer = Mock(return_value=offer_mock)
        self.strategy.offer_update.initial_rate = {market_mock.time_slot: 11}
        self.strategy.offers.post = Mock()

        self.strategy._post_offer(market_mock)
        self.strategy.offers.post.assert_called_once_with(offer_mock, market_mock.id)

    def _create_profile_mock(self):
        return OrderedDict([
            (self.slot_times[0], 1), (self.slot_times[1], -0.5), (self.slot_times[2], -0.1)])

    def _create_market_mocks(self, num_of_markets=3):
        market_mocks = [create_autospec(OneSidedMarket) for _ in range(num_of_markets)]
        slot_time = self.slot_times[0]
        for market_mock in market_mocks:
            market_mock.time_slot = slot_time
            market_mock.id = uuid.uuid4()
            slot_time += duration(minutes=15)

        return market_mocks
