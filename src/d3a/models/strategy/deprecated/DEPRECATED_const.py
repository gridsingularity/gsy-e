class ConstSettings:

    class HeatpumpSettings:
        # This is the season depended temperature of the earth in 2-3m depth (Between 4C and 10C)
        EARTH_TEMP = 6.0
        # Unit is degree celsius
        MAX_STORAGE_TEMP = 55.0
        # Unit is degree celsius
        MIN_STORAGE_TEMP = 30.0
        # Unit is degree celsius
        INITIAL_STORAGE_TEMP = 30.0
        # Unit is in Wh
        MIN_NEEDED_ENERGY = 50
        # Temperature increment of the storage per min Needed Energy
        # Assuming 200L storage capacity and a heat pump conversion efficiency of 5
        # --> (1kWh energy = 5kWh heat)
        # This means 50 Wh increase the temp of the storage for 0.2C
        MIN_TEMP_INCREASE = 2

    class EcarSettings:
        # Car: Arrival time at charging station
        ARRIVAL_TIME = 1
        # Car: Depart time from charging station
        DEPART_TIME = 23

    class PredefinedLoadSettings:
        # Minimal consumption per household in Wh
        MIN_HOUSEHOLD_CONSUMPTION = 70

    class FridgeSettings:
        # Unit is degree celsius
        MAX_TEMP = 8.0
        # Unit is degree celsius
        MIN_TEMP = 4.0
        # Unit is degree celsius
        TEMPERATURE = 6.0
        # MARKET RELATED LIMITATIONS
        # Unit is in Wh
        MIN_NEEDED_ENERGY = 10
