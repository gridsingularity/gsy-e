"""
This is a template which represent a community of 28 houses. Only the devices of house 1 can be controlled with an external connection

This configuration can be subject to modifications (PV & storage capacity, adding/deleting devices and area)

We recommend to train your smart agents on multiple configurations to achieve better result during the hackathon
"""
# flake8: noqa
import os
import platform
from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.market_maker_strategy import MarketMakerStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a_interface.constants_limits import ConstSettings
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.predefined_pv import PVUserProfileStrategy
from d3a.models.strategy.external_strategies.pv import PVUserProfileExternalStrategy
from d3a.models.strategy.external_strategies.load import LoadProfileExternalStrategy
from d3a.models.strategy.external_strategies.storage import StorageExternalStrategy
from random import random

current_dir = os.path.dirname(__file__)
print(current_dir)

WEEK_NUM = 3  # 3 = 06.10.2016, 2 = 29.09.2016, 1 = 22.09.2016
VARIANCE_RATES = 0.2  # variance against starting rate (0.8 to 1.2 times starting if set to 0.2)

load1 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_1week"+str(WEEK_NUM)+".csv")  #path to your csv file
pv1 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_1week"+str(WEEK_NUM)+".csv")
load2 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_2week"+str(WEEK_NUM)+".csv")
pv2 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_2week"+str(WEEK_NUM)+".csv")
load3 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_3week"+str(WEEK_NUM)+".csv")
pv3 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_3week"+str(WEEK_NUM)+".csv")
load4 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_4week"+str(WEEK_NUM)+".csv")
pv4 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_4week"+str(WEEK_NUM)+".csv")
load5 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_5week"+str(WEEK_NUM)+".csv")
load6 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_6week"+str(WEEK_NUM)+".csv")
pv6 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_6week"+str(WEEK_NUM)+".csv")
load7 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_7week"+str(WEEK_NUM)+".csv")
pv7 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_7week"+str(WEEK_NUM)+".csv")
load8 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_8week"+str(WEEK_NUM)+".csv")
pv8 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_8week"+str(WEEK_NUM)+".csv")
load9 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_9week"+str(WEEK_NUM)+".csv")
pv9 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_9week"+str(WEEK_NUM)+".csv")
load10 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_10week"+str(WEEK_NUM)+".csv")
pv10 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_10week"+str(WEEK_NUM)+".csv")
load11 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_11week"+str(WEEK_NUM)+".csv")
pv11 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_11week"+str(WEEK_NUM)+".csv")
load12 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_12week"+str(WEEK_NUM)+".csv")
pv12 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_12week"+str(WEEK_NUM)+".csv")
load13 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_13week"+str(WEEK_NUM)+".csv")
pv13 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_13week"+str(WEEK_NUM)+".csv")
load14 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_14week"+str(WEEK_NUM)+".csv")
pv14 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_14week"+str(WEEK_NUM)+".csv")
load15 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_15week"+str(WEEK_NUM)+".csv")
load16 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_16week"+str(WEEK_NUM)+".csv")
load17 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_17week"+str(WEEK_NUM)+".csv")
load18 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_18week"+str(WEEK_NUM)+".csv")
pv18 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_18week"+str(WEEK_NUM)+".csv")
load19 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_19week"+str(WEEK_NUM)+".csv")
pv19 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_19week"+str(WEEK_NUM)+".csv")
load20 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_20week"+str(WEEK_NUM)+".csv")
pv20 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_20week"+str(WEEK_NUM)+".csv")
load21 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_21week"+str(WEEK_NUM)+".csv")
pv21 = os.path.join(current_dir, "resources/PV/week"+str(WEEK_NUM)+"/PV_21week"+str(WEEK_NUM)+".csv")
load22 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_22week"+str(WEEK_NUM)+".csv")
load23 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_23week"+str(WEEK_NUM)+".csv")
load24 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_24week"+str(WEEK_NUM)+".csv")
load25 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_25week"+str(WEEK_NUM)+".csv")
load26 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_26week"+str(WEEK_NUM)+".csv")
load27 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_27week"+str(WEEK_NUM)+".csv")
load28 = os.path.join(current_dir, "resources/Load/week"+str(WEEK_NUM)+"/Load_28week"+str(WEEK_NUM)+".csv")


def get_setup(config):

    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 3
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE = 30

    Houses_initial_buying_rate = 10
    PV_initial = 20
    PV_final = 4

    area = Area(
        'grid',
        [
            Area(
                'Community',
                [
                    Area(
                        'house-1-s',
                        [
                            Area('h1-load-s', strategy=LoadProfileExternalStrategy(daily_load_profile=load1,
                                                                                   initial_buying_rate=Houses_initial_buying_rate,
                                                                                   use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h1-pv-s', strategy=PVUserProfileExternalStrategy(power_profile=pv1,
                                                                                   initial_selling_rate=PV_initial,
                                                                                   final_selling_rate=PV_final),
                                 appliance=PVAppliance()),

                            Area('h1-storage-s', strategy=StorageExternalStrategy(initial_soc=50,
                                                                       min_allowed_soc=10,
                                                                       battery_capacity_kWh=5,
                                                                       max_abs_battery_power_kW=4),
                                 appliance=SwitchableAppliance()),

                        ], grid_fee_percentage=0, transfer_fee_const=0, external_connection_available=True
                    ),
                    Area(
                        'house-2',
                        [
                            Area('h2-load', strategy=DefinedLoadStrategy(daily_load_profile=load2,
                                                                         initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h2-pv', strategy=PVUserProfileStrategy(power_profile=pv2,
                                                                         initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         final_selling_rate=PV_final),
                                 appliance=PVAppliance()),

                            Area('h2-storage', strategy=StorageStrategy(initial_soc=50,
                                                                       min_allowed_soc=10,
                                                                       battery_capacity_kWh=5,
                                                                       max_abs_battery_power_kW=4,
                                                                       initial_buying_rate=12,
                                                                       final_buying_rate=15,
                                                                       initial_selling_rate=29,
                                                                       final_selling_rate=15.01),
                                 appliance=SwitchableAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-3',
                        [
                            Area('h3-load', strategy=DefinedLoadStrategy(daily_load_profile=load3,
                                                                         initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h3-pv', strategy=PVUserProfileStrategy(power_profile=pv3,
                                                                         initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         final_selling_rate=PV_final),
                                 appliance=PVAppliance()),

                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-4',
                        [
                            Area('h4-load', strategy=DefinedLoadStrategy(daily_load_profile=load4,
                                                                         initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h4-pv', strategy=PVUserProfileStrategy(power_profile=pv4,
                                                                         initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         final_selling_rate=PV_final),
                                 appliance=PVAppliance()),

                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-5',
                        [
                            Area('h5-load', strategy=DefinedLoadStrategy(daily_load_profile=load5,
                                                                         initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-6',
                        [
                            Area('h6-load', strategy=DefinedLoadStrategy(daily_load_profile=load6,
                                                                         initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h6-pv', strategy=PVUserProfileStrategy(power_profile=pv6,
                                                                         initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         final_selling_rate=PV_final),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-7',
                        [
                            Area('h7-load', strategy=DefinedLoadStrategy(daily_load_profile=load7,
                                                                         initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h7-pv', strategy=PVUserProfileStrategy(power_profile=pv7,
                                                                         initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         final_selling_rate=PV_final),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-8',
                        [
                            Area('h8-load', strategy=DefinedLoadStrategy(daily_load_profile=load8,
                                                                         initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h8-pv', strategy=PVUserProfileStrategy(power_profile=pv8,
                                                                         initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         final_selling_rate=PV_final),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-9',
                        [
                            Area('h9-load', strategy=DefinedLoadStrategy(daily_load_profile=load9,
                                                                         initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h9-pv', strategy=PVUserProfileStrategy(power_profile=pv9,
                                                                         initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                         final_selling_rate=PV_final),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-10',
                        [
                            Area('h10-load', strategy=DefinedLoadStrategy(daily_load_profile=load10,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h10-pv', strategy=PVUserProfileStrategy(power_profile=pv10,
                                                                          initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          final_selling_rate=PV_final),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-11',
                        [
                            Area('h11-load', strategy=DefinedLoadStrategy(daily_load_profile=load11,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h11-pv', strategy=PVUserProfileStrategy(power_profile=pv11,
                                                                          initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          final_selling_rate=PV_final),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-12',
                        [
                            Area('h12-load', strategy=DefinedLoadStrategy(daily_load_profile=load12,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h12-pv', strategy=PVUserProfileStrategy(power_profile=pv12,
                                                                          initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          final_selling_rate=PV_final),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-13',
                        [
                            Area('h13-load', strategy=DefinedLoadStrategy(daily_load_profile=load13,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h13-pv', strategy=PVUserProfileStrategy(power_profile=pv13,
                                                                          initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          final_selling_rate=PV_final),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-14',
                        [
                            Area('h14-load', strategy=DefinedLoadStrategy(daily_load_profile=load14,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h14-pv', strategy=PVUserProfileStrategy(power_profile=pv14,
                                                                          initial_selling_rate=PV_initial * round((random() - 0.5) * VARIANCE_RATES + 1, 2),
                                                                          final_selling_rate=PV_final),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-15',
                        [
                            Area('h15-load', strategy=DefinedLoadStrategy(daily_load_profile=load15,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-16',
                        [
                            Area('h16-load', strategy=DefinedLoadStrategy(daily_load_profile=load16,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-17',
                        [
                            Area('h17-load', strategy=DefinedLoadStrategy(daily_load_profile=load17,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-18',
                        [
                            Area('h18-load', strategy=DefinedLoadStrategy(daily_load_profile=load18,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h18-pv', strategy=PVUserProfileStrategy(power_profile=pv18,
                                                                          initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          final_selling_rate=PV_final),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-19',
                        [
                            Area('h19-load', strategy=DefinedLoadStrategy(daily_load_profile=load19,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h19-pv', strategy=PVUserProfileStrategy(power_profile=pv19,
                                                                          initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          final_selling_rate=PV_final),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-20',
                        [
                            Area('h20-load', strategy=DefinedLoadStrategy(daily_load_profile=load20,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h20-pv', strategy=PVUserProfileStrategy(power_profile=pv20,
                                                                          initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          final_selling_rate=PV_final),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-21',
                        [
                            Area('h21-load', strategy=DefinedLoadStrategy(daily_load_profile=load21,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),

                            Area('h21-pv', strategy=PVUserProfileStrategy(power_profile=pv21,
                                                                          initial_selling_rate=PV_initial*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          final_selling_rate=PV_final),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-22',
                        [
                            Area('h22-load', strategy=DefinedLoadStrategy(daily_load_profile=load22,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-23',
                        [
                            Area('h23-load', strategy=DefinedLoadStrategy(daily_load_profile=load23,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-24',
                        [
                            Area('h24-load', strategy=DefinedLoadStrategy(daily_load_profile=load24,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-25',
                        [
                            Area('h25-load', strategy=DefinedLoadStrategy(daily_load_profile=load25,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-26',
                        [
                            Area('h26-load', strategy=DefinedLoadStrategy(daily_load_profile=load26,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-27',
                        [
                            Area('h27-load', strategy=DefinedLoadStrategy(daily_load_profile=load27,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'house-28',
                        [
                            Area('h28-load', strategy=DefinedLoadStrategy(daily_load_profile=load28,
                                                                          initial_buying_rate=Houses_initial_buying_rate*round((random()-0.5)*VARIANCE_RATES + 1, 2),
                                                                          use_market_maker_rate=True),
                                 appliance=SwitchableAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                ], grid_fee_percentage=0, transfer_fee_const=0, external_connection_available=True
            ),


            Area('Feed-in tariff', strategy=LoadHoursStrategy(avg_power_W=100000000, hrs_per_day=24, hrs_of_day=list(range(0, 24)),
                                                              initial_buying_rate=11,
                                                              final_buying_rate=11),
                 appliance=SwitchableAppliance()),


            Area('Market Maker', strategy=MarketMakerStrategy(energy_rate=ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE, grid_connected=True), appliance=SimpleAppliance()),


        ],
        config=config, grid_fee_percentage=0, transfer_fee_const=0, external_connection_available=False
    )
    return area
