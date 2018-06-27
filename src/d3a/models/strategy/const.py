# GENERAL SETTINGS
# Unit is percentage
MAX_RISK = 100
# Unit is percentage
DEFAULT_RISK = 50
# Max energy price in ct / kWh
MAX_ENERGY_RATE = 30  # 0.3 Eur

# FRIDGE SETTINGS
# Unit is degree celsius
MAX_FRIDGE_TEMP = 8.0
# Unit is degree celsius
MIN_FRIDGE_TEMP = 4.0
# Unit is degree celsius
FRIDGE_TEMPERATURE = 6.0

# MARKET RELATED LIMITATIONS
# Unit is cent
MIN_AVERAGE_PRICE = 15
# Unit is in Wh
FRIDGE_MIN_NEEDED_ENERGY = 10

# ENERGY STORAGE SETTINGS
# Unit is kWh
STORAGE_CAPACITY = 1.2
# Unit is kW
MAX_ABS_BATTERY_POWER = 1.2
# Energy Sell/Buy Break-even
STORAGE_BREAK_EVEN = 25
STORAGE_MAX_SELL_RATE_c_per_Kwh = MAX_ENERGY_RATE-1

STORAGE_MIN_ALLOWED_SOC = 0.1

# PV SETTINGS
# This price should be just above the marginal costs for a PV system - unit is cent
MIN_PV_SELLING_PRICE = 0

DEFAULT_PV_POWER_PROFILE = 0  # sunny

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

# COMMERCIAL PRODUCER SETTINGS
# Amount of posted offers per market
COMMERCIAL_OFFERS = 20

MAX_OFFER_TRAVERSAL_LENGTH = 10
PV_DECREASE_PER_SECOND_BY = 0.01

INTER_AREA_AGENT_FEE_PERCENTAGE = 1
