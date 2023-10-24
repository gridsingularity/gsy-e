from typing import TYPE_CHECKING

from gsy_framework.read_user_profile import InputProfileTypes, read_arbitrary_profile

from gsy_e.gsy_e_core.util import get_market_maker_rate_from_config

if TYPE_CHECKING:
    from gsy_e.models.area import Area
    from gsy_e.models.strategy.update_frequency import (TemplateStrategyBidUpdater,
                                                        TemplateStrategyOfferUpdater)


class UseMarketMakerMixin:
    """Handles update of strategy price settings when using the market maker rates"""

    area: "Area"
    owner: "Area"
    offer_update: "TemplateStrategyOfferUpdater"
    bid_update: "TemplateStrategyBidUpdater"
    use_market_maker_rate: bool

    def _reconfigure_initial_selling_rate(self, initial_selling_rate: float):
        """validation is not needed"""
        initial_selling_rate = (
            read_arbitrary_profile(InputProfileTypes.IDENTITY, initial_selling_rate))
        self.offer_update.set_parameters(initial_rate=initial_selling_rate)

    def _reconfigure_final_buying_rate(self, final_buying_rate: float):
        final_buying_rate = (
            read_arbitrary_profile(InputProfileTypes.IDENTITY, final_buying_rate))
        self.bid_update.set_parameters(final_rate=final_buying_rate)

    def _replace_rates_with_market_maker_rates(self):
        if not self.use_market_maker_rate:
            return
        if hasattr(self, "bid_update"):
            self._reconfigure_final_buying_rate(
                final_buying_rate=get_market_maker_rate_from_config(
                    self.area.spot_market, 0) + self.owner.get_path_to_root_fees())

        if hasattr(self, "offer_update"):
            # Reconfigure the initial selling rate (for energy production)
            self._reconfigure_initial_selling_rate(
                initial_selling_rate=get_market_maker_rate_from_config(
                    self.area.spot_market, 0) - self.owner.get_path_to_root_fees())
