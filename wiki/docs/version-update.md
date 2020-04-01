## How to update the D3A and API Client

The D3A is often updated with new features. These steps allow you to update to the most current version

### Update the D3A

Open a terminal and activate the d3a virtual environment as described in the Installation Instructions for your OS. Then type:

```
git pull origin/master
fab sync
```

If fab sync does not work on your machine, please try:

```
pip install -e .
```

The D3A should now be up to date.

### Update the API Client

Open a terminal and activate the API client virtual environment as described in the [API Installation Instructions](api.md). Then type:

```
pip uninstall d3a-api-client
```

Press `y` when prompted. Once the uninstall is complete, type:

```
pip install git+https://github.com/gridsingularity/d3a-api-client.git
```

Now, the API client should be up to date.
