from typing import Dict, TYPE_CHECKING
from pendulum import DateTime

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes

from gsy_e.models.strategy.forward import ForwardStrategyBase
from gsy_e.models.strategy.forward.order_updater import OrderUpdater, OrderUpdaterParameters
from gsy_e.models.strategy.energy_parameters.energy_params_eb import (
    ConsumptionStandardProfileEnergyParameters)

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
        super().__init__()
        self._energy_params = ConsumptionStandardProfileEnergyParameters(capacity_kW)
        self._order_updater_params = order_updater_parameters
        self._order_updaters = {}

    def _order_updater_for_market_slot_exists(self, market: "ForwardMarketBase", market_slot):
        if market.id not in self._order_updaters:
            return False
        return market_slot in self._order_updaters[market.id]

    def update_open_orders(self):
        for market, market_slot_updater_dict in self._order_updaters.items():
            for market_slot, updater in market_slot_updater_dict.items():
                if updater.is_time_for_update(self.area.now):
                    self._remove_open_bid(market, market_slot)
                    self._post_bid(market, market_slot)

    def post_orders_to_new_markets(self):
        forward_markets = self.area.forward_markets
        for market_type, market in forward_markets.items():
            if market not in self._order_updaters:
                self._order_updaters[market] = {}

            for market_slot in market.market_time_slots:
                if not self._order_updater_for_market_slot_exists(market, market_slot):
                    self._order_updaters[market][market_slot] = OrderUpdater(
                        self._order_updater_params[market_type],
                        market.get_market_parameters_for_market_slot(market_slot)
                    )

                    self._post_bid(market, market_slot)

    def _delete_past_order_updaters(self):
        for market_slot_updater_dict in self._order_updaters.values():
            slots_to_delete = [
                market_slot
                for market_slot in market_slot_updater_dict.keys()
                if market_slot < self.area.now
            ]
            for slot in slots_to_delete:
                market_slot_updater_dict.pop(slot)

    def _remove_open_bid(self, market: "ForwardMarketBase", market_slot: DateTime):
        bids = [bid
                for bid in market.slot_bid_mapping[market_slot]
                if bid.buyer == self.owner.name]
        for bid in bids:
            market.delete_bid(bid)

    def _post_bid(self, market: "ForwardMarketBase", market_slot: DateTime):
        order_rate = self._order_updaters[market][market_slot].get_energy_rate(
            self.area.now)
        energy_kWh = 10.0  # TODO: Connect the energy params
        market.bid(
            order_rate * energy_kWh, energy_kWh,
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
