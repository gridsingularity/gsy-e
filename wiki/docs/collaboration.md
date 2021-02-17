Collaboration is a type of simulation in the [Grid Singularity UI](https://www.d3a.io/) that allows multiple users to participate in the same environment. These users can act in a **collaborative** or **competitive** way, aiming to optimize specific metrics. Users can connect through the [API client](api-overview.md) to actively engage in the collaboration.

##User roles

###Exchange Operator

The exchange operator (EO) is responsible for **building the digital twin of the electrical grid**, including energy assets and markets in the modelling page. Once the setup is complete, the EO facilitates the approval of other users to register to manage a set of markets and energy assets, and subsequently launches the collaboration.The EO is also in charge of expanding the grid (with [events](events.md)) or registering new users desiring to connect to the exchange over the course of a simulation.

###Grid Operator

The grid operator role is designed specifically for Distribution System Operators (DSOs) and Transmission System Operators (TSOs). Those users have the possibility to register to different markets, on different grid levels in the collaboration. Once registered and approved by the EO, they can **manage the relevant markets** by using the Grid Operator API to change [grid fees](grid-fees.md) in order to influence trades to optimize specific metrics (e.g. [peak percentage](peak-percentage.md)).

###Researcher

The researcher role is designed to represent smart meters, PV and battery vendors, community leaders, energy management companies, data scientists and aggregators in collaborations. Researchers can claim assets ([Load](model-load.md), [PV](model-pv.md) and [Storage](model-storage.md)) and, once approved by the Exchange Operator, are responsible for **buying and selling energy for the assets** they manage on markets through the Asset API.

##How to connect

If you wish to connect to a collaboration in the framework of an event (e.g. [Energy Singularity Chaos Experiment](https://gridsingularity.medium.com/en-route-to-energy-singularity-odyssey-momentum-learnings-from-the-2020-chaos-experiment-8dc38ff26869)) or to a [Canary Test Network](canary-network.md) in the framework of a live running exchange please follow these steps:

* Login on the [User-Interface](https://www.d3a.io/)
* Go to the Collaborations (or Canary Test Network page), where you will see a list of all active collaborations. For each, any user may view the settings and the grid setup.
* If the collaboration the user wishes to join is public, they can click on **Registry** and **Scoreboard**. On this page, each market and asset of the collaboration is listed. The user can apply to manage the trading strategies of assets or the grid fee strategy of markets on the Registry. The EO is able to either approve or deny the request.
* Once approved, the user can start the API script and wait until the EO starts the collaboration / canary network, when trading will begin.