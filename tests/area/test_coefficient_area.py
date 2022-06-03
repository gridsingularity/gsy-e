from math import isclose
from unittest.mock import MagicMock

import pytest
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import SpotMarketTypeEnum
from pendulum import duration, today

from gsy_e import constants
from gsy_e.models.area import CoefficientArea
from gsy_e.models.config import SimulationConfig
from gsy_e.models.strategy.scm.load import SCMLoadHoursStrategy
from gsy_e.models.strategy.scm.pv import SCMPVStrategy
from gsy_e.models.strategy.scm.storage import SCMStorageStrategy


class TestCoefficientArea:
    """Test the Area class behavior and state controllers."""

    @staticmethod
    @pytest.fixture(name="config")
    def config_fixture():
        """Instantiate a mocked configuration."""
        config = MagicMock(spec=SimulationConfig)
        config.slot_length = duration(minutes=15)
        config.tick_length = duration(seconds=15)
        config.ticks_per_slot = int(config.slot_length.seconds / config.tick_length.seconds)
        config.start_date = today(tz=constants.TIME_ZONE)
        config.sim_duration = duration(days=1)

        return config

    @staticmethod
    def setup_method():
        ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.COEFFICIENTS.value

    @staticmethod
    def teardown_method():
        ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.ONE_SIDED.value

    def test_calculate_after_meter_data(self):
        strategy = MagicMock(spec=SCMStorageStrategy)
        strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.1)
        strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.2)
        bat = CoefficientArea(name="battery", strategy=strategy)

        strategy = MagicMock(spec=SCMPVStrategy)
        strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.5)
        strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.0)
        pv = CoefficientArea(name="pv", strategy=strategy)

        strategy = MagicMock(spec=SCMLoadHoursStrategy)
        strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.0)
        strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.7)
        load = CoefficientArea(name="load", strategy=strategy)

        house = CoefficientArea(name="House", children=[bat, load])
        house1 = CoefficientArea(name="House 1", children=[load, pv])
        house2 = CoefficientArea(name="House 2", children=[bat, pv])
        grid_area = CoefficientArea(name="Grid", children=[house, house1, house2])

        after_meter_data = grid_area.calculate_after_meter_data(None)
        assert isclose(after_meter_data[house.uuid].consumption_kWh, 0.9)
        assert isclose(after_meter_data[house.uuid].production_kWh, 0.1)
        assert isclose(after_meter_data[house.uuid].self_consumed_energy_kWh, 0.1)
        assert isclose(after_meter_data[house.uuid].energy_surplus_kWh, 0.0)
        assert isclose(after_meter_data[house.uuid].energy_need_kWh, 0.8)

        assert isclose(after_meter_data[house1.uuid].consumption_kWh, 0.7)
        assert isclose(after_meter_data[house1.uuid].production_kWh, 0.5)
        assert isclose(after_meter_data[house1.uuid].self_consumed_energy_kWh, 0.5)
        assert isclose(after_meter_data[house1.uuid].energy_surplus_kWh, 0.0)
        assert isclose(after_meter_data[house1.uuid].energy_need_kWh, 0.2)

        assert isclose(after_meter_data[house2.uuid].consumption_kWh, 0.2)
        assert isclose(after_meter_data[house2.uuid].production_kWh, 0.6)
        assert isclose(after_meter_data[house2.uuid].self_consumed_energy_kWh, 0.2)
        assert isclose(after_meter_data[house2.uuid].energy_surplus_kWh, 0.4)
        assert isclose(after_meter_data[house2.uuid].energy_need_kWh, 0.0)
