from unittest.mock import MagicMock

from gsy_framework.constants_limits import GlobalConfig
import pytest
from pendulum import today, duration

from gsy_e.models.area.coefficient_area import CoefficientArea
from gsy_e.models.strategy.scm.storage import SCMStorageStrategy

TIME_SLOT_BUY = today(tz="UTC").set(hour=11)
TIME_SLOT_SELL = today(tz="UTC").set(hour=12)
PROSUMPTION_KWH_PROFILE = {
    today(tz="UTC").set(hour=hour): 1 if hour < 12 else -1 for hour in range(0, 24)
}


@pytest.fixture(name="scm_storage")
def fixture_scm_storage():
    initial_slot_length = GlobalConfig.slot_length
    GlobalConfig.slot_length = duration(minutes=60)
    yield SCMStorageStrategy(prosumption_kWh_profile=PROSUMPTION_KWH_PROFILE)
    GlobalConfig.slot_length = initial_slot_length


class TestScmStorage:
    # pylint: disable= protected-access

    @staticmethod
    def test_market_cycle_rotates_profile(scm_storage):
        area = MagicMock(spec=CoefficientArea)
        assert scm_storage._energy_params.energy_profile.profile == {}
        scm_storage.market_cycle(area)
        assert len(list(scm_storage._energy_params.energy_profile.profile.keys())) == 24
        assert all(
            abs(v) == 1 for v in scm_storage._energy_params.energy_profile.profile.values())

    @staticmethod
    def test_get_energy_to_sell_kWh_returns_correctly(scm_storage):
        area = MagicMock(spec=CoefficientArea)
        scm_storage.market_cycle(area)
        assert scm_storage.get_energy_to_sell_kWh(TIME_SLOT_SELL) == 1
        assert scm_storage.get_energy_to_sell_kWh(TIME_SLOT_BUY) == 0

    @staticmethod
    def test_get_energy_to_buy_kWh_returns_correctly(scm_storage):
        area = MagicMock(spec=CoefficientArea)
        scm_storage.market_cycle(area)
        assert scm_storage.get_energy_to_buy_kWh(TIME_SLOT_SELL) == 0
        assert scm_storage.get_energy_to_buy_kWh(TIME_SLOT_BUY) == 1
