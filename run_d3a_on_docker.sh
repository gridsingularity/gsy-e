#!/usr/bin/env bash

_docker_export_path=/app/d3a-simulation
_git_repo_hash=$(git rev-parse HEAD)
_image_name="d3a:$_git_repo_hash"

if [ "$(docker images $_image_name -q)" = "" ]; then
    echo "Building d3a image ..."
    docker build -t $_image_name .
    echo "Done building d3a image"
fi

if [ "$1" = "" ]; then
    d3a_command="d3a -l ERROR run --setup default_2a -t 15s"
else
    d3a_command=$1
fi

if [ "$2" = "" ]; then
    export_path="$HOME/d3a-simulation"
else
    export_path=$2
fi

echo "Running d3a simulation settings: ${d3a_command}"

docker run --rm -it -v $export_path:$_docker_export_path $_image_name ${d3a_command//d3a/} --export --export-path=$_docker_export_path --exit-on-finish

if [ $? = 0 ]; then
    echo "Simulation results are written to ${export_path}"
fi
