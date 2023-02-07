from gsy_e.gsy_e_core import cli


if __name__ == '__main__':
    cli.run(['--setup', 'bc4p.fhcampus', '--start-date', '2022-11-01', '--enable-bc', '--slot-length-realtime', '5s'])