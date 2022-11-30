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
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from pendulum import datetime

from gsy_e import setup as d3a_setup
from gsy_e.gsy_e_core import util
from gsy_e.gsy_e_core.cli import available_simulation_scenarios
from gsy_e.gsy_e_core.util import (retry_function,
                                   get_simulation_queue_name, get_market_maker_rate_from_config,
                                   export_default_settings_to_json_file, constsettings_to_dict,
                                   convert_str_to_pause_after_interval)
from gsy_e.gsy_e_core.market_counters import FutureMarketCounter


class TestD3ACoreUtil:

    def setup_method(self):
        self.original_d3a_path = util.d3a_path

    def teardown_method(self):
        util.d3a_path = self.original_d3a_path
        GlobalConfig.market_maker_rate = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE
        os.environ.pop("LISTEN_TO_CANARY_NETWORK_REDIS_QUEUE", None)

    @staticmethod
    def test_validate_all_setup_scenarios_are_available():
        file_list = []
        root_path = d3a_setup.__path__[0] + "/"
        for path, _, files in os.walk(root_path):
            for name in files:
                if name.endswith(".py") and name != "__init__.py":
                    module_name = os.path.join(path, name[:-3]).\
                        replace(root_path, "").replace("/", ".")
                    file_list.append(module_name)
        assert set(file_list) == set(available_simulation_scenarios)

    @staticmethod
    def test_retry_function():
        retry_counter = 0

        @retry_function(max_retries=2)
        def erroneous_func():
            nonlocal retry_counter
            retry_counter += 1
            assert False

        with pytest.raises(AssertionError):
            erroneous_func()

        assert retry_counter == 3

    @staticmethod
    def test_get_simulation_queue_name():
        assert get_simulation_queue_name() == "exchange"
        os.environ["LISTEN_TO_CANARY_NETWORK_REDIS_QUEUE"] = "no"
        assert get_simulation_queue_name() == "exchange"
        os.environ["LISTEN_TO_CANARY_NETWORK_REDIS_QUEUE"] = "yes"
        assert get_simulation_queue_name() == "canary_network"

    @staticmethod
    def test_get_market_maker_rate_from_config():
        original_mmr = GlobalConfig.market_maker_rate
        assert get_market_maker_rate_from_config(None, 2) == 2
        market = MagicMock()
        market.time_slot = datetime(year=2019, month=2, day=3)
        GlobalConfig.market_maker_rate = {
            datetime(year=2019, month=2, day=3): 321
        }
        assert get_market_maker_rate_from_config(market, None) == 321
        GlobalConfig.market_maker_rate = 4321
        assert get_market_maker_rate_from_config(market, None) == 4321
        GlobalConfig.market_maker_rate = original_mmr

    @staticmethod
    def test_export_default_settings_to_json_file():
        temp_dir = tempfile.TemporaryDirectory()
        util.d3a_path = temp_dir.name
        os.mkdir(os.path.join(temp_dir.name, "setup"))
        export_default_settings_to_json_file()
        setup_dir = os.path.join(temp_dir.name, "setup")
        assert os.path.exists(setup_dir)
        assert set(os.listdir(setup_dir)) == {"gsy_e_settings.json"}
        file_path = os.path.join(setup_dir, "gsy_e_settings.json")
        file_contents = json.load(open(file_path))
        assert file_contents["basic_settings"]["sim_duration"] == "24h"
        assert file_contents["basic_settings"]["slot_length"] == "15m"
        assert file_contents["basic_settings"]["tick_length"] == "15s"
        assert file_contents["basic_settings"]["cloud_coverage"] == 0
        assert "advanced_settings" in file_contents
        temp_dir.cleanup()

    @staticmethod
    def test_convert_str_to_pause_after_interval():
        starttime = datetime(year=2020, month=3, day=12)
        input_str = "2020-03-12T15:00"
        interval = convert_str_to_pause_after_interval(starttime, input_str)
        assert interval.hours == 15

    @staticmethod
    def test_constsettings_to_dict():
        settings_dict = constsettings_to_dict()
        assert (settings_dict["GeneralSettings"]["DEFAULT_MARKET_MAKER_RATE"] ==
                ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE)
        assert (settings_dict["AreaSettings"]["PERCENTAGE_FEE_LIMIT"] ==
                ConstSettings.AreaSettings.PERCENTAGE_FEE_LIMIT)
        assert (settings_dict["StorageSettings"]["CAPACITY"] ==
                ConstSettings.StorageSettings.CAPACITY)
        assert (settings_dict["MASettings"]["MARKET_TYPE"] ==
                ConstSettings.MASettings.MARKET_TYPE)

    @staticmethod
    @patch("gsy_framework.constants_limits.ConstSettings.FutureMarketSettings."
           "FUTURE_MARKET_DURATION_HOURS", 1)
    def test_future_market_counter():
        """Test the counter of future market clearing."""
        with patch("gsy_framework.constants_limits.ConstSettings.FutureMarketSettings."
                   "FUTURE_MARKET_CLEARING_INTERVAL_MINUTES", 15):
            future_market_counter = FutureMarketCounter()
            current_time = datetime(year=2021, month=11, day=2,
                                    hour=1, minute=1, second=0)
            # When the _last_time_dispatched is None -> return True
            assert future_market_counter.is_time_for_clearing(current_time) is True

            # The interval time did not pass yet
            assert future_market_counter.is_time_for_clearing(current_time) is False

            # Skip the 15 minutes duration
            current_time = current_time.add(minutes=15)
            assert future_market_counter.is_time_for_clearing(current_time) is True
