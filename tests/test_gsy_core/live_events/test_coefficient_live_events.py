from unittest.mock import patch

import pytest
from gsy_framework.constants_limits import ConstSettings, SpotMarketTypeEnum, GlobalConfig
from pendulum import duration

from gsy_e.gsy_e_core.live_events import (
    CreateAreaEventCoefficient, UpdateAreaEventCoefficient)
from gsy_e.models.area.coefficient_area import CoefficientArea
from gsy_e.models.config import SimulationConfig
from gsy_e.models.strategy.scm.load import SCMLoadProfileStrategy
from gsy_e.models.strategy.scm.pv import SCMPVUserProfile
from gsy_e.models.strategy.scm.storage import SCMStorageStrategy


@pytest.fixture(name="coefficient_community")
def fixture_coefficient_community():
    ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.COEFFICIENTS.value
    config = SimulationConfig(
        sim_duration=duration(hours=12),
        slot_length=duration(minutes=15),
        tick_length=duration(seconds=15),
        cloud_coverage=0,
        external_connection_enabled=False
    )
    load = CoefficientArea("load", None, None, SCMLoadProfileStrategy(),
                           config)
    pv = CoefficientArea("pv", None, None, SCMPVUserProfile(), config)
    storage = CoefficientArea("storage", None, None, SCMStorageStrategy(),
                              config)
    house_area = CoefficientArea("House 1", children=[load, pv, storage], config=config)
    community_area = CoefficientArea("House 1", children=[house_area], config=config)
    yield community_area, config
    ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.ONE_SIDED.value
    GlobalConfig.sim_duration = duration(days=GlobalConfig.DURATION_D)
    GlobalConfig.slot_length = duration(minutes=GlobalConfig.SLOT_LENGTH_M)
    GlobalConfig.tick_length = duration(seconds=GlobalConfig.TICK_LENGTH_S)


class TestCoefficientLiveEvents:
    @staticmethod
    def test_create_area_event_coefficient(coefficient_community):
        community, config = coefficient_community
        event_dict = {
            "parent_uuid": community.uuid,
            "area_representation": {
                "name": "House 2", "grid_fee_constant": 0.3,
                "children": [
                    {"name": "PV 4", "type": "PVProfile", "cloud_coverage": 5,
                     "power_profile":
                         "{'filename': 'rebase_94703d11-f936-45ca-bbce-0f3cdd7c8b3d'}"}]
            }
        }
        create_event = CreateAreaEventCoefficient(
            parent_uuid=event_dict["parent_uuid"],
            area_representation=event_dict["area_representation"],
            config=config)
        with patch("gsy_e.models.area.coefficient_area.CoefficientArea."
                   "activate_energy_parameters") as activate_mock:
            create_event.apply(community)
            activate_mock.assert_called_once()
        assert [child.name for child in community.children] == ["House 1", "House 2"]
        assert [child.children[0].name
                for child in community.children if child.name == "House 2"] == ["PV 4"]

    @staticmethod
    def test_update_area_event_coefficient_applied_for_markets(coefficient_community):
        community, _ = coefficient_community
        house_1 = [child for child in community.children if child.name == "House 1"][0]
        update_event = UpdateAreaEventCoefficient(
            area_uuid=house_1.uuid,
            area_params={"fixed_monthly_fee": 2})
        with patch("gsy_e.models.area.coefficient_area.CoefficientArea."
                   "area_reconfigure_event") as reconfigure_mock:
            update_event.apply(house_1)
            reconfigure_mock.assert_called_once()

    @staticmethod
    def test_update_area_event_coefficient_not_applied_for_assets(coefficient_community):
        community, _ = coefficient_community
        house_1 = [child for child in community.children if child.name == "House 1"][0]
        storage = [child for child in house_1.children if child.name == "storage"][0]
        update_event = UpdateAreaEventCoefficient(
            area_uuid=storage.uuid,
            area_params={"battery_capacity_kWh": 2})
        with patch("gsy_e.models.area.coefficient_area.CoefficientArea."
                   "area_reconfigure_event") as reconfigure_mock:
            update_event.apply(storage)
            reconfigure_mock.assert_not_called()
