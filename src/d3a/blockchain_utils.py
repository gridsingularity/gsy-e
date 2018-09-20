
BC_NUM_FACTOR = 10 ** 10


class InvalidBlockchainOffer(Exception):
    pass


class InvalidBlockchainTrade(Exception):
    pass


def create_market_contract(bc_interface, duration_s, listeners=[]):
    contract = bc_interface.init_contract(
        "Market.sol",
        "Market",
        [
            bc_interface.contracts['ClearingToken'].address,
            duration_s
        ],
        listeners
    )
    clearing_contract_instance = bc_interface.contracts['ClearingToken']
    market_address = contract.address
    tx_hash = clearing_contract_instance.functions\
        .globallyApprove(market_address, 10 ** 18)\
        .transact({'from': bc_interface.chain.eth.accounts[0]})
    tx_receipt = bc_interface.chain.eth.waitForTransactionReceipt(tx_hash)
    approve_retval = clearing_contract_instance.events\
        .ApproveClearingMember()\
        .processReceipt(tx_receipt)
    assert len(approve_retval) > 0
    assert approve_retval[0]["args"]["approver"] == bc_interface.chain.eth.accounts[0]
    assert approve_retval[0]["args"]["market"] == market_address
    assert approve_retval[0]["event"] == "ApproveClearingMember"
    return contract


def create_new_offer(bc_interface, bc_contract, energy, price, seller):
    tx_hash = bc_contract.functions.offer(
        int(energy * BC_NUM_FACTOR),
        int(price * BC_NUM_FACTOR)).transact({"from": bc_interface.users[seller].address})
    tx_receipt = bc_interface.chain.eth.waitForTransactionReceipt(tx_hash)
    offer_id = bc_contract.events \
        .NewOffer() \
        .processReceipt(tx_receipt)[0]['args']["offerId"]
    return offer_id


def cancel_offer(bc_interface, bc_contract, offer_id, seller):
    bc_interface.chain.eth.waitForTransactionReceipt(
        bc_contract.functions.cancel(offer_id).transact(
            {"from": bc_interface.users[seller].address}
        )
    )


def trade_offer(bc_interface, bc_contract, offer_id, energy, buyer):
    tx_hash = bc_contract.functions.trade(
        offer_id, int(energy * BC_NUM_FACTOR)
    ).transact({"from": bc_interface.users[buyer].address})
    tx_receipt = bc_interface.chain.eth.waitForTransactionReceipt(tx_hash)
    new_trade_retval = bc_contract.events.NewTrade().processReceipt(tx_receipt)
    offer_changed_retval = bc_contract.events \
        .OfferChanged() \
        .processReceipt(tx_receipt)

    if len(offer_changed_retval) > 0 and \
            not offer_changed_retval[0]['args']['success']:
        raise InvalidBlockchainOffer(f"Invalid blockchain offer changed. Transaction return "
                                     f"value {offer_changed_retval}")

    if not new_trade_retval[0]['args']['success']:
        raise InvalidBlockchainTrade(f"Invalid blockchain trade. Transaction return "
                                     f"value {new_trade_retval}")

    trade_id = new_trade_retval[0]['args']['tradeId']
    new_offer_id = offer_changed_retval[0]['args']['newOfferId'] \
        if len(offer_changed_retval) > 0 \
        else None
    return trade_id, new_offer_id
