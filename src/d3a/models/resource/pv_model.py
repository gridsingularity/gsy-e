import datetime
# import inspect
# import os

# import numpy as np
import pandas as pd

# from pvlib import solarposition, irradiance, atmosphere, pvsystem
from pvlib.modelchain import ModelChain
from pvlib.pvsystem import retrieve_sam
from pvlib.tracking import SingleAxisTracker
from pvlib.forecast import GFS

"""
Implementation to generate PV production profile based on weather, location and time of day
"""
# California
latitude = 38.244923
longitude = -122.626991
tz = 'US/Pacific'

surface_tilt = 30
surface_azimuth = 180
albedo = 0.2

start = pd.Timestamp(datetime.date.today(), tz=tz)
end = start + pd.Timedelta(days=7)

fm = GFS()

sandia_modules = retrieve_sam('SandiaMod')
cec_inverters = retrieve_sam('cecinverter')

module = sandia_modules['Canadian_Solar_CS5P_220M___2009_']
inverter = cec_inverters['SMA_America__SC630CP_US_315V__CEC_2012_']

system = SingleAxisTracker(module_parameters=module,
                           inverter_parameters=inverter,
                           modules_per_string=15,
                           strings_per_inverter=300)

fx_data = fm.get_processed_data(latitude, longitude, start, end)

mc = ModelChain(system, fm.location)

irradiance = fx_data[['ghi', 'dni', 'dhi']]

weather = fx_data[['wind_speed', 'temp_air']]

mc.run_model(fx_data.index, irradiance=irradiance, weather=weather)

print(mc.ac)

