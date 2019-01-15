import pypsa

network = pypsa.Network()

network.add("Bus", "Grid bus bar")
network.add("Bus", "Outer Grid bus bar")
network.add("Transformer", "Grid trafo", type="0.25 MVA 20/0.4 kV",
            bus0="Outer Grid bus bar", bus1="Grid bus bar")
network.add("Bus", "House 1 bus bar")
network.add("Line", "Grid-House 1 Line", bus0="Grid bus bar",
            bus1="House 1 bus bar", type="NAYY 4x150 SE")
# network.add("Store", "House 1 Storage", bus="House 1 bus bar", e_cyclic=True, e_nom=100.)
network.add("Load", "House 1 Load", bus="House 1 bus bar", p_set=0.1)
network.add("Bus", "House 2 bus bar")
network.add("Line", "Grid-House 2 Line", bus0="Grid bus bar",
            bus1="House 2 bus bar", type="NAYY 4x150 SE")
network.add("Load", "House 2 Load", bus="House 2 bus bar", p_set=0.1, control="PQ")
network.add("Generator", "House 2 PV", bus="House 2 bus bar", p_nom=0.1)

# Do a Newton-Raphson power flow
network.pf()
print(network.loads_t.p_set)

print(network.lines.tail())

print(network.loads)
print(network.generators)
print(network.transformers)
