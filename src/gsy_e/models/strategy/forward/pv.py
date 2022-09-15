from typing import Dict, TYPE_CHECKING

from gsy_framework.enums import AvailableMarketTypes
from pendulum import DateTime

from gsy_e.models.strategy.energy_parameters.energy_params_eb import (
    ProductionStandardProfileEnergyParameters)
from gsy_e.models.strategy.forward import ForwardStrategyBase
from gsy_e.models.strategy.forward.order_updater import OrderUpdaterParameters

if TYPE_CHECKING:
    from gsy_e.models.market.forward import ForwardMarketBase
    from gsy_framework.data_classes import Trade


class ForwardPVStrategy(ForwardStrategyBase):
    """
    Strategy that models a PV that trades with a Standard Solar Profile on the forward
    exchanges.
    """
    def __init__(
            self, capacity_kW: float,
            order_updater_parameters: Dict[AvailableMarketTypes, OrderUpdaterParameters]):
        super().__init__(order_updater_parameters)
        self._energy_params = ProductionStandardProfileEnergyParameters(capacity_kW)

    def remove_open_orders(self, market: "ForwardMarketBase", market_slot: DateTime):
        offers = [offer
                  for offer in market.slot_offer_mapping[market_slot]
                  if offer.seller == self.owner.name]
        for offer in offers:
            market.delete_offer(offer)

    def post_order(self, market: "ForwardMarketBase", market_slot: DateTime):
        order_rate = self._order_updaters[market][market_slot].get_energy_rate(
            self.area.now)
        energy_kWh = self._energy_params.get_available_energy_kWh(market_slot)
        market.offer(
            order_rate * energy_kWh, energy_kWh,
            seller=self.owner.name,
            original_price=order_rate * energy_kWh,
            seller_origin=self.owner.name,
            seller_origin_id=self.owner.uuid,
            seller_id=self.owner.uuid,
            time_slot=market_slot)

    def event_traded(self, *, market_id: str, trade: "Trade"):
        """Method triggered by the MarketEvent.OFFER_TRADED event."""
        market = [market
                  for market in self.area.forward_markets.values()
                  if market_id == market.id]
        if not market:
            return

        self._energy_params.event_traded_energy(trade.traded_energy,
                                                trade.time_slot, market[0].market_type)
