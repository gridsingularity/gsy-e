from unittest.mock import MagicMock

import pytest
from pendulum import today

from gsy_e.models.area.coefficient_area import CoefficientArea
from gsy_e.models.strategy.scm.storage import SCMStorageStrategy

TIME_SLOT_BUY = today(tz="UTC").set(hour=11)
TIME_SLOT_SELL = today(tz="UTC").set(hour=12)


@pytest.fixture(name="scm_storage")
def fixture_scm_storage():
    return SCMStorageStrategy(storage_profile={0: 1, 12: -1})


class TestScmStorage:
    # pylint: disable= protected-access

    @staticmethod
    def test_market_cycle_rotates_profile(scm_storage):
        area = MagicMock(spec=CoefficientArea)
        assert scm_storage._energy_params.energy_profile.profile == {}
        scm_storage.market_cycle(area)
        assert len(list(scm_storage._energy_params.energy_profile.profile.keys())) == 24 * 4
        assert all(
            abs(v) == 0.00025 for v in scm_storage._energy_params.energy_profile.profile.values())

    @staticmethod
    def test_get_energy_to_sell_kWh_returns_correctly(scm_storage):
        area = MagicMock(spec=CoefficientArea)
        scm_storage.market_cycle(area)
        assert scm_storage.get_energy_to_sell_kWh(TIME_SLOT_SELL) == 0.00025
        assert scm_storage.get_energy_to_sell_kWh(TIME_SLOT_BUY) == 0

    @staticmethod
    def test_get_energy_to_buy_kWh_returns_correctly(scm_storage):
        area = MagicMock(spec=CoefficientArea)
        scm_storage.market_cycle(area)
        assert scm_storage.get_energy_to_buy_kWh(TIME_SLOT_SELL) == 0
        assert scm_storage.get_energy_to_buy_kWh(TIME_SLOT_BUY) == 0.00025
