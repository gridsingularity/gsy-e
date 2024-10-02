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
                    "children": [{"name": "Load", "type": "Load"}, {"name": "PV", "type": "PV"}],
                },
                {
                    "name": "House 2",
                    "children": [{"name": "Load", "type": "Load"}, {"name": "PV", "type": "PV"}],
                },
            ],
        },
    ],
}


class TestNonP2PHandler:

    @staticmethod
    def test_handle_non_p2p_scenario_adds_market_makers_to_homes():
        handler = NonP2PHandler(SCENARIO)
        assert handler.non_p2p_scenario == {
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
                                {"name": "Load", "type": "Load"},
                                {"name": "PV", "type": "PV"},
                                {
                                    "name": "MarketMaker",
                                    "type": "InfiniteBus",
                                    "energy_buy_rate": 15.0,
                                    "energy_sell_rate": 31.0,
                                },
                            ],
                        },
                        {
                            "name": "House 2",
                            "children": [
                                {"name": "Load", "type": "Load"},
                                {"name": "PV", "type": "PV"},
                                {
                                    "name": "MarketMaker",
                                    "type": "InfiniteBus",
                                    "energy_buy_rate": 15.0,
                                    "energy_sell_rate": 31.0,
                                },
                            ],
                        },
                    ],
                },
            ],
        }
