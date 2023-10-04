##Installing Grid Singularity Exchange on Linux Ubuntu 18.04
###Step 1: In case you have not already installed git, Python 3.8 and pip (otherwise please go directly to step 2):

```
sudo apt-get update
sudo apt-get install git-core software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.8 -y
sudo apt-get install git-core -y
sudo apt-get install python3-pip -y
```


###Step 2: Install virtualenv and create a Python virtual environment
```
pip3 install virtualenv
mkdir envs
cd envs
virtualenv -p /usr/bin/python3.8 gsy-e
```

####How to activate the environment:
```
source gsy-e/bin/activate
```

####How to deactivate the environment:
```
deactivate
```

###Step 3: Please add the following lines to your .bashrc and reopen the shell:

```
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
```

###Step 4: Clone the Grid Singularity Exchange repository, gsy-e, to a directory of your choice:
```
git clone https://github.com/gridsingularity/gsy-e.git
```

###Step 5: Install

####Activate your virtual environment and go into the d3a repository

```
source gsy-e/bin/activate
```

####Install pip-tools

```
pip3 install pendulum pip-tools
```

####Install dependencies

```
pip install -e.
```

Now, if you run `gsy-e run -–help` , the help of gsy-e should be shown.


##Installing Grid Singularity Exchange on Linux Ubuntu 20.04
Please follow the installation instructions for Ubuntu 18.04.

In case  you encounter the following error:

```
error: command 'x86_64-linux-gnu-gcc' failed with exit status 1
```

please install the following package:

```
sudo apt-get install build-essential python3.8-dev -y
```
