from collections import OrderedDict
from statistics import mean

from d3a.d3a_core.util import round_floats_for_ui
from d3a_interface.utils import key_in_dict_and_not_none


class MarketPriceEnergyDay:
    def __init__(self, should_export_plots):
        self._price_energy_day = {}
        self.csv_output = {}
        self.redis_output = {}
        self.should_export_plots = should_export_plots

    @classmethod
    def gather_trade_rates(cls, area_dict, core_stats, current_market_slot, price_lists):
        if area_dict['children'] == []:
            return price_lists

        cls.gather_rates_one_market(area_dict, core_stats, current_market_slot, price_lists)

        for child in area_dict['children']:
            price_lists = cls.gather_trade_rates(child, core_stats, current_market_slot,
                                                 price_lists)

        return price_lists

    @classmethod
    def gather_rates_one_market(cls, area_dict, core_stats, current_market_slot, price_lists):
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

    def update(self, area_result_dict=None, core_stats=None, current_market_slot=None):
        if current_market_slot is None or area_result_dict is None or core_stats is None:
            return
        current_price_lists = self.gather_trade_rates(
            area_result_dict, core_stats, current_market_slot, {}
        )
        price_energy_redis_output = {}
        self._convert_output_format(current_price_lists, price_energy_redis_output,
                                    core_stats)
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
                "price-energy-day": []
            }
        self.csv_output[area_dict['name']]["price-energy-day"].\
            append(price_energy_redis_output[area_dict['uuid']]['price-energy-day'])
        for child in area_dict['children']:
            self.calculate_csv_output(child, price_energy_redis_output)

    @staticmethod
    def _convert_output_format(price_energy, redis_output, core_stats):
        for node_uuid, trade_rates in price_energy.items():
            if node_uuid not in redis_output:
                redis_output[node_uuid] = {
                    "price-currency": "Euros",
                    "load-unit": "kWh",
                    "price-energy-day": []
                }
            redis_output[node_uuid]["price-energy-day"] = [
                {
                    "time": timeslot,
                    "av_price": round_floats_for_ui(mean(trades) if len(trades) > 0 else 0),
                    "min_price": round_floats_for_ui(min(trades) if len(trades) > 0 else 0),
                    "max_price": round_floats_for_ui(max(trades) if len(trades) > 0 else 0),
                } for timeslot, trades in trade_rates.items()
            ]

            area_core_stats = core_stats.get(node_uuid, {})
            fee = area_core_stats['grid_fee_constant'] / 100 \
                if key_in_dict_and_not_none(area_core_stats, 'grid_fee_constant') else None

            redis_output[node_uuid]["price-energy-day"][0].update({"fee_price": fee})
