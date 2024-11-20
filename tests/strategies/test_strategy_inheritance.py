from typing import Callable, List
from unittest.mock import Mock

import pytest

from gsy_e.models.strategy.external_strategies.load import (
    LoadProfileExternalStrategy,
    LoadProfileForecastExternalStrategy,
)
from gsy_e.models.strategy.external_strategies.pv import PVUserProfileExternalStrategy
from gsy_e.models.strategy.external_strategies.smart_meter import SmartMeterExternalStrategy
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy
from gsy_e.models.strategy.market_maker_strategy import MarketMakerStrategy
from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy
from gsy_e.models.strategy.predefined_pv import PVUserProfileStrategy
from scm.strategies.load import SCMLoadProfileStrategy
from scm.strategies.pv import SCMPVUserProfile
from scm.strategies.smart_meter import SCMSmartMeterStrategy
from gsy_e.models.strategy.smart_meter import SmartMeterStrategy


class ReadProfilesMock:
    """Mock read_or_rotate_profiles class method of strategy classes using a context manager."""

    def __init__(self, strategy_class: Callable):
        self._strategy_class = strategy_class
        self._read_or_rotate_profiles_orig = None

    def __enter__(self):
        if not hasattr(self._strategy_class, "_read_or_rotate_profiles"):
            return
        self._read_or_rotate_profiles_orig = self._strategy_class._read_or_rotate_profiles
        self._strategy_class._read_or_rotate_profiles = Mock()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._read_or_rotate_profiles_orig:
            return
        self._strategy_class._read_or_rotate_profiles = self._read_or_rotate_profiles_orig


class TestStrategyInheritance:

    # pylint: disable=protected-access
    @staticmethod
    @pytest.mark.parametrize(
        "attr_name, strategy_classes",
        [
            [
                "daily_load_profile_uuid",
                [
                    DefinedLoadStrategy,
                    SCMLoadProfileStrategy,
                    LoadProfileExternalStrategy,
                    LoadProfileForecastExternalStrategy,
                ],
            ],
            [
                "power_profile_uuid",
                [PVUserProfileStrategy, PVUserProfileExternalStrategy, SCMPVUserProfile],
            ],
            [
                "smart_meter_profile_uuid",
                [SmartMeterStrategy, SmartMeterExternalStrategy, SCMSmartMeterStrategy],
            ],
            ["energy_rate_profile_uuid", [MarketMakerStrategy, InfiniteBusStrategy]],
            ["buying_rate_profile_uuid", [InfiniteBusStrategy]],
        ],
    )
    def test_profile_uuids_are_part_of_strategy_attrs(
        attr_name: str, strategy_classes: List[Callable]
    ):
        """
        Makes sure that the profile_uuid are saved in the attributes
        in order to be read by the profile handler.
        """
        profile_uuid = "profile_uuid"
        for strategy_class in strategy_classes:
            parameter_dict = {attr_name: profile_uuid}
            with ReadProfilesMock(strategy_class):
                strategy = strategy_class(**parameter_dict)
                assert getattr(strategy, attr_name) == profile_uuid
