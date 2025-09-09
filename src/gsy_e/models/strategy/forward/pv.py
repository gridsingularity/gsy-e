from decimal import Decimal
from typing import Dict, TYPE_CHECKING

from pendulum import DateTime, duration
from gsy_framework.data_classes import TraderDetails
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.constants_limits import FLOATING_POINT_TOLERANCE

from gsy_e.models.strategy.energy_parameters.energy_params_eb import (
    ProductionStandardProfileEnergyParameters,
)
from gsy_e.models.strategy.forward import ForwardStrategyBase
from gsy_e.models.strategy.forward.order_updater import ForwardOrderUpdaterParameters

if TYPE_CHECKING:
    from gsy_e.models.market.forward import ForwardMarketBase
    from gsy_framework.data_classes import Trade
    from gsy_e.models.strategy.state import PVState


DEFAULT_PV_ORDER_UPDATER_PARAMS = {
    AvailableMarketTypes.INTRADAY: ForwardOrderUpdaterParameters(duration(minutes=5), 10, 10, 10),
    AvailableMarketTypes.DAY_FORWARD: ForwardOrderUpdaterParameters(
        duration(minutes=30), 10, 10, 10
    ),
    AvailableMarketTypes.WEEK_FORWARD: ForwardOrderUpdaterParameters(duration(days=1), 10, 10, 10),
    AvailableMarketTypes.MONTH_FORWARD: ForwardOrderUpdaterParameters(
        duration(weeks=1), 10, 10, 20
    ),
    AvailableMarketTypes.YEAR_FORWARD: ForwardOrderUpdaterParameters(
        duration(months=1), 10, 10, 50
    ),
}


class ForwardPVStrategy(ForwardStrategyBase):
    """
    Strategy that models a PV that trades with a Standard Solar Profile on the forward
    exchanges.
    """

    def __init__(
        self,
        capacity_kW: float,
        order_updater_parameters: Dict[AvailableMarketTypes, ForwardOrderUpdaterParameters] = None,
    ):
        if not order_updater_parameters:
            order_updater_parameters = DEFAULT_PV_ORDER_UPDATER_PARAMS

        super().__init__(order_updater_parameters)
        self._energy_params = ProductionStandardProfileEnergyParameters(capacity_kW)

    @property
    def state(self) -> "PVState":
        return self._energy_params.state

    def event_activate(self, **kwargs):
        self._energy_params.event_activate_energy(self.area)

    def remove_open_orders(self, market: "ForwardMarketBase", market_slot: DateTime):
        offers = [
            offer
            for offer in market.slot_offer_mapping[market_slot]
            if offer.seller.name == self.owner.name
        ]
        for offer in offers:
            market.delete_offer(offer)

    def remove_order(self, market: "ForwardMarketBase", market_slot: DateTime, order_uuid: str):
        offers = [
            offer
            for offer in market.slot_offer_mapping[market_slot]
            if offer.seller.name == self.owner.name and offer.id == order_uuid
        ]
        if not offers:
            self.log.error(
                "Bid with id %s does not exist on the market %s %s.",
                order_uuid,
                market.market_type,
                market_slot,
            )
            return
        market.delete_offer(offers[0])

    def post_order(
        self,
        market: "ForwardMarketBase",
        market_slot: DateTime,
        order_rate: float = None,
        **kwargs
    ):
        if not order_rate:
            order_rate = self._order_updaters[market][market_slot].get_energy_rate(self.area.now)
        else:
            order_rate = Decimal(order_rate)
        capacity_percent = kwargs.get("capacity_percent")
        if not capacity_percent:
            capacity_percent = self._order_updaters[market][market_slot].capacity_percent / 100.0
        max_energy_kWh = self._energy_params.peak_energy_kWh * capacity_percent
        available_energy_kWh = self._energy_params.get_available_energy_kWh(
            market_slot, market.market_type
        )

        posted_energy_kWh = self._energy_params.get_posted_energy_kWh(
            market_slot, market.market_type
        )

        order_energy_kWh = Decimal(min(available_energy_kWh - posted_energy_kWh, max_energy_kWh))

        if order_energy_kWh <= FLOATING_POINT_TOLERANCE:
            return

        market.offer(
            float(order_rate * order_energy_kWh),
            float(order_energy_kWh),
            TraderDetails(self.owner.name, self.owner.uuid, self.owner.name, self.owner.uuid),
            original_price=float(order_rate * order_energy_kWh),
            time_slot=market_slot,
        )
        self._energy_params.increment_posted_energy(
            market_slot, float(order_energy_kWh), market.market_type
        )

    def event_traded(self, *, market_id: str, trade: "Trade"):
        """Method triggered by the MarketEvent.OFFER_TRADED event."""
        market = [
            market for market in self.area.forward_markets.values() if market_id == market.id
        ]
        if not market:
            return

        if trade.seller.uuid != self.owner.uuid:
            return

        self._energy_params.event_traded_energy(
            trade.traded_energy, trade.time_slot, market[0].market_type
        )
        self._energy_params.decrement_posted_energy(
            trade.time_slot, trade.traded_energy, market[0].market_type
        )
