from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import SpotMarketTypeEnum
from gsy_framework.exceptions import GSyException

import gsy_e.constants
from gsy_e.models.area.area import Area
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.predefined_pv import PVUserProfileStrategy


def set_non_p2p_settings(spot_market_type: int):
    """Set up non-P2P settings."""
    if spot_market_type == SpotMarketTypeEnum.NO_MARKET.value:
        ConstSettings.MASettings.MIN_BID_AGE = gsy_e.constants.MIN_OFFER_BID_AGE_P2P_DISABLED
        ConstSettings.MASettings.MIN_OFFER_AGE = gsy_e.constants.MIN_OFFER_BID_AGE_P2P_DISABLED
        gsy_e.constants.RUN_IN_NON_P2P_MODE = True


class NonP2PHandler:
    """Handles non-p2p case"""

    def __init__(self, scenario: Area):
        if not gsy_e.constants.RUN_IN_NON_P2P_MODE:
            return
        self.non_p2p_scenario = scenario
        self._energy_sell_rate = 0.0
        self._energy_buy_rate = 0.0
        self._get_energy_rates_from_infinite_bus(scenario)
        self._handle_non_p2p_scenario(scenario)

    def _get_energy_rates_from_infinite_bus(self, scenario: Area):
        for child in scenario.children:
            if isinstance(child.strategy, InfiniteBusStrategy):
                self._energy_buy_rate = child.strategy.energy_buy_rate
                self._energy_sell_rate = child.strategy.energy_rate
                return

        raise GSyException(
            "For non-p2p simulation, an InfiniteBus has to be present in the first "
            "level of the configuration tree."
        )

    @staticmethod
    def _is_home_area(area: Area):
        return area.children and all(child.strategy is not None for child in area.children)

    def _get_rates_from_home_assets(self, home_area: Area):
        mmr = None
        fit = None
        for area in home_area.children:
            if isinstance(area.strategy, (LoadHoursStrategy, DefinedLoadStrategy)):
                mmr = area.strategy.bid_update.final_rate_input
            if isinstance(area.strategy, (PVStrategy, PVUserProfileStrategy)):
                fit = area.strategy.offer_update.final_rate_input

        energy_sell_rate = self._energy_sell_rate if mmr is None else mmr
        energy_buy_rate = self._energy_buy_rate if fit is None else fit
        return energy_sell_rate, energy_buy_rate

    def _add_market_maker_to_home(self, area: Area):
        if not area.children:
            return
        if not self._is_home_area(area):
            return

        energy_sell_rate, energy_buy_rate = self._get_rates_from_home_assets(area)

        market_maker_area = Area(
            name="MarketMaker",
            strategy=InfiniteBusStrategy(
                energy_buy_rate=energy_buy_rate, energy_sell_rate=energy_sell_rate
            ),
        )
        market_maker_area.parent = area

        area.children.append(market_maker_area)
        area.set_order_age(gsy_e.constants.MIN_OFFER_BID_AGE_P2P_DISABLED)

    def _handle_non_p2p_scenario(self, area: Area):
        if not area.children:
            return
        self._add_market_maker_to_home(area)
        for child in area.children:
            self._handle_non_p2p_scenario(child)
