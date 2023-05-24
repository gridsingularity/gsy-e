import csv

from gsy_e.gsy_e_core.util import d3a_path
import os
from gsy_e.utils.csv_to_dict import CsvToDict


day = "2022-04-09"
b04_path = os.path.join(d3a_path,"resources","liege",day,"b04.csv")

print(CsvToDict.convert(path=b04_path, multiplier=1.0))