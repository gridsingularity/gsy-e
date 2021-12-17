The Grid Operator API can function once at the start of each [market slot](markets.md#market-slots). When the current market slot ends, a new one is automatically created and the client is notified via the on_market_cycle event. It is possible to capture this event and perform operations when it occurs by overriding the functionality of the [on_market_cycle](grid-operator-api.md#each-new-market-slot) method.

The Grid Operator API can send batch commands, grouping different commands, for different markets. The commands can be grouped and then all executed at the same time. Three different commands are available for the Grid Operator API:

###last_market_dso_stats()

This command is used to **request information** from different markets for the last market slot.

This batch command receives one argument : **area_uuid**. This latter is the Universal Unique Identifier of the requested market statistic. Here is an example:

```
self.add_to_batch_commands.last_market_dso_stats(area_uuid = "62f827ec-ef86-4782-b5c3-88327751d97d")
```

###grid_fees()

This command is used to **send the new grid fee** for a specific market. The grid fee needs to be set as a positive value and the unit is cents/kWh.

This batch command receives two arguments: **area_uuid** and **fee_cents_kwh**. Here is an example:

```
self.add_to_batch_commands.grid_fees(area_uuid=62f827ec-ef86-4782-b5c3-88327751d97d", fee_cents_kwh=3.2)
```

After adding all the wanted commands in the batch, the API can execute it with the following command:

```
response = self.execute_batch_commands()
```

In return the simulation will provide a response for all commands submitted.
