"""
Copyright 2018 Grid Singularity
This file is part of D3A.

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
from unittest.mock import Mock, patch

from d3a.models.strategy.home_meter import HomeMeterStrategy
from d3a_interface.device_validator import HomeMeterValidator
from pendulum import duration


class HomeMeterStrategyTest(unittest.TestCase):

    @classmethod
    def setUp(self) -> None:
        self.strategy = HomeMeterStrategy(
            initial_selling_rate=30, final_selling_rate=5, home_meter_profile="some_path.csv")
        self.area_mock = Mock()
        self.strategy.area = self.area_mock
        self.strategy.owner = Mock(name="owner")

    @patch.object(HomeMeterValidator, "validate")
    def test_init(self, validate_mock):
        """Test the side-effects of the init function of the home meter strategy."""
        strategy = HomeMeterStrategy(
            initial_selling_rate=30, final_selling_rate=5, home_meter_profile="some_path.csv",
            update_interval=1, energy_rate_increase_per_update=2,
            energy_rate_decrease_per_update=4)

        assert strategy.update_interval == duration(minutes=1)
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

    @patch("d3a.models.strategy.home_meter.get_market_maker_rate_from_config")
    def test_event_activate_price_with_market_maker_rate(
            self, get_market_maker_rate_from_config_mock):
        """If the market maker rate is used, call bid/offer updaters to replace existing rates."""
        self.strategy.use_market_maker_rate = True
        get_market_maker_rate_from_config_mock.return_value = 15
        self.strategy.owner.get_path_to_root_fees.return_value = 1
        self.strategy.bid_update.set_parameters = Mock()
        self.strategy.offer_update.set_parameters = Mock()
        self.strategy.event_activate_price()

        # Expect to send outgoing command messages to strategy.bid_update
        self.strategy.bid_update.set_parameters.assert_called_once()
        call_args = self.strategy.bid_update.set_parameters.call_args
        assert set(call_args.kwargs["initial_rate_profile_buffer"].values()) == {0}
        # The final buying rate is the sum of the market maker rate and the fees
        assert set(call_args.kwargs["final_rate_profile_buffer"].values()) == {16}
        assert call_args.kwargs["energy_rate_change_per_update_profile_buffer"] == {}
        assert call_args.kwargs["fit_to_limit"] is True
        assert call_args.kwargs["update_interval"] == duration(minutes=1)

        # Expect to send outgoing command messages to strategy.offer_update
        self.strategy.offer_update.set_parameters.assert_called_once()
        call_args = self.strategy.offer_update.set_parameters.call_args
        # The initial selling rate is the difference between the market maker rate and the fees
        assert set(call_args.kwargs["initial_rate_profile_buffer"].values()) == {14}
        assert set(call_args.kwargs["final_rate_profile_buffer"].values()) == {5}
        assert call_args.kwargs["energy_rate_change_per_update_profile_buffer"] == {}
        assert call_args.kwargs["fit_to_limit"] is True
        assert call_args.kwargs["update_interval"] == duration(minutes=1)

    def test_event_activate_price_without_market_maker_rate(self):
        """If the market maker rate is not used, bid/offer updaters' methods are not called."""
        self.strategy.use_market_maker_rate = False
        self.strategy.bid_update.set_parameters = Mock()
        self.strategy.offer_update.set_parameters = Mock()
        self.strategy.event_activate_price()

        # Expect not to send outgoing command messages to strategy.bid_update
        self.strategy.bid_update.set_parameters.assert_not_called()
        self.strategy.offer_update.set_parameters.assert_not_called()
