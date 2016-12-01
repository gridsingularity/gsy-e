#!/usr/bin/env bash

if [ "$TOXENV" == "solium" ]; then
	. $HOME/.nvm/nvm.sh
	nvm use stable
fi

tox -- --verbose
