
##Grid Singularity [energy exchange engine](https://github.com/gridsingularity/d3a) (D3A) Update

Please start by opening a terminal and activating the Grid Singularity D3A virtual environment as described in the Installation Instructions. Then type:
```
git pull origin/master
fab sync
```

If fab sync does not work on your machine, please try:

```
pip install -e .
```

##Grid Singularity [API](https://github.com/gridsingularity/d3a-api-client) Client Update

Please start by opening a terminal and activating the API client virtual environment as described in the API Installation Instructions. Then type:

```
pip uninstall d3a-api-client
```

Press y when prompted. Once the uninstall is complete, type:

```
pip install git+https://github.com/gridsingularity/d3a-api-client.git
```