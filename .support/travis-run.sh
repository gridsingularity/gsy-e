#!/usr/bin/env bash

if [ "$TOXENV" == "solium" ]; then
	. $HOME/.nvm/nvm.sh
	nvm use stable
fi

# Sigh, since travis container infrastructure doesn't support sudo we manually "install" solc
export SOLC_BINARY=$HOME/solc/usr/bin/solc
export LD_LIBRARY_PATH=$HOME/solc/usr/lib
export GANACHE_BINARY=$HOME/node_modules/.bin/ganache-cli

tox -- --verbose
