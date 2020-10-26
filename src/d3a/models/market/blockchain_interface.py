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
from d3a.blockchain import ENABLE_SUBSTRATE
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from pathlib import Path
import platform
import random
import logging

logger = logging.getLogger()


if platform.python_implementation() != "PyPy" and \
        ConstSettings.BlockchainSettings.BC_INSTALLED is True:
    from d3a.models.market.blockchain_utils import create_market_contract, create_new_offer, \
        cancel_offer, trade_offer
    if ENABLE_SUBSTRATE is True:
        from d3a.models.market.blockchain_utils import get_function_metadata, \
            address_to_hex, swap_byte_order, BOB_ADDRESS, ALICE_ADDRESS, \
            test_value, test_rate, main_address, mnemonic, hex2
        from substrateinterface import SubstrateRequestException, Keypair  # NOQA


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

    def track_trade_event(self, trade):
        pass

    def bc_listener(self):
        pass


class SubstrateBlockchainInterface:
    def __init__(self, bc):
        self.contracts = {'main': main_address}
        self.substrate = bc

    def compose_call(self, data, contract_address):
        call = self.substrate.compose_call(
            call_module='Contracts',
            call_function='call',
            call_params={
                'dest': contract_address,
                'value': 1 * 10**18,
                'gas_limit': 1000000000000,
                'data': data
            }
        )
        return call

    def simple_contract_call(self, contract_address, function, path):
        data = get_function_metadata(function, path)
        call = self.compose_call(data, contract_address)
        return call

    def storage_contract_call(self, contract_address, function, path):
        trade_id = random.randint(10, 32)
        logger.info('TRADE ID {}'.format(trade_id))
        data = get_function_metadata(function, path) + hex2(trade_id) + \
            address_to_hex(ALICE_ADDRESS) + address_to_hex(BOB_ADDRESS) + \
            swap_byte_order(hex2(test_value)) + '000000000000000000' + hex2(test_rate)
        call = self.compose_call(data, contract_address)
        return trade_id, call

    def create_new_offer(self, energy, price, seller):
        return str(uuid.uuid4())

    def cancel_offer(self, offer):
        pass

    def change_offer(self, offer, original_offer, residual_offer):
        pass

    def handle_blockchain_trade_event(self, offer, buyer, original_offer, residual_offer):
        return str(uuid.uuid4()), residual_offer

    def track_trade_event(self, trade):
        path = Path.cwd().joinpath('src', 'd3a', 'models', 'market', 'metadata.json')
        trade_id, call = self.storage_contract_call(
            self.contracts['main'],
            "trade",
            str(path)
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
        self.bc_contract = create_market_contract(bc,
                                                  GlobalConfig.sim_duration.in_seconds(),
                                                  [self.bc_listener])

    def create_new_offer(self, energy, price, seller):
        return create_new_offer(self.bc_interface, self.bc_contract, energy, price, seller)

    def cancel_offer(self, offer):
        cancel_offer(self.bc_interface, self.bc_contract, offer)
        # Hold on to deleted offer until bc event is processed
        self.offers_deleted[offer.id] = offer

    def change_offer(self, offer, original_offer, residual_offer):
        self.offers_changed[offer.id] = (original_offer, residual_offer)

    def handle_blockchain_trade_event(self, offer, buyer, original_offer, residual_offer):
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
