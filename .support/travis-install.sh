#!/usr/bin/env bash

if [ "$TOXENV" == "solium" ]; then
	. $HOME/.nvm/nvm.sh
	nvm install stable
	nvm use stable
	npm install -g solium@0.2.0

	# Patch https://github.com/duaraghav8/Solium/issues/53
	sed -i '/var strBetweenLeftAndRight/i \
	if (node.left.type == "BinaryExpression") { return; }' $(npm root --global)/solium/lib/rules/operator-whitespace.js
fi

pip install -U tox
