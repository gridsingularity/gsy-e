# flake8: noqa

"""
This is a template which represent a community of 25 diverse members. Every devices can be controlled with an external connection
This configuration can be subject to modifications (PV & storage capacity, adding/deleting devices and area)
"""

import os
from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a_interface.constants_limits import ConstSettings
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.strategy.external_strategies.pv import PVUserProfileExternalStrategy
from d3a.models.strategy.external_strategies.load import LoadProfileExternalStrategy
from d3a.models.strategy.external_strategies.storage import StorageExternalStrategy


months = ['Sep', 'Oct', 'Nov', 'Dec', 'Hack']
month = 1  # 0 for Sep, 1 for Oct, 2 for Nov, 3 for Dec and 4 for Hackathon data (Hack data will be provided at Odyssey Momentum)

current_dir = os.path.dirname(__file__)
load_data = []
pv_data = []
chp_data = []
month = months[month]

for i in range(0, 26):
    load = os.path.join(current_dir, "resources/Training_data/Load/" + month + "/Load_" + month + "_" + str(i) + ".csv")  # path to your csv file
    load_data.append(load)
    pv = os.path.join(current_dir, "resources/Training_data/PV/" + month + "/PV_" + month + "_" + str(i) + ".csv")
    pv_data.append(pv)
    chp = os.path.join(current_dir, "resources/Training_data/CHP/" + month + "/CHP_" + month + "_" + str(i) + ".csv")
    chp_data.append(chp)


def get_setup(config):

    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 1
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE = 22
    ConstSettings.StorageSettings.MIN_ALLOWED_SOC = 0
    ConstSettings.GeneralSettings.EXPORT_ENERGY_TRADE_PROFILE_HR = False

    Load_initial_buying_rate = 11
    Load_final_buying_rate = 29.2

    PV_initial = 27
    PV_final = 0

    batt_ini_sell = 23
    batt_fin_sell = 19.6
    batt_ini_buy = 16
    batt_fin_buy = 19.5
    ini_SOC = 0

    area = Area(
        'Grid',
        [
            Area(
                'Community',
                [
                    Area('Member 1',
                         [
                             Area('Load 1', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[1],
                                                                                 initial_buying_rate=Load_initial_buying_rate,
                                                                                 final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 1', strategy=PVUserProfileExternalStrategy(power_profile=pv_data[1],
                                                                                 initial_selling_rate=PV_initial,
                                                                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 1', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                min_allowed_soc=0,
                                                                                battery_capacity_kWh=10,
                                                                                max_abs_battery_power_kW=5.451,
                                                                                initial_buying_rate=batt_ini_buy,
                                                                                final_buying_rate=batt_fin_buy,
                                                                                initial_selling_rate=batt_ini_sell,
                                                                                final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ], external_connection_available=True),
                    #
                    Area('Member 2',
                         [
                             Area('Load 2', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[2],
                                                                                 initial_buying_rate=Load_initial_buying_rate,
                                                                                 final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 2', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[2],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 2', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                min_allowed_soc=0,
                                                                                battery_capacity_kWh=4,
                                                                                max_abs_battery_power_kW=4,
                                                                                initial_buying_rate=batt_ini_buy,
                                                                                final_buying_rate=batt_fin_buy,
                                                                                initial_selling_rate=batt_ini_sell,
                                                                                final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ], external_connection_available=True),

                    Area('Member 3',
                         [
                             Area('Load 3', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[3],
                                                                                 initial_buying_rate=Load_initial_buying_rate,
                                                                                 final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 3', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[3],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 3', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                min_allowed_soc=0,
                                                                                battery_capacity_kWh=6,
                                                                                max_abs_battery_power_kW=6,
                                                                                initial_buying_rate=batt_ini_buy,
                                                                                final_buying_rate=batt_fin_buy,
                                                                                initial_selling_rate=batt_ini_sell,
                                                                                final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 4',
                         [
                             Area('Load 4', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[4],
                                                                                 initial_buying_rate=Load_initial_buying_rate,
                                                                                 final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 4', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[4],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 4', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                min_allowed_soc=0,
                                                                                battery_capacity_kWh=12,
                                                                                max_abs_battery_power_kW=5.055,
                                                                                initial_buying_rate=batt_ini_buy,
                                                                                final_buying_rate=batt_fin_buy,
                                                                                initial_selling_rate=batt_ini_sell,
                                                                                final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 5',
                         [
                             Area('Load 5', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[5],
                                                                                 initial_buying_rate=Load_initial_buying_rate,
                                                                                 final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 5', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[5],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 5', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                min_allowed_soc=0,
                                                                                battery_capacity_kWh=10,
                                                                                max_abs_battery_power_kW=5.239,
                                                                                initial_buying_rate=batt_ini_buy,
                                                                                final_buying_rate=batt_fin_buy,
                                                                                initial_selling_rate=batt_ini_sell,
                                                                                final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 6',
                         [
                             Area('Load 6', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[6],
                                                                                 initial_buying_rate=Load_initial_buying_rate,
                                                                                 final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),

                             Area('CHP 6', strategy=PVUserProfileExternalStrategy(
                                 power_profile=chp_data[6],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                         ]),

                    Area('Member 7',
                         [
                             Area('Load 7', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[7],
                                                                                 initial_buying_rate=Load_initial_buying_rate,
                                                                                 final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 7', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[7],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 7', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                min_allowed_soc=0,
                                                                                battery_capacity_kWh=8,
                                                                                max_abs_battery_power_kW=5.272,
                                                                                initial_buying_rate=batt_ini_buy,
                                                                                final_buying_rate=batt_fin_buy,
                                                                                initial_selling_rate=batt_ini_sell,
                                                                                final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 8',
                         [
                             Area('Load 8', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[8],
                                                                                 initial_buying_rate=Load_initial_buying_rate,
                                                                                 final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 8', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[8],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 8', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                min_allowed_soc=0,
                                                                                battery_capacity_kWh=6,
                                                                                max_abs_battery_power_kW=4.791,
                                                                                initial_buying_rate=batt_ini_buy,
                                                                                final_buying_rate=batt_fin_buy,
                                                                                initial_selling_rate=batt_ini_sell,
                                                                                final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 9',
                         [
                             Area('PV 9', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[9],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                         ]),

                    Area('Member 10',
                         [
                             Area('Load 10', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[10],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 10', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[10],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 10', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                 min_allowed_soc=0,
                                                                                 battery_capacity_kWh=6,
                                                                                 max_abs_battery_power_kW=4.16,
                                                                                 initial_buying_rate=batt_ini_buy,
                                                                                 final_buying_rate=batt_fin_buy,
                                                                                 initial_selling_rate=batt_ini_sell,
                                                                                 final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 11',
                         [
                             Area('Load 11', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[11],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 11', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[11],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 11', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                 min_allowed_soc=0,
                                                                                 battery_capacity_kWh=12,
                                                                                 max_abs_battery_power_kW=6.526,
                                                                                 initial_buying_rate=batt_ini_buy,
                                                                                 final_buying_rate=batt_fin_buy,
                                                                                 initial_selling_rate=batt_ini_sell,
                                                                                 final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 12',
                         [
                             Area('Load 12', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[12],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 12', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[12],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 12', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                 min_allowed_soc=0,
                                                                                 battery_capacity_kWh=6,
                                                                                 max_abs_battery_power_kW=6,
                                                                                 initial_buying_rate=batt_ini_buy,
                                                                                 final_buying_rate=batt_fin_buy,
                                                                                 initial_selling_rate=batt_ini_sell,
                                                                                 final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 13',
                         [
                             Area('Load 13', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[13],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 13', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[13],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),

                             Area('CHP 13', strategy=PVUserProfileExternalStrategy(
                                 power_profile=chp_data[13],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                         ]),

                    Area('Member 14',
                         [
                             Area('Load 14', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[14],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 14', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[14],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 14', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                 min_allowed_soc=0,
                                                                                 battery_capacity_kWh=6,
                                                                                 max_abs_battery_power_kW=4.816,
                                                                                 initial_buying_rate=batt_ini_buy,
                                                                                 final_buying_rate=batt_fin_buy,
                                                                                 initial_selling_rate=batt_ini_sell,
                                                                                 final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 15',
                         [
                             Area('Load 15', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[15],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('CHP 15', strategy=PVUserProfileExternalStrategy(
                                 power_profile=chp_data[15],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                         ]),

                    Area('Member 16',
                         [
                             Area('Load 16', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[16],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 16', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[16],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 16', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                 min_allowed_soc=0,
                                                                                 battery_capacity_kWh=6,
                                                                                 max_abs_battery_power_kW=6,
                                                                                 initial_buying_rate=batt_ini_buy,
                                                                                 final_buying_rate=batt_fin_buy,
                                                                                 initial_selling_rate=batt_ini_sell,
                                                                                 final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 17',
                         [
                             Area('Load 17', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[17],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 17', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[17],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 17', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                 min_allowed_soc=0,
                                                                                 battery_capacity_kWh=6,
                                                                                 max_abs_battery_power_kW=6,
                                                                                 initial_buying_rate=batt_ini_buy,
                                                                                 final_buying_rate=batt_fin_buy,
                                                                                 initial_selling_rate=batt_ini_sell,
                                                                                 final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 18',
                         [
                             Area('Load 18', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[18],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 18', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[18],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 18', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                 min_allowed_soc=0,
                                                                                 battery_capacity_kWh=12,
                                                                                 max_abs_battery_power_kW=7.578,
                                                                                 initial_buying_rate=batt_ini_buy,
                                                                                 final_buying_rate=batt_fin_buy,
                                                                                 initial_selling_rate=batt_ini_sell,
                                                                                 final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 19',
                         [
                             Area('Load 19', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[19],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 19', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[19],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 19', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                 min_allowed_soc=0,
                                                                                 battery_capacity_kWh=6,
                                                                                 max_abs_battery_power_kW=5.4,
                                                                                 initial_buying_rate=batt_ini_buy,
                                                                                 final_buying_rate=batt_fin_buy,
                                                                                 initial_selling_rate=batt_ini_sell,
                                                                                 final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 20',
                         [
                             Area('Load 20', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[20],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 20', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[20],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 20', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                 min_allowed_soc=0,
                                                                                 battery_capacity_kWh=6,
                                                                                 max_abs_battery_power_kW=3.738,
                                                                                 initial_buying_rate=batt_ini_buy,
                                                                                 final_buying_rate=batt_fin_buy,
                                                                                 initial_selling_rate=batt_ini_sell,
                                                                                 final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 21',
                         [
                             Area('Load 21', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[21],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('CHP 21', strategy=PVUserProfileExternalStrategy(
                                 power_profile=chp_data[21],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                         ]),

                    Area('Member 22',
                         [
                             Area('Load 22', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[22],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('CHP 22', strategy=PVUserProfileExternalStrategy(
                                 power_profile=chp_data[22],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                         ]),

                    Area('Member 23',
                         [
                             Area('Load 23', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[23],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 23', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[23],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 23', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                 min_allowed_soc=0,
                                                                                 battery_capacity_kWh=150,
                                                                                 max_abs_battery_power_kW=50,
                                                                                 initial_buying_rate=batt_ini_buy,
                                                                                 final_buying_rate=batt_fin_buy,
                                                                                 initial_selling_rate=batt_ini_sell,
                                                                                 final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 24',
                         [
                             Area('Load 24', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[24],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 24', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[24],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 24', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                 min_allowed_soc=0,
                                                                                 battery_capacity_kWh=6,
                                                                                 max_abs_battery_power_kW=6,
                                                                                 initial_buying_rate=batt_ini_buy,
                                                                                 final_buying_rate=batt_fin_buy,
                                                                                 initial_selling_rate=batt_ini_sell,
                                                                                 final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                    Area('Member 25',
                         [
                             Area('Load 25', strategy=LoadProfileExternalStrategy(daily_load_profile=load_data[25],
                                                                                  initial_buying_rate=Load_initial_buying_rate,
                                                                                  final_buying_rate=Load_final_buying_rate),
                                  appliance=SwitchableAppliance()),
                             Area('PV 25', strategy=PVUserProfileExternalStrategy(
                                 power_profile=pv_data[25],
                                 initial_selling_rate=PV_initial,
                                 final_selling_rate=PV_final),
                                  appliance=PVAppliance()),
                             Area('Storage 25', strategy=StorageExternalStrategy(initial_soc=ini_SOC,
                                                                                 min_allowed_soc=0,
                                                                                 battery_capacity_kWh=8,
                                                                                 max_abs_battery_power_kW=3.839,
                                                                                 initial_buying_rate=batt_ini_buy,
                                                                                 final_buying_rate=batt_fin_buy,
                                                                                 initial_selling_rate=batt_ini_sell,
                                                                                 final_selling_rate=batt_fin_sell),
                                  appliance=SwitchableAppliance()),
                         ]),

                ], grid_fee_constant=4, external_connection_available=True),


            Area('Market maker and FiT', strategy=InfiniteBusStrategy(energy_buy_rate=21.9, energy_sell_rate=22),
                 appliance=SimpleAppliance()),

        ],
        config=config, grid_fee_constant=4, external_connection_available=True
    )
    return area
