import uuid
from typing import Dict, List, Set, Union  # noqa
from pendulum import DateTime
from logging import getLogger

from d3a.models.market.market_structures import Offer
from d3a.models.market.one_sided import OneSidedMarket
from d3a.models.events import MarketEvent
from d3a.models.market.market_structures import BalancingOffer, BalancingTrade
from d3a.exceptions import InvalidOffer, MarketReadOnlyException, OfferNotFoundException, \
    InvalidBalancingTradeException, DeviceNotInRegistryError
from d3a.device_registry import DeviceRegistry

log = getLogger(__name__)


class BalancingMarket(OneSidedMarket):
    def __init__(self, time_slot=None, area=None, notification_listener=None, readonly=False):
        self.unmatched_energy_upward = 0
        self.unmatched_energy_downward = 0
        self.accumulated_supply_balancing_trade_price = 0
        self.accumulated_supply_balancing_trade_energy = 0
        self.accumulated_demand_balancing_trade_price = 0
        self.accumulated_demand_balancing_trade_energy = 0

        OneSidedMarket.__init__(self, time_slot, area, notification_listener, readonly)

    def offer(self, price: float, energy: float, seller: str, balancing_agent: bool=False):
        return self.balancing_offer(price, energy, seller, balancing_agent)

    def balancing_offer(self, price: float, energy: float,
                        seller: str, balancing_agent: bool=False) -> BalancingOffer:
        if seller not in DeviceRegistry.REGISTRY.keys() and not balancing_agent:
            raise DeviceNotInRegistryError(f"Device {seller} "
                                           f"not in registry ({DeviceRegistry.REGISTRY}).")
        if self.readonly:
            raise MarketReadOnlyException()
        if energy == 0:
            raise InvalidOffer()
        offer = BalancingOffer(str(uuid.uuid4()), price, energy, seller, self)
        self.offers[offer.id] = offer
        self._sorted_offers = \
            sorted(self.offers.values(), key=lambda o: o.price / o.energy)
        log.info(f"[BALANCING_OFFER][NEW][{self.time_slot_str}] {offer}")
        self._notify_listeners(MarketEvent.BALANCING_OFFER, offer=offer)
        return offer

    def accept_offer(self, offer_or_id: Union[str, BalancingOffer], buyer: str, *,
                     energy: int = None, time: DateTime = None, price_drop:
                     bool = False) -> BalancingTrade:
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        residual_offer = None
        offer = self.offers.pop(offer_or_id, None)
        self._sorted_offers = sorted(self.offers.values(),
                                     key=lambda o: o.price / o.energy)
        if offer is None:
            raise OfferNotFoundException()
        if (offer.energy > 0 and energy < 0) or (offer.energy < 0 and energy > 0):
            raise InvalidBalancingTradeException("BalancingOffer and energy "
                                                 "are not compatible")
        try:
            if time is None:
                time = self._now
            if energy is not None:
                # Partial trade
                if energy == 0:
                    raise InvalidBalancingTradeException("Energy can not be zero.")
                elif abs(energy) < abs(offer.energy):
                    original_offer = offer
                    accepted_offer = Offer(
                        offer.id,
                        abs((offer.price / offer.energy) * energy),
                        energy,
                        offer.seller,
                        offer.market
                    )
                    residual_energy = (offer.energy - energy)
                    residual_offer = Offer(
                        str(uuid.uuid4()),
                        abs((offer.price / offer.energy) * residual_energy),
                        residual_energy,
                        offer.seller,
                        offer.market
                    )
                    self.offers[residual_offer.id] = residual_offer
                    log.info(f"[BALANCING_OFFER][CHANGED][{self.time_slot_str}] "
                             f"{original_offer} -> {residual_offer}")
                    offer = accepted_offer
                    self._sorted_offers = sorted(self.offers.values(),
                                                 key=lambda o: o.price / o.energy)
                    self._notify_listeners(
                        MarketEvent.BALANCING_OFFER_CHANGED,
                        existing_offer=original_offer,
                        new_offer=residual_offer
                    )
                elif abs(energy) > abs(offer.energy):
                    raise InvalidBalancingTradeException(
                        f"Energy {energy} can't be greater than offered energy {offer}"
                    )
                else:
                    # Requested partial is equal to offered energy - just proceed normally
                    pass
        except Exception:
            # Exception happened - restore offer
            self.offers[offer.id] = offer
            self._sorted_offers = sorted(self.offers.values(),
                                         key=lambda o: o.price / o.energy)
            raise
        trade = BalancingTrade(id=str(uuid.uuid4()), time=time, offer=offer,
                               seller=offer.seller, buyer=buyer,
                               residual=residual_offer, price_drop=price_drop)
        self.trades.append(trade)
        self._update_accumulated_trade_price_energy(trade)
        log.warning(f"[BALANCING_TRADE][{self.time_slot_str}] {trade}")
        self.traded_energy[offer.seller] += offer.energy
        self.traded_energy[buyer] -= offer.energy
        self.ious[buyer][offer.seller] += offer.price
        self._update_min_max_avg_trade_prices(offer.price / offer.energy)
        # Recalculate offer min/max price since offer was removed
        self._update_min_max_avg_offer_prices()
        offer._traded(trade, self)
        self._notify_listeners(MarketEvent.BALANCING_TRADE, trade=trade)
        return trade

    def delete_balancing_offer(self, offer_or_id: Union[str, BalancingOffer]):
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        offer = self.offers.pop(offer_or_id, None)
        self._sorted_offers = sorted(self.offers.values(), key=lambda o: o.price / o.energy)
        self._update_min_max_avg_offer_prices()
        if not offer:
            raise OfferNotFoundException()
        log.info(f"[BALANCING_OFFER][DEL][{self.time_slot_str}] {offer}")
        self._notify_listeners(MarketEvent.BALANCING_OFFER_DELETED, offer=offer)

    def _update_accumulated_trade_price_energy(self, trade):
        if trade.offer.energy > 0:
            self.accumulated_supply_balancing_trade_price += trade.offer.price
            self.accumulated_supply_balancing_trade_energy += trade.offer.energy
        elif trade.offer.energy < 0:
            self.accumulated_demand_balancing_trade_price += trade.offer.price
            self.accumulated_demand_balancing_trade_energy += abs(trade.offer.energy)

    @property
    def avg_supply_balancing_trade_rate(self):
        price = self.accumulated_supply_balancing_trade_price
        energy = self.accumulated_supply_balancing_trade_energy
        return round(price / energy, 4) if energy else 0

    @property
    def avg_demand_balancing_trade_rate(self):
        price = self.accumulated_demand_balancing_trade_price
        energy = self.accumulated_demand_balancing_trade_energy
        return round(price / energy, 4) if energy else 0
