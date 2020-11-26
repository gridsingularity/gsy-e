Currently D3A has optional blockchain support, meaning that instead of the Python-simulated blockchain, a private blockchain can be used instead.

There are 3 configuration parameters that control whether D3A is using blockchain, and which blockchain it uses (the default D3A blockchain, your own local blockchain, or a remote one). The most important one is the command-line option `--enable-bc`. This starts a simulation using a real blockchain, instead of using the simulated blockchain.

Currently it requires a substrate testnet created specifically for smart contracts. The blockchain connectivity can be enabled when the canvas node is running.

#TO DO: add a more detailed description of the canvas node and the polkadot wallet keys.
