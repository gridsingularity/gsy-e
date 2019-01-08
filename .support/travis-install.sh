#!/usr/bin/env bash

if [ "$TOXENV" == "solium" ] || [ "$TOXENV" == "py36" ] || [ "$TOXENV" == "travis" ]; then
    . $HOME/.nvm/nvm.sh
    nvm install stable
    nvm use stable
    npm install -g solium@1.1.8
    npm install --prefix $HOME ganache-cli@6.1.8
    which ganache-cli
fi


if [ "$TOXENV" == "py36,coverage" ] || [ "$TOXENV" == "py36" ] || [ "$TOXENV" == "travis" ]; then
	# Arghhhh travis. Sudo is not available
	mkdir $HOME/solc

	wget https://s3.eu-central-1.amazonaws.com/d3a-installation-files/solidity_0.5.1/solc_0.5.1-0ubuntu1_trusty_amd64.deb
	dpkg -x solc_0.5.1-0ubuntu1_trusty_amd64.deb $HOME/solc
fi

pip install -U tox
