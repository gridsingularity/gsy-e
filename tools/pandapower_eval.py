# In order to install PandaPower run 'pip install matplotlib pandapower'
import pandapower as pp
from pandapower.plotting import to_html


# create empty net
net = pp.create_empty_network()

# create buses
bus1 = pp.create_bus(net, vn_kv=20., name="Bus Grid 1")
bus_trafo = pp.create_bus(net, vn_kv=0.4, name="Bus Trafo")
bus_h1 = pp.create_bus(net, vn_kv=0.4, name="Bus House 1")
bus_h2 = pp.create_bus(net, vn_kv=0.4, name="Bus House 2")

# create bus elements
pp.create_ext_grid(net, bus=bus1, vm_pu=1.0, name="Grid Connection")
pp.create_load(net, bus=bus_h1, p_mw=0.1e-3, q_mvar=0.005e-3, name="H1 Load")
pp.create_sgen(net, bus=bus_h1, p_mw=-0.1e-3, name="H1 PV")
pp.create_load(net, bus=bus_h2, p_mw=0.1e-3, name="H2 Load")
pp.create_storage(net, bus=bus_h2, p_mw=-0.1e-3, max_e_mwh=3e-3, name="H2 Storage")

# create branch elements
trafo = pp.create_transformer(net, hv_bus=bus1, lv_bus=bus_trafo,
                              std_type="0.25 MVA 20/0.4 kV", name="Trafo")
line = pp.create_line(net, from_bus=bus_h1, to_bus=bus_trafo,
                      length_km=0.1, std_type="NAYY 4x150 SE", name="Line")
line2 = pp.create_line(net, from_bus=bus_h2, to_bus=bus_trafo,
                       length_km=0.1, std_type="NAYY 4x150 SE", name="Line")

pp.runpp(net)

print(net.res_load)
print(net.res_sgen)
print(net.res_trafo)

to_html(net, 'test.html')
