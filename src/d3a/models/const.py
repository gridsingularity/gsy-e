"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


class ConstSettings:
    class GeneralSettings:
        # Max risk value for all risk based strategies. Unit is percentage.
        MAX_RISK = 100
        # Default risk value for all risk based strategies. Unit is percentage.
        DEFAULT_RISK = 50
        # Max energy price (market maker rate) in ct / kWh
        DEFAULT_MARKET_MAKER_RATE = 30  # 0.3 Eur
        # Maximum number of area hierarchies. If None, this parameter will be
        # automatically calculated.
        MAX_OFFER_TRAVERSAL_LENGTH = None
        # Number of times Market cwlearing rate has to be calculated per slot
        MARKET_CLEARING_FREQUENCY_PER_SLOT = 3
        ENERGY_RATE_DECREASE_PER_UPDATE = 1  # rate decrease in cents_per_update
        SETUP_FILE_PATH = None  # Default path of the available setup files

    class StorageSettings:
        # Max battery capacity in kWh.
        CAPACITY = 1.2
        # Maximum battery power for supply/demand, in Watts.
        MAX_ABS_POWER = 5
        # Initial ESS rate calculation for every market slot, before rate reduction per tick
        # Option 1, use the historical market average
        # Default value 2 stands for market maker rate
        # Option 3, use the initial_selling_rate
        INITIAL_RATE_OPTION = 2
        # Energy rate decrease option for unsold ESS offers
        # Default value 1 stands for percentage/RISK based energy rate decrease
        # Option 2, use the constant energy rate decrease
        RATE_DECREASE_OPTION = 1
        # Energy sell break-even point, storage never sells for less than this value.
        # Unit is ct/kWh.
        BREAK_EVEN_SELL = 25
        # Energy buy break-even point, storage never buys for more than this value.
        # Unit is ct/kWh.
        BREAK_EVEN_BUY = 24.9
        # Minimum acceptable buy rate for the battery, in ct/kWh.
        MIN_BUYING_RATE = 24.9
        # Min allowed battery SOC, range is [0, 1].
        MIN_ALLOWED_SOC = 0.1
        # Controls whether energy is sold only on the most expensive market, default is
        # to sell to all markets
        SELL_ON_MOST_EXPENSIVE_MARKET = False

    class LoadSettings:
        # Min load energy rate, in ct/kWh
        MIN_ENERGY_RATE = 0
        # Max load energy rate, in ct/kWh
        MAX_ENERGY_RATE = 35

    class PVSettings:
        # This price should be just above the marginal costs for a PV system - unit is cents
        FINAL_SELLING_RATE = 0
        # Option 1, use the historical market average
        # Default value 2 stands for market maker rate
        # Option 3, use the initial_selling_rate
        INITIAL_RATE_OPTION = 2
        # Energy rate decrease option for unsold PV offers
        # Default value 1 stands for percentage/RISK based energy rate decrease
        # Option 2, use the constant energy rate decrease
        RATE_DECREASE_OPTION = 1
        # Applies to the predefined PV strategy, where a PV profile is selected out of 3 predefined
        # ones. Available values 0: sunny, 1: partial cloudy, 2: cloudy
        DEFAULT_POWER_PROFILE = 0
        # Applies to gaussian PVStrategy, controls the max panel output in Watts.
        MAX_PANEL_OUTPUT_W = 160

    class WindSettings:
        # This price should be just above the marginal costs for a Wind Power Plant - unit is cent
        FINAL_SELLING_RATE = 0
        # Option 1, use the historical market average
        # Default value 2 stands for market maker rate
        INITIAL_RATE_OPTION = 2
        # Energy rate decrease option for unsold WindPower offers
        # Default value 1 stands for percentage/RISK based energy rate decrease
        # Option 2, use the constant energy rate decrease
        RATE_DECREASE_OPTION = 1
        MAX_WIND_TURBINE_OUTPUT_W = 160

    class IAASettings:
        # Percentage value that controls the fee the IAA adds to the offers and bids.
        FEE_PERCENTAGE = 1
        # Market type option
        # Default value 1 stands for single sided market
        # Option 2 stands for double sided pay as bid market
        # Option 3 stands for double sided pay as clear market
        MARKET_TYPE = 1

    class BlockchainSettings:
        # Blockchain URL, default is localhost.
        URL = "http://127.0.0.1:8545"
        # Controls whether a local Ganache blockchain will start automatically by D3A.
        START_LOCAL_CHAIN = True
        # Password for the base blockchain account
        ACCOUNT_PASSWORD = "testgsy"
        # Timeout for blockchain operations, in seconds
        TIMEOUT = 30

    class BalancingSettings:
        # Enables/disables balancing market
        ENABLE_BALANCING_MARKET = False
        # Controls the percentage of the energy traded in the spot market that needs to be
        # acquired by the balancing market on each IAA.
        SPOT_TRADE_RATIO = 0.2
        # Controls the percentage of demand that can be offered on the balancing markets
        # by devices that can offer demand. Range between [0, 1]
        OFFER_DEMAND_RATIO = 0.1
        # Controls the percentage of supply that can be offered on the balancing markets
        # by devices that can offer supply. Range between [0, 1]
        OFFER_SUPPLY_RATIO = 0.1
        # Adds flexible load support.
        FLEXIBLE_LOADS_SUPPORT = True
