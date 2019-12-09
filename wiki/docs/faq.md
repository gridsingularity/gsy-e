This list of frequently asked questions is updated gradually, by adding the questions that come up on our [gitter community chat](https://gitter.im/D3A-community/welcome)

# D3A Functionality 

### What is the D3A ? 

The D3A is an energy exchange engine. It is an open source software, enabling users to model, simulate, optimise, download, and deploy their own energy exchanges. The D3A is designed to build “digital twin” representations of physical energy systems and energy markets. It aims to build open energy exchanges, extending access for new energy players, a class which is growing due to increased investments in distributed energy resources and smart devices. By creating energy exchanges from bottom to top, smart, local, and flexible devices as well as distributed renewable generation can be monetised for a faster transition to 100% renewable energy. 


The D3A simulation engine is currently available in two formats - the open source [backend code](https://github.com/gridsingularity/d3a), and the user friendly [frontend User Interface (UI)](https://www.d3a.io/).

### What are the possible use cases to simulate with the D3A ?

The D3A is an energy exchange engine capable of simulating (and after further development facilitating) power flows and energy transactions in local marketplaces. The D3A showcases and harnesses the potential of transactive grids, renewable energy sources (RES) and peer to peer (P2P) energy trading for all stakeholders in the energy transition and can have multiple applications, including the following use cases.

- **Community as a Service**. Creates a local energy market within the *grid-tied community* and allows all energy assets (e.g. residential rooftop solar) equal access to market alongside traditional energy providers. This enables prosumers to participate actively in the energy market by trading locally before buying from or selling to the grid provider. 
- **Energy Access**. Creates a local energy market within an *islanded microgrid* *energy community*. This allows for a more optimal microgrid configuration.


To see an example of use case of “Community as a Service” with the D3A engine, please read our [Medium article](https://medium.com/@contact_82008/an-energy-exchange-engine-for-local-energy-marketplaces-28d5be23705e) and watch our presentation from Event Horizon 2019 [here](https://youtu.be/P7I0sYpGnXY). Both the “Community as a Service” and “Energy Access” use cases are available as public projects at [d3a.io](http://d3a.io/).

### Do the D3A frontend and the backend have the same functionalities ?

The backend code offers the full functionality of the active version of the D3A. The frontend User Interface (UI) offers a user friendly interface to the majority of features found in the backend. New features are typically developed in the backend first and are made available in the UI after internal testing for usability and accuracy.

 

## Frontend / User Interface at [d3a.io](http://d3a.io/)

### How do I setup a simulation in the frontend ? 

1. To start using the D3A you need to register your account. The D3A team will approve accounts in one business day. You will then be asked to confirm your email to enable login.
2. You can design your own project by clicking on “new project” and then create a new simulation in it.
3. The first step in setting up a simulation is to define the simulation settings. You can set the simulation duration, the solar profile type, the market type, and other relevant parameters. In the D3A you can choose one of the 3 market types available : single-sided pay as offer, two-sided pay as bid and two-sided pay as clear (for more information on the simulation settings please follow this [link](change-global-sim-settings.md)). 
4. The next step is to design your grid. Once you arrive in the grid setup, the first thing that you will have to do is to define the market maker. Its goal is to represent a static or fluctuating base market price which will serve as a reference point for the selected device strategies. After creating this market maker, you can start building the digital twin of your grid. The D3A works by creating area markets. In each of these areas you can put devices or other grid areas. The devices can be loads, PV, storage, etc. The setup is intended to represent the physical architecture of the real energy market (country, region, neighbourhood, house, etc.). Importantly, each area contains a spot market where trades can occur. Each device places a bid/offer in their home market. When bids/offers are not matched in their own area, they are forwarded to the upper market in the upper area and so on. 
5. After your grid setup is complete, you can run your simulation. When it is finished you can view multiple scrollable plots and tables on the results page (for more on how to use these visuals, please see this [link](results.md)) and you can also download the results file on your computer. 

For a step-by-step explanation on how to setup your simulation, please watch our [tutorial](https://youtu.be/ktqYAySU_5k). You can also see a video explaining the new release features implemented on the frontend [here](https://youtu.be/hHXWzs1PJGI). If you have any other problems, please visit our documentation wiki page for the [frontend](user-interface-d3a.md) and the [backend](backend-codebase.md) D3A versions.

### Are there any limitations concerning the size of the simulation ?

For smoother simulations and smaller queue, we have set some boundaries. First, the simulations are limited in their duration. You can currently set the duration from 1 to 7 days. Furthermore, the number of agents allowed per simulation is limited. Each device and area is considered as an agent and you can define up to 50 of these.

 

## Backend Codebase

### How do I setup a simulation in the backend ? 

There is no need to login to set up a simulation in the backend. You just need to follow the steps bellow : 

1. Download the code from our [GitHub Repository](https://github.com/gridsingularity/d3a).
2. Please follow the technical instructions [here](installation-instructions.md) to correctly install the D3A on your computer.
3. To design a grid setup, please create a python file and follow our tips on how to [setup file](create-setup-file.md) and [global settings](change-global-sim-settings.md). You can also review our setup examples located at `d3a/src/d3a/setup/`. 
4. To run a setup file you need to place it in the directory `d3a/src/d3a/setup/`, or change the path yourself in the `ConstSettings.py` file.
5. To launch the simulation in the command line interface, follow our [technical instructions](launch-sim-via-cli.md).

### Why do my results keep changing when I rerun the same setup ?

This is caused by the random seed number. This number controls the randomness of the market, the bids, offers and the trades. If you have not defined this number, at each simulation a new random seed number will be generated and therefore you will keep observing different results (for example the trades between the areas and the storage SOC can vary). To set the random seed number you have to add this in the simulation launch command line interface --seed TEXT. By doing so, the randomness of the simulation will be frozen and your results won’t change anymore.

### I am creating a long simulation (week/month/year) and would like to establish my spot market in the day ahead. Is this possible or is it frozen/strictly at 15 minutes ahead ?

No, for now you cannot establish your spot market in the day ahead, but you can choose the number of tradable market slots into the future. This will allow your devices to trade in multiple future spot markets. To enable this functionality, you have to add to your simulation a launch command -m number_of_tradable_markets. The size of the market slot is configurable. You can change the market slot length of 15 minutes to be any integer between 2 minutes and 60 minutes.

### I am using the energy storage system (ESS) to represent a compressed air storage (with an electric-to-electric efficiency of 50%). How can I implement the efficiency in the ESS component ?

For the time being, the storage component has a 100% electric-to-electric efficiency by default. Changing this characteristic is not possible at the moment but it will be possible in the near future. Users are welcome to add additional features to our open source code base on GitHub.

### I have created a setup with 2 identical areas. I would like to know how the d3a works if one area is prioritised over the other during clearing. Does it change when I change the random seed number ?

If two areas are completely identical i.e post the same offer/bid, the market will randomly choose one of them. You can control this randomness by changing the random seed number in the launch CLI by adding --seed TEXT.

### I would like to study a structure with multiple microgrids exchanging energy based on a two sided market pay as clear. Furthermore, I would like that the exchanges inside microgrids (between houses) be based on a two sided market pay as bid. Can I setup such a structure with multiple market types inside one simulation ?

No, for now that is not possible. You can only have one market type per simulation.

### In my simulations results, sometimes an area/device is both a seller and a buyer at the same time. Why does this happen ? 

Sometimes areas can be both a seller and a buyer at the same time. This is explained by the open market. It happens that loads in the area are not fast enough to place bids to buy their own generation. This also happens because of the device’s strategy. If other loads (outside of the area) have the same buying rate as the load inside the area (and there are no grid fees), they can possibly “steal” the offers. To avoid this, you have to change the strategies and/or add grid fees in your simulation. This will help to prioritise self consumption inside each area.

### I am creating a simulation with one load and one generation and I am using the two sided market pay as clear. Sometimes, when my generation is lower than my demand, there are no trades at all. What is the reason for that ?

The two sided market pay as clear is cleared if at least one bid is satisfied. For example in your case, since your only bid is not entirely satisfied, the market will not clear and therefore there won’t be any trades.

### Can I configure all types of grid topography from meshed to radial under the same voltage level ? 

The D3A is designed for radial and hierarchical grid structures. Other topography types might be possible as long as they do not contain "cycles" (essentially closed loops in the grid structure). What you cannot currently simulate are loop networks, like rings.

### If I have a use case that has both residential consumers at 240V and industrial customers at 415V or higher, how can I set this up ?

For now, voltage level is irrelevant, meaning that the D3A only simulate the amounts of energy transferred between each node (this will become important once we implement imbalances, differences between consumption and generation, which impact the frequency and the voltage of the grid). You can now simulate a grid that contains both residential and industrial consumers ignoring voltage limitations by taking for granted that the step-up transformers and transmission lines power rating will not be violated (since D3A does not check this for now). This will change once the power flows feature is implemented. By adding this new functionality, the electrical properties of the grid will be represented and used in the simulations. We recommend that each level of the D3A is tied to a specific grid voltage, so that each voltage level has its own market.

### How are the grid fees applied ? How do I set them up ?

The grid fees represent the cost of the grid, taxes and other fees that are paid to another entity in exchange for using the grid. You can look at [this page](configure-transfer-fee.md) to see how you can set this up. When you define grid fees, it is applied inside of the specific area. These fees will be applied on the offers and bids, by raising or lowering their prices. Consequently, when an offer is published, its selling price will be the one defined by the seller plus the relevant grid fees. For trades to occur, the bid price minus the expected grid fees should be higher than the selling price plus the expected grid fees (for the two sided markets).

 

# Use of Blockchain

### Does D3A use blockchain technology ? 

The D3A has been designed so that it does not require blockchain technology but that it can benefit from this technology to provide enhanced functionality. Namely, if D3A-enabled deployment of energy markets is implemented via blockchain smart contracts there is full transparency of transactions, placing full trust in fair collaboration of energy actors rather than one actor having a market advantage. 

### What are the current technological limitations for D3A’s blockchain implementation and possible solutions ? 

The main limitation relates to scale or transactions throughput per second. We have tested the D3A on the ganache’s private blockchain and it works only with increased simulation time as the processing is slower than when using the Python interpreter. The [Energy Web Chain](https://www.energyweb.org/technology/energy-web-chain/), designed especially for energy sector, is more efficient and less costly (in terms of transaction fees) than any other available public platform and hence would be the current blockchain of choice. 

As one single blockchain may never be able to handle the number and size of transactions of a large electrical grid, one solution to the problem lies in the interoperability of blockchains, with each responsible for one grid/area. This solution is proposed by [the Polkadot Network](https://polkadot.network/), which will be launched and tested in 2020. In this scenario, the Energy Web Chain 2.0 could act as the relay chain for parachains for specific domains i.e. grid areas. 

### Considering the hierarchical nature of the D3A market structure, do you look for special features on the blockchain for D3A to work more efficiently ?

As D3A is hierarchical in design, there is a need of hierarchies of blockchain that specifically handle their own local grid/area. The Polkadot Network is therefore well suited for future D3A implementation.

# Grid Singularity’s Approach

### Why is the D3A open source ?

We believe that disruptive innovation that will lead us to new solutions to bring about the energy transition can not be achieved with private projects but rather with an open source community where everyone can contribute value, opportunities and challenges. The GPLv.3 license protects our code in a way that anyone who wishes to pursue proprietary commercialisation of the software would need to apply for a license, while open source applications continue to be free.

### What is the link between Grid Singularity and Energy Web Foundation ?

Grid Singularity, an energy technology startup, and the Rocky Mountain Institute, a nonprofit clean technology organisation, jointly founded the Energy Web Foundation (EWF) in January 2017. EWF is a nonprofit foundation gathering an ecosystem of over 100 energy corporates and startups with a shared, public blockchain platform, the Energy Web Chain. While Grid Singularity has significantly contributed to EWF development and the launch of the Energy Web Chain, its role today is supervisory and advisory, with two Grid Singularity representatives serving on the EWF’s Foundation Council. The Energy Web Chain is the blockchain of choice for D3A’s future blockchain implementation.

### What are the future development plans ?

We have partnered with innovative energy companies to facilitate further D3A development in the framework of the [Odyssey 2020](https://www.odyssey.org/odyssey-hackathon-2020/) Energy Singularity Track led by Grid Singularity. We will also work on some specific market simulation studies with partners to demonstrate the value of local energy markets. Following Odyssey Hackathon in April, we plan to deploy the D3A engine on real smart-meters to allow trades in a neighbourhood by the end of 2020 as part of a pilot project.

![img](img\faq-1.png)

 

### If I have questions regarding the D3A use, how can I contact you ?

Please first review our [wiki page](d3a-documentation.md) documentation on the UI and the backend code. The best way to engage with us is via the D3A community/ecosystem channel on [Gitter](https://gitter.im/D3A-community/welcome). For any additional comments/feedback you can also send us an email at [d3a@gridsingularity.com](mailto:d3a@gridsingularity.com). 