from unittest.mock import patch

from gsy_e.gsy_e_core.non_p2p_handler import NonP2PHandler

SCENARIO = {
    "name": "Grid",
    "type": "Area",
    "children": [
        {
            "name": "Community",
            "type": "Area",
            "children": [
                {
                    "name": "House 1",
                    "type": "Area",
                    "children": [{"name": "Load", "type": "Load"}, {"name": "PV", "type": "PV"}],
                },
                {
                    "name": "House 2",
                    "type": "Area",
                    "children": [{"name": "Load", "type": "Load"}, {"name": "PV", "type": "PV"}],
                },
            ],
        }
    ],
}


class TestNonP2PHandler:

    @staticmethod
    @patch("gsy_framework.constants_limits.GlobalConfig.MARKET_MAKER_RATE", 31)
    @patch("gsy_framework.constants_limits.GlobalConfig.FEED_IN_TARIFF", 8)
    def test_handle_non_p2p_scenario_adds_market_makers_to_homes():
        handler = NonP2PHandler(SCENARIO)
        assert handler.non_p2p_scenario == {
            "name": "Grid",
            "type": "Area",
            "children": [
                {
                    "name": "Community",
                    "type": "Area",
                    "children": [
                        {
                            "name": "House 1",
                            "type": "Area",
                            "children": [
                                {"name": "Load", "type": "Load"},
                                {"name": "PV", "type": "PV"},
                                {
                                    "name": "MarketMaker",
                                    "type": "InfiniteBus",
                                    "energy_buy_rate": 8,
                                    "energy_sell_rate": 31,
                                },
                            ],
                        },
                        {
                            "name": "House 2",
                            "type": "Area",
                            "children": [
                                {"name": "Load", "type": "Load"},
                                {"name": "PV", "type": "PV"},
                                {
                                    "name": "MarketMaker",
                                    "type": "InfiniteBus",
                                    "energy_buy_rate": 8,
                                    "energy_sell_rate": 31,
                                },
                            ],
                        },
                    ],
                }
            ],
        }
