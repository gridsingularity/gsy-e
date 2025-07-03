The [GSY DEX](blockchain.md) is composed of six key components that work together to provide a secure, scalable and efficient technology platform for energy trading. These are  listed below and described in the following sections, as well as in dedicated wiki pages for each of the developed and published GSY DEX v.1 components:


- [GSY Node](gsy-node.md){target=_blank}, a set of blockchain validator nodes, responsible for network activities, settling and executing blockchain state transitions;
- [GSY DEX Off-Chain Storage](blockchain-off-chain-storage.md){target=_blank}, storing various types of data that are crucial to the platform’s operation but do not need to be recorded on the blockchain, thereby enhancing scalability and efficiency;
- [GSY DEX Matching Engine](blockchain-matching-engine.md){target=_blank}, with the accompanying GSY DEX Matching API,  purposed to efficiently and securely match the select market supply with demand, based on participant preferences and market conditions.
- [GSY DEX Execution Engine](blockchain-execution-engine.md){target=_blank}, responsible for the execution or reconciliation of settled trades securely, transparently and in accordance with the agreed terms upon the energy delivery verification;
- **GSY DEX Analytics Engine**, collecting and processing live trading data (bids, offers, trades) and related energy asset information, providing valuable insights and market intelligence;
- **GSY DEX API Gateway**, which facilitates user interfacing.


Additionally, the system includes a set of ancillary services, as shown in the figure below.


<figure markdown>
  ![alt_text](img/blockchain-system-components-overview-1.png){:text-align:center"}
  <figcaption><b>Figure 6.2</b>: Grid Singularity Decentralised Energy Exchange (GSY DEX) Architecture (Note: GSY DEX system components, designated in green, interact with the GSY Node for on-chain operations, optimally via Energy Web Digital Spine that provides a secure and interoperable data exchange service. Grid and asset management services are provided through interoperable API interfaces, as are third party services, such as billing and payments.
</figcaption>
</figure>



### GSY Node
GSY Node, a set of blockchain validator nodes, comprises the backbone of the Grid Singularity Decentralised Exchange - [GSY DEX](blockchain.md){target=_blank}, responsible for network activities, settling and executing blockchain state transitions. It enables secure data and data service exchange and defines how different types of market participants and service providers interact. Another critical function of the GSY Node is communication of transactional data directly to the blockchain, ensuring the immutability of transactions and the integrity of exchanged information. This secure data communication mechanism is essential for enabling verified energy and flexibility trades, and maintaining consensus across a decentralised system, fostering scalability, transparency and trust.

For more, please see the section on [GSY Node Installation, Operation and Development](blockchain-installation.md){target=_blank}.


### GSY DEX Off-Chain Storage

The GSY DEX Off-Chain Storage stores various types of data that are crucial to the platform’s operation but do not need to be recorded on the blockchain. This approach enhances scalability and efficiency, while ensuring compliance with privacy protection regulation such as the [GDPR](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng){target=_blank} by reducing the amount of data stored on-chain and facilitating the user’s right to private data deletion. Importantly, final price and energy verification for each trade is performed on-chain. The GSY DEX Off-Chain Storage comprises four distinct subcomponents, named substorages and described below:

1. **GSY DEX Grid Topology Storage**: contains information about the physical grid structure, such as the location and configuration of energy assets and electrical grid components, as well as their interconnections. This data enables the GSY DEX to both verify the eligibility of the assets for trading, and to facilitate [performance analytics](results-dashboard.md){target=_blank} that involve the topology of the grid.
2. **GSY DEX Measurements Storage**: stores the energy consumption and production data from energy assets. Accurate measurement data is essential for validating and executing energy trades, managing grid stability, and optimising energy consumption and production patterns.
3. **GSY DEX Trades Storage**: stores all energy trades of the GSY DEX, along with the associated metadata, such as grid costs and any potential penalties. This data is required in order to maintain and update the trade status to facilitate trade execution, as well as for analytics, auditing the trading behaviour of the energy assets, and historical market analysis.
4. **GSY DEX Order Book Storage**: holds all the orders inserted in the respective market operated by the GSY DEX, including bids and offers issued by participants, both open and closed, along with metadata that is automatically generated by the GSY DEX for each order. This data facilitates efficient matching operation according to any participant preferences and market conditions.


For more, please see the section on the [GSY DEX Off-Chain Storage](blockchain-off-chain-storage.md){target=_blank}.


### GSY DEX Matching Engine

The GSY DEX Matching Engine is responsible for identifying suitable matches for energy supply and demand based on participant preferences and market conditions. It facilitates seamless and optimised exchange clearance, relying on the accompanying GSY DEX Matching API to collect inputs and share outputs of the service, including the application of relevant trading mechanisms and algorithms.  The GSY Matching Engine deploys a [two-sided pay-as-bid](market-types.md#two-sided-pay-as-bid-market){target=_blank} strategy, ensuring that buyers and sellers receive the best possible prices for their energy trades. Future versions will integrate pay-as-clear and automated market maker (AMM) as alternative trading mechanisms.

Inspired by the GSY concept of [Symbiotic Energy Markets](https://gridsingularity.medium.com/discussion-paper-grid-singularitys-implementation-of-symbiotic-energy-markets-bd3954af43c8){target=_blank}, the GSY DEX Matching Engine is designed to improve the existing matching approaches and advance the GSY’s vision to empower individuals with choices on their energy use, technically implemented as a multi-attribute double auction with dynamic pricing. Multi-attribute auctions require more complex and computationally intensive matching algorithms than single attribute auctions that are based on price alone. To enable this functionality, the matching process is decoupled from the settlement verification in the GSY DEX system architecture.

For more, please see the section on the [GSY DEX Matching Engine](blockchain-matching-engine.md){target=_blank}.


### GSY DEX Execution Engine
The GSY DEX Execution Engine is a core component of the Grid Singularity Decentralised Exchange - GSY DEX responsible for execution or reconciliation of settled trades securely, transparently and in accordance with the agreed terms upon the energy delivery verification.

Once a trade has been matched by the [GSY DEX Matching Engine](blockchain-matching-engine.md){target=_blank}, the GSY DEX Execution Engine handles the execution or reconciliation of the trades by processing energy measurements retrieved from the [GSY DEX Off-Chain Storage](blockchain-off-chain-storage.md){target=_blank} to verify energy delivery (validating whether the actual energy production and consumption correspond to matched trades) and enforcing penalties when there is a deviation between traded and delivered energy (underproduction or overconsumption). The calculated penalties are submitted to the [GSY Node](gsy-node.md){target=_blank} for clearance and financial reconciliation administered by the applicable billing and payments service. In brief, the GSY DEX Execution Engine acts as the critical link between off-chain trade settlement and on-chain financial enforcement.

For more, please see the section on the [GSY DEX Execution Engine](blockchain-execution-engine.md){target=_blank}.


### GSY DEX Analytics Engine
The GSY DEX Analytics Engine collects and processes live trading data (bids, offers, trades) and related energy asset information, providing valuable insights and market intelligence to the exchange platform users and / or operators by generating key performance indicators. This information helps users make informed decisions and identify trends, which can lead to more efficient energy trading strategies and improved market dynamics.

A list of currently supported key performance indicators can be found [here](results-dashboard.md){target=_blank}, with more under development. The [GSY DEX API Gateway](#gsy-dex-api-gateway){target=_blank} provides REST endpoints in order to facilitate access for authenticated customers to the calculated key performance indicators overview. In addition, the full dataset pertaining to the performance indicators can be [downloaded](results-download.md){target=_blank} in JSON format for detailed analysis.

_The GSY DEX Analytics Engine system component is in development._

### GSY DEX API Gateway

The GSY DEX API Gateway serves as a bridge between user and community clients and the [GSY DEX](blockchain.md){target=_blank}. It provides an interface (HTTP REST API) that facilitates user access to the platform's features, namely submission of energy orders, and retrieval of key performance indicators, including the trade volume and the current and historical asset data (e.g. energy consumption/production, traded energy). The user access is facilitated via User Client for intra-community trading and Community Client for inter-community trading. Secure and privacy-embedded access rights management compliant with [GDPR](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng){target=_blank} is enabled by integration with the [Energy Web](https://energy-web-foundation.gitbook.io/energy-web/solutions-2023/data-exchange/use-cases-and-reference-implementations/digital-spine-for-electricity-markets){target=_blank}’s open-source tool for decentralised identity and access management.

The GSY DEX API Gateway is designed to foster interoperability with external platforms and services, ranging from grid operators to aggregators and other market actors. It encourages community engagement and collaboration by allowing third-party developers to build and integrate complementary applications and services.

_The GSY DEX API Gateway system component is in development._


### Ancillary Service Integration

GSY DEX is highly interoperable, interacting with complementary blockchain-based solutions. It is currently prioritising functional API integration with the Energy Web’s decentralised identity access management for energy assets and related open-source tools of the [Energy Web Digital Spine](https://energy-web-foundation.gitbook.io/energy-web/solutions-2023/data-exchange/use-cases-and-reference-implementations/digital-spine-for-electricity-markets){target=_blank} toolkit and [Energy Web Green Proofs](https://energy-web-foundation.gitbook.io/energy-web/solutions-2023/green-proofs){target=_blank}, a customisable solution for registering and tracking low-carbon products and their attributes throughout complex supply chains
