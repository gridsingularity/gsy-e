# import time
from d3a import wait_until_timeout_blocking


BC_NUM_FACTOR = 10 ** 10


class InvalidBlockchainOffer(Exception):
    pass


class InvalidBlockchainTrade(Exception):
    pass


def _wait_for_node_synchronization(bc_interface):
    node_status = bc_interface.chain.eth.syncing
    while not node_status:
        node_status = bc_interface.chain.eth.syncing
    else:
        highest_block = node_status["highestBlock"]
        # print("Status: " + str(a))
        # print("Highest Block: " + str(highest_block))
        # print("Current Block: " + str(web3.eth.blockNumber))
        while bc_interface.chain.eth.blockNumber < highest_block:
            pass
        # else:
        #     print("Current Block: " +
        #           str(web3.eth.blockNumber))


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

    bc_interface.chain.personal.unlockAccount(bc_interface.chain.eth.accounts[0], 'testgsy')
    tx_hash = clearing_contract_instance.functions\
        .globallyApprove(market_address, 10 ** 18)\
        .transact({'from': bc_interface.chain.eth.accounts[0]})
    tx_receipt = bc_interface.chain.eth.waitForTransactionReceipt(tx_hash)
    approve_retval = clearing_contract_instance.events\
        .ApproveClearingMember()\
        .processReceipt(tx_receipt)
    _wait_for_node_synchronization(bc_interface)
    assert len(approve_retval) > 0
    assert approve_retval[0]["args"]["approver"] == bc_interface.chain.eth.accounts[0]
    assert approve_retval[0]["args"]["market"] == market_address
    assert approve_retval[0]["event"] == "ApproveClearingMember"
    return contract


def create_new_offer(bc_interface, bc_contract, energy, price, seller):
    print(bc_interface.chain.personal.unlockAccount(bc_interface.users[seller].address, 'testgsy'))
    print("Address: " + str(bc_interface.users[seller].address))
    bc_energy = int(energy * BC_NUM_FACTOR)
    print("Offered Energy: " + str(bc_energy))
    tx_hash = bc_contract.functions.offer(
        bc_energy,
        int(price * BC_NUM_FACTOR)).transact({"from": bc_interface.users[seller].address})
    tx_receipt = bc_interface.chain.eth.waitForTransactionReceipt(tx_hash, timeout=200)
    _wait_for_node_synchronization(bc_interface)
    offer_id = bc_contract.events.NewOffer().processReceipt(tx_receipt)[0]['args']["offerId"]
    print("ID Type: " + str(type(offer_id)))
    print("Offer id: {} & Event: {}".format(offer_id, bc_contract.events.
                                            NewOffer().processReceipt(tx_receipt)[0]['args']))
    get_offer = bc_contract.functions.getOffer(offer_id).call()
    print("Offer ID: {} & Details: {}".format(offer_id, get_offer))
    # while get_offer[0] == 0:
    #     time.sleep(1)
    #     get_offer = bc_contract.functions.getOffer(offer_id).call()
    # else:
    #     print("Offer ID: {} & Details: {}".format(offer_id, get_offer))
    # return offer_id

    def get_offer():
        print("Waiting for offers")
        return bc_contract.functions.getOffer(offer_id).call() is not 0

    assert wait_until_timeout_blocking(get_offer, timeout=20)
    return offer_id


def cancel_offer(bc_interface, bc_contract, offer_id, seller):
    bc_interface.chain.personal.unlockAccount(bc_interface.users[seller].address, 'testgsy')
    bc_interface.chain.eth.waitForTransactionReceipt(
        bc_contract.functions.cancel(offer_id).transact(
            {"from": bc_interface.users[seller].address}
        )
    )


def trade_offer(bc_interface, bc_contract, offer_id, energy, buyer):
    bc_interface.chain.personal.unlockAccount(bc_interface.users[buyer].address, 'testgsy')
    print("Balance: " + str(bc_interface.chain.eth.getBalance(bc_interface.users[buyer].address)))
    print("Buyer: " + str(buyer))
    print("Trade id: " + str(offer_id))
    trade_energy = int(energy * BC_NUM_FACTOR)
    print("Traded Energy: " + str(trade_energy))
    print(offer_id)
    offer_id = bytes(offer_id)
    print(f'Trade seller {bc_interface.users[buyer].address}')
    tx_hash = bc_contract.functions.trade(offer_id, trade_energy).\
        transact({"from": bc_interface.users[buyer].address})
    print("tx_hash: " + str(tx_hash))
    tx_receipt = bc_interface.chain.eth.waitForTransactionReceipt(tx_hash)
    print("tx_receipt: " + str(tx_receipt))
    _wait_for_node_synchronization(bc_interface)

    new_trade_retval = bc_contract.events.NewTrade().processReceipt(tx_receipt)

    print("new_trade_retval: " + str(new_trade_retval))
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
