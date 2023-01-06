##Send live energy asset data streams to the Grid Singularity exchange

Once the Grid Singularity Canary Test Network is created, you need to send the live data stream from your community energy assets to the Grid Singularity exchange by establishing a connection from your hardware’s data service through the Grid Singularity [Asset API](asset-api-template-script.md). Please make sure to satisfy all the data requirements (check [here](data-requirements.md)) in order to connect live data streams to the Canary Network.

##Enable Live Asset data on the User Interface
On the map, the Canary Network owner can click on the home and the asset they’d like to connect live data to. In the *Advanced Settings* tab, the *live data* switch can be toggled so the checkmark is highlighted. Once this step and the one below is completed (*Establish a connection with your energy assets*), the real energy data will be represented for those assets in the results in the UI.

*Note that if live data is turned off, data will be read through the uploaded profiles instead of reading data sent through the Asset API.*

##Establish a connection with your energy assets

It is possible to connect and register automatically to a running Canary Network:

###User-Interface (gridsingularity.com; please note that the energy asset uuid has to be obtained first for this option)
```
asset_uuid = get_area_uuid_from_area_name_and_collaboration_id(
              <simulation_id>, <asset_name>, <domain_name>
              )
asset_client = RestAssetClient(asset_uuid, autoregister=True)

```
###Backend simulation
```
asset_client = RedisAssetClient(<asset-uuid>, autoregister=True)
```

Otherwise, it is also possible to connect manually by doing:
```
asset_client.register()
```

To disconnect/unregistering, the following command is available:
```
asset_client.unregister()
```

There are two options for you to connect live data streaming to the Grid Singularity Exchange:

1. Exchange SDK  (recommended, python-based agents)
2. REST API (for non-python trading agents)
