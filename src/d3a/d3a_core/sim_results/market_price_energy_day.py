from collections import OrderedDict
from statistics import mean

from d3a.d3a_core.util import round_floats_for_ui


class MarketPriceEnergyDay:
    def __init__(self, should_export_plots):
        self._price_energy_day = {}
        self.csv_output = {}
        self.redis_output = {}
        self.should_export_plots = should_export_plots

    @classmethod
    def gather_trade_rates(cls, area_dict, core_stats, current_market_slot, price_lists,
                           fee_lists):
        if area_dict['children'] == []:
            return price_lists, fee_lists

        cls.gather_rates_one_market(area_dict, core_stats, current_market_slot, price_lists,
                                    fee_lists)

        for child in area_dict['children']:
            price_lists, fee_lists = cls.gather_trade_rates(child, core_stats, current_market_slot,
                                                            price_lists, fee_lists)

        return price_lists, fee_lists

    @classmethod
    def gather_rates_one_market(cls, area_dict, core_stats, current_market_slot, price_lists,
                                fee_lists):
        if area_dict['uuid'] not in price_lists:
            price_lists[area_dict['uuid']] = OrderedDict()
        if current_market_slot not in price_lists[area_dict['uuid']].keys():
            price_lists[area_dict['uuid']][current_market_slot] = []
        trade_rates = [
            # Convert from cents to euro
            t['energy_rate'] / 100.0
            for t in core_stats.get(area_dict['uuid'], {}).get('trades', [])
        ]
        price_lists[area_dict['uuid']][current_market_slot].extend(trade_rates)

        if area_dict['uuid'] not in fee_lists:
            fee_lists[area_dict['uuid']] = OrderedDict()
        if current_market_slot not in fee_lists[area_dict['uuid']].keys():
            fee_lists[area_dict['uuid']][current_market_slot] = []
        fee_rates = [
            # Convert from cents to euro
            t['fee_price'] / 100.0 / t['energy']
            for t in core_stats.get(area_dict['uuid'], {}).get('trades', [])
        ]
        fee_lists[area_dict['uuid']][current_market_slot].extend(fee_rates)

    def update(self, area_result_dict={}, core_stats={}, current_market_slot=None):
        if current_market_slot is None:
            return
        current_price_lists, current_fee_lists = self.gather_trade_rates(
            area_result_dict, core_stats, current_market_slot, {}, {}
        )
        price_energy_redis_output = {}
        self._convert_output_format(current_price_lists, price_energy_redis_output,
                                    current_fee_lists)
        if self.should_export_plots:
            self.calculate_csv_output(area_result_dict, price_energy_redis_output)
        else:
            self.redis_output = price_energy_redis_output

    def calculate_csv_output(self, area_dict, price_energy_redis_output):
        if not price_energy_redis_output.get(area_dict['uuid'], {}).get('price-energy-day', []):
            return
        if area_dict['name'] not in self.csv_output:
            self.csv_output[area_dict['name']] = {
                "price-currency": "Euros",
                "load-unit": "kWh",
                "price-energy-day": [],
                "grid-fee-rate": []
            }
        self.csv_output[area_dict['name']]["price-energy-day"].\
            append(price_energy_redis_output[area_dict['uuid']]['price-energy-day'])
        self.csv_output[area_dict['name']]["grid-fee-rate"].\
            append(price_energy_redis_output[area_dict['uuid']]['grid-fee-rate'])
        for child in area_dict['children']:
            self.calculate_csv_output(child, price_energy_redis_output)

    @staticmethod
    def _convert_output_format(price_energy, redis_output, fees):
        for node_name, trade_rates in price_energy.items():
            if node_name not in redis_output:
                redis_output[node_name] = {
                    "price-currency": "Euros",
                    "load-unit": "kWh",
                    "price-energy-day": [],
                    "grid-fee-rate": []
                }
            redis_output[node_name]["price-energy-day"] = [
                {
                    "time": timeslot,
                    "av_price": round_floats_for_ui(mean(trades) if len(trades) > 0 else 0),
                    "min_price": round_floats_for_ui(min(trades) if len(trades) > 0 else 0),
                    "max_price": round_floats_for_ui(max(trades) if len(trades) > 0 else 0),
                } for timeslot, trades in trade_rates.items()
            ]
        for node_name, fee_rates in fees.items():
            redis_output[node_name]["grid-fee-rate"] = [
                {
                    "time": timeslot,
                    "av_price": round_floats_for_ui(mean(fee_rate) if len(fee_rate) > 0 else 0),
                    "min_price": round_floats_for_ui(min(fee_rate) if len(fee_rate) > 0 else 0),
                    "max_price": round_floats_for_ui(max(fee_rate) if len(fee_rate) > 0 else 0),
                } for timeslot, fee_rate in fee_rates.items()
            ]
