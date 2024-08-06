##Version 1.5
The following features were implemented:

* An updated **energy bills table** shows the amount of energy communities or homes are buying and selling in the market
* Simulation **results can be filtered by week** to view the results for individual weeks
* Users can **request a Grid Singularity Canary Test Network**, a real-time test network version of a local energy market that uses real asset data when available. Requesting a Canary Network will give information about the process and requirements to set up a local energy community in your region, within regulation. A first step to setting up a Canary Network is connecting asset data sources to the simulation.
* Individual users can apply to participate in Canary Networks through a **registry**, where the exchange operator grants or denies access. Users can be invited to register through an invitation tool, and can see a list of Canary Networks to which they have been invited.
* **Aggregators can apply through the registry** to manage (i.e. run trading algorithms on behalf of) assets through the Asset API
* Assets can be configured to read live or uploaded data that has been sent through a **live data API**. The details of setting up live asset data through the API can be found here.
* Template scripts are available for aggregators or advanced users to trade energy through the Asset trading API. The scripts, documentation and additional information can be found here.
* Grid operators can also run scripts that set and change grid fees for the exchange.
* Both template scripts include **readable text outputs** from the trading or grid fee strategy
* **Canary network results** are viewable real-time, with data and trading results populated in 15 minute intervals. Results for previous weeks are available by selecting the week at the top of results.
* Users can **view and duplicate public simulations** on the map, allowing experimentation and rapid prototyping.
  [Grid Singularity v1.5 Tutorial](https://www.youtube.com/watch?v=8tAl8Td2XsU&list=PLdIkfx9NcrQeD8kLBvASosLce9qJ4gQIH&index=19){target=_blank}

##Version 1.4
The following features were implemented:

* A **map legend** has been added to clarify how colors on the map represent the exporting or importing of energy
* Users can add a **profile picture** to personalize their account by clicking on their name
* **Custom assets** can be added to a home with configurable production / consumption quantity or storage capacity through the advanced menu.
* **Custom PVs** can be added which use the [energydatamap.com](https://energydatamap.com/){target=_blank} API, allowing a production forecast to be used for the simulation’s geographical location. Advanced custom PV settings allow users to set the orientation of the PV (e.g. flat, tilted, facade) and azimuth and tilt.
* A **list view navigation** shows all assets in a home and community. Clicking on an asset allows further configuration.
* **Key results have been simplified** for easier reference, including community self-sufficiency and self-consumption with information about what the metrics mean.
* A **Savings KPI** has been introduced for each home in the community, showing if and how much a home has been saving compared to buying from the local utility. The total bill including amount owed or earned is shown, along with a graph of the daily savings.
* **Asset result highlights** the total amount spent or earnt by each asset, including an average price per kWh of energy. Batteries also show their current state of charge and average buying and selling price.
  [Grid Singularity v1.4 Tutorial](https://www.youtube.com/watch?v=NMlHwe6da0k&list=PLdIkfx9NcrQeD8kLBvASosLce9qJ4gQIH&index=3){target=_blank}

##Version 1.0.0
The following features were implemented :

* Our new user interface (UI), found at [Grid Singularity map](https://map.gridsingularity.com/singularity-map){target=_blank} will replace the old one at [d3a.io](https://www.d3a.io/){target=_blank}. This new UI is intended to make creating and running simulations much **easier** for users who might be new to thinking about their energy use and **simulating** their own energy community.
* Additional features in the map include a **search bar**, which facilitates searching for an address or town on the map. After running the simulation, highlighted results displayed directly above each home and community in the map.
* There are standard (template) homes and profiles that can be used by users who do not have information about actual energy consumption and/or production, generated from [loadprofilegenerator.de](https://www.loadprofilegenerator.de/){target=_blank} and [energydatamap.com](https://energydatamap.com/){target=_blank}.
* We provide additional information on the [Canary Test Network](canary-network.md) for live data simulations, which is the next step in building an energy community
* Animated color visuals in the map view assist analysis, with a color assigned to each home and community on the [map](https://map.gridsingularity.com/singularity-map){target=_blank} when the simulation is running: **green** for net exports, **blue** for neutral, and **red** for net imports
* We also provide **Map 3D** view, where users can view their simulations and homes in 3-Dimensions
* Side navigation bar summarizes the contents of a users’ energy community to additionally aid optimal energy community configuration
* Smart meter asset, a new asset type which can be configured directly in the codebase simulation file to allow users to upload **smart meter** net consumption and production profiles


<iframe width="560" height="315" src="https://www.youtube.com/embed/5_nbtxR-SYM" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
##Version 0.12.0
The following features were implemented :

* [Market slot](markets.md) length realtime: This can be set to simulations and collaborations. It slows down the running pace with a constant value (speed can go from the fasted as possible up until real-time.
* Public library is updated: New [loads](model-load.md) and [PVs](model-pv.md) profiles were added to the public library. A total of **24** loads, representing various types of households was generated using [loadprofilegenerator.de](https://www.loadprofilegenerator.de/){target=_blank}. PV production profiles were taken from [energydatamap.com](https://energydatamap.com/) for different cities. These new loads and PVs have profiles of a full year (2021).
* Users can now download the **registry** page as a JSON file, to facilitate the connection with the API to a collaboration/Canary Network.

##Version 0.11.0
The following features were implemented :

* Time Resolution setting for graphs: Users can choose to **view data** in the graphs in 2 hour, 1 hour, or 15 minutes time resolution. This allows for **faster** loading of the graphs as the simulation run time is extended. Users can change the time resolution for the Energy Trade Profile, Energy Pricing, and Asset Profile graphs.
* Add a Library as an [Event](events.md): Users can add **grid components** from the Library into their simulation while it is running.
* [Canary Network](canary-network.md) Enhancements: Canary Networks are automatically restarted in the event of a software deploy or other system disruption. Users can view previous weeks of Canary Network data and [download the results](results-download.md). Canary Network simulations can run for weeks at a time and store all data for future analysis and research.
* Users can trade through the Grid Singularity [Asset](configure-trading-strategies-walkthrough.md) and [Grid Operator](implement-grid-fees-walkthrough.md) APIs through a cloud web service. This feature allows users to **automate** their trading algorithms and connect to the API from the cloud instead of hosting and monitoring on a local computer.


<iframe width="560" height="315" src="https://www.youtube.com/embed/b2LGxgnEAcM" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
##Version 0.10.0
The following features were implemented :

* [Canary Networks](canary-network.md): An admin user can create a Canary Network simulation, which duplicates a [collaboration](collaboration.md) simulation and allows the admin to connect each energy asset in the grid to its **live data stream** in order to simulate trading on the asset's live metered data readings. The Canary Network runs in **real-time**, with incoming data collected during each 15 minute market slot. Researcher users can trade on behalf of energy assets using the registry to connect to the live data stream which broadcasts the energy required for each asset through the [Asset API](configure-trading-strategies-walkthrough.md). Grid Operator users can change the grid fees and grid parameters of each grid market using the registry which connects them to their markets through the [Grid Operator API](implement-grid-fees-walkthrough.md). Therefore, the Canary Network realizes the digital twin model of an energy asset and enables Researcher users to trade in real-time on behalf of their assets as a proof of concept. Once a Canary Network is established, it continues to run and agents can trade over weeks and months of time, for long term study of energy asset data and agent and market behavior. Previous weeks of data and results are saved in the results page weekly history.
* Island or Grid-connect a [Market Maker](model-market-maker.md) as an event: Users can now change the role and mode of the Market Maker as an event, allowing users to simulate **blackouts** by changing the Market Maker to an islanding role, or simulating other impacts resulting from a change in the Market Maker parameters, such as showing the effect of connecting an islanded Market Maker to the grid.

<iframe width="560" height="315" src="https://www.youtube.com/embed/kHacTJvTRwM" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
##Version 0.9.0
The following features were implemented :

* [Market API](implement-grid-fees-walkthrough.md), which allows grid operators and researchers to monitor metrics and set grid fees in the select local energy market simulation collaboration
* Easier registration for researchers and grid operators to manage multiple assets and use market [API](APIs-introduction.md) through the Registry page.
* Bids and offers are prioritised in their first market by setting a wait time of 2 ticks before allowing them to propagate to higher markets in the grid hierarchy. This wait time is set in the backend as the minimum bid or offer age parameter.
* [Grid fees](constant-fees.md) integrated in the Results page - [Energy Pricing](results.md#energy-pricing) graph for each market
* Total grid fees reported in the Scoreboard page that demonstrates market performance metrics for each collaboration simulation.
* Net Energy calculation added to Results page - [Energy Trade Profile](results.md#energy-trade-profile) graph in order to calculate the peak energy at a market node in the simulation. The current peak imports and exports were previously calculated based on the cumulative trades, but are now calculated from the net energy consumption, which can be a net import or export.
* Updated load final selling rate and PV initial buying rate in the [template strategies](trading-agents-and-strategies) now take the total grid fees into account in addition to the market maker (usually utility) rate.
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
* Information Aggregator to compile and send average market measurements to assist data scientists in building smart strategies to trade through the [API](configure-trading-strategies-walkthrough.md).



<iframe width="560" height="315" src="https://www.youtube.com/embed/RrYMdITH1CA" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
##Version 0.6.0
The following features were implemented :

* [Bid and Offer matching graph](results.md#bids-offers-and-trades-per-market-slot) <br /> Analyze all bids, offers, and trades in a market and see why they match based on their strategies.
* [Simulation events](events.md) <br />Add, delete, or update areas or energy resources in a simulation while it is running. This allows users to grow their simulations in real-time and analyze the impacts of energy resources coming online and changes to grid parameters such as grid fees.
* Timeline to view [events](events.md) and zoom in <br />View all events in a timeline and click on each event to view its relevant grid configuration and results. Zoom in to view results for a specific day.
* Pause or stop a simulation <br />Pause a simulation to freeze it while adding an event. Stop a simulation pre-maturely in order to run another version sooner.
* Configure an infinite bus as part of the [Market Maker](model-market-maker.md) <br />Configure an Infinite Bus in order to add a feed-in-tariff to the simulation.


<iframe width="560" height="315" src="https://www.youtube.com/embed/X5Fhb1mEBu4" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

##Version 0.5.0
The following features were implemented :

* [Constant based Grid Fees](constant-fees.md)
* [Self Sufficiency, Self Consumption](self-sufficiency-consumption.md), and [Energy Peak Percentage](peak-percentage.md) KPIs
* Simulation runtime status indicator
* Increased node limit to [1000 nodes](general-settings.md)
* [Collaborations](collaboration.md) Scoreboard
* Select visible charts on [Results page](results.md)
* Colors for Energy Bills Bought and Sold

<iframe width="560" height="315" src="https://www.youtube.com/embed/RJmKY-sPxKo" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

##Version 0.4.0
The following features were implemented :

* [Grid fees](grid-fees.md) configuration
* User roles, including 'Collaborations' feature for multi user testing and Grid Singularity-hosted challenges
* [API](configure-trading-strategies-walkthrough.md) connection to energy assets allowing bids and offers to be submitted by external algorithms


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
* New user friendly asset strategies
* Configure your [market maker](model-market-maker.md)
* Scrollable graphs on the results page optimized for longer simulations
* Download simulation results

<iframe width="560" height="315" src="https://www.youtube.com/embed/hHXWzs1PJGI" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
