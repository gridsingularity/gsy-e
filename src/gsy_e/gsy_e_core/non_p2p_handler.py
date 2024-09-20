from gsy_framework.constants_limits import GlobalConfig


class NonP2PHandler:
    """Handles non-p2p case"""

    def __init__(self, scenario: dict):
        self.non_p2p_scenario = scenario
        self._handle_non_p2p_scenario(scenario)

    @staticmethod
    def _is_home_area(area: dict):
        return (
            area["type"] == "Area"
            and area["children"]
            and all(child["type"] != "Area" for child in area["children"])
        )

    def _add_market_maker_to_home(self, area: dict):
        if "children" not in area or not area["children"]:
            return
        if not self._is_home_area(area):
            return
        area["children"].append(
            {
                "name": "MarketMaker",
                "type": "InfiniteBus",
                "energy_buy_rate": GlobalConfig.FEED_IN_TARIFF,
                "energy_sell_rate": GlobalConfig.MARKET_MAKER_RATE,
            }
        )

    def _handle_non_p2p_scenario(self, area: dict):
        if "children" not in area or not area["children"]:
            return
        self._add_market_maker_to_home(area)
        for child in area["children"]:
            self._handle_non_p2p_scenario(child)
