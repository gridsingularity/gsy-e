import sys

#trick, use my code, without constantly requiring me to install stuff.
sys.path.append("./src/")
#sys.path.append("./gsy-framework//")

#it does not import like this I need the line above
from gsy_e.gsy_e_core.simulation import Simulation
from gsy_e.gsy_e_core import cli


cli.run(['--setup', 'api_setup.default_community', '--slot-length-realtime', '10s', '--enable-external-connection', "--paused"])