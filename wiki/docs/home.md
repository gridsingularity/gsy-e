Users can add homes/buildings to their community by selecting the custom home or one of the template home types. For the custom home the user has to manually add all assets, while the template home types have diverse assets included. The number of assets included in template homes can be seen in the individual listings. All template homes have at least one consumption profile by default, while some others also have PV generation profiles or batteries. For example, the template of a retired couple's home has 1 asset included, as shown in the Figure below. The 6-apartments building + PV template has 7 assets, including consumption profiles representing a 6-apartment building and a PV generation profile.

![alt_text](img/home-types.png){: style="height:500px;width:300px"}

***Figure 2.6***. *A selection of template home types*

A home functions as a market, where multiple assets can trade with each other or trade together as a single entity. The custom home has no assets included initially and it is suited for users who would prefer to configure the  energy assets manually or upload their own energy data.
The template homes are suitable for users who are interested in quickly building a prototype of an energy community using template data to represent the homes and assets. They can still add, remove or edit assets to assess the impact of different configurations.

The template homes have been created using data from [Load Profile Generator](https://www.loadprofilegenerator.de/){target=_blank} and [Energy Data Map](https://energydatamap.com/){target=_blank} to represent the typical consumption and generation behaviour for different types of homes in an active energy community.

##Configuration options

Homes can be configured using the express and advanced mode:

**Express Mode**

1. Name - Must be unique
2. Geo-tag - This automatically uploads the location a user selects

**Advanced Mode**

1. Exchange Information; Users can choose between different [market types](market-types.md) where the market can clear bids and offers. At the moment only the spot market is available.
2. Grid Fees - Users can choose to switch this on ✅ or off 🆇. If switched on, users can enter a [constant grid fee](constant-fees.md) value expressed in cents/kWh. This value will then function as a fee that will be applied to each trade that passes through or is cleared in this market.
3. Transformer Capacity -  Users can choose to switch this on ✅ or off 🆇. If switched on, users can choose import and export limits of the transformer in kVA. In the current implementation these limits are purely visual indicators and do not limit actual import/export of the market.
4. Energy Peak Percentage - The energy peak imports/exports is the maximum value of the aggregate imports/exports of each asset inside a market. The user has the possibility to set a baseline_peak_energy_import_kWh and a baseline_peak_energy_export_kWh that they may have gotten from another simulation in order to calculate the energy peak percentage. The peak percentage is a tool used to measure how much the peak imports or exports have changed between a defined baseline and the current simulation. Users can choose to switch this on ✅ or off 🆇. If switched on, users can choose baseline peak import and export. These two values will be used for the calculation of the [peak percentage](trade-profile.md).

![alt_text](img/home-advanced.png)

***Figure 2.7***. *Advanced Home Configuration Options*
