from web3 import Web3, HTTPProvider
from solc import compile_source
from d3a.util import get_cached_joined_contract_source


web3 = Web3(HTTPProvider("http://127.0.0.1:8545", request_kwargs={'timeout': 600}))

coinbase = web3.eth.coinbase  #
web3.eth.defaultBlock = "latest"  #
transaction = {'from': coinbase}  #
# print(coinbase)

web3.personal.unlockAccount(web3.eth.accounts[0], 'testgsy')

compiled = compile_source(get_cached_joined_contract_source("DemoStorage"))
# print("Compiled: " + str(compiled))
contract_interface = compiled['<stdin>:' + 'DemoStorage']


# Instantiate and deploy contract
DemoStorage = web3.eth.contract(abi=contract_interface['abi'], bytecode=contract_interface['bin'])

web3.personal.unlockAccount(web3.eth.accounts[0], 'testgsy')

# Submit the transaction that deploys the contract
tx_hash = DemoStorage.constructor().transact({'from': web3.eth.accounts[0]})

# Wait for the transaction to be mined, and get the transaction receipt
tx_receipt = web3.eth.waitForTransactionReceipt(tx_hash)

# print("tx_receipt: " + str(tx_receipt))

# Create the contract instance with the newly-deployed address
demostorage_contract = web3.eth.contract(
    address=tx_receipt.contractAddress,
    abi=contract_interface['abi'],
)
# time.sleep(10)

# print("demostorage_contract: " + str(demostorage_contract))

for i in range(20):
    filt = web3.eth.filter('latest')
    web3.personal.unlockAccount(coinbase, 'testgsy')

    tx_hash = demostorage_contract.transact(transaction).set_power(4155 + i)

    # Wait for the transaction to be mined, and get the transaction receipt
    tx_receipt = web3.eth.waitForTransactionReceipt(transaction_hash=tx_hash, timeout=120)
    # print("tx_receipt: " + str(tx_receipt))
    new_trade_retval = demostorage_contract.events.NewPower().processReceipt(tx_receipt)
    print("New Power: " + str(new_trade_retval[0]["args"]["energyUnits"]))
    # event_filter = web3.eth.getFilterChanges(filt.filter_id)
    # print("event_filter: " + str(event_filter))


# time.sleep(10)


# a = demostorage_contract.call().get_power()
# print("Power: " + str(a))
