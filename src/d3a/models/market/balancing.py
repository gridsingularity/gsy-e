"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import uuid
from typing import Union  # noqa
from pendulum import DateTime
from logging import getLogger

from d3a.models.market.market_structures import Offer
from d3a.models.market.one_sided import OneSidedMarket
from d3a.events.event_structures import MarketEvent
from d3a.models.market.market_structures import BalancingOffer, BalancingTrade
from d3a.d3a_core.exceptions import InvalidOffer, MarketReadOnlyException, \
    OfferNotFoundException, InvalidBalancingTradeException, \
    DeviceNotInRegistryError
from d3a.d3a_core.device_registry import DeviceRegistry
from d3a.constants import FLOATING_POINT_TOLERANCE

log = getLogger(__name__)


class BalancingMarket(OneSidedMarket):
    def __init__(self, time_slot=None, bc=None, notification_listener=None, readonly=False,
                 transfer_fees=None, name=None):
        self.unmatched_energy_upward = 0
        self.unmatched_energy_downward = 0
        self.accumulated_supply_balancing_trade_price = 0
        self.accumulated_supply_balancing_trade_energy = 0
        self.accumulated_demand_balancing_trade_price = 0
        self.accumulated_demand_balancing_trade_energy = 0

        super().__init__(time_slot, bc, notification_listener, readonly, transfer_fees, name)

    def offer(self, price: float, energy: float, seller: str, iaa_fee: bool = False,
              original_offer_price=None, seller_origin=None):
        assert False

    def balancing_offer(self, price: float, energy: float,
                        seller: str, from_agent: bool=False,
                        iaa_fee: bool = False,
                        seller_origin=None) -> BalancingOffer:
        if seller not in DeviceRegistry.REGISTRY.keys() and not from_agent:
            raise DeviceNotInRegistryError(f"Device {seller} "
                                           f"not in registry ({DeviceRegistry.REGISTRY}).")
        if self.readonly:
            raise MarketReadOnlyException()
        if energy == 0:
            raise InvalidOffer()
        if iaa_fee:
            price = price * (1 + self.transfer_fee_ratio) + self.transfer_fee_const * energy

        offer = BalancingOffer(str(uuid.uuid4()), price, energy, seller,
                               seller_origin=seller_origin)
        self.offers[offer.id] = offer
        self._sorted_offers = \
            sorted(self.offers.values(), key=lambda o: o.price / o.energy)
        self.offer_history.append(offer)
        log.debug(f"[BALANCING_OFFER][NEW][{self.time_slot_str}] {offer}")
        self._notify_listeners(MarketEvent.BALANCING_OFFER, offer=offer)
        return offer

    def accept_offer(self, offer_or_id: Union[str, BalancingOffer], buyer: str, *,
                     energy: int = None, time: DateTime = None,
                     already_tracked: bool = False, trade_rate: float = None,
                     trade_bid_info: float = None,
                     buyer_origin=None) -> BalancingTrade:
        if self.readonly:
            raise MarketReadOnlyException()
        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        offer = self.offers.pop(offer_or_id, None)
        if offer is None:
            raise OfferNotFoundException()
        if (offer.energy > 0 and energy < 0) or (offer.energy < 0 and energy > 0):
            raise InvalidBalancingTradeException("BalancingOffer and energy "
                                                 "are not compatible")
        if energy is None:
            energy = offer.energy

        original_offer = offer
        residual_offer = None

        if trade_rate is None:
            trade_rate = offer.price / offer.energy

        orig_offer_price = self._calculate_original_prices(
            offer
        )

        self._sorted_offers = sorted(self.offers.values(),
                                     key=lambda o: o.price / o.energy)
        try:
            if time is None:
                time = self.now

            energy_portion = energy / offer.energy
            if energy == 0:
                raise InvalidBalancingTradeException("Energy can not be zero.")
            # partial energy is requested
            elif abs(energy) < abs(offer.energy):
                original_offer = offer
                accepted_offer_id = offer.id if self.bc is None else offer.real_id

                assert trade_rate + FLOATING_POINT_TOLERANCE >= (offer.price / offer.energy)

                final_price = self._update_offer_fee_and_calculate_final_price(
                    energy, trade_rate, energy_portion, orig_offer_price
                ) if already_tracked is False else energy * trade_rate

                accepted_offer = Offer(
                    accepted_offer_id,
                    abs(final_price),
                    energy,
                    offer.seller,
                    seller_origin=offer.seller_origin
                )

                residual_price = (1 - energy_portion) * offer.price
                residual_energy = offer.energy - energy
                original_residual_price = \
                    ((offer.energy - energy) / offer.energy) * orig_offer_price

                residual_offer = Offer(
                    str(uuid.uuid4()),
                    abs(residual_price),
                    residual_energy,
                    offer.seller,
                    original_offer_price=original_residual_price,
                    seller_origin=offer.seller_origin
                )
                self.offers[residual_offer.id] = residual_offer
                log.debug(f"[BALANCING_OFFER][CHANGED][{self.time_slot_str}] "
                          f"{original_offer} -> {residual_offer}")
                offer = accepted_offer

                self.bc_interface.change_offer(offer, original_offer, residual_offer)
                self._sorted_offers = sorted(self.offers.values(),
                                             key=lambda o: o.price / o.energy)
                self._notify_listeners(
                    MarketEvent.BALANCING_OFFER_CHANGED,
                    existing_offer=original_offer,
                    new_offer=residual_offer
                )
            elif abs(energy) > abs(offer.energy):
                raise InvalidBalancingTradeException("Energy can't be greater than offered energy")
            else:
                # Requested energy is equal to offer's energy - just proceed normally
                offer.price = self._update_offer_fee_and_calculate_final_price(
                    energy, trade_rate, 1, orig_offer_price
                ) if already_tracked is False else energy * trade_rate

        except Exception:
            # Exception happened - restore offer
            self.offers[offer.id] = offer
            self._sorted_offers = sorted(self.offers.values(),
                                         key=lambda o: o.price / o.energy)
            raise

        trade_id, residual_offer = \
            self.bc_interface.handle_blockchain_trade_event(
                offer, buyer, original_offer, residual_offer
            )
        trade = BalancingTrade(trade_id, time, offer, offer.seller, buyer,
                               residual_offer, seller_origin=offer.seller_origin,
                               buyer_origin=buyer_origin)
        self.bc_interface.track_trade_event(trade)

        if already_tracked is False:
            self._update_stats_after_trade(trade, offer, buyer)
            log.info(f"[BALANCING_TRADE] [{self.time_slot_str}] {trade}")

        # TODO: Use non-blockchain non-event-driven version for now for both blockchain and
        # normal runs.
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
        log.debug(f"[BALANCING_OFFER][DEL][{self.time_slot_str}] {offer}")
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
