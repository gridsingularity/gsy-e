Users can add homes/buildings to their community by selecting the custom home or one of the template home types. The custom home represents an empty home where the user has to manually add all assets inside, while the template home types have various other assets already included. The number of assets included in the template homes can be seen in the individual listings. All template homes have at least one consumption profile attached by default, with some template homes having generation profiles from PVs and batteries. For example, the retired couple's home has 1 asset attached already, as shown in the Figure below, which is the retired couple's consumption profile. The 6 apartments building+PV home has 7 assets included, which includes consumption profiles representing a 6 apartment building and a generation profile from a  PV. To see the exact assets included in a template home, a user must add the home to their community.

![alt_text](img/home-types.png)

***Figure 2.4***. *A selection of the different template home types available.*

A home functions as a market, inside of which multiple assets can trade with each other or trade together as a single entity. The custom home has no assets included initially and so it is more suited to users who would prefer to configure the details of the energy assets added to their home or upload their own energy data. Building a community using custom homes gives users a greater degree of control over the details and more customised results.
The template homes are suitable for users who are interested in quickly building a prototype of an energy community using template data to represent the homes and assets. They can also have assets added, removed and edited within them, which can show users the impact that different configurations can have on results, however this is not necessary and results of communities built with template homes provide value to users interested in template data representing homes and understanding the impact of changes in asset configuration.

The template homes have been created using data from Load Profile Generator and Energy Data Map to represent the typical consumption and generation behaviour for different types of homes in an active energy community.

##Configuration options

The Homes can be configured using the express and advanced mode:

**Express Mode**

1. Name - Must be unique
2. Geo-tag - This automatically loads for the location a user selects

**Advanced Mode**

1. Exchange Information; Users can choose between different [market types](market-types.md) where the market can clear bids and offers. At the moment only the spot market is available.
2. Grid Fees - Users can choose to switch this on ✅ or off 🆇. If switched on, users can enter a [constant grid fee](constant-fees.md) value expressed in cents/kWh. This value will then function as a fee that will be applied to each trade that passes through or is cleared in this market.
3. Transformer Capacity -  Users can choose to switch this on ✅ or off 🆇. If switched on, users can choose import and export limits of the transformer in kVA. In the current implementation these limits are purely visual indicators and do not limit actual import/export of the market.
4. Energy Peak Percentage - The energy peak imports/exports is the maximum value of the aggregate imports/exports of each asset inside a market. The user has the possibility to set a baseline_peak_energy_import_kWh and a baseline_peak_energy_export_kWh that they may have gotten from another simulation in order to calculate the energy peak percentage. The peak percentage is  a tool used to measure how much the peak imports or exports have changed between a defined baseline and the current simulation. Users can choose to switch this on ✅ or off 🆇. If switched on, users can choose baseline peak import and export. These two values will be used for the calculation of the peak percentage.

![alt_text](img/home-advanced.png)

***Figure 2.5***. *Advanced Home Configuration Options*
