from gsy_framework.constants_limits import GlobalConfig
from gsy_framework.exceptions import GSyException


class NonP2PHandler:
    """Handles non-p2p case"""

    def __init__(self, scenario: dict):
        self.non_p2p_scenario = scenario
        self._energy_sell_rate = 0.0
        self._energy_buy_rate = 0.0
        self._get_energy_rates_from_infinite_bus(scenario)
        self._handle_non_p2p_scenario(scenario)

    def _get_energy_rates_from_infinite_bus(self, scenario: dict):
        for child in scenario["children"]:
            if child.get("type") == "InfiniteBus":
                self._energy_buy_rate = child.get("energy_buy_rate", GlobalConfig.FEED_IN_TARIFF)
                self._energy_sell_rate = child.get(
                    "energy_sell_rate", GlobalConfig.MARKET_MAKER_RATE
                )
                return

        raise GSyException(
            "For non-p2p simulation, an InfiniteBus has to be present in the first "
            "level of the configuration tree."
        )

    @staticmethod
    def _is_home_area(area: dict):
        return area.get("children") and all(
            child.get("type", None) for child in area.get("children")
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
                "energy_buy_rate": self._energy_buy_rate,
                "energy_sell_rate": self._energy_sell_rate,
            }
        )

    def _handle_non_p2p_scenario(self, area: dict):
        if "children" not in area or not area["children"]:
            return
        self._add_market_maker_to_home(area)
        for child in area["children"]:
            self._handle_non_p2p_scenario(child)
