from gsy_e.gsy_e_core import cli


cli.run(['--setup', 'api_setup.default_community', '--slot-length-realtime', '10s', '--enable-external-connection', "--paused"])