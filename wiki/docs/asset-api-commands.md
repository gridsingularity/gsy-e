An Oracle (see [above](asset-api-events.md)) is able to request information and post bids and offers for multiple assets at the same time by aggregating multiple commands in a single batch to be executed at the same time. The following are the different commands available for the Asset API:

###bid_energy()
It sends an energy bid to the exchange. This command receives 4 arguments :

*   **asset_uuid**: Universal Unique Identifier of the selected asset
*   **energy**:  energy in kWh
*   **price**: price in Euro cents
*   **replace_existing**: if set to TRUE replace all existing bids with a new one

Here is an example:

```
self.add_to_batch_commands.bid_energy(asset_uuid = "2e7866d8-34c6-49ad-a388-fd5876a3e679", energy = 2, price = 60, replace_existing = True)
```
If the bid is placed successfully, it returns the detailed information about the bid. If not, it returns the reason for the error.

###bid_energy_rate()

It sends an energy bid to the exchange. This batch command receives 4 arguments :

*   **asset_uuid**: Universal Unique Identifier  of the selected asset
*   **energy**: energy in kWh
*   **rate**: price per volume in Euro cents/kWh
*   **replace_existing**: if set to TRUE replace all existing bids with a new one

Here is an example:

```
self.add_to_batch_commands.bid_energy_rate(asset_uuid = "2e7866d8-34c6-49ad-a388-fd5876a3e679", energy = 2, rate = 30, replace_existing = True)
```

###lists_bids()

It lists all posted bids on the selected market. This command takes one argument: area_uuid, which is the Universal Unique Identifier of the selected market.

Here is an example:

```
self.add_to_batch_commands.list_bids(asset_uuid="62f827ec-ef86-4782-b5c3-88327751d97d")
```

###delete_bid()

It deletes a bid posted on the market using its ID. This command receives two arguments :

*   **asset_uuid**: Universal Unique Identifier of the selected asset
*   **bid_id**: ID of the selected bid. If None, all the bids posted by the selected asset will be deleted.

Here is an example:

```
self.add_to_batch_commands.delete_bid(asset_uuid="62f827ec-ef86-4782-b5c3-88327751d97d", bid_id = "2e7866d8-3dg6-49ad-afe8-fd5876a3e679")
```

###offer_energy()

It sends an energy offer to the exchange. This command receives 4 arguments :

*   **asset_uuid**: Universal Unique Identifier  of the selected asset
*   **energy**:  energy in kWh
*   **price**: price in Euro cents
*   **replace_existing**: if set to TRUE replace all existing bids with a new one

Here is an example:

```
self.add_to_batch_commands.offer_energy(asset_uuid = "2e7866d8-34c6-49ad-a388-fd5876a3e679", energy = 2, price_cents = 60, replace_existing = True)
```
If the offer is placed successfully, it returns the detailed information about the bid. If not, it returns the reason for the error.

###offer_energy_rate()

It sends an energy offer to the exchange. This command receives four arguments :

*   **asset_uuid**: Universal Unique Identifier  of the selected asset
*   **energy**:  energy in kWh
*   **rate**: price per volume in Euro cents/kWh
*   **replace_existing**: if set to TRUE replace all existing offers with a new one

Here is an example:

```
self.add_to_batch_commands.offer_energy_rate(asset_uuid = "2e7866d8-34c6-49ad-a388-fd5876a3e679", energy = 2, rate = 30, replace_existing = True)
```

###lists_offers()

It lists all posted offers on the selected market. This command takes one argument: area_uuid, which is the Universal Unique Identifier of the selected market.
Here is an example:

```
self.add_to_batch_commands.list_offers(asset_uuid="62f827ec-ef86-4782-b5c3-88327751d97d")
```

###delete_offer()

It deletes an offer posted on the market using its ID. This command receives two arguments :

*   **asset_uuid**: Universal Unique Identifier  of the selected asset
*   **offer_id**: ID of the selected offer. If None, all the bids posted by the selected asset will be deleted.

Here is an example:

```
self.add_to_batch_commands.delete_offer(asset_uuid="62f827ec-ef86-4782-b5c3-88327751d97d", bid_id = "2e7866d8-3dg6-49ad-afe8-fd5876a3e679")
```

###asset_info()

It gets asset information(returns required energy for Loads, available energy for PVs and energy to buy/sell for storages). This command receives one argument: asset_uuid, which is the Universal Unique Identifier of the selected asset.
Here is an example:

```
self.add_to_batch_commands.asset_info(asset_uuid="62f827ec-ef86-4782-b5c3-88327751d97d")
```

After adding all the wanted commands in the batch, the API can execute it with the following command:

```
response = self.execute_batch_commands()
```

In return the simulation will provide a detailed response for all commands submitted.

*Note: The total amount of energy to bid/offer at any point is limited to the energy requirement/available of the asset. Replacing/updating a bid/offer during a market slot deletes other active bids/offers. Additionally, the price of your bids/offers must be a positive float otherwise it will get rejected by the market.*
*
