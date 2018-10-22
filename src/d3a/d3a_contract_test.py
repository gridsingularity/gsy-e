from web3 import Web3, HTTPProvider
import time
from solc import compile_source
from d3a.util import get_cached_joined_contract_source

web3 = Web3(HTTPProvider("http://127.0.0.1:8545", request_kwargs={'timeout': 600}))

web3.personal.unlockAccount(web3.eth.accounts[0], 'testgsy')
compiled = compile_source(get_cached_joined_contract_source("ClearingToken"))
contract_interface = compiled['<stdin>:' + 'ClearingToken']

##########################
# ###ClearingToken.sol####
#########################


# Instantiate and deploy contract
ClearingToken = web3.eth.contract(abi=contract_interface['abi'],
                                  bytecode=contract_interface['bin'])

web3.personal.unlockAccount(web3.eth.accounts[0], 'testgsy')

# Submit the transaction that deploys the contract
tx_hash = ClearingToken.constructor(10 ** 10, "ClearingToken", 0, "CT").\
    transact({'from': web3.eth.accounts[0]})

# Wait for the transaction to be mined, and get the transaction receipt
tx_receipt = web3.eth.waitForTransactionReceipt(tx_hash)

# print("tx_receipt: " + str(tx_receipt))

# Create the contract instance with the newly-deployed address
clearingtoken_contract = web3.eth.contract(
    address=tx_receipt.contractAddress,
    abi=contract_interface['abi'],
)

##################
# ###Market.sol####
##################

web3.personal.unlockAccount(web3.eth.accounts[0], 'testgsy')
compiled = compile_source(get_cached_joined_contract_source("Market"))
contract_interface = compiled['<stdin>:' + 'Market']


# Instantiate and deploy contract
Market = web3.eth.contract(abi=contract_interface['abi'], bytecode=contract_interface['bin'])

print(web3.personal.unlockAccount(web3.eth.accounts[0], 'testgsy'))

# Submit the transaction that deploys the contract
tx_hash = Market.constructor(clearingtoken_contract.address, 900).\
    transact({'from': web3.eth.accounts[0]})

# Wait for the transaction to be mined, and get the transaction receipt
tx_receipt = web3.eth.waitForTransactionReceipt(tx_hash)

# print("tx_receipt: " + str(tx_receipt))

# Create the contract instance with the newly-deployed address
market_contract = web3.eth.contract(
    address=tx_receipt.contractAddress,
    abi=contract_interface['abi'],
)
print("market_contract: " + str(market_contract))
time.sleep(10)
for i in range(10):
    energy = 100
    print(web3.personal.unlockAccount(web3.eth.accounts[1], 'testgsy'))
    print(web3.eth.accounts[1])

    tx_hash = \
        market_contract.functions.offer(energy, 30*energy).transact({"from": web3.eth.accounts[1]})
    tx_receipt = web3.eth.waitForTransactionReceipt(tx_hash)
    a = web3.eth.syncing
    while not a:
        a = web3.eth.syncing
    else:
        highest_block = a["highestBlock"]
        # print("Status: " + str(a))
        # print("Highest Block: " + str(highest_block))
        # print("Current Block: " + str(web3.eth.blockNumber))
        while web3.eth.blockNumber < highest_block:
            pass
    event = market_contract.events.NewOffer().processReceipt(tx_receipt)
    # offer_id = bytes(str(offer_id), 'utf-8')
    offer_id = market_contract.events.NewOffer().processReceipt(tx_receipt)[0]['args']["offerId"]
    print("ID Type: " + str(type(offer_id)))
    print("Offer id: {} & Event: {}".
          format(offer_id, market_contract.events.
                 NewOffer().processReceipt(tx_receipt)[0]['args']))
    get_offer = market_contract.functions.getOffer(offer_id).call()
    print("Offer ID: {} & Details: {}".format(offer_id, get_offer))

    print(web3.personal.unlockAccount(web3.eth.accounts[2], 'testgsy'))
    tx_hash = market_contract.functions.trade(bytes(offer_id), int(10000)).\
        transact({"from": web3.eth.accounts[2]})
    tx_receipt = web3.eth.waitForTransactionReceipt(transaction_hash=tx_hash, timeout=120)
    while not a:
        a = web3.eth.syncing
    else:
        highest_block = a["highestBlock"]
        # print("Status: " + str(a))
        # print("Highest Block: " + str(highest_block))
        # print("Current Block: " + str(web3.eth.blockNumber))
        while web3.eth.blockNumber < highest_block:
            pass
    trade_event = market_contract.events.NewTrade().processReceipt(tx_receipt)
    print("trade_event: " + str(trade_event))
    # event_filter = web3.eth.filter({"address": market_contract.address})
    # print("event_filter: " + str(event_filter))
