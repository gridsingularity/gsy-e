import csv

class CsvToDict:
    @staticmethod
    def convert(path, multiplier = 1.0):

        with open(path, mode='r') as infile:
            reader = csv.reader(infile)
            next(reader)
            mydict = {rows[0]:float(rows[1]) * multiplier for rows in reader}

            return mydict