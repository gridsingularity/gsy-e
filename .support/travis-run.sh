#!/usr/bin/env bash

if [ "$TOXENV" == "solium" ]; then
	. $HOME/.nvm/nvm.sh
	nvm use stable
fi

# Sigh, since travis container infrastructure doesn't support sudo we manually "install" solc
export PATH=$HOME/solc/usr/bin
export LD_LIBRARY_PATH=$HOME/solc/usr/lib

tox -- --verbose
