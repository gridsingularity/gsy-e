from typing import Dict, TYPE_CHECKING

from gsy_framework.enums import AvailableMarketTypes
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.energy_parameters.energy_params_eb import (
    ConsumptionStandardProfileEnergyParameters)
from gsy_e.models.strategy.forward import ForwardStrategyBase
from gsy_e.models.strategy.forward.order_updater import OrderUpdaterParameters

if TYPE_CHECKING:
    from gsy_e.models.market.forward import ForwardMarketBase
    from gsy_framework.data_classes import Trade
    from gsy_e.models.state import LoadState


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

    @property
    def state(self) -> "LoadState":
        return self._energy_params.state

    def event_activate(self, **kwargs):
        self._energy_params.event_activate_energy(self.area)

    def remove_open_orders(self, market: "ForwardMarketBase", market_slot: DateTime):
        bids = [bid
                for bid in market.slot_bid_mapping[market_slot]
                if bid.buyer == self.owner.name]
        for bid in bids:
            market.delete_bid(bid)

    def post_order(self, market: "ForwardMarketBase", market_slot: DateTime):
        order_rate = self._order_updaters[market][market_slot].get_energy_rate(
            self.area.now)
        capacity_percent = self._order_updaters[market][market_slot].capacity_percent / 100.0
        max_energy_kWh = self._energy_params.peak_energy_kWh * capacity_percent
        available_energy_kWh = self._energy_params.get_available_energy_kWh(
            market_slot, market.market_type)

        posted_energy_kWh = self._energy_params.get_posted_energy_kWh(
            market_slot, market.market_type)

        available_energy_kWh = min(available_energy_kWh - posted_energy_kWh, max_energy_kWh)

        if available_energy_kWh <= FLOATING_POINT_TOLERANCE:
            return
        market.bid(
            order_rate * available_energy_kWh, available_energy_kWh,
            buyer=self.owner.name,
            original_price=order_rate * available_energy_kWh,
            buyer_origin=self.owner.name,
            buyer_origin_id=self.owner.uuid,
            buyer_id=self.owner.uuid,
            time_slot=market_slot)
        self._energy_params.increment_posted_energy(
            market_slot, available_energy_kWh, market.market_type)

    def event_bid_traded(self, *, market_id: str, bid_trade: "Trade"):
        """Method triggered by the MarketEvent.BID_TRADED event."""
        market = [market
                  for market in self.area.forward_markets.values()
                  if market_id == market.id]
        if not market:
            return

        if bid_trade.buyer_id != self.owner.uuid:
            return

        self._energy_params.event_traded_energy(bid_trade.traded_energy,
                                                bid_trade.time_slot, market[0].market_type)
        self._energy_params.decrement_posted_energy(
            bid_trade.time_slot, bid_trade.traded_energy, market[0].market_type)
