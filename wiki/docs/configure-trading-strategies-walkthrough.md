The Grid Singularity Asset API is designed for aggregators (energy service providers) who wish to provide their customers (individuals and communities) with benefits of peer-to-peer and community trading facilitated by the Grid Singularity Exchange. They can create agents that follow custom trading strategies to buy and sell energy in the energy market on behalf of managed energy assets. The agent can request and receive information through the Asset API, feed that information into an algorithm, and post bids or offers on the exchange.

To actively place bids and offers on behalf of energy assets, please follow these steps:

1. Follow the steps [here](connect-ctn.md#grid-singularity-test-network-user-roles)
2. Install the Grid Singularity Exchange SDK on your computer by launching the following commands on your terminal window:

**Install gsy-e-sdk**
```
mkvirtualenv gsy-e-sdk
pip install git+https://github.com/gridsingularity/gsy-e-sdk.git
```

**Update gsy-e-sdk (needed when an update is deployed)**
```
pip uninstall -y gsy-e-sdk
pip install git+https://github.com/gridsingularity/gsy-e-sdk.git
```
