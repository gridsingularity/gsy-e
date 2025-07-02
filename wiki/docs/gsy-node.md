GSY Node, a set of blockchain validator nodes, comprises the backbone of the Grid Singularity Decentralised Exchange - [GSY DEX](blockchain.md){target=_blank}, responsible for network activities, settling and executing blockchain state transitions. It enables secure data and data service exchange and defines how different types of market participants and service providers interact, including blockchain validators, exchange operators, aggregators (energy service providers managing energy assets, usually technically managing energy communities), grid operators, and others. Another critical function of the GSY Node is communication of transactional data directly to the blockchain, ensuring the immutability of transactions and the integrity of exchanged information. This secure data communication mechanism is essential for enabling verified energy and flexibility trades, and maintaining consensus across a decentralised system, fostering scalability, transparency and trust.

The section below describes the GSY Node implementation, including its runtime, pallets, primitives and modules. In addition, guidance is provided on installation and potential co-development.


### GSY Node Implementation

GSY Node is programmed using Parity’s [Substrate](https://polkadot.com/platform/sdk/){target=_blank}, also termed Polkadot software development kit (SDK), customising and deploying different pallets to build  components to run a blockchain network for an energy exchange. It consists of two subcomponents that extend the [Substrate](https://polkadot.com/platform/sdk/){target=_blank} runtime and set the operational framework for GSY DEX services:

1. Client with external node services: This component handles network activities such as peer discovery, managing transaction requests, reaching consensus with peers, and responding to remote procedure calls (Substrate [RPC](https://docs.substrate.io/build/remote-procedure-calls/){target=_blank}).
2. Custom runtime: This component contains the business logic for executing the state transition functions of the blockchain. The custom runtime is designed to improve performance, scalability and security, avoiding and mitigating multiple blockchain attack types more effectively than by using smart contracts or a generalised virtual machine. To facilitate auditability and thereby safeguard trust, the critical functions of order registration, as well as trade settlement, execution and clearing are performed on-chain. In contrast, to address scalability and data privacy constraints, the supporting functions of bid and order matching and general user management are performed off-chain. The core on-chain business logic is provided by these pallets: Order Book (and related Order Worker pallet), [Trade Settlement](blockchain-matching-engine.md#gsy-dex-matching-engine-gsy-node-communication-trade-settlement-pallet){target=_blank} and [Trade Execution](blockchain-execution-engine.md#trade-execution-pallet-gsy-dex-execution-engine-gsy-node-communication){target=_blank}, with the latter including the Penalties Registry.

To support the above, GSY Node incorporates different pallets that implement different functionalities of the GSY DEX.  Its Collateral Management System manages different user accounts of the GSY DEX. It incorporates the User, Proxy and Matching Registry pallets, which are responsible for registration of different GSY DEX users. Moreover, each user is associated with a Vault pallet that maintains and manages the collateral used for transactions in the GSY DEX. As for order book management, it is performed via the Order Book Registry and Order Book Worker pallets, which are responsible for registering the orders that GSY DEX receives, and to forward them to external node services. Finally, there is an option to implement a remuneration service directly in the GSY Node as a separate Substrate pallet (enabling a Payment Worker), which operates alongside other GSY DEX pallets within the GSY Node, interacting with the third party payment providers. This type of a payment service is under development in the framework of an EU co-financed [FEDECOM](https://fedecom-project.eu/){target=_blank} project by [SUPSI](https://www.supsi.ch/){target=_blank}, benefiting from the GSY DEX common infrastructure and runtime environment to simplify deployment and improve overall system coherence.

This structure ensures a range of capabilities:

- Networking: Substrate nodes use the `libp2p` networking stack to allow the nodes in the network to communicate with one another.
- Consensus: Blockchains need to reach [consensus](https://docs.substrate.io/v3/advanced/consensus){target=_blank} on the state of the network to validate transactions. Substrate facilitates custom consensus engines and includes a choice of consensus mechanisms built by the [Web3 Foundation research](https://research.web3.foundation/en/latest/polkadot/NPoS/index.html){target=_blank} community.
- RPC Server: A remote procedure call (RPC) server is used to interact with Substrate-based nodes.

For instance, the select consensus mechanism for validating transactions in the GSY DEX implementation proof-of-concept canary test networks used for research and innovation projects is Proof-of-Authority (PoA), which deploys dedicated preauthorised validator nodes, comprising trusted validators (legal entities with interest to support the network operation). This is similar to Proof-of-Stake (PoS), whereby the stake is the reputation and legal standing of the validator. The selected consensus mechanism provides the following advantages:

- Ensures the blockchain network’s integrity and reliability, since its validator nodes’ identity is legally defined. This is particularly important for energy community trading operations, which require sensitive data, including energy measurements and anonymised user identities that can be managed only by trusted entities. PoA envisages that only preauthorised trusted entities will engage in on-chain data processing, effectively prohibiting any malicious actors to process, view or tamper with sensitive data.
- Improves the blockchain performance. PoA (and more generally PoS) supports a much higher transaction throughput than Proof-of-Work. Currently, the Polkadot network can manage up to more than [140,000 transactions per second](https://polkadot.com/reports/polkadot-spammening-report-2024.pdf){target=_blank}, which starkly contrasts with Bitcoin’s limit to [7 transactions per second](https://ieeexplore.ieee.org/abstract/document/8215367){target=_blank}. Moreover, the transaction latency is low due to the predefined validator nodes, facilitating a fast validation process.
- Improves the energy efficiency and minimises the carbon footprint of the blockchain. Since the energy-intensive mining process included in many Proof-of-Work blockchains (notably Bitcoin, Litecoin) is not used in PoA, the energy requirements of the GSY Node are limited to the energy consumption of the validator nodes, resulting in more than [99% decrease](https://www.carbon-ratings.com/dl/pos-report-2022){target=_blank} in electricity consumption.

The importance of sensitive data management for the EU co-financed research and innovation projects was reflected in the implementation of GSY Node as a Substrate node to operate the test network. A public, enterprise-grade open-source blockchain designed to handle the specific needs of the energy sector such as the [Energy Web Chain](https://www.energyweb.org/){target=_blank} could be leveraged to deploy the GSY Node pallets in future commercial applications, which would have the advantage of integration with other complementary decentralised applications and ecosystems, thus enhancing the functionalities and extensibility of GSY DEX.

The blockchain configuration described above is reflected in the following files in GSY DEX GitHub repository, with the code published under open source GPL v.3 licence:

- `chain_spec.rs`: A chain specification is the source code file that defines the GSY Node blockchain's initial (genesis) state. Chain specifications are useful for development and testing, and critical when architecting the launch of a production chain. In addition, the `development_config` and `testnet_genesis` functions define the genesis state for the local development and testnet chain configuration. These functions jointly facilitate the set up of the initial accounts of the GSY DEX deployment, configuring the blockchain's initial state.
- `service.rs`: This file defines the GSY Node implementation. Numerous consensus-related configurations are determined here, such as the [fork choice rule](https://docs.polkadot.com/polkadot-protocol/glossary/#fork-choice-rulestrategy){target=_blank}, the [Aura](https://docs.polkadot.com/polkadot-protocol/glossary/#authority-round-aura){target=_blank} consensus mechanism and the [GRANDPA](https://docs.polkadot.com/polkadot-protocol/glossary/#grandpa){target=_blank} finality gadget.


#### GSY Node Runtime

In Substrate, the terms "[runtime](https://docs.polkadot.com/polkadot-protocol/glossary/#runtime){target=_blank}" and "[state transition function](https://docs.polkadot.com/polkadot-protocol/glossary/#state-transition-function-stf){target=_blank}" are analogous and refer to the core logic of the blockchain that is responsible for validating blocks and executing the state changes. The gsy-node [Rust](https://www.rust-lang.org/){target=_blank} package in the GSY DEX GitHub repository uses [FRAME](https://docs.polkadot.com/polkadot-protocol/glossary/#frame-framework-for-runtime-aggregation-of-modularized-entities){target=_blank}, Polkadot’s framework to construct a blockchain runtime. FRAME allows for domain-specific logic to be declared in the runtime by implementing modules called "pallets". At the heart of FRAME is helpful [macro language](https://paritytech.github.io/polkadot-sdk/master/frame_support/pallet_macros/index.html){target=_blank} that makes it easy to create and flexibly compose pallets to generate blockchains that can address a variety of needs.
The FRAME runtime implementation included in the GSY Node source code `./runtime/src/lib.rs` has the following structure:

- This file configures several pallets to include in the runtime. Each pallet configuration is defined by a code block that begins with `impl $PALLET_NAME::Config for Runtime`.
- The pallets are integrated into a single runtime by way of the [construct_runtime!](https://crates.parity.io/frame_support/macro.construct_runtime.html){target=_blank} macro, which is part of the core [FRAME Support](https://docs.polkadot.com/develop/parachains/customize-parachain/overview/#support-libraries){target=_blank} library.

#### GSY Node Pallets

GSY Node comprises the following pallets: Order Book Registry, and the related Order Worker, as well as Trade Settlement and Trade Execution pallets, with the latter including the Penalties Registry. The GSY Node Runtime is constructed using many FRAME pallets that ship with the [core Substrate repository](https://github.com/paritytech/substrate/tree/master/frame){target=_blank} and the GSY DEX-specific `orderbook-registry`, `orderbook-worker`, `trades-settlement`, `trades-execution` and any directly implemented remuneration pallets that are defined in the `./modules` directory of the repository.
A FRAME pallet is composed of a number of blockchain primitives:

- Storage: FRAME defines a rich set of powerful [storage abstractions](https://docs.polkadot.com/develop/parachains/customize-parachain/make-custom-pallet/#pallet-storage){target=_blank} that makes it easy to use Substrate's efficient key-value database to manage the evolving state of a blockchain.
- Dispatchables: FRAME pallets define special types of functions that can be invoked (dispatched) from outside of the runtime in order to update its state.
- Events: Substrate uses [events](https://docs.polkadot.com/develop/parachains/customize-parachain/make-custom-pallet/#pallet-events){target=_blank} and [errors](https://docs.polkadot.com/develop/parachains/customize-parachain/make-custom-pallet/#pallet-errors){target=_blank} to notify users of important changes in the runtime.
- Errors: When a dispatchable fails, it returns an error.
- Config: The Config configuration interface is used to define the types and parameters of the FRAME pallet.

Substrate-based relay chain runtimes do not support floating point arithmetic operations since these are [non-deterministic](https://medium.com/@decenomy/the-non-deterministic-nature-of-floating-point-operations-in-blockchain-applications-abab668bc526){target=_blank} in the context of blockchain. This prevents the pallet dispatchable functions from using floating-point numbers as inputs. To counter this, the GSY Node uses integer arithmetic by representing floating point numbers as unsigned 64-bit integers scaled by a (configurable) fixed factor of 10000, thus applying a rounding of 5 decimal places to all floating point numbers. This scaling applies to all GSY Node dispatchable functions’ floating point inputs, including forecast energy values and energy price values. The scaling factor is automatically applied by the [GSY DEX API Gateway](blockchain-system-components-overview.md#gsy-dex-api-gateway){target=_blank}, the [GSY DEX Off-Chain Storage](blockchain-off-chain-storage.md){target=_blank} and the GSY DEX [Matching](blockchain-matching-engine.md){target=_blank} and [Execution Engine](blockchain-execution-engine.md){target=_blank}. Furthermore, the operation is reversed for numerical data GSY DEX outputs by dividing expected floating point numbers by the same scaling factor, thus rendering the scaling operation transparent for off-chain services and GSY DEX users.
Notably, the GSY DEX uses kWh and EUR as default units of energy and price respectively, but these can be easily adapted to support different energy values and currencies depending on the market context and the regulatory environment.
GSY Node Order Book pallets are described below, while the [Trade Settlement](blockchain-matching-engine.md#gsy-dex-matching-engine-gsy-node-communication-trade-settlement-pallet){target=_blank} and the [Trade Execution](blockchain-execution-engine.md#trade-execution-pallet-gsy-dex-execution-engine-gsy-node-communication){target=_blank} pallets are described as components of the GSY DEX Matching Engine and the GSY DEX Execution Engine, respectively.


#### GSY Node Order Book Registry Pallet

The Order Book Registry Pallet provides a decentralised order book management system that incorporates user management functionalities. It enables exchange operators, aggregators or grid operators to register participants and their assets, as well as to set up proxy accounts for delegating order management. They can then insert new orders and delete existing orders that were previously inserted, as needed. The orders are generated and logged using on-chain timestamping, with a unique identifier (hash) automatically assigned to each order. This ensures order immutability, facilitating transparency, auditability and any dispute resolution.

The following are the components of the Order Book Registry Pallet:


##### Order Book Registry Pallet Storage Items

- `RegisteredUser`: Maps an AccountId to a Hash for registered users.
- `RegisteredMatchingEngine`: Maps an AccountId to a Hash for registered matching engine operators.
- `ProxyAccounts`: Maps an AccountId to a BoundedVec of ProxyDefinition for the registered proxy accounts.
- `OrdersRegistry`: Maps an OrderReference to an OrderStatus.


##### Order Book Registry Pallet Events

- `MatchingEngineOperatorRegistered`: Emitted when a new matching engine operator is registered.
- `NewOrderInserted`: Emitted when a new order is inserted.
- `NewOrderInsertedByProxy`: Emitted when a new order is inserted by a proxy account.
- `OrderDeleted`: Emitted when an order is deleted.
- `OrderDeletedByProxy`: Emitted when an order is deleted by a proxy account.
- `ProxyAccountRegistered`: Emitted when a new proxy account is registered.
- `ProxyAccountUnregistered`: Emitted when a proxy account is deregistered.
- `UserRegistered`: Emitted when a new user is registered.

##### Order Book Registry Pallet Errors

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


##### Order Book Registry Pallet Dispatchable Functions

- `insert_orders`: Insert an order with a given order hash for a registered user account.
- `insert_orders_by_proxy`: Insert an order with a given order hash for a registered user account by a registered proxy account.
- `delete_order`: Delete an order with a given order hash for a registered user account.
- `delete_order_by_proxy`: Delete an order with a given order hash for a registered user account by a registered proxy account.
- `register_proxy_account`: Register a new proxy account for a registered user account.
- `register_matching_engine_operator`: Register a new matching engine operator account.
- `register_user`: Register a new user account.
- `unregister_proxy_account`: Unregister a proxy account for a registered user account.


##### Order Book Registry Pallet Helper Functions

- `add_matching_engine_operator`: Add a matching engine operator account.
- `add_proxy_account`: Add a proxy account for a registered user account.
- `add_user`: Add a user account.
- `is_order_registered`: Check if an order is registered.
- `is_registered_matching_engine_operator`: Check if an account is a registered matching engine operator.


#### GSY Node Order Book Worker Pallet

The Order Book Worker pallet manages the lifecycle of energy orders for the GSY DEX, communicating with its on- and off-chain services. It ensures the integrity of the GSY Node Order Book and serves as the entry point for all incoming orders. The Order Book Worker Pallet facilitates the following functions:

- Insert orders into the order book
- Insert orders into the order book by proxy
- Remove orders
- Remove orders by order reference
- Remove orders by proxy

By interacting with the GSY DEX API Gateway and the GSY DEX Off-Chain Storage, it routes all orders transmitted from the GSY DEX API Gateway to off-chain services that require them, such as the GSY DEX Off-Chain Storage. Furthermore, the incoming orders are forwarded to other pallets that require them as inputs, such as the Order Book Registry Pallet. In detail, the interactions of the Order Book Worker Pallet with other services comprise of:

- [GSY DEX API Gateway](blockchain-system-components-overview.md#gsy-dex-api-gateway){target=_blank}: The Order Book Worker Pallet receives new orders submitted through the API gateway. It processes and validates these orders before adding them to the off-chain order book storage. The pallet also communicates, using on-chain events, any update or other changes in the order status back to the users.
- [GSY DEX Off-Chain Storage](blockchain-off-chain-storage.md){target=_blank}: The Order Book Worker Pallet works closely with the off-chain storage service to manage the order book. It broadcasts orders to the off-chain order book storage component. This interaction ensures that the order book data is always up-to-date and readily available for subsequent processing by the GSY DEX Matching Engine.

The following are the components of the Order Book Worker Pallet:

##### Order Book Worker Pallet Storage Items

- `Orderbook`: A storage map that temporarily contains the orders in the order book.
- `UserNonce`: A storage map that contains nonces for each user.

##### Order Book Worker Pallet Events

- `OrderRemoved`: Emitted when an order is removed from the order book storage.
- `NewOrderInserted`: Emitted when a new order is inserted into the order book storage.

##### Order Book Worker Pallet Errors

- `OffchainUnsignedTxError`: An error that occurs when processing an unsigned transaction.
- `OffchainSignedTxError`: An error that occurs when processing a signed transaction.
- `OrderProcessingError`: An error that occurs when processing an order.
- `NoLocalAcctForSigning`: An error that occurs when there is no local account for signing.
- `NonceCheckOverflow`: Returned when the nonce check overflows.
- `OrderIsNotRegistered`: Returned when an order is not registered.
- `NotARootUser`: Returned when the user is not a root user.
- `InvalidNonce`: Returned when the nonce is invalid.

##### Order Book Worker Pallet Dispatchable Functions

- `insert_orders`: Insert a vector of orders into the order book.
- `insert_orders_by_proxy`: Insert a vector of orders into the order book on behalf of a delegator.
- `remove_orders`: Remove a vector of orders from the order book.
- `remove_orders_by_order_reference`: Remove an order from the order book by its order reference. This function requires an unsigned transaction and provides an interface for the off-chain workers.
- `remove_orders_by_proxy`:  Remove a vector of orders from the order book on behalf of a delegator.

##### Order Book Worker Pallet Hooks

- `offchain_worker`: An offchain worker that processes orders in the order book for broadcasting them to the off-chain storage and removes them from the on-chain storage.


#### GSY DEX Primitives


The implemented [Rust](https://www.rust-lang.org/){target=_blank} code defines the primitive data structures used in the GSY DEX, such as types for block numbers, moments, signatures, public keys, account IDs, account indices, chain IDs, hashes, nonces, balances, headers, blocks, and extrinsics. Additionally, it exports the OrderReference and OrderStatus types from the GSY Node `Orders` Module.
Here is an overview of the input data types (structs) for the GSY DEX:

- `BlockNumber`: a type alias for a 64-bit unsigned integer used to represent block numbers
- `Moment`: a type alias for a 64-bit unsigned integer used to represent an instant or duration in time
- `Signature`: a type alias for the `MultiSignature` type from the `sp_runtime` module. This type is used to represent a signature for a transaction. It allows one of several underlying cryptographic algorithms to be used, so it isn't a fixed size when encoded.
- `AccountPublic`: a type alias for the `Signer` associated type of the `Verify` trait implemented for `Signature`. This type represents the public key used for the GSY chain and is actually a `MultiSigner`. Like the signature, this type also isn't a fixed size when encoded, as different cryptographic algorithms have different size public keys.
- `AccountId`: a type alias for the `AccountId32` type associated with the `IdentifyAccount` trait implemented for `AccountPublic`. This type is an opaque account ID type and is always 32 bytes.
- `AccountIndex`: a type alias for a 32-bit unsigned integer used to represent the type for looking up accounts.
- `ChainId`: a type alias for a 32-bit unsigned integer used to represent the identifier for a chain.
- `Hash`: a type alias for the `H256` type from the `sp_core` module. This type is used to represent a hash of arbitrary data objects (e.g. asset identifiers, orderbook identifiers).
- `Nonce`: a type alias for a 32-bit unsigned integer used to represent the index of a transaction.
- `Balance`: a type alias for a 128-bit unsigned integer used to represent the balance of an account.
- `Header`: a type alias for the `generic::Header<BlockNumber, BlakeTwo256>` type from the `sp_runtime` module. This type represents the header of a block.
- `Block`: a type alias for the `generic::Block<Header, UncheckedExtrinsic>` type from the `sp_runtime` module. This type represents a block.
- `BlockId`: a type alias for the `generic::BlockId<Block>` type from the `sp_runtime` module. This type represents the ID of a block e.
- `UncheckedExtrinsic`: an opaque, encoded, unchecked extrinsic that is used to represent a transaction.
- `OrderReference`: a type defined in the `orders` module that represents a reference to a Bid or an Offer.
- `OrderStatus`: a type defined in the `orders` module that represents the status of a Bid or an Offer.
mod orders: a module that exports the `OrderReference` and `OrderStatus` types.


##### GSY Node Orders Module

The orders module defines several types:

- `Order`: An enum representing the order in the GSY DEX, with two variants:
  - `Bid`: A struct representing a bid order, including the buyer, nonce and the bid components.
  - `Offer`: A struct representing an offer (ask) order, including the seller, nonce, and the offer components.
- `OrderStatus`: An enum that represents the status of an `Order`, with three variants:
  - `Open`: The default status.
  - `Executed`: The order has been executed.
  - `Deleted`: The order has been cancelled.
- `OrderReference`: A struct that represents a reference to an order in the GSY DEX, with two fields:
  - `user_id`: The account ID of the user who created the order.
  - `hash`: The hash of the order struct which represents a unique reference of the `Order` object.
- `InputOrder`: An enum representing the input format of the order of the GSY DEX. It has two variants:
  - `InputBid`: A struct representing an input bid order, including the buyer and the bid components.
  - `InputOffer`: A struct representing an input offer (ask) order, including the seller and the offer components.
- `OrderComponent`: A struct representing the common components of an order, including area UUID, market UUID, time slot, creation time, energy, and energy rate.
- `OrderSchema`: A struct representing the schema of the order. It is needed in order to enforce the order book storage and other ancillary services to use the same schema/protocol for the `Order` struct as the GSY Node.

##### GSY Node Trades Module

The `trades` module defines several types:

- `Trade`: A struct representing a trade, including the seller, buyer, market ID, trade UUID, creation time, time slot, offer, offer hash, bid, bid hash, residual offer, residual bid, and trade parameters.
- `TradeParameters`: A struct representing the trade parameters, including the selected energy, energy rate, and trade UUID.
- `BidOfferMatch`: A struct representing a bid and offer match, including the selected energy, energy rate, and trade UUID
- `Validator`: A trait defining the validation functions for the `trades` module.


### GSY Node Installation

#### Run the GSY DEX code using Docker Compose

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

#### Setting up your computer for Substrate development

Please install Rust toolchain and the Developer Tools following the instructions from Substrate [here](https://docs.substrate.io/main-docs/install/){target=_blank}.

#### Running the GSY DEX code

The `cargo run` command will perform an initial build. Use the following command to build the node without launching it:

```commandline
cd gsy-node
cargo build --release
```

Once the build has been completed, the following command can be used to explore all parameters and subcommands:

```commandline
./target/release/gsy-node -h
```

The `cargo run` command will launch a temporary node and its state will be discarded after you terminate the process.
This command will start the single-node development chain with persistent state. This is useful to maintain the state of the node once the node stops running:

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
Integration with the non-decentralized version of the [GSY Energy Exchange](https://github.com/gridsingularity/gsy-e){target=_blank} is also possible, with the objective of modelling, simulation and optimisation of energy marketplaces. To install, please refer to these [installation instructions](https://github.com/gridsingularity/gsy-e#basic-setup).

Once installation is completed, a new energy marketplace can be modelled following the instructions [here](general-settings.md#backend-simulation-configuration). The same marketplace can also be simulated using the GSY DEX as the exchange engine.  In order to switch to the GSY DEX and enable blockchain operations, the command-line flag `--enable-bc` should be used. The mnemonic of the GSY DEX account should also be provided, in order to authorise the exchange engine to restore your key when needed and interact as bids and offers’ aggregator on your behalf with the blockchain. Finally, the `ENABLE_SUBSTRATE` parameter should be set to True.

#### Co-developing the GSY DEX
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

#### Connect external UI to the GSY DEX

Once the node is running locally, you can connect it with the Polkadot-JS Apps User Interface to interact with the running node [here](https://polkadot.js.org/apps/#/explorer){target=_blank}.
