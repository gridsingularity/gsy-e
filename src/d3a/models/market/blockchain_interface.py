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
from datetime import datetime
from d3a.events.event_structures import MarketEvent
from d3a.d3a_core.exceptions import InvalidTrade
from d3a.d3a_core.util import retry_function
from d3a.blockchain import ENABLE_SUBSTRATE, BlockChainInterface
import platform
import logging

logger = logging.getLogger()


if platform.python_implementation() != "PyPy" and ENABLE_SUBSTRATE:
    from d3a.blockchain.constants import mnemonic, \
        BOB_STASH_ADDRESS, ALICE_STASH_ADDRESS, \
        default_call_module, default_call_function, \
        address_type
    from d3a.models.market.blockchain_utils import create_new_offer, \
        cancel_offer, trade_offer
    from substrateinterface import Keypair  # NOQA
    from substrateinterface.exceptions import SubstrateRequestException

BC_EVENT_MAP = {
    b"NewOffer": MarketEvent.OFFER,
    b"CancelOffer": MarketEvent.OFFER_DELETED,
    b"NewTrade": MarketEvent.TRADE,
    b"OfferSplit": MarketEvent.OFFER_SPLIT
}


class NonBlockchainInterface:
    def __init__(self):
        pass

    def create_new_offer(self, energy, price, seller):
        return str(uuid.uuid4())

    def cancel_offer(self, offer):
        pass

    def change_offer(self, offer, original_offer, residual_offer):
        pass

    def handle_blockchain_trade_event(self, offer, buyer, original_offer, residual_offer):
        return str(uuid.uuid4()), residual_offer

    def track_trade_event(self, simulation_id, market_id, time_slot, trade):
        pass

    def bc_listener(self):
        pass


class SubstrateBlockchainInterface(BlockChainInterface):
    def __init__(self):
        super().__init__()

    def load_keypair(mnemonic):
        return Keypair.create_from_mnemonic(mnemonic, address_type=address_type)

    def compose_call(self, call_module, call_function, call_params):
        call = self.substrate.compose_call(
            call_module=call_module,
            call_function=call_function,
            call_params=call_params
        )
        return call

    def create_new_offer(self, energy, price, seller):
        return str(uuid.uuid4())

    def cancel_offer(self, offer):
        pass

    def change_offer(self, offer, original_offer, residual_offer):
        pass

    def handle_blockchain_trade_event(self, offer, buyer, original_offer, residual_offer):
        return str(uuid.uuid4()), residual_offer

    @retry_function(max_retries=3)
    def track_trade_event(self, simulation_id, market_id, time_slot, trade):
        print(f"track_trade_event: {trade}")

        call_params = {
            'simulation_id': str(simulation_id),
            'market_id': str(market_id),
            'market_slot': datetime.timestamp(time_slot),
            'trade_id': trade.id,
            'buyer': ALICE_STASH_ADDRESS,
            'seller': BOB_STASH_ADDRESS,
            'energy': int(trade.offer.energy),
            'rate': int(trade.offer.energy_rate)
        }

        call = self.substrate.compose_call(
            default_call_module,
            default_call_function,
            call_params
        )

        keypair = Keypair.create_from_mnemonic(mnemonic)
        extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=keypair)

        try:
            result = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            logger.info("Extrinsic '{}' sent and included in block '{}'".format(
                result['extrinsic_hash'], result['block_hash']))

        except SubstrateRequestException as e:
            logger.info("Failed to send: {}".format(e))

    def bc_listener(self):
        pass


class MarketBlockchainInterface:
    def __init__(self, bc):
        self.offers_deleted = {}
        self.offers_changed = {}
        self._trades_by_id = {}

        self.bc_interface = bc

    def create_new_offer(self, energy, price, seller):
        return create_new_offer(energy, price, seller)

    def cancel_offer(self, offer):
        cancel_offer(offer)
        # Hold on to deleted offer until bc event is processed
        self.offers_deleted[offer.id] = offer

    def change_offer(self, offer, original_offer, residual_offer):
        self.offers_changed[offer.id] = (original_offer, residual_offer)

    def handle_blockchain_trade_event(self, offer, buyer, original_offer, residual_offer):
        trade_id, new_offer_id = trade_offer(
            offer.real_id, offer.energy, buyer
        )

        if residual_offer is not None:
            if new_offer_id is None:
                raise InvalidTrade("Blockchain and local residual offers are out of sync")
            residual_offer.id = str(new_offer_id)
            residual_offer.real_id = new_offer_id
        return trade_id, residual_offer

    def track_trade_event(self, trade):
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
        # elif event_type is MarketEvent.OFFER_SPLIT:
        #     existing_offer, new_offer = interface.offers_changed.pop(event['oldOfferId'])
        #     kwargs['existing_offer'] = existing_offer
        #     kwargs['new_offer'] = new_offer
        # elif event_type is MarketEvent.TRADE:
        #     kwargs['trade'] = interface._trades_by_id.pop(event['tradeId'])
        # interface._notify_listeners(event_type, **kwargs)
        return
