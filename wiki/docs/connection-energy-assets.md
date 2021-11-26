Once the Grid Singularity Canary Test Network is created, you need to send the live data stream from your community energy assets to the Grid Singularity exchange by establishing a connection from your hardware’s data service through the Grid Singularity [Asset API](asset-api-template-script.md). Please make sure to satisfy all the data requirements (check [here](data-requirements.md)) in order to connect live data streams to the Canary Network.

It is possible to connect and register automatically to a running Canary Network.

###User-Interface (currently d3a.io) (here the energy asset uuid has to be obtained first)
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
