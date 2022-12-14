from dataclasses import dataclass
from typing import Dict, TYPE_CHECKING, Optional

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Trade, TraderDetails
from gsy_framework.enums import AvailableMarketTypes
from pendulum import DateTime, duration

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.gsy_e_core.util import (get_market_maker_rate_from_config,
                                   get_feed_in_tariff_rate_from_config)
from gsy_e.models.state import HeatPumpState
from gsy_e.models.strategy.energy_parameters.heat_pump import HeatPumpEnergyParameters
from gsy_e.models.strategy.order_updater import OrderUpdaterParameters, OrderUpdater
from gsy_e.models.strategy.trading_strategy_base import TradingStrategyBase

if TYPE_CHECKING:
    from gsy_e.models.market import MarketBase


@dataclass
class HeatPumpOrderUpdaterParameters(OrderUpdaterParameters):
    """Order updater parameters for the HeatPump"""
    update_interval: Optional[duration] = None
    initial_rate: Optional[float] = None
    final_rate: Optional[float] = None

    def update(self, market: "MarketBase", use_default: bool = False):
        """Update class members if set to None or if global default values should be used."""
        if use_default or self.update_interval is None:
            self.update_interval = duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)
        if use_default or self.final_rate is None:
            self.final_rate = get_market_maker_rate_from_config(market)
        if use_default or self.initial_rate is None:
            self.initial_rate = get_feed_in_tariff_rate_from_config(market)


class HeatPumpStrategy(TradingStrategyBase):
    """Strategy for heat pumps with storages."""

    # pylint: disable=too-many-arguments)
    def __init__(self,
                 maximum_power_rating: float = ConstSettings.HeatPumpSettings.MAX_POWER_RATING_KW,
                 min_temperatur_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C,
                 max_temperatur_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C,
                 external_temperatur_C: float = ConstSettings.HeatPumpSettings.EXT_TEMP_C,
                 tank_volume_l: float = ConstSettings.HeatPumpSettings.TANK_VOL_L,
                 average_consumption: float =
                 ConstSettings.HeatPumpSettings.CONSUMPTION_KW,
                 source_type: int = ConstSettings.HeatPumpSettings.SOURCE_TYPE,
                 order_updater_parameters: Dict[
                     AvailableMarketTypes, HeatPumpOrderUpdaterParameters] = None,
                 preferred_buying_rate: float =
                 ConstSettings.HeatPumpSettings.PREFERRED_BUYING_RATE
                 ):

        self.use_default_updater_params: bool = not order_updater_parameters

        if self.use_default_updater_params:
            order_updater_parameters = {
                AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters()}

        super().__init__(order_updater_parameters=order_updater_parameters)

        self._energy_params = HeatPumpEnergyParameters(
            maximum_power_rating=maximum_power_rating,
            min_temperatur_C=min_temperatur_C,
            max_temperatur_C=max_temperatur_C,
            external_temperatur_C=external_temperatur_C,
            tank_volume_l=tank_volume_l,
            average_consumption=average_consumption,
            source_type=source_type
        )

        self.preferred_buying_rate = preferred_buying_rate

    def serialize(self):
        """Return serialised energy params."""
        return {**self._energy_params.serialize()}

    @property
    def state(self) -> HeatPumpState:
        return self._energy_params.state

    def event_market_cycle(self) -> None:
        super().event_market_cycle()
        self._post_order_to_new_market(
            self.area.spot_market, self.area.spot_market.time_slot)

    def event_tick(self):
        self._update_open_orders()

    def event_bid_traded(self, *, _market_id: str, bid_trade: Trade) -> None:
        """TODO: to be tested in the frame of GSYE-426"""
        market = self.area.spot_market
        if not market:
            return

        time_slot = bid_trade.time_slot
        if bid_trade.buyer.origin_uuid != self.owner.uuid:
            return

        self._energy_params.event_traded_energy(market, time_slot)
        self._energy_params.decrement_posted_energy(market, time_slot)

    def remove_order(self, market: "MarketBase", market_slot: DateTime, order_uuid: str):
        pass

    def post_order(
            self, market: "MarketBase", market_slot: DateTime, order_rate: float = None, **kwargs):

        if not order_rate:
            order_rate = self._order_updaters[market][market_slot].get_energy_rate(
                self.area.now)
        order_energy_kWh = self._get_energy_buy_energy(order_rate, market_slot)

        if order_energy_kWh <= FLOATING_POINT_TOLERANCE:
            return

        market.bid(
            order_rate * order_energy_kWh, order_energy_kWh,
            original_price=order_rate * order_energy_kWh,
            buyer=TraderDetails(self.owner.name, self.owner.uuid,
                                self.owner.name, self.owner.uuid),
            time_slot=market_slot)

    def remove_open_orders(self, market: "MarketBase", market_slot: DateTime):
        if self.area.is_market_spot(market.id):
            bids = [bid
                    for bid in market.bids.values()
                    if bid.buyer.name == self.owner.name]
        else:
            bids = [bid
                    for bid in market.slot_bid_mapping[market_slot]
                    if bid.buyer.name == self.owner.name]

        for bid in bids:
            market.delete_bid(bid)

    def _get_energy_buy_energy(self, buy_rate: float, market_slot: DateTime) -> float:
        if buy_rate > self.preferred_buying_rate:
            return self._energy_params.energy_loss_kWh.get(market_slot, 1)
        return self._energy_params.energy_demand_kWh.get(market_slot, 1)

    def _create_order_updaters(
            self, market: "MarketBase", market_slot: DateTime, market_type: AvailableMarketTypes):
        if not self._order_updater_for_market_slot_exists(market, market_slot):
            if market not in self._order_updaters:
                self._order_updaters[market] = {}
            self._order_updater_params[market_type].update(market, self.use_default_updater_params)
            self._order_updaters[market][market_slot] = OrderUpdater(
                self._order_updater_params[market_type],
                market.get_market_parameters_for_market_slot(market_slot))

    def _post_order_to_new_market(self, market, market_slot,
                                  market_type=AvailableMarketTypes.SPOT):
        self._create_order_updaters(market, market_slot, market_type)
        self.post_order(market, market_slot)

    def _post_orders_to_new_markets(self):
        self._post_order_to_new_market(
            self.area.spot_market, self.area.spot_market.time_slot)

    def _update_open_orders(self):
        for market, market_slot_updater_dict in self._order_updaters.items():
            for market_slot, updater in market_slot_updater_dict.items():
                if updater.is_time_for_update(self.area.now):
                    self.remove_open_orders(market, market_slot)
                    self.post_order(market, market_slot)
