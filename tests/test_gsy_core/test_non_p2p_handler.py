from unittest.mock import Mock, patch

from gsy_e.gsy_e_core.area_serializer import area_from_dict
from gsy_e.gsy_e_core.non_p2p_handler import NonP2PHandler

SCENARIO = {
    "name": "Grid",
    "children": [
        {
            "name": "InfiniteBus",
            "type": "InfiniteBus",
            "energy_sell_rate": 31.0,
            "energy_buy_rate": 15.0,
        },
        {
            "name": "Community",
            "children": [
                {
                    "name": "House 1",
                    "children": [
                        {"name": "Load", "type": "LoadHours", "avg_power_W": 1},
                        {"name": "PV", "type": "PV"},
                    ],
                },
                {
                    "name": "House 2",
                    "children": [
                        {"name": "Load", "type": "LoadHours", "avg_power_W": 1},
                        {"name": "PV", "type": "PV"},
                    ],
                },
            ],
        },
    ],
}


class TestNonP2PHandler:

    @staticmethod
    def test_handle_non_p2p_scenario_adds_market_makers_to_homes():

        config = Mock()
        area = area_from_dict(SCENARIO, config)
        with patch("gsy_e.constants.RUN_IN_NON_P2P_MODE", True):
            handler = NonP2PHandler(area)

        house_count = 0
        community_area = [c for c in handler.non_p2p_scenario.children if c.name == "Community"][0]
        for child in community_area.children:
            if child.name not in ["House 1", "House 2"]:
                continue
            market_maker_area = [c for c in child.children if c.name == "MarketMaker"][0]
            assert all(v == 15 for v in market_maker_area.strategy.energy_buy_rate.values())
            assert all(v == 31 for v in market_maker_area.strategy.energy_rate.values())
            house_count += 1

        assert house_count == 2
