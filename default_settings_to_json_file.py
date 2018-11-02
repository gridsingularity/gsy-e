import json
import os


def export_default_settings_to_json_file():
    from d3a.util import d3a_path
    from d3a.util import constsettings_to_dict

    base_settings_str = '{ \n "basic_settings": { \n   "duration": "24h", \n   ' \
                        '"slot_length": "60m", \n   "tick_length": "60s", \n   ' \
                        '"market_count": 4, \n   "cloud_coverage": 0, \n   ' \
                        '"market_maker_rate": 30, \n   "iaa_fee": 1 \n },'
    constsettings_str = json.dumps({"advanced_settings": constsettings_to_dict()}, indent=2)
    settings_filename = os.path.join(d3a_path, "setup", "d3a-settings.json")
    with open(settings_filename, "w") as settings_file:
        settings_file.write(base_settings_str)
        settings_file.write(constsettings_str[1::])  # remove leading '{'
