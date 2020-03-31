## How to Install D3A using a Virtual Machine (useful especially on Windows)

### Preparations

#####  Install Vagrant by navigating to https://vagrantup.com

This is a software wrapper around virtualbox and other supervisors, that allows easy creation, download, and installation of virtual machines.

After vagrant is installed, run the following commands to download the VM image and install it on your local machine

```
vagrant init spyrostz/d3a --box-version 1
vagrant up
```

##### Login to vagrant Virtual Machine

```
vagrant up
```

Activate the d3a environment used to run simulations in one terminal:

```
source d3a/bin/activate
```

Now, if you run `d3a run –help` , the help of d3a should be shown.

#### Setting Up the API Client for Custom Trading Strategies (Optional)

Open a second terminal and activate the api client if you'd like to experiment with custom trading or grid fee strategies:

```
source api-client/bin/activate
```

You may now follow the instructions on the [API documentation](api.md) file to get started with custom trading strategies
