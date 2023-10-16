
##Grid Singularity [Exchange](https://github.com/gridsingularity/gsy-e){target=_blank} Update
Please start by opening a terminal and activating the 'gsy-e' virtual environment as described in the Installation Instructions. Then type:
```
git pull origin/master
fab sync
```

If fab sync does not work on your machine, please try:

```
pip install -e .
```

##Grid Singularity Exchange [SDK](https://github.com/gridsingularity/gsy-e-sdk){target=_blank} Update

Please start by opening a terminal and activating the Exchange SDK virtual environment as described in the API Installation Instructions. Then type:

```
pip uninstall gsy-e-sdk
```

Press y when prompted. Once the uninstall is complete, type:

```
pip install git+https://github.com/gridsingularity/gsy-e-sdk.git
```
