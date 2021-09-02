##Installing Grid Singularity energy exchange on Linux Ubuntu 18.04:

###Step 1: In case you have not already installed git, python3.8 and pip (otherwise please go directly to step 2):

```
sudo apt-get update
sudo apt-get install git-core software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.8 -y
sudo apt-get install git-core -y
sudo apt-get install python3-pip -y
```


###Step 2: Install virtualenv and create a python virtual environment
```
pip3 install virtualenv
mkdir envs
cd envs
virtualenv -p /usr/bin/python3.8 d3a
```

####How to activate the environment:
```
source d3a/bin/activate
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

###Step 4: Clone the Grid Singularity repository to a directory of your choice:
```
git clone https://github.com/gridsingularity/d3a.git
```

###Step 5: Install the Grid Singularity energy exchange:

####Activate your virtual environment and go into the d3a repository

```
source d3a/bin/activate
```

####Install pip-tools

```
pip3 install pendulum pip-tools
```

####Install dependencies

```
pip install -e.
```

Now, if you run `d3a run -–help` , the help of d3a should be shown.

##Installing Grid Singularity energy exchange on Linux Ubuntu 20.04:

Please follow the installation instructions for [Ubuntu 18.04](https://gridsingularity.github.io/d3a/installation-instructions/#ubuntu-1804) 

If case  you encounter the following error 

```
error: command 'x86_64-linux-gnu-gcc' failed with exit status 1
```

please install the following package: 

```
sudo apt-get install build-essential python3.8-dev -y
```
