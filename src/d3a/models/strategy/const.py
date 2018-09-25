class ConstSettings:

    # GENERAL SETTINGS
    # Unit is percentage
    MAX_RISK = 100
    # Unit is percentage
    DEFAULT_RISK = 50
    # Max energy price in ct / kWh
    DEFAULT_MARKET_MAKER_RATE = 30  # 0.3 Eur

    # FRIDGE SETTINGS
    # Unit is degree celsius
    MAX_FRIDGE_TEMP = 8.0
    # Unit is degree celsius
    MIN_FRIDGE_TEMP = 4.0
    # Unit is degree celsius
    FRIDGE_TEMPERATURE = 6.0

    # MARKET RELATED LIMITATIONS
    # Unit is in Wh
    FRIDGE_MIN_NEEDED_ENERGY = 10

    # ENERGY STORAGE SETTINGS
    # Unit is kWh
    STORAGE_CAPACITY = 1.2
    # Unit is kW
    MAX_ABS_BATTERY_POWER = 5
    # Initial ESS rate calculation for every market slot, before rate reduction per tick
    # Option 1, use the historical market average
    # Default value 2 stands for market maker rate
    INITIAL_ESS_RATE_OPTION = 2
    # Energy rate decrease option for unsold ESS offers
    # Default value 1 stands for percentage/RISK based energy rate decrease
    # Option 2, use the constant energy rate decrease
    ESS_RATE_DECREASE_OPTION = 1
    # Energy Sell/Buy Break-even
    STORAGE_BREAK_EVEN_SELL = 25
    STORAGE_BREAK_EVEN_BUY = 24.9
    STORAGE_MIN_BUYING_RATE = 24.9
    STORAGE_MIN_ALLOWED_SOC = 0.1
    STORAGE_SELL_ON_MOST_EXPENSIVE_MARKET = False
    # PV SETTINGS
    # This price should be just above the marginal costs for a PV system - unit is cent
    MIN_PV_SELLING_RATE = 0

    # LOAD SETTINGS
    LOAD_MIN_ENERGY_RATE = 0
    LOAD_MAX_ENERGY_RATE = 35

    # Option 1, use the historical market average
    # Default value 2 stands for market maker rate
    INITIAL_PV_RATE_OPTION = 2

    # Energy rate decrease option for unsold PV offers
    # Default value 1 stands for percentage/RISK based energy rate decrease
    # Option 2, use the constant energy rate decrease
    PV_RATE_DECREASE_OPTION = 1

    ENERGY_RATE_DECREASE_PER_UPDATE = 1  # rate decrease in cents_per_update

    DEFAULT_PV_POWER_PROFILE = 0  # sunny
    PV_MAX_PANEL_OUTPUT_W = 160

    # HEATPUMP SETTINGS
    # This is the season depended temperature of the earth in 2-3m depth (Between 4C and 10C)
    EARTH_TEMP = 6.0
    # Unit is degree celsius
    MAX_STORAGE_TEMP = 55.0
    # Unit is degree celsius
    MIN_STORAGE_TEMP = 30.0
    # Unit is degree celsius
    INITIAL_PUMP_STORAGE_TEMP = 30.0
    # Unit is in Wh
    PUMP_MIN_NEEDED_ENERGY = 50
    # Temperature increment of the storage per min Needed Energy
    # Assuming 200L storage capacity and a heat pump conversion efficiency of 5
    # --> (1kWh energy = 5kWh heat)
    # This means 50 Wh increase the temp of the storage for 0.2C
    PUMP_MIN_TEMP_INCREASE = 2

    # ECAR SETTINGS
    # Car: Arrival time at charging station
    ARRIVAL_TIME = 1
    # Car: Depart time from charging station
    DEPART_TIME = 23

    # PREDEF_LEAD SETTINGS
    # Minimal consumption per household in Wh
    MIN_HOUSEHOLD_CONSUMPTION = 70

    # INTER_AREA_AGENT
    # This parameter is modified by the Simulation class
    MAX_OFFER_TRAVERSAL_LENGTH = None

    INTER_AREA_AGENT_FEE_PERCENTAGE = 1

    # Market type option
    # Default value 1 stands for single sided market
    # Option 2 stands for double sided pay as bid market
    INTER_AREA_AGENT_MARKET_TYPE = 1

    # Balancing Market parameter
    BALANCING_SPOT_TRADE_RATIO = 0.2
