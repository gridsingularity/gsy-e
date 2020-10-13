## Introduction

Collaboration is a type of simulation that allows multiple D3A's users to participate inside the same grid. These user can act in a collaborative or competitive way, to optimize specific metrics. Users can connect through the [API client](api.md) to actively engage in the collaboration. As part of collaborations, users have different role that influence their capabilities and their objectives : 

##User roles

###Exchange Operator
The exchange operator (EO) is responsible to build the digital twin of the electrical grid, including energy resources, in a collaboration. Once the [setup](grid-setup.md) is set the EO can open an external connection to devices and markets. By doing so, it allows other users to register to those nodes. Once the EO has approved the registration of external users for those devices and markets, they gain control on those.

The exchange operator is also in charge of expanding the grid (with [events](events.md)) to new user desiring to connect to the exchange.

###Grid Operator
The grid operator roles is designed towards Distribution System Operators (DSOs) and Transmission System Operators (TSOs). Those users have the possibility to register to different markets, on different grid level in the collaboration. Once registered and approved by the EO, they can control their owned markets with the API client. Through this latter grid operators can change [grid fees](constant-fees.md) in order to influence trades to optimize specific metrics (e.g. [peak percentage](kpis.md#peak-percentage)).

###Researcher
The researcher is designed towards meters, PV and batteries vendors, communities leaders, energy management companies and data scientists. Researchers can register to devices ([Load](load.md), [PV](pv-strategy.md) and [Storage](storage.md)) and once approved by the EO are responsible of buying and selling energy on markets. While the collaboration is running they are sending bids and offers, for their respective owned devices through the API to the exchange.

##How to connect
If you desire to connect to a collaboration (in the framework of an event such as the Chaos Experiments hack) please follow these following steps : 

* Go to the collaboration page from your account. On this page are listed all collaborations made in the D3A. For every simulation you are allowed to see the settings and the grid setup.
* If the collaboration you wish to participate in is public, you can click on *Registry and Scoreboard*. On this page is listed every markets and devices of the collaboration. For the ones that have their API connection opened, you can apply to them. The EO on his side will see that you have applied and is able to either approve or deny your request.
* Once you're approved you can start your API script 

