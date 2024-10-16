## Historical Data API

The Historical Data API has been developed by Grid Singularity to allow users to retrieve the assets’ historical data in a given simulation, such as loads (consumption profiles) or generation profiles. This information can be used, for instance, by trading agents to adapt the assets’ trading settings to optimise the asset owner’s savings / revenue from these assets.

This API requires the following parameters:

* _Simulation_id_: This is the ID of the simulation or the Grid [Singularity Canary Test Network](connect-ctn.md){target=_blank}, and can be found in the url on the [Grid Singularity user interface (UI)](https://gridsingularity.com/singularity-map){target=_blank} (see Fig. 1)
* _Market_uuid_: This is the ID of the asset or market of the energy community for which the historical information is to be retrieved. It can also be found in the url on the [Grid Singularity UI](https://gridsingularity.com/singularity-map){target=_blank} (see Fig. 1)
* _Start_time_ and _end_time_: This is the time period for which the historical information is downloaded

You can then connect to the API with the following URL, which divides the parameters with a slash (/):

_https://gsyweb.gridsingularity.com/historical-data/assets/{simulation_id}/{market_uuid}/{start_time}/{end_time}_

## Grid Data API
Grid Singularity has developed the Grid Data API to provide information about the topology of a simulated energy community, listing the relevant attributes and connections for each energy asset.

This API requires the following parameters:

* _Simulation_id_: This is the ID of the simulation or the Grid [Singularity Canary Test Network](connect-ctn.md), and can be found in the url on the [Grid Singularity user interface (UI)](https://gridsingularity.com/singularity-map){target=_blank} (see Fig. 1)

You can then connect to the API with the following URL, which divides the parameters with a slash (/):

_https://gsyweb.gridsingularity.com/external-connection/configurations/{simulation_id}/registry_

The response will include the following data:

* _Uuid_: unique identifier of each asset
* _Name_: name of each asset
* _Type_: type of each asset
* _Aggregator_: name of the aggregator that manages the asset, if any
* _Attributes_: any relevant asset attributes

We will gradually add more data points to the response of the Grid Data API, for instance the geographic location (longitude and latitude) of each asset.


![alt_text](img/get-simulation-data_1.png)
Figure 1: Screenshot of a simulation url, which includes the simulation_id and the market_uuid parameters in the [Grid Singularity UI](https://gridsingularity.com/singularity-map){target=_blank}


##Connect to the data APIs

### Perform a request using Postman

Postman is a widely used API client that enables you to save your requests as well as share settings with others. To use Postman with this API, the first step is to create a “collection” that contains all settings needed to perform a request to the Historical Data API.

To install and set up a collection on postman, please follow these steps:

1. Download and install app from [Postman](https://www.postman.com/downloads/){target=_blank}
2. Import attached collection:

      - Download the collection file [here](https://api.media.atlassian.com/file/f0ebe667-59bd-494c-baba-d6a21e9ad730/binary?token=eyJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJjZGM0ZmNjYS1kMzc5LTRlMmMtOGM4YS02OGI5MjY4OWExNTYiLCJhY2Nlc3MiOnsidXJuOmZpbGVzdG9yZTpmaWxlOmYwZWJlNjY3LTU5YmQtNDk0Yy1iYWJhLWQ2YTIxZTlhZDczMCI6WyJyZWFkIl19LCJleHAiOjE2NTg1ODAzMzQsIm5iZiI6MTY1ODQ5NzQxNH0.MGCG6Dc-VKD7_Dn8y2eiT3LlahLzjzr-TkxEcdIxUM4&client=cdc4fcca-d379-4e2c-8c8a-68b92689a156&name=historical_data_api_postman_collection_20210722.postman_collection.json){target=_blank}.
      - Go to _File_ > _Import_ and click on _Upload Files_, select the collection file that you just downloaded and click on _Import_.

      [![VIDEO](https://img.youtube.com/vi/i1Xy6RYOv_o/0.jpg)](https://www.youtube.com/watch?v=i1Xy6RYOv_o)

      - Change user credentials in the pre-request scripts

      [![VIDEO](https://img.youtube.com/vi/uC-vBZT37Q4/0.jpg)](https://www.youtube.com/watch?v=uC-vBZT37Q4)

      - Adapt the url with the wanted parameters following the description mentioned above and press _Send_ (the results should be shown in the _Body_ tab of the response):

      [![VIDEO](https://img.youtube.com/vi/J9wCld-dQLg/0.jpg)](https://www.youtube.com/watch?v=J9wCld-dQLg)

      - (Optional) Save the response as a json file clicking on Save Response on the right side.


### Perform a request using a Python script

Alternatively, you can directly use Python to make a request to the API. For this method, please follow this steps:

1. Import the library and set the parameters of your simulation
```python
import requests

username = "<your_user>"
password = "<your_password>"

domain = "https://gsyweb.gridsingularity.com"
simulation_id = "990abe5e-3126-4b8b-9978-66ca07824d3c"
market_uuid = "a245cff8-d90a-44d9-82e5-d37999b62e04"
start_date = "2021-09-25T00:00"
end_date = "2021-10-01T00:00"
```
2. Generate your JWT token
```python
response = requests.post(url=domain + "/api-token-auth/",
                         json={"username": username, "password": password})

token = response.json()["token"]
```
3. Create a URL and send the request:
```python
historical_data_url = f"{domain}/historical-data/assets/{configuration_id}/{asset_id}/{start_date}/{end_date}"
headers = {"Authorization": f"JWT {token}"}

response = requests.get(url=historical_data_url,
                        headers=headers)

profile = response.json()

```
