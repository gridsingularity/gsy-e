#!/usr/bin/env bash

if [ "$TOXENV" == "solium" ]; then
	. $HOME/.nvm/nvm.sh
	nvm install stable
	nvm use stable
	npm install -g solium@0.2.2
fi

if [ "$TOXENV" == "py35,coverage" ] || [ "$TOXENV" == "py35" ]; then
	# Arghhhh travis. Sudo is not available
	mkdir $HOME/solc
	wget https://launchpad.net/~ethereum/+archive/ubuntu/ethereum/+files/solc_0.4.17-0ubuntu1~trusty_amd64.deb
	dpkg -x solc_0.4.17-0ubuntu1~trusty_amd64.deb $HOME/solc
fi

pip install -U tox
