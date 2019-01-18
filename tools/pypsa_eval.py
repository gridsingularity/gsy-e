# In order to install PyPSA run 'pip install pypsa'
import pypsa
from pypsa.io import export_to_csv_folder


network = pypsa.Network()

network.add("Bus", "Grid bus bar", v_nom=0.4)
network.add("Generator", "Grid Slack", bus="Grid bus bar", control="Slack")
network.add("Bus", "House 1 bus bar", v_nom=0.4)
network.add("Bus", "House 2 bus bar", v_nom=0.4)

network.add("Line", "Grid-House 1 Line", bus0="Grid bus bar",
            bus1="House 1 bus bar", type="NAYY 4x150 SE")
network.add("Line", "Grid-House 2 Line", bus0="Grid bus bar",
            bus1="House 2 bus bar", type="NAYY 4x150 SE")

network.add("Load", "House 1 Load", bus="House 1 bus bar", p_set=0.3, control="PQ")
network.add("StorageUnit", "House 1 Storage", bus="House 1 bus bar",
            p_set=0.4, control="PV")
network.add("Load", "House 2 Load", bus="House 2 bus bar", p_set=0.3, control="PQ")
network.add("Generator", "House 2 PV", bus="House 2 bus bar",
            p_set=0.2, control="PV")

# Do a Newton-Raphson power flow
network.lpf()

print(network.buses_t["p"])
print(network.loads_t["p"])
print(network.generators_t["p"])
print(network.storage_units_t["p"])

export_to_csv_folder(network, "pypsa_output")
