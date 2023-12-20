In the following section you will learn how to:

- [Setup your computer for Substrate development](#setup-your-computer-for-substrate-development)
- [Run the GSY DEX code](#run-the-gsy-dex-code)
- [Co-develop the GSY DEX](#co-develop-the-gsy-dex)
- [Connect external UI to the GSY DEX](#connect-external-ui-to-the-gsy-dex)
- [Run the GSY DEX code using docker-compose](#run-the-gsy-dex-code-using-docker-compose)


You will also be provided with information on [select pallets](#pallets) and choice of [primitives/data structures](#gsy-dex-primitives) to help you explore the [GSY DEX](blockchain.md) codebase.

### Setup your computer for Substrate development

Please install Rust toolchain and the Developer Tools following the instructions from Substrate [here](https://docs.substrate.io/main-docs/install/){target=_blank}.

### Run the GSY DEX code

The `cargo run` command will perform an initial build. Use the following command to build the node without launching it:

```commandline
cd gsy-node
cargo build --release
```

Once the project has been built, the following command can be used to explore all parameters and subcommands:

```commandline
./target/release/gsy-node -h
```

The `cargo run` command will launch a temporary node and its state will be discarded after you terminate the process.
This command will start the single-node development chain with persistent state. This is useful in order to not discard the state of the node once the node stops running:

```commandline
./target/release/gsy-node --dev
```
Purge the development chain's state:

```commandline
./target/release/gsy-node purge-chain --dev
```
Start the development chain with detailed logging:

```commandline
RUST_BACKTRACE=1 ./target/release/gsy-node -ldebug --dev
```
Integration with the current version of the [GSY Energy Exchange](https://github.com/gridsingularity/gsy-e){target=_blank} is also possible, with the objective of modelling, simulation and optimisation of energy marketplaces. To install, please refer to these [installation instructions](https://github.com/gridsingularity/gsy-e#basic-setup).

Once installation is completed, a new energy marketplace can be modelled following the instructions [here](general-settings.md#backend-simulation-configuration). The same marketplace can also be simulated using the GSY DEX as the exchange engine.  In order to switch to the GSY DEX and enable blockchain operations, the command-line flag `--enable-bc` should be used. The mnemonic of the GSY DEX account should also be provided, in order to authorise the exchange engine to restore your key when needed and interact as bids and offers’ aggregator on your behalf with the blockchain. Finally, the `ENABLE_SUBSTRATE` parameter should be set to True.

### Co-develop the GSY DEX
To develop and extend the GSY DEX features and applications please follow this guide, which is based on the [rustup](https://rustup.rs){target=_blank} installer tool for Rust toolchain management.

First install and configure `rustup`:
```commandline
# Install
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# Configure
source ~/.cargo/env
```
Configure the Rust toolchain to default to the latest stable version, add nightly and the nightly wasm target:
```commandline
rustup default stable
rustup update
rustup update nightly
rustup target add wasm32-unknown-unknown --toolchain nightly
```
In order to test your setup, the best way to ensure that you have successfully prepared a computer for the [GSY Node](blockchain-system-components-overview.md#gsy-node) development is to follow the steps in the [first Substrate tutorial](https://docs.substrate.io/tutorials/).

In order to run the code in developer mode, use Rust's native `cargo` command to build and launch the [GSY Node](blockchain-system-components-overview.md#gsy-node):
```commandline
cd gsy-node
cargo run --release -- --dev --tmp
```
You should always use the `--release` flag to build [optimised artifacts](https://docs.substrate.io/build/build-process/){target=_blank}.

The command-line options specify how you want the running node to operate. In this case, the `--dev` option specifies that the node runs in development mode using the predefined development chain specification.

By default, this option also deletes all active data - such as keys, the blockchain database, and networking information when you stop the node by pressing Control-c.

Using the `--dev` option ensures that you have a clean working state any time you stop and restart the node.

Verify your node is up and running successfully by reviewing the output displayed in the terminal.

The terminal should display output similar to this:

```commandline
2022-08-16 13:43:58 Substrate Node
2022-08-16 13:43:58 ✌️  version 4.0.0-dev-de262935ede
2022-08-16 13:43:58 ❤️  by Substrate DevHub <https://github.com/substrate-developer-hub>, 2017-2022
2022-08-16 13:43:58 📋 Chain specification: Development
2022-08-16 13:43:58 🏷  Node name: limping-oatmeal-7460
2022-08-16 13:43:58 👤 Role: AUTHORITY
2022-08-16 13:43:58 💾 Database: RocksDb at /var/folders/2_/g86ns85j5l7fdnl621ptzn500000gn/T/substrate95LPvM/chains/dev/db/full
2022-08-16 13:43:58 ⛓  Native runtime: node-template-100 (node-template-1.tx1.au1)
2022-08-16 13:43:58 🔨 Initializing Genesis block/state (state: 0xf6f5…423f, header-hash: 0xc665…cf6a)
2022-08-16 13:43:58 👴 Loading GRANDPA authority set from genesis on what appears to be first startup.
2022-08-16 13:43:59 Using default protocol ID "sup" because none is configured in the chain specs
2022-08-16 13:43:59 🏷  Local node identity is: 12D3KooWCu9uPCYZVsayaCKLdZLF8CmqiHkX2wHsAwSYVc2CxmiE
...
...
...
...
2022-08-16 13:54:26 💤 Idle (0 peers), best: #3 (0xcdac…26e5), finalized #1 (0x107c…9bae), ⬇ 0 ⬆ 0
```

If the block number, denoted by the logs that include the string `finalized #<block-number>`, is increasing, the [GSY Node](blockchain-system-components-overview.md#gsy-node) is producing new blocks and its consensus algorithm is operating correctly.

### Connect external UI to the GSY DEX

Once the node is running locally, you can connect it with the Polkadot-JS Apps User Interface to interact with the running node [here](https://polkadot.js.org/apps/#/explorer){target=_blank}.

### Run the GSY DEX code using Docker Compose

First, install [Docker](https://docs.docker.com/get-docker/){target=_blank} and [Docker Compose](https://docs.docker.com/compose/install/){target=_blank}.

Build and tag the docker image:

```commandline
docker build -t gsy_dex_image .
docker tag gsy_dex_image:latest gsy_dex_image:staging
```
and start docker-compose:

```commandline
docker-compose up
```

### Explore the GSY DEX code

A blockchain node is an application that allows users to participate in a blockchain network. Substrate-based blockchain nodes ensure a number of capabilities:

- Networking: Substrate nodes use the [libp2p](https://libp2p.io/){target=_blank} networking stack to allow the nodes in the network to communicate with one another.
- Consensus: Blockchains need to reach [consensus](https://docs.substrate.io/learn/consensus/){target=_blank} on the state of the network to validate transactions. Substrate facilitates custom consensus engines and includes a choice of consensus mechanisms built by the [Web3 Foundation research](https://research.web3.foundation/Polkadot/protocols/NPoS) community.
- RPC Server: A remote procedure call (RPC) server is used to interact with Substrate-based nodes.

There are several files in the node directory - take special note of the following:
- `chain_spec.rs`: A [chain specification](https://docs.substrate.io/build/chain-spec/){target=_blank} is a source code file that defines a Substrate chain's initial (genesis) state. Chain specifications are useful for development and testing, and critical when architecting the launch of a production chain. Take note of the `development_config` and `testnet_genesis` functions, which are used to define the genesis state for the local development chain configuration. These functions identify some [well-known accounts](https://docs.substrate.io/learn/accounts-addresses-keys/) and use them to configure the blockchain's initial state.
- `service.rs`: This file defines the node implementation. Take note of the libraries that this file imports and the names of the functions it invokes. In particular, there are references to consensus-related topics, such as the [longest chain rule](https://docs.substrate.io/learn/consensus/#finalization-and-forks){target=_blank}, the [Aura](https://paritytech.github.io/substrate/master/sc_consensus_aura/index.html){target=_blank} block authoring mechanism and the [GRANDPA](https://paritytech.github.io/substrate/master/sc_consensus_grandpa/index.html){target=_blank} finality gadget.

After the node has been built, refer to the embedded documentation to learn more about the capabilities and configuration parameters it facilitates:

```commandline
./target/release/gsy-node --help
```
#### Runtime

In Substrate, the terms "[runtime](https://docs.substrate.io/reference/glossary/#runtime){target=_blank}" and "[state transition function](https://docs.substrate.io/reference/glossary/#state-transition-function-stf){target=_blank}" are analogous and refer to the core logic of the blockchain that is responsible for validating blocks and executing the state changes. The gsy-node Rust package in this repository uses the [FRAME](https://docs.substrate.io/quick-start/substrate-at-a-glance/#what-is-frame){target=_blank} framework to construct a blockchain runtime. FRAME allows runtime developers to declare domain-specific logic in modules called "pallets". At the heart of FRAME is helpful [macro language](https://docs.substrate.io/reference/frame-macros/){target=_blank} that makes it easy to create and flexibly compose pallets to generate blockchains that can address a [variety of needs](https://substrate.io/ecosystem/projects/){target=_blank}.

Review the FRAME runtime implementation included in the node source code `./runtime/src/lib.rs` and note the following:

- This file configures several pallets to include in the runtime. Each pallet configuration is defined by a code block that begins with `impl $PALLET_NAME::Config for Runtime`.
- The pallets are composed into a single runtime by way of the [construct_runtime!](https://crates.parity.io/frame_support/macro.construct_runtime.html){target=_blank} macro, which is part of the core [FRAME Support library](https://docs.substrate.io/reference/frame-macros/#frame-support-and-system-macros){target=_blank}.

#### Pallets

The runtime in this project is constructed using many FRAME pallets that ship with the [core Substrate repository](https://github.com/paritytech/substrate/tree/master/frame){target=_blank} and `orderbook-registry`, `orderbook-worker` and `trades-settlement` pallets that are defined in the `./modules` directory.

A FRAME pallet is comprised of a number of blockchain primitives:

- Storage: FRAME defines a rich set of powerful [storage abstractions](https://docs.substrate.io/build/runtime-storage/){target=_blank} that makes it easy to use Substrate's efficient key-value database to manage the evolving state of a blockchain.
- Dispatchables: FRAME pallets define special types of functions that can be invoked (dispatched) from outside of the runtime in order to update its state.
- Events: Substrate uses [events and errors](https://docs.substrate.io/build/events-and-errors/){target=_blank} to notify users of important changes in the runtime.
- Errors: When a dispatchable fails, it returns an error.
- Config: The `Config` configuration interface is used to define the types and parameters upon which a FRAME pallet depends.

#### Order Book Registry Pallet

The Order Book Registry pallet provides a decentralised order book management system that allows users to register accounts, insert and delete orders, and manage proxies for delegating order management.

#### Pallet Overview

The pallet provides several key components:
1. User and Matching Engine Operator registration.
2. Proxy account management for users.
3. Order management, including insertion and deletion.


#### Storage Items
- `RegisteredUser`: Maps an `AccountId` to a `Hash` for registered users.
- `RegisteredMatchingEngine`: Maps an `AccountId` to a `Hash` for registered matching engine operators.
- `ProxyAccounts`: Maps an `AccountId` to a `BoundedVec` of `ProxyDefinition` for the registered proxy accounts.
- `OrdersRegistry`: Maps an [OrderReference](#bc-order-reference) to an [OrderStatus](#bc-order-status).

#### Events
- `MatchingEngineOperatorRegistered`: Emitted when a new matching engine operator is registered.
- `NewOrderInserted`: Emitted when a new order is inserted.
- `NewOrderInsertedByProxy`: Emitted when a new order is inserted by a proxy account.
- `OrderDeleted`: Emitted when an order is deleted.
- `OrderDeletedByProxy`: Emitted when an order is deleted by a proxy account.
- `ProxyAccountRegistered`: Emitted when a new proxy account is registered.
- `ProxyAccountUnregistered`: Emitted when a proxy account is unregistered.
- `UserRegistered`: Emitted when a new user is registered.

#### Errors
- `AlreadyRegistered`: Returned when an account is already registered.
- `AlreadyRegisteredProxyAccount`: Returned when a proxy account is already registered.
- `NoSelfProxy`: Returned when an account tries to register itself as a proxy account.
- `NotARegisteredMatchingEngineOperator`: Returned when an account is not a registered matching engine operator.
- `NotARegisteredProxyAccount`: Returned when an account is not a registered proxy account.
- `NotARegisteredUserAccount`: Returned when an account is not a registered user account.
- `NotARegisteredUserOrProxyAccount`: Returned when an account is not a registered user or proxy account.
- `NotRegisteredProxyAccounts`: Returned when there are no registered proxy accounts.
- `OpenOrderNotFound`: Returned when an open order is not found.
- `OrderAlreadyDeleted`: Returned when an order is already deleted.
- `OrderAlreadyExecuted`: Returned when an order is already executed.
- `OrderAlreadyInserted`: Returned when an order is already inserted.
- `ProxyAccountsLimitReached`: Returned when the proxy accounts limit has been reached.

#### Dispatchable Functions
- `insert_orders`: Insert an order with a given order hash for a registered user account.
- `insert_orders_by_proxy`: Insert an order with a given order hash for a registered user account by a registered proxy account.
- `delete_order`: Delete an order with a given order hash for a registered user account.
- `delete_order_by_proxy`: Delete an order with a given order hash for a registered user account by a registered proxy account.
- `register_proxy_account`: Register a new proxy account for a registered user account.
- `register_matching_engine_operator`: Register a new matching engine operator account.
- `register_user`: Register a new user account.
- `unregister_proxy_account`: Unregister a proxy account for a registered user account.

#### Helper Functions
- `add_matching_engine_operator`: Add a matching engine operator account.
- `add_proxy_account`: Add a proxy account for a registered user account.
- `add_user`: Add a user account.
- `is_order_registered`: Check if an order is registered.
- `is_registered_matching_engine_operator`: Check if an account is a registered matching engine operator.

#### GSY DEX Primitives

The implemented Rust code defines the primitive data structures used in the GSY DEX, such as types for block numbers, moments, signatures, public keys, account IDs, account indices, chain IDs, hashes, nonces, balances, headers, blocks, and extrinsics. Additionally, it exports the OrderReference and OrderStatus types from the [orders module](#the-orders-module).

Here is an overview of the input data types for the GSY DEX:

- `BlockNumber`: a type alias for a 64-bit unsigned integer used to represent block numbers
- `Moment`: a type alias for a 64-bit unsigned integer used to represent an instant or duration in time
- `Signature`: <a name="bc-primitive-signature"></a>a type alias for the `MultiSignature` type from the `sp_runtime` module. This type is used to represent a signature for a transaction. It allows one of several underlying cryptographic algorithms to be used, so it isn't a fixed size when encoded.
- `AccountPublic`: a type alias for the `Signer` associated type of the `Verify` trait implemented for [Signature](#bc-primitive-signature). This type represents the public key used for the [GSY Node](blockchain-system-components-overview.md#gsy-node) and is actually a `MultiSigner`. Like the signature, this type also isn't a fixed size when encoded, as different cryptographic algorithms have different size public keys.
- `AccountId`: a type alias for the `AccountId32` type associated with the IdentifyAccount trait implemented for `AccountPublic`. This type is an opaque account ID type and is always 32 bytes.
- `AccountIndex`: a type alias for a 32-bit unsigned integer used to represent the type for looking up accounts.
- `ChainId`: a type alias for a 32-bit unsigned integer used to represent the identifier for a chain.
- `Hash`: a type alias for the `H256` type from the `sp_core` module. This type is used to represent a hash of arbitrary data objects (e.g. asset identifiers, orderbook identifiers).
- `Nonce`: a type alias for a 32-bit unsigned integer used to represent the index of a transaction.
- `Balance`: a type alias for a 128-bit unsigned integer used to represent the balance of an account.
- `Header`: a type alias for the `generic::Header<BlockNumber, BlakeTwo256>` type from the `sp_runtime` module. This type represents the header of a block.
- `Block`: a type alias for the `generic::Block<Header, UncheckedExtrinsic>` type from the `sp_runtime` module. This type represents a block.
- `BlockId`: a type alias for the `generic::BlockId<Block>` type from the `sp_runtime` module. This type represents the ID of a block.
- `UncheckedExtrinsic`: an opaque, encoded, unchecked extrinsic that is used to represent a transaction.
- `OrderReference`: a type defined in the [orders](#the-orders-module) module that represents a reference to a [Bid](#bc-bid) or an [Offer](#bc-offer).
- `OrderStatus`: a type defined in the [orders](#the-orders-module) module that represents the status of a [Bid](#bc-bid) or an [Offer](#bc-offer).
- `mod orders`: a module that exports the [OrderReference](#bc-order-reference) and [OrderStatus](#bc-order-status) types.

#### The Orders Module
The orders module defines several types:

- `Order`: <a name="bc-order"></a>An enum representing the order in the GSY DEX, with two variants:
    - `Bid`: <a name="bc-bid"></a>A struct representing a bid order, including the buyer, nonce and the bid components.
    - `Offer`: <a name="bc-offer"></a>A struct representing an offer (ask) order, including the seller, nonce, and the offer components.
- `OrderStatus`: <a name="bc-order-status"></a>An enum that represents the status of an [Order](#bc-order), with three variants:
    - `Open`: The default status.
    - `Executed`: The order has been executed.
    - `Deleted`: The order has been cancelled.
- `OrderReference`: <a name="bc-order-reference"></a>A struct that represents a reference to an [Order](#bc-order) in the GSY DEX, with two fields:
    - `user_id`: The account ID of the user who created the order.
    - `hash`: The hash of the order struct which represents a unique reference of the [Order](#bc-order) object.
- `InputOrder`: An enum representing the input format of the order of the GSY DEX. It has two variants:
    - `InputBid`: A struct representing an input bid order, including the buyer and the bid components.
    - `InputOffer`: A struct representing an input offer (ask) order, including the seller and the offer components.
- `OrderComponent`: A struct representing the common components of an order, including area UUID, market UUID, time slot, creation time, energy, and energy rate.
- `OrderSchema`: A struct representing the schema of the order. It is needed in order to enforce the order book storage and other ancillary services to use the same schema/protocol for the [Order](#bc-order) struct as the [GSY Node](blockchain-system-components-overview.md#gsy-node).


#### The Trades Module

The `trades` module defines several types:

- `Trade`: A struct representing a trade, including the seller, buyer, market ID, trade UUID, creation time, time slot, offer, offer hash, bid, bid hash, residual offer, residual bid, and trade parameters.
- `TradeParameters`: A struct representing the trade parameters, including the selected energy, energy rate, and trade UUID.
- `BidOfferMatch`: A struct representing a bid and offer match, including the selected energy, energy rate, and trade UUID
- `Validator`: A trait defining the validation functions for the [trades](#the-trades-module) module.
