#!/usr/bin/env bash

INSTALL_DIR=$HOME/.d3a_pkgs

if [[ -d "$INSTALL_DIR" ]]; then
    echo "$INSTALL_DIR already exists, exiting..."
    exit 1
fi

if [[ "$1" = "" ]]; then
    echo "Enter github username"
    read GITHUB_USER
    echo "Enter github key"
    read GITHUB_KEY
else
    GITHUB_USER=$1
    GITHUB_KEY=$2
fi

mkdir -p ${INSTALL_DIR}
cd ${INSTALL_DIR}
git clone https://${GITHUB_USER}:${GITHUB_KEY}@github.com/gridsingularity/d3a-interface.git
cd d3a-interface
python setup.py install
rm -rf ${INSTALL_DIR}
