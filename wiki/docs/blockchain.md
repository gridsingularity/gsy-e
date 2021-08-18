##Purpose
Grid Singularity energy exchange engine has been designed so that it does not require blockchain technology, but that it can benefit from this technology to provide enhanced functionality. 

Grid Singularity aims to integrate blockchain for specific benefits: 

1. **Decentralisation** and **transparency**: blockchain can be used to create decentralized registry and identity. By doing so, the privacy and security of users are enhanced.
2. **Data ownership** : End-users would have complete control over their data access and use
3. **Payments**: Trades cleared on the market will be recorded on the chain and the payments executed. While the privacy of users will be preserved, the system would be more transparent.
4. **Degrees of Freedom:** Bids and offers can be tagged with validated attributes to enable trading degrees of freedom such as preferred trading partner, energy source selection, or location restrictions on trades
5. **Asset validation**: energy assets, smart meters, and entities can be validated using tools like the [Energy Web Switchboard. ](https://switchboard-dev.energyweb.org/#/)

The [Energy Web Chain](https://www.energyweb.org/technology/energy-web-chain/) is the blockchain of choice for Grid Singularity Exchange future blockchain implementation. Grid Singularity, an energy technology startup, and the Rocky Mountain Institute, a nonprofit clean technology organisation, jointly founded the Energy Web Foundation (EWF) in January 2017. EWF is a nonprofit foundation gathering an ecosystem of over 100 energy corporations and startups with a shared, public blockchain platform, the Energy Web Chain. While Grid Singularity has significantly contributed to EWF development and the launch of the Energy Web Chain, its role today is supervisory and advisory, with two Grid Singularity representatives serving on [the EWF’s Foundation Council](https://www.energyweb.org/about/foundation-council/). 

At present, Grid Singularity Exchange blockchain integration is used just for simulated transactions and it is based on [Substrate](https://www.substrate.io/). We are also in the process of integrating with the [Energy Web Switchboard](https://switchboard-dev.energyweb.org/#/), which will be used as a **decentralized asset registry**. In the future we plan to move to full implementation on the Energy Web Chain, benefiting from [Polkadot’s](https://polkadot.network/) scaling solution.

The current basic blockchain integration uses Substrate, which allows modular business logic to be built directly in the blockchain and facilitates a high transaction throughput. Substrate has components called pallets, where each pallet can represent different functionality, such as **smart contracts, storage, auctions, and more**. Currently, our integration includes a storage pallet that provides immutable storage of executed transactions, and additional functionalities will continue to be actively developed. 

Blockchain can optionally be enabled on simulations running locally with the backend code base. There are three configuration parameters. The  command-line flag is  `--enable-bc`, used to enable blockchain operations. The two other parameters are the mnemonic to restore your key and interact with the blockchain, and the `ENABLE_SUBSTRATE` parameter described in the steps below.

##Connecting to Grid Singularity node

```html
https://polkadot.js.org/apps/?rpc=wss%3A%2F%2Fcanvas-node.dev.gridsingularity.com
```

When you go to the endpoint, you will see the standard interface. That’s the easiest point of interaction with the node, where you can call extrinsics, upload contracts, deploy them, test their functions, send funds and more.

##Simulating Grid Singularity local energy markets on Substrate

###Wallet
Ensure that you have the Polkadot Chrome extension (it is a browser extension that allows you to manage accounts for any Substrate-based blockchain). Create an account and save your seed phrase. You will need to save "your twelve words" mnemonic to be able to restore your key in general, and later to pass it the models/market/blockchain_utils.py in order to call the contracts on-chain from python code. Make sure never to push your mnemonic to GitHub.

###Balance
If you want to send a transaction manually or through Grid Singularity Exchange in the development chain, you need to pay transaction fees (`gas`), which requires that you have funds in your wallet. In the Polkadot User Interface, go to Network → Accounts where you will see a list of pre-funded addresses called Alice, Bob, and so on. There you can send funds to your newly generated address to be able to pay for the gas. Sending 10 Units will suffice for running hundreds of simulations. These pre-funded accounts serve as a faucet as they do not represent real financial value and the transactions are simulated. 

###Test pallet calls
It is possible to manually test the Developer → Extrinsics → tradestorage in the UI. You can choose the prefunded addresses as the buyer (Alice) and the seller (Bob). Set a small amount e.g. 1 and rate (e.g.12) (rate here is the price at which the trade is executed). Trade ID is a bytes vector (e.g. `0x1234`). If the extrinsic hash is successfully submitted, you will see a success message pop up in the top right corner of the UI. The Polkadot user interface does not allow you to directly go to that extrinsic hash, but you can go to Network and find the latest block. You may have to go to its parent or further to see the extrinsic hash.

###Running Grid Singularity Exchange with Substrate
Go to `src/d3a/blockchain/constants.py` and set `ENABLE_SUBSTRATE = True` and add your mnemonic. That will allow all the blockchain dependencies to be installed with:

```
fab sync
```

Each transaction in the simulation triggers a call to the pallet. Currently, the buyer and the seller are default addresses. In addition to the buyer and seller, the trade structure has a trade ID, energy quantity, and rate. Following Grid Singularity Exchange’s integration with the decentralized identity registry (Energy Web Switchboard), the addresses will be actual user accounts. In the terminal, you should see the extrinsic hash and the block hash.

```
17:39:37.466 WARNING  ( 333) d3a.d3a_core.simulation       : Slot 1 of 96 - (1.0%) 0.00 second elapsed, ETA: 0.01 second
17:39:41.974 INFO     ( 122) root                          : Extrinsic '0xe1357be7db683e0f3f85e101ea017da10fcaa63310e4dc7040e505cad9ac1a0a' sent and included in block '0x2199d0870583183e6f2c591b66e9a1a9cb2399b7b3ed21b21c3804c3cfcf730f'
17:39:41.975 INFO     ( 271) d3a.models.market.one_sided   : [TRADE] [Grid] [2021-01-26T00:00] {7f15aa} [origin: H1 Storage2 -> Cell Tower] [IAA House 1 -> Cell Tower] 0.025 kWh @ 0.7500000000000001 30.0 db09b600-22a9-4feb-ae4d-620cb6247702 [fee: 0.0 cts.]
```

The block hash will allow you to find your extrinsic hash, as in this [example](https://polkadot.js.org/apps/?rpc=wss%3A%2F%2Fcanvas-node.dev.gridsingularity.com#/explorer/query/0xf33563d5a2e3e5cef0629fa8c83b39a216fb2e61700855a67c232f800fe6b44e).

View events → tradestorage.TradeMapStored (this event is triggered every time we call the pallet’s store trade map function).
