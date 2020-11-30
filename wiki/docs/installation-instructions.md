## How to Install D3A on Linux

## Ubuntu 18.04

### Preparations

#####  In case you have not installed git, python3.6 and pip yet:

```
sudo apt-get update
sudo apt-get install git-core software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.6 -y
sudo apt-get install git-core -y
sudo apt-get install python3-pip -y
```

##### Install virtualenv and create a python virtual environment for d3a

```
pip3 install virtualenv
mkdir envs
cd envs
virtualenv -p /usr/bin/python3.6 d3a
```

How to activate the environment:

```
source d3a/bin/activate
```

How to deactivate:

```
deactivate
```

####  Before you start:

1. Please add the following lines to your **.bashrc** and reopen the shell:

```
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
```

2. Clone the d3a repository to a directory of your choice:

```
git clone https://github.com/gridsingularity/d3a.git
```

###  Install the D3A:

1. Activate your *virtualenvironment* and go into the d3a repository

2. Install pip-tools

    `pip3 install pendulum pip-tools`


3. Install dependencies  
    `pip install -e . `

Now, if you run `d3a run -–help` , the help of d3a should be shown.

## Ubuntu 20.04

Please follow the installation instructions for [Ubuntu 18.04](#ubuntu-1804)
```
error: command 'x86_64-linux-gnu-gcc' failed with exit status 1
```

Installing the following packages was fixing the issue in the past:
```
sudo apt-get install build-essential python3.6-dev -y
```
