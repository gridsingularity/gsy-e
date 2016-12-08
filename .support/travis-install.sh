#!/usr/bin/env bash

if [ "$TOXENV" == "solium" ]; then
	. $HOME/.nvm/nvm.sh
	nvm install stable
	nvm use stable
	npm install -g solium@0.2.2
fi

if [ "$TOXENV" == "py35,coverage" ] || [ "$TOXENV" == "py35" ]; then
	add-apt-repository -y ppa:ethereum/ethereum
	apt-get update
	apt-get install -y solc
fi

pip install -U tox
