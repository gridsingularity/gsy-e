import uuid
from d3a.blockchain.utils import trade_offer
from d3a.exceptions import InvalidTrade
from d3a.models.events import MarketEvent


BC_EVENT_MAP = {
    b"NewOffer": MarketEvent.OFFER,
    b"CancelOffer": MarketEvent.OFFER_DELETED,
    b"NewTrade": MarketEvent.TRADE,
    b"OfferChanged": MarketEvent.OFFER_CHANGED
}


def handle_blockchain_trade_event(interface, offer, buyer, original_offer, residual_offer):
    if interface.bc_contract:
        trade_id, new_offer_id = trade_offer(interface.area.bc, interface.bc_contract,
                                             offer.real_id, offer.energy, buyer)

        if residual_offer is not None:
            if new_offer_id is None:
                raise InvalidTrade("Blockchain and local residual offers are out of sync")
            residual_offer.id = str(new_offer_id)
            residual_offer.real_id = new_offer_id
            interface._notify_listeners(
                MarketEvent.OFFER_CHANGED,
                existing_offer=original_offer,
                new_offer=residual_offer
            )
    else:
        trade_id = str(uuid.uuid4())
    return trade_id, residual_offer


def bc_listener(interface):
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
