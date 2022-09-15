from typing import Dict, TYPE_CHECKING

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes
from pendulum import DateTime

from gsy_e.models.strategy.energy_parameters.energy_params_eb import (
    ConsumptionStandardProfileEnergyParameters)
from gsy_e.models.strategy.forward import ForwardStrategyBase
from gsy_e.models.strategy.forward.order_updater import OrderUpdaterParameters

if TYPE_CHECKING:
    from gsy_e.models.market.forward import ForwardMarketBase
    from gsy_framework.data_classes import Trade


BUYING_RATE_RANGE = ConstSettings.LoadSettings.BUYING_RATE_RANGE


class ForwardLoadStrategy(ForwardStrategyBase):
    """
    Strategy that models a Load that trades with a Standard Solar Profile on the forward
    exchanges.
    """
    def __init__(
            self, capacity_kW: float,
            order_updater_parameters: Dict[AvailableMarketTypes, OrderUpdaterParameters]):
        super().__init__(order_updater_parameters)
        self._energy_params = ConsumptionStandardProfileEnergyParameters(capacity_kW)

    def remove_open_orders(self, market: "ForwardMarketBase", market_slot: DateTime):
        bids = [bid
                for bid in market.slot_bid_mapping[market_slot]
                if bid.buyer == self.owner.name]
        for bid in bids:
            market.delete_bid(bid)

    def post_order(self, market: "ForwardMarketBase", market_slot: DateTime):
        order_rate = self._order_updaters[market][market_slot].get_energy_rate(
            self.area.now)
        energy_kWh = 10.0  # TODO: Connect the energy params
        market.bid(
            order_rate * energy_kWh, energy_kWh,
            buyer=self.owner.name,
            original_price=order_rate * energy_kWh,
            buyer_origin=self.owner.name,
            buyer_origin_id=self.owner.uuid,
            buyer_id=self.owner.uuid,
            time_slot=market_slot)

    def event_bid_traded(self, *, market_id: str, bid_trade: "Trade"):
        """Method triggered by the MarketEvent.BID_TRADED event."""
        market = [market
                  for market in self.area.forward_markets.values()
                  if market_id == market.id]
        if not market:
            return

        self._energy_params.event_traded_energy(bid_trade.traded_energy,
                                                bid_trade.time_slot, market[0].market_type)
