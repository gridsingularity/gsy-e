from dataclasses import dataclass
from typing import Dict, TYPE_CHECKING, Optional, Union
from decimal import Decimal

from gsy_framework.constants_limits import FLOATING_POINT_TOLERANCE
from gsy_framework.data_classes import Trade, TraderDetails
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.exceptions import GSyException
from gsy_framework.utils import convert_pendulum_to_str_in_dict
from pendulum import DateTime, duration

from gsy_e.models.strategy.order_updater import OrderUpdaterParameters, OrderUpdater  # NOQA
from gsy_e.models.strategy.trading_strategy_base import TradingStrategyBase  # NOQA

if TYPE_CHECKING:
    from gsy_e.models.market import MarketBase


COMMUNITY_MIN_PRICE = 10
COMMUNITY_MAX_PRICE = 50


class ExternalValidator:
    """Validator for ExternalStrategy"""

    @staticmethod
    def validate_rate(*args, **kwargs):
        """Validate ExternalStrategy energy rates."""
        # TODO: Add validation of the energy rates inputs


@dataclass
class ExternalOrderUpdaterParameters(OrderUpdaterParameters):
    """Order updater parameters for the HeatPump"""

    update_interval: Optional[duration] = None
    initial_rate: Optional[Union[dict[DateTime, float], float, int]] = None
    final_rate: Optional[Union[dict[DateTime, float], float, int]] = None
    use_market_maker_rate: bool = False
    grid_fee: float = 0

    @staticmethod
    def _get_default_value_initial_rate(_):
        return COMMUNITY_MIN_PRICE

    def _get_default_value_final_rate(self, _):
        return COMMUNITY_MAX_PRICE + self.grid_fee

    def get_final_rate(self, time_slot: DateTime):
        if self.final_rate is None or self.use_market_maker_rate:
            return self._get_default_value_final_rate(time_slot)
        if isinstance(self.final_rate, (float, int)):
            return self.final_rate
        try:
            return self.final_rate[time_slot]
        except KeyError as exc:
            raise GSyException(
                f"Final rate profile does not contain timestamp {time_slot}"
            ) from exc

    def serialize(self):
        return {
            "update_interval": self.update_interval,
            "initial_buying_rate": (
                self.initial_rate
                if isinstance(self.initial_rate, (type(None), int, float))
                else convert_pendulum_to_str_in_dict(self.initial_rate)
            ),
            "final_buying_rate": (
                self.final_rate
                if isinstance(self.final_rate, (type(None), int, float))
                else convert_pendulum_to_str_in_dict(self.final_rate)
            ),
            "use_market_maker_rate": self.use_market_maker_rate,
        }


class ExternalEnergyParameters:
    """Energy parameters for the external strategy. Available and traded energy management."""

    def event_activate(self):
        """Update energy parameters during strategy startup."""

    def event_market_cycle(self, time_slot: DateTime):
        """Update energy parameters during the cycling of the markets."""

    def event_traded_energy(self, time_slot: DateTime, energy_kWh: Decimal):
        """Update energy parameters when a new trade has been created."""

    def serialize(self):
        """Get serializable dict of energy parameters."""

    def get_energy_demand_kWh(self, time_slot: DateTime):
        """Get the available energy demand or supply for specific timeslot."""


class ExternalMarket:

    def __init__(self, time_slot: DateTime):
        self.time_slot = time_slot

    def get_market_parameters_for_market_slot(self, time_slot: DateTime):
        pass


class ExternalStrategyBase(TradingStrategyBase):
    """Heat pump strategy base class"""

    def __init__(
        self,
        order_updater_parameters: Dict[
            AvailableMarketTypes, ExternalOrderUpdaterParameters
        ] = None,
    ):
        self._owner_name = "AssetOwner"
        self._owner_uuid = "OwnerUuid"
        self._spot_market = None
        self._energy_params = ExternalEnergyParameters()
        self.use_default_updater_params: bool = not order_updater_parameters
        if self.use_default_updater_params:
            order_updater_parameters = {
                AvailableMarketTypes.SPOT: ExternalOrderUpdaterParameters(),
            }
        else:
            for market_type in AvailableMarketTypes:
                if not order_updater_parameters.get(market_type):
                    continue
                ExternalValidator.validate_rate(
                    initial_buying_rate=order_updater_parameters[market_type].initial_rate,
                    final_buying_rate=order_updater_parameters[market_type].final_rate,
                    update_interval=order_updater_parameters[market_type].update_interval,
                    use_market_maker_rate=(
                        order_updater_parameters[market_type].use_market_maker_rate
                    ),
                )

        super().__init__(order_updater_parameters=order_updater_parameters)

    # pylint: disable=no-member
    def event_market_cycle(self) -> None:
        super().event_market_cycle()
        # TODO: Update market
        self._spot_market = self.area.spot_market
        if not self._spot_market:
            return

        # Order matters: First update the energy state and then post orders
        self._energy_params.event_market_cycle(self._spot_market.time_slot)

        self._post_orders_to_new_markets()

    def event_activate(self, **_kwargs):
        """Received activate event, signaling the trading strategy on-chain registration."""
        self._energy_params.event_activate()

    def event_tick(self):
        """Received tick event, signaling a new block creation."""
        self._update_open_orders()

    def event_bid_traded(self, *, market_id: str, bid_trade: Trade) -> None:
        """Received bid traded event, signaling a new trade event from a bid."""
        if bid_trade.buyer.origin_uuid != self._owner_uuid:
            return
        if not self._spot_market:
            return
        if market_id != self._spot_market.id:
            return
        time_slot = bid_trade.time_slot

        self._energy_params.event_traded_energy(time_slot, Decimal(-bid_trade.traded_energy))

    def event_offer_traded(self, *, market_id: str, bid_trade: Trade) -> None:
        """Received offer traded event, signaling a new trade event from an offer."""
        if bid_trade.buyer.origin_uuid != self._owner_uuid:
            return
        if not self._spot_market:
            return
        if market_id != self._spot_market.id:
            return
        time_slot = bid_trade.time_slot

        self._energy_params.event_traded_energy(time_slot, Decimal(bid_trade.traded_energy))

    def _post_order(
        self,
        order_energy_kWh: Decimal,
        order_rate: Optional[Decimal] = None,
    ):

        if order_energy_kWh <= FLOATING_POINT_TOLERANCE:
            return
        self._spot_market.bid(
            float(order_rate * order_energy_kWh),
            float(order_energy_kWh),
            original_price=float(order_rate * order_energy_kWh),
            buyer=TraderDetails(
                self._owner_name, self._owner_uuid, self._owner_name, self._owner_uuid
            ),
            time_slot=self._spot_market.time_slot,
        )

    def remove_open_orders(self):
        bids = [
            bid for bid in self._spot_market.bids.values() if bid.buyer.uuid == self._owner_uuid
        ]

        for bid in bids:
            self._spot_market.delete_bid(bid)

    def _create_order_updaters(self, market_type: AvailableMarketTypes):
        if not self._order_updater_for_market_slot_exists(
            self._spot_market.market, self._spot_market.time_slot
        ):
            if self._spot_market not in self._order_updaters:
                self._order_updaters[self._spot_market] = {}
            self._order_updaters[self._spot_market][self._spot_market.time_slot] = OrderUpdater(
                self._order_updater_params[market_type],
                self._spot_market.get_market_parameters_for_market_slot(
                    self._spot_market.time_slot
                ),
            )

    def _post_order_to_new_market(self, market_type=AvailableMarketTypes.SPOT):
        self._create_order_updaters(market, market_slot, market_type)
        self.post_order(market, market_slot)

    def _post_orders_to_new_markets(self) -> None:
        # TODO: If separate supply demand, should be managed here
        self._post_order_to_new_market()

    def _update_open_orders(self):
        for market, market_slot_updater_dict in self._order_updaters.items():
            if market is None:
                continue
            for market_slot, updater in market_slot_updater_dict.items():
                if updater.is_time_for_update(self.area.now):
                    self.remove_open_orders()
                    self.post_order(market, market_slot)

    @staticmethod
    def deserialize_args(constructor_args: Dict) -> Dict:
        """Deserialize the constructor arguments for the HeatPump strategy."""
        if "order_updater_parameters" not in constructor_args:
            constructor_args["order_updater_parameters"] = {
                AvailableMarketTypes.SPOT: ExternalOrderUpdaterParameters(
                    update_interval=(
                        duration(minutes=constructor_args.get("update_interval"))
                        if constructor_args.get("update_interval") is not None
                        else None
                    ),
                    initial_rate=constructor_args.get("initial_buying_rate", None),
                    final_rate=constructor_args.get("final_buying_rate", None),
                    use_market_maker_rate=constructor_args.get("use_market_maker_rate", False),
                )
            }
            constructor_args.pop("initial_buying_rate", None)
            constructor_args.pop("final_buying_rate", None)
            constructor_args.pop("update_interval", None)
            constructor_args.pop("use_market_maker_rate", None)
        return constructor_args

    def serialize(self):
        """Serialize strategy parameters."""
        return {
            **self._energy_params.serialize(),
            **self._order_updater_params.get(AvailableMarketTypes.SPOT).serialize(),
        }

    def post_order(self, order_rate: float = None, **_kwargs):
        """Submit new energy order."""
        if not order_rate:
            order_rate = self._order_updaters[self._spot_market][
                self._spot_market.time_slot
            ].get_energy_rate(self.area.now)
        else:
            order_rate = Decimal(order_rate)

        order_energy_kWh = Decimal(
            self._energy_params.get_energy_demand_kWh(time_slot=self._spot_market.time_slot)
        )
        self._post_order(order_energy_kWh, order_rate)
