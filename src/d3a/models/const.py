class ConstSettings:

    class GeneralSettings:
        # Unit is percentage
        MAX_RISK = 100
        # Unit is percentage
        DEFAULT_RISK = 50
        # Max energy price in ct / kWh
        DEFAULT_MARKET_MAKER_RATE = 30  # 0.3 Eur
        # This parameter is modified by the Simulation class
        MAX_OFFER_TRAVERSAL_LENGTH = None
        ENERGY_RATE_DECREASE_PER_UPDATE = 1  # rate decrease in cents_per_update

    class StorageSettings:
        # Unit is kWh
        CAPACITY = 1.2
        # Unit is kW
        MAX_ABS_POWER = 5
        # Initial ESS rate calculation for every market slot, before rate reduction per tick
        # Option 1, use the historical market average
        # Default value 2 stands for market maker rate
        INITIAL_RATE_OPTION = 2
        # Energy rate decrease option for unsold ESS offers
        # Default value 1 stands for percentage/RISK based energy rate decrease
        # Option 2, use the constant energy rate decrease
        RATE_DECREASE_OPTION = 1
        # Energy Sell/Buy Break-even
        BREAK_EVEN_SELL = 25
        BREAK_EVEN_BUY = 24.9
        MIN_BUYING_RATE = 24.9
        MIN_ALLOWED_SOC = 0.1
        SELL_ON_MOST_EXPENSIVE_MARKET = False

    class LoadSettings:
        MIN_ENERGY_RATE = 0
        MAX_ENERGY_RATE = 35

    class PVSettings:
        # This price should be just above the marginal costs for a PV system - unit is cent
        MIN_SELLING_RATE = 0
        # Option 1, use the historical market average
        # Default value 2 stands for market maker rate
        INITIAL_RATE_OPTION = 2
        # Energy rate decrease option for unsold PV offers
        # Default value 1 stands for percentage/RISK based energy rate decrease
        # Option 2, use the constant energy rate decrease
        RATE_DECREASE_OPTION = 1
        DEFAULT_POWER_PROFILE = 0  # sunny
        MAX_PANEL_OUTPUT_W = 160

    class WindSettings:
        # This price should be just above the marginal costs for a Wind Power Plant - unit is cent
        MIN_SELLING_RATE = 0
        # Option 1, use the historical market average
        # Default value 2 stands for market maker rate
        INITIAL_RATE_OPTION = 2
        # Energy rate decrease option for unsold WindPower offers
        # Default value 1 stands for percentage/RISK based energy rate decrease
        # Option 2, use the constant energy rate decrease
        RATE_DECREASE_OPTION = 1
        MAX_WIND_TURBINE_OUTPUT_W = 160

    class IAASettings:
        # IAA fee
        FEE_PERCENTAGE = 1
        # Market type option
        # Default value 1 stands for single sided market
        # Option 2 stands for double sided pay as bid market
        MARKET_TYPE = 1

    class BlockchainSettings:
        URL = "http://127.0.0.1:8545"
        START_LOCAL_CHAIN = True
        ACCOUNT_PASSWORD = "testgsy"

    class BalancingSettings:
        ENABLE_BALANCING_MARKET = False
        SPOT_TRADE_RATIO = 0.2
        OFFER_DEMAND_RATIO = 0.1
        OFFER_SUPPLY_RATIO = 0.1
        FLEXIBLE_LOADS_SUPPORT = True
