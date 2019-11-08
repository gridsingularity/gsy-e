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
from d3a.events.event_structures import MarketEvent
from d3a.d3a_core.exceptions import InvalidTrade
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
import platform


if platform.python_implementation() != "PyPy" and \
        ConstSettings.BlockchainSettings.BC_INSTALLED is True:
    from d3a.models.market.blockchain_utils import create_market_contract, create_new_offer, \
        cancel_offer, trade_offer


BC_EVENT_MAP = {
    b"NewOffer": MarketEvent.OFFER,
    b"CancelOffer": MarketEvent.OFFER_DELETED,
    b"NewTrade": MarketEvent.TRADE,
    b"OfferChanged": MarketEvent.OFFER_CHANGED
}


class MarketBlockchainInterface:
    def __init__(self, bc):
        self.offers_deleted = {}  # type: Dict[str, Offer]
        self.offers_changed = {}  # type: Dict[str, (Offer, Offer)]
        self._trades_by_id = {}  # type: Dict[str, Trade]

        if bc:
            self.bc_interface = bc
            self.bc_contract = create_market_contract(bc,
                                                      GlobalConfig.sim_duration.in_seconds(),
                                                      [self.bc_listener])
        else:
            self.bc_interface = None

    def create_new_offer(self, energy, price, seller):
        if not self.bc_interface:
            return str(uuid.uuid4())
        else:
            return create_new_offer(self.bc_interface, self.bc_contract, energy, price, seller)

    def cancel_offer(self, offer):
        if self.bc_interface and offer:
            cancel_offer(self.bc_interface, self.bc_contract, offer)
            # Hold on to deleted offer until bc event is processed
            self.offers_deleted[offer.id] = offer

    def change_offer(self, offer, original_offer, residual_offer):
        if self.bc_interface:
            self.offers_changed[offer.id] = (original_offer, residual_offer)

    def handle_blockchain_trade_event(self, offer, buyer, original_offer, residual_offer):
        if not self.bc_interface:
            return str(uuid.uuid4()), residual_offer

        trade_id, new_offer_id = trade_offer(
            self.bc_interface, self.bc_contract, offer.real_id, offer.energy, buyer
        )

        if residual_offer is not None:
            if new_offer_id is None:
                raise InvalidTrade("Blockchain and local residual offers are out of sync")
            residual_offer.id = str(new_offer_id)
            residual_offer.real_id = new_offer_id
        return trade_id, residual_offer

    def track_trade_event(self, trade):
        if self.bc_interface:
            self._trades_by_id[trade.id] = trade

    def bc_listener(self):
        # TODO: Disabled for now, should be added once event driven blockchain transaction
        # handling is introduced
        # event_type = BC_EVENT_MAP[event['_event_type']]
        # kwargs = {}
        # if event_type is MarketEvent.OFFER:
        #     kwargs['offer'] = interface.offers[event['offerId']]
        # elif event_type is MarketEvent.OFFER_DELETED:
        #     kwargs['offer'] = interface.offers_deleted.pop(event['offerId'])
        # elif event_type is MarketEvent.OFFER_CHANGED:
        #     existing_offer, new_offer = interface.offers_changed.pop(event['oldOfferId'])
        #     kwargs['existing_offer'] = existing_offer
        #     kwargs['new_offer'] = new_offer
        # elif event_type is MarketEvent.TRADE:
        #     kwargs['trade'] = interface._trades_by_id.pop(event['tradeId'])
        # interface._notify_listeners(event_type, **kwargs)
        return
