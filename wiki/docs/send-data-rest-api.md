To send asset data without using the SDK Client or to set up a data pipeline in another programming language than the SDK Client, the raw REST API can be used instead. An additional authentication step has to be performed first.

##Authentication with JSON Web Token

Authentication is done via JSON Web Token (JWT). In order to retrieve the JWT, the following POST request has to be performed:
```
POST https://gsyweb.gridsingularity.com/api-token-auth/
```

The body of the request needs to contain the following information (JSON string):

```
{"username": "<your_username>", "password": "<your_password>"}
```

The returned JWT needs to be sent via the Authorization HTTP header when sending the forecast data. For that the user needs to add the following key value pair to the header of **every** POST command: _Authorization: JWT <your_token>_.

##Send energy forecast

The POST to send the energy value is (please fill in <Canary Network UUID> and <Asset UUID>):

```
POST https://gsyweb.gridsingularity.com/external-connection/api/
<Canary Network_UUID>/<Asset UUID>/set_energy_forecast/
```

The body of the request needs to contain the following information (JSON string):

```
{"energy_Wh": <energy_value_for_asset>}
```

Once the connection with the Grid Singularity Canary Test Network is complete, we recommend to verify that the data are sent successfully to the Grid Singularity exchange,  by comparing the data visualized on the Grid Singularity user interface with the data in your local database to identify incoherences or mistakes during the connection. Iterate this process until each asset is successfully connected to send the correct data.

***Warning: Ensure your Internet connection/server is stable and the script persists. Any connection issue/loss on your side will result in inaccurate data reporting and representation in the Grid Singularity Exchange.***
