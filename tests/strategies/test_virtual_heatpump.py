from math import isclose

import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from pendulum import DateTime, UTC

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.area import Area
from gsy_e.models.strategy.virtual_heatpump import VirtualHeatpumpStrategy


class TestVirtualHeatpumpStrategy:
    # pylint: disable=too-many-arguments,protected-access,attribute-defined-outside-init
    def setup_method(self):
        ConstSettings.MASettings.MARKET_TYPE = 2
        self._datetime = DateTime(year=2022, month=7, day=1, tzinfo=UTC)
        self._default_start_date = GlobalConfig.start_date
        GlobalConfig.start_date = DateTime(year=2022, month=7, day=1, tzinfo=UTC)
        self._virtual_hp = VirtualHeatpumpStrategy(
            10, 10, 60, 20, 500,
            water_supply_temp_C_profile={self._datetime: 60},
            water_supply_temp_C_profile_uuid=None,
            water_return_temp_C_profile={self._datetime: 45},
            water_return_temp_C_profile_uuid=None,
            dh_water_flow_m3_profile={self._datetime: 0.1},
            dh_water_flow_m3_profile_uuid=None,
            preferred_buying_rate=20
        )
        strategy_area = Area("asset", strategy=self._virtual_hp)
        area = Area("grid", children=[strategy_area])
        area.config.start_date = self._datetime
        area.config.end_date = area.config.start_date.add(days=1)
        area.activate()

    def teardown_method(self):
        ConstSettings.MASettings.MARKET_TYPE = 1
        GlobalConfig.start_date = self._default_start_date

    parameterized_arg_list = [
        (60.0, 45.0, 0.1, 30, 6.98603741, 0.75),
        (50.0, 40.0, 0.1, 30, 6.81625000, 0.5),
        (60.0, 45.0, 0.5, 50, 21.5665540, 3.75),
        (60.0, 20.0, 0.1, 50, 21.4863768, 2.0)
    ]

    @pytest.mark.parametrize(
        "water_supply_temp, water_return_temp, water_flow, storage_temp, energy, _temp_decrease",
        parameterized_arg_list)
    def test_energy_from_storage_temp(
            self, water_supply_temp, water_return_temp, water_flow,
            storage_temp, energy, _temp_decrease):
        self._virtual_hp._energy_params._water_supply_temp_C.profile = {
            self._datetime: water_supply_temp}
        self._virtual_hp._energy_params._water_return_temp_C.profile = {
            self._datetime: water_return_temp}
        self._virtual_hp._energy_params._dh_water_flow_m3.profile = {
            self._datetime: water_flow}
        calculated_energy = self._virtual_hp._energy_params._target_storage_temp_to_energy(
            storage_temp, self._datetime)
        assert isclose(calculated_energy, energy, abs_tol=FLOATING_POINT_TOLERANCE)

    @pytest.mark.parametrize(
        "water_supply_temp, water_return_temp, water_flow, storage_temp, energy, _temp_decrease",
        parameterized_arg_list)
    def test_storage_temp_from_energy(
            self, water_supply_temp, water_return_temp, water_flow,
            storage_temp, energy, _temp_decrease):
        self._virtual_hp._energy_params._water_supply_temp_C.profile = {
            self._datetime: water_supply_temp}
        self._virtual_hp._energy_params._water_return_temp_C.profile = {
            self._datetime: water_return_temp}
        self._virtual_hp._energy_params._dh_water_flow_m3.profile = {
            self._datetime: water_flow}
        calculated_storage_temp = self._virtual_hp._energy_params._energy_to_storage_temp(
            energy, self._datetime)
        assert isclose(calculated_storage_temp, storage_temp, abs_tol=FLOATING_POINT_TOLERANCE)

    @pytest.mark.parametrize(
        "water_supply_temp, water_return_temp, water_flow, _storage_temp, _energy, temp_decrease",
        parameterized_arg_list)
    def test_storage_temp_decrease(
            self, water_supply_temp, water_return_temp, water_flow,
            _storage_temp, _energy, temp_decrease):
        self._virtual_hp._energy_params._water_supply_temp_C.profile = {
            self._datetime: water_supply_temp}
        self._virtual_hp._energy_params._water_return_temp_C.profile = {
            self._datetime: water_return_temp}
        self._virtual_hp._energy_params._dh_water_flow_m3.profile = {
            self._datetime: water_flow}
        calculated_temp_decrease = self._virtual_hp._energy_params._calc_temp_decrease_K(
            self._datetime)
        assert isclose(calculated_temp_decrease, temp_decrease, abs_tol=FLOATING_POINT_TOLERANCE)
