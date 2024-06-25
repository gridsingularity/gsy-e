*Note: The following instructions serve as a guide to launch the Grid Operator API as well.*

The Asset API is launched with a cli command. To launch the Asset API, the user needs to open a new terminal and activate the gsy-e-sdk environment (Grid Singularity Exchange SDK).

```
workon gsy-e-sdk
```

And go to the [GSy Exchange SDK repository](https://github.com/gridsingularity/gsy-e-sdk){target=_blank}

```
cd path_to_repository/gsy-e-sdk
```

The API launch CLI command takes several arguments that can be listed with:

```
gsy-e-sdk run --help
```

The arguments are :

*   `base-setup-path` --> Set the base path where the user's client script resides, otherwise `gsy-e-sdk/setups` is taken as default for the user's client scripts. Users can provide either an absolute or a relative file path.
*   `setup` --> Name of user's SDK module/script.
*   `username` --> Username of agent authorised to communicate with respective collaboration/CN.
*   `password` --> Password of respective agent
*   `domain-name` --> Grid Singularity Exchange domain name
*   `web-socket` --> Grid Singularity Exchange websocket URI
*   `simulation-id` --> UUID of the collaboration or Canary Test Network
*   `simulation-config-path` --> Path to the JSON file that contains the user's collaboration/CN information.
*   `run-on-redis` --> This flag targets the local testing of the SDK, where no user authentication is required. A locally running redis server and a running Grid Singularity CLI simulation are needed here.

The API agent can interface with a local simulation ([backend](setup-configuration.md)) or a [collaboration](collaboration.md)/[Canary Network](connect-ctn.md) ([User-Interface](https://www.d3a.io/){target=_blank}). There are 3 methods to parse the required information when launching the API to connect to the UI, as thoroughly explained in the text below:

1. CLI command
2. Environment variables

####CLI command:

The user can directly pass the relevant variables as arguments in the CLI commands. For that to work, the user needs to pass the domain name and websocket name (both are optional parameters and only relevant when connecting to specific domains) and the simulation_id. The simulation_id corresponds to the Universally Unique Identifier (UUID). This token can be found in the URL of a collaboration or a Canary Test Network in the User Interface. It is the UUID right after the URL `https://gridsingularity.com/singularity-map/results/` (marked in the screenshot below)

![alt_text](img/api-overview-4.png)

To run the Asset API, users can run the following command by adapting the arguments to their case:

```commandline
gsy-e-sdk --log-level INFO run  --setup asset_api_template -u username -p password --simulation-id UUID
```

####Environnement variables:

The last method to launch the API is send the set the required variable in the environment. To do that users can simply define those parameters at the top of their script as follows:

```
os.environ["API_CLIENT_USERNAME"] = "username"
os.environ["API_CLIENT_PASSWORD"] = "password"
os.environ["API_CLIENT_SIMULATION_ID"] = "simulation_uuid"
```

To run the Asset API, you can run the following command by adapting the arguments to your case:

```
gsy-e-sdk --log-level INFO run  --setup asset_api_template
```

####Local simulation:

To interact with a locally running simulation (backend simulation), username, passwords, domain and websocket names and simulation_id are not necessary. There is only an additional flag required in the CLI command : `--run-on-redis`.

```
gsy-e-sdk --log-level INFO run --setup asset_api_template --run-on-redis
```

Once the Asset SDK Script has been launched, you can click on “Run” in the Results page of your Collaboration in the User-Interface.
