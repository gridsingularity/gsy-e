##Version 0.9.0
The following features were implemented : 

* [Market API](grid-api.md), which allows grid operators and researchers to monitor metrics and set grid fees in the select local energy market simulation collaboration 
* Easier registration for researchers and grid operators to manage multiple assets and use market [API](api-overview.md) through the Registry page.
* Bids and offers are prioritised in their first market by setting a wait time of 2 ticks before allowing them to propagate to higher markets in the grid hierarchy. This wait time is set in the backend as the minimum bid or offer age parameter. 
* [Grid fees](constant-fees.md) integrated in the Results page - [Energy Pricing](results.md#energy-pricing) graph for each market 
* Total grid fees reported in the Scoreboard page that demonstrates market performance metrics for each collaboration simulation.
* Net Energy calculation added to Results page - [Energy Trade Profile](results.md#energy-trade-profile) graph in order to calculate the peak energy at a market node in the simulation. The current peak imports and exports were previously calculated based on the cumulative trades, but are now calculated from the net energy consumption, which can be a net import or export.
* Updated [load final selling rate and PV initial buying rate](how-strategies-adjust-prices.md) in the [template strategies](how-strategies-adjust-prices.md) now take the total grid fees into account in addition to the market maker (usually utility) rate. 
* Users can now run three simulations and/or collaborations at once (previous limit was two)


<iframe width="560" height="315" src="https://www.youtube.com/embed/x32D7zl1mig" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>


##Version 0.8.0
The following features were implemented : 

* Simulation Location Map. Users can geo-tag all energy resources and markets in their simulation to make a map view of the simulation and results. A summary of all simulations can be viewed in a global map, to see where Grid Singularity is running simulations all over the world!

<iframe width="560" height="315" src="https://www.youtube.com/embed/2ylGNMjbhDY" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>


##Version 0.7.0
The following features were implemented : 

* [Detailed energy trade profile graph](results.md#detailed-energy-trade-profile). Zoom in to each 15 minute market slot to view the scheduled trades with 1 minute resolution. 
* Grid Operator user can change grid parameters inside a collaboration and while it is running, like [grid fees](constant-fees.md) or the transformer capacity.
* Allow collaboration participants to register for [events](events.md) while the simulation is running. Allows users to simulate a growing community.
* Information Aggregator to compile and send average market measurements to assist data scientists in building smart strategies to trade through the [API](assets-api.md).



<iframe width="560" height="315" src="https://www.youtube.com/embed/RrYMdITH1CA" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

##Version 0.6.0
The following features were implemented : 

* [Bid and Offer matching graph](results.md#bids-offers-and-trades-per-market-slot) <br /> Analyze all bids, offers, and trades in a market and see why they match based on their strategies.
* [Simulation events](events.md) <br />Add, delete, or update areas or energy resources in a simulation while it is running. This allows users to grow their simulations in real-time and analyze the impacts of energy resources coming online and changes to grid parameters such as grid fees.
* Timeline to view [events](events.md) and zoom in <br />View all events in a timeline and click on each event to view its relevant grid configuration and results. Zoom in to view results for a specific day.
* Pause or stop a simulation <br />Pause a simulation to freeze it while adding an event. Stop a simulation pre-maturely in order to run another version sooner.
* Configure an infinite bus as part of the [Market Maker](market-maker.md) <br />Configure an Infinite Bus in order to add a feed-in-tariff to the simulation.


<iframe width="560" height="315" src="https://www.youtube.com/embed/X5Fhb1mEBu4" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>


##Version 0.5.0
The following features were implemented :

* [Constant based Grid Fees](constant-fees.md)
* [Self Sufficiency, Self Consumption, and Energy Peak Percentage KPIs](kpis.md)
* Simulation runtime status indicator
* Increased node limit to [1000 nodes](grid-setup.md)
* Collaborations Scoreboard
* Select visible charts on [Results page](results.md)
* Colors for Energy Bills Bought and Sold


<iframe width="560" height="315" src="https://www.youtube.com/embed/RJmKY-sPxKo" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>


##Version 0.4.0
The following features were implemented :

* [Grid fees](percentage-fees.md) configuration
* User roles, including 'Collaborations' feature for multi user testing and Grid Singularity-hosted challenges
* [API](assets-api.md) connection to energy devices allowing bids and offers to be submitted by external algorithms 


<iframe width="560" height="315" src="https://www.youtube.com/embed/8un6qw_CGjI" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>


##Version 0.3.0
The following features were implemented :

* Run simulations with up to 250 nodes
* Compare results of two simulations side by side
* New navigation side bar with Home, Projects, and Library easily accessible


<iframe width="560" height="315" src="https://www.youtube.com/embed/0hOJ_GAH-rs" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

##Version 0.2.0
The following features were implemented :

* Run simulations for [one week](general-settings.md)
* Choose your market type: additional access to [two-sided pay as bid](two-sided-pay-as-bid.md) and [two-sided pay as clear](two-sided-pay-as-clear.md) market types
* New user friendly device strategies
* Configure your [market maker](market-maker.md)
* Scrollable graphs on the results page optimized for longer simulations
* Download simulation results

<iframe width="560" height="315" src="https://www.youtube.com/embed/hHXWzs1PJGI" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>


