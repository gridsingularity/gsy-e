mnemonic = "MNEMONIC_TO_RESTORE_YOUR_KEYPAIR"

BC_NUM_FACTOR = 10 ** 12
BOB_STASH_ADDRESS = "5HpG9w8EBLe5XCrbczpwq5TSXvedjrBGCwqxK1iQ7qUsSWFc"
ALICE_STASH_ADDRESS = "5GNJqTPyNqANBkUVMN1LPPrxXnFouWXoe2wNSmmEoLctxiZY"

default_call_module = 'Tradestorage'
default_call_function = 'store_trade_map'
default_amount = {
    'free': 1 * BC_NUM_FACTOR,
    'reserved': 0,
    'miscFrozen': 0,
    'feeFrozen': 0
}
default_rate = 12
address_type = 42
