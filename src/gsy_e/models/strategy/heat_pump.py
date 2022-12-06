from typing import Dict, TYPE_CHECKING, Optional

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Trade
from gsy_framework.enums import AvailableMarketTypes
from pendulum import DateTime, duration

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.constants import FutureTemplateStrategiesConstants
from gsy_e.models.state import HeatPumpState
from gsy_e.models.strategy.energy_parameters.heat_pump import HeatPumpEnergyParameters
from gsy_e.models.strategy.new_base_strategy import NewStrategyBase
from gsy_e.models.strategy.order_updater import OrderUpdaterParameters, OrderUpdater

DEFAULT_HEAT_PUMP_ORDER_UPDATE_PARAMS = {
    AvailableMarketTypes.SPOT: OrderUpdaterParameters(
        initial_rate=ConstSettings.HeatPumpSettings.BUYING_RATE_RANGE.initial,
        final_rate=ConstSettings.HeatPumpSettings.BUYING_RATE_RANGE.final,
        update_interval=duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)),
    AvailableMarketTypes.FUTURE: OrderUpdaterParameters(
        initial_rate=FutureTemplateStrategiesConstants.INITIAL_BUYING_RATE,
        final_rate=FutureTemplateStrategiesConstants.FINAL_BUYING_RATE,
        update_interval=duration(
            minutes=FutureTemplateStrategiesConstants.UPDATE_INTERVAL_MIN)),
}

if TYPE_CHECKING:
    from gsy_e.models.market import MarketBase


class HeatPumpStrategy(NewStrategyBase):
    """Strategy for heat pumps with storages."""
    # pylint: disable=too-many-arguments)
    def __init__(self,
                 maximum_power_rating_kW: float =
                 ConstSettings.HeatPumpSettings.MAX_POWER_RATING_KW,
                 min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C,
                 max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C,
                 initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C,
                 external_temp_C: Optional[float] = None,
                 external_temp_profile_uuid: Optional[str] = None,
                 tank_volume_l: float = ConstSettings.HeatPumpSettings.TANK_VOL_L,
                 consumption_kW: Optional[float] = None,
                 consumption_profile_uuid: Optional[str] = None,
                 source_type: int = ConstSettings.HeatPumpSettings.SOURCE_TYPE,
                 order_updater_parameters: Dict[
                     AvailableMarketTypes, OrderUpdaterParameters] = None,
                 preferred_buying_rate: float =
                 ConstSettings.HeatPumpSettings.PREFERRED_BUYING_RATE
                 ):
        if not order_updater_parameters:
            order_updater_parameters = DEFAULT_HEAT_PUMP_ORDER_UPDATE_PARAMS

        super().__init__(order_updater_parameters=order_updater_parameters)

        self._energy_params = HeatPumpEnergyParameters(
            maximum_power_rating_kW=maximum_power_rating_kW,
            min_temp_C=min_temp_C,
            max_temp_C=max_temp_C,
            initial_temp_C=initial_temp_C,
            external_temp_C=external_temp_C,
            external_temp_profile_uuid=external_temp_profile_uuid,
            tank_volume_l=tank_volume_l,
            consumption_kW=consumption_kW,
            consumption_profile_uuid=consumption_profile_uuid,
            source_type=source_type
        )

        self.preferred_buying_rate = preferred_buying_rate
        self._markets_buffer = []  # TODO: discuss if this buffer is really necessary

    def serialize(self):
        """Return serialised energy params."""
        return {**self._energy_params.serialize()}

    @property
    def state(self) -> HeatPumpState:
        return self._energy_params.state

    def event_activate(self, **kwargs):
        self._energy_params.event_activate()
        self._populate_markets()

    def _populate_markets(self):
        self._markets_buffer = [self.area.spot_market]
        if ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS > 0:
            self._markets_buffer.append(self.area.future_markets)

    def event_market_cycle(self) -> None:
        super().event_market_cycle()
        current_market = self.area.current_market
        if not current_market:
            return
        self._energy_params.event_market_cycle(current_market.time_slot)
        self._post_orders_to_new_markets()

    def event_tick(self):
        self._update_open_orders()

    def event_bid_traded(self, *, market_id: str, bid_trade: Trade) -> None:
        """TODO: to be tested in the frame of GSYE-426"""
        market = [market for market in self._markets_buffer if market_id == market.id]
        if not market:
            return

        time_slot = bid_trade.time_slot
        if bid_trade.buyer_id != self.owner.uuid:
            return

        self._energy_params.event_traded_energy(time_slot, bid_trade.traded_energy)

    def remove_order(self, market: "MarketBase", market_slot: DateTime, order_uuid: str):
        """TODO: discuss if this is needed and decide: implement or pass"""

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
            buyer=self.owner.name,
            original_price=order_rate * order_energy_kWh,
            buyer_origin=self.owner.name,
            buyer_origin_id=self.owner.uuid,
            buyer_id=self.owner.uuid,
            time_slot=market_slot)

    def remove_open_orders(self, market: "MarketBase", market_slot: DateTime):
        if self.area.is_market_spot(market.id):
            bids = [bid
                    for bid in market.bids.values()
                    if bid.buyer == self.owner.name]
        else:
            bids = [bid
                    for bid in market.slot_bid_mapping[market_slot]
                    if bid.buyer == self.owner.name]

        for bid in bids:
            market.delete_bid(bid)

    def _get_energy_buy_energy(self, buy_rate: float, market_slot: DateTime) -> float:
        if buy_rate > self.preferred_buying_rate:
            return self._energy_params.get_min_energy_demand_kWh(market_slot)
        return self._energy_params.get_max_energy_demand_kWh(market_slot)

    def _create_order_updaters(self, market, market_slot, market_type):
        if not self._order_updater_for_market_slot_exists(market, market_slot):
            if market not in self._order_updaters:
                self._order_updaters[market] = {}
            self._order_updaters[market][market_slot] = OrderUpdater(
                self._order_updater_params[market_type],
                market.get_market_parameters_for_market_slot(market_slot))

    def _post_order_to_new_market(self, market, market_slot,
                                  market_type=AvailableMarketTypes.SPOT):
        self._create_order_updaters(market, market_slot, market_type)
        self.post_order(market, market_slot)

    def _post_orders_to_new_markets(self):
        for market in self._markets_buffer:
            print(market, self.area.is_market_spot(market.id))
            if self.area.is_market_spot(market.id):
                self._post_order_to_new_market(
                    self.area.spot_market, self.area.spot_market.time_slot)
            else:
                for market_slot in market.market_time_slots:
                    self._post_order_to_new_market(market, market_slot,
                                                   market_type=AvailableMarketTypes.FUTURE)

    def _update_open_orders(self):
        for market, market_slot_updater_dict in self._order_updaters.items():
            for market_slot, updater in market_slot_updater_dict.items():
                if updater.is_time_for_update(self.area.now):
                    self.remove_open_orders(market, market_slot)
                    self.post_order(market, market_slot)
