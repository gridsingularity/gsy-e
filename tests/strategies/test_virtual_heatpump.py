from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_e.models.strategy.virtual_heatpump import VirtualHeatpumpStrategy
from pendulum import DateTime, UTC
from unittest.mock import MagicMock


class TestVirtualHeatpumpStrategy:

    def setup_method(self):
        ConstSettings.MASettings.MARKET_TYPE = 2
        self._datetime = DateTime(year=2022, month=7, day=1, tzinfo=UTC)
        GlobalConfig.start_date = DateTime(year=2022, month=7, day=1, tzinfo=UTC)

    def teardown_method(self):
        ConstSettings.MASettings.MARKET_TYPE = 1

    def test_power_from_storage_temp(self):

        virtual_hp = VirtualHeatpumpStrategy(
            10, 10, 60, 30, 500,
            water_supply_temp_C_profile={self._datetime: 30},
            water_supply_temp_C_profile_uuid=None,
            water_return_temp_C_profile={self._datetime: 20},
            water_return_temp_C_profile_uuid=None,
            dh_water_flow_m3_profile={self._datetime: 21.2},
            dh_water_flow_m3_profile_uuid=None,
            preferred_buying_rate=20
        )

        virtual_hp.area = MagicMock()
        spot_market = MagicMock()
        spot_market.time_slot = self._datetime
        virtual_hp.area.spot_market = spot_market

        virtual_hp.event_activate()
        virtual_hp.event_market_cycle()
        virtual_hp._energy_params._water_supply_temp_C.profile = {self._datetime: 30}
        virtual_hp._energy_params._water_return_temp_C.profile = {self._datetime: 20}
        virtual_hp._energy_params._dh_water_flow_m3.profile = {self._datetime: 21.2}

        retval = virtual_hp._energy_params._storage_temp_to_energy(30, self._datetime)
        print(retval)
        assert False
