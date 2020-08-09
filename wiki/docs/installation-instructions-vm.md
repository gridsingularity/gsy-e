## How to Install D3A using a Virtual Machine (useful especially on Windows)


### Prerequisites

#####  Windows environment settings
1. Enable [Intel Virtualization](https://stackoverflow.com/a/34305608/13507565) on your computer in [BIOS](https://2nwiki.2n.cz/pages/viewpage.action?pageId=75202968).
2. Go to your [Windows Features](https://www.windowscentral.com/how-manage-optional-features-windows-10) setting and disable Windows Hypervisor Platform (or Hyper-V) and enable Virtual Machine Platform.


##### Install VirtualBox and Vagrant
It is recommended to use Chocolatey as a package management tool for Windows.

1. Install [chocolatey](https://chocolatey.org/) 
2. Install Virtualbox from a Windows console
```
choco install virtualbox
```
3. Install Vagrant
- This is a software wrapper around virtualbox and other supervisors, that allows easy creation, download, and installation of virtual machines.
```
choco install vagrant
```


### Install D3A while sharing a folder between guest and host machine via vagarnt
##### Install D3A in a sharing folder
- Create a new-folder that you want to share across guest & host machine.
- Add the [Vagrantfile](https://github.com/gridsingularity/d3a/blob/master/vagrant/Vagrantfile) from d3a repository to your newly created folder.
- ``` cd <your-sharing-folder> ```
- ``` vagrant up ```: start your virtual machine
- ```vagrant ssh```: get remote access to your virtual machine
- Execute the following commands inside your vagrant shell to create d3a virtual environment.
```
pip3 install virtualenv
mkdir envs
cd envs
virtualenv -p /usr/bin/python3.6 d3a
```
- Clone the d3a repository to the share d3a folder.
```
cd /vagrant/
git clone https://github.com/gridsingularity/d3a.git
cd d3a
pip install --upgrade setuptools pendulum pip
pip install -r requirements/pandapower.txt
pip install -e .
```


##### Execute D3A to simulate your experiment
- Now you can execute your simulation via
```
source /home/vagrant/envs/d3a/bin/activate # to activate d3a virtual env
d3a run --help # to get help and execute the simulation
```


##### Share your simulation result
- You can zip the simulation result and copy it to the shared folder
```
cd /home/vagrant/d3a-simulation/
zip -r <your-zip-filename>.zip ./<folder-to-be-zipped>/
cp <your-zip-filename>.zip /vagrant/
```


##### How to get d3a-api-client in Vagrant
- To get your d3a-api-client working in your virtual machine, first create a separate python virtual environment
```
cd /home/vagrant/envs/
virtualenv -p /usr/bin/python3.6 api-client
```
- Now clone your d3a-api-client to your shared folder
```
cd /vagrant/
git clone https://github.com/gridsingularity/d3a-api-client.git
cd d3a-api-client
source /home/envs/api-client/bin/activate
pip install -e .
```


### Steps to Execute D3A via Vagrant
After installing D3A through the steps above, now you can run simulations through your virtual machine by following the steps below on a Windows console:
1.	```cd <your-sharing-folder>```: go to the directory where you have created a virtual machine via vagrant for d3a (check the step 'Install the D3A in a sharing folder' above)
2.	```vagrant up```: start your virtual machine
3.	```vagrant ssh```: get remote access to your virtual machine
4.	```source envs/d3a/bin/activate```: activate the d3a environment used to run simulations in one terminal
5.	```cd d3a```: switch to d3a repository
6.	```d3a run```: start playing around with d3a (```d3a run --help``` could help you understand the command line interface)
7.	```exit```: come out of your remote virtual machine once you are finished running d3a
8.	```vagrant halt```: shut down your virtual machine

### Setting Up the API Client for Custom Trading Strategies (Optional)

Open a second terminal, activate vagrant with vagrant ssh, and activate the api client if you'd like to experiment with custom trading or grid fee strategies:

```
source envs/api-client/bin/activate
```

You may now follow the instructions on the [API documentation](api.md) file to get started with custom trading strategies
