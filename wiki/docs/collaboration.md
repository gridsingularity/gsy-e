Collaboration is a type of simulation in the [Grid Singularity ](https://www.d3a.io/){target=_blank}user interface that allows multiple users to participate in the same environment. They can act in a collaborative or competitive way, aiming to optimize specific metrics, for instance the cost of [energy bill](bills-traded-energy.md) or peak congestion. Users can connect through the [Grid Singularity API](APIs-introduction.md) to actively engage in the collaboration, assuming one of the following roles:

###Exchange Operator

The exchange operator (EO) is responsible for building the digital twin representation of the electrical grid, including energy assets and (sub)markets. Once the setup is complete, the EO facilitates the approval of other users to register to manage a set of (sub)markets and energy assets, and subsequently launches the collaboration. The EO is also in charge of expanding the grid (see [events](events.md)) or registering new energy assets in the course of a simulated collaboration.

###Grid Operator

The grid operator role is designed specifically for Distribution System Operators (DSOs), Distribution Network Operators (DNOs), Independent System Operators (ISOs) and Transmission System Operators (TSOs), which can register to manage different (sub)markets, on different grid levels in the collaboration. Once registered and approved by the EO, they can manage the relevant markets by using the Grid Operator API to change grid fees to manage the grid congestion in the local energy market by optimizing specific metrics, such as peak percentage.

###Aggregator

The aggregator role is designed for aggregator (energy service provider / asset management) companies participating in the Grid Singularity Exchange. Aggregators can apply to manage energy assets (Load i.e. [energy  consumption](consumption.md), [PV](solar-panels.md) and Storage i.e. [batteries](battery.md)) owned by communities, consumers, producers and prosumers. Once approved by the Exchange Operator, aggregators are responsible for buying and selling energy on behalf of their customers by connecting their energy assets with set trading preferences through the [Asset API]('configure-trading-strategies-walkthrough.md').

To create a Collaboration in the Grid Singularity user interface, follow these steps:

* Log-in to Grid Singularity Exchange with your Grid Singularity credentials to automatically access previously created simulations.

* Select the simulation that you want to set up as a Collaboration by clicking on *Edit → Create a Collaboration*. If you have not yet created a simulation or want to create a new one, please follow the instructions [here](community.md).

*Currently, this step is managed manually. A personal account of an external user does not have the admin rights to create a Collaboration. We are currently working on automating the functionalities of a Collaboration (i.e., connection with API). Please contact us at contact@gridsingularity.com for technical support and provide us with the following information:*

- *Your Name*
- *Grid Singularity account email address*
- *Company name*
- *Location of the community*
- *Size of the community (number of participants, assets)*
- *Current utility / grid operator*
- *Purpose of the Collaboration*
- *Simulation URL*

The *simulation URL* should look like this:
```
https://gridsingularity.com/singularity-map/results/522d9105-8447-462e-8651-7611c071578c/2f3ac36b-7249-4321-8e48-dd87f4e5d39c
```
