#!/usr/bin/env bash

_docker_export_path=/app/gsy_e-simulation
_git_repo_hash=$(git rev-parse HEAD)
_image_name="gsy-e:$_git_repo_hash"

if [ "$(docker images $_image_name -q)" = "" ]; then
    echo "Building gsy-e image ..."
    docker build -t $_image_name .
    echo "Done building gsy-e image"
fi

if [ "$1" = "" ]; then
    gsy_e_command="gsy-e -l ERROR run --setup default_2a -t 15s"
else
    gsy_e_command=$1
fi

if [ "$2" = "" ]; then
    export_path="$HOME/gsy_e-simulation"
else
    export_path=$2
fi

echo "Running d3a simulation settings: ${gsy_e_command}"

docker run --rm -it -v $export_path:$_docker_export_path $_image_name ${gsy_e_command//gsy_e/} --export-path=$_docker_export_path

if [ $? = 0 ]; then
    echo "Simulation results are written to ${export_path}"
fi
