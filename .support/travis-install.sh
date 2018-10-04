#!/usr/bin/env bash

if [ "$TOXENV" == "solium" ] || [ "$TOXENV" == "py36" ] || [ "$TOXENV" == "travis" ]; then
    . $HOME/.nvm/nvm.sh
    nvm install stable
    nvm use stable
    npm install -g solium@1.1.8
    npm install --prefix $HOME ganache-cli
    which ganache-cli
fi


if [ "$TOXENV" == "py36,coverage" ] || [ "$TOXENV" == "py36" ] || [ "$TOXENV" == "travis" ]; then
	# Arghhhh travis. Sudo is not available
	mkdir $HOME/solc
	wget https://launchpad.net/~ethereum/+archive/ubuntu/ethereum/+files/solc_0.4.25-0ubuntu1~trusty_amd64.deb
	dpkg -x solc_0.4.25-0ubuntu1~trusty_amd64.deb $HOME/solc
fi

pip install -U tox
