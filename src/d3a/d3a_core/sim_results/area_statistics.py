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
from collections import namedtuple, OrderedDict
from statistics import mean
from copy import deepcopy

from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.strategy.area_agents.one_sided_agent import InterAreaAgent
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.market_maker_strategy import MarketMakerStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.d3a_core.util import round_floats_for_ui
from d3a_interface.sim_results.aggregate_results import merge_price_energy_day_results_to_global

loads_avg_prices = namedtuple('loads_avg_prices', ['load', 'price'])


def gather_area_loads_and_trade_prices(area, load_price_lists):
    for child in area.children:
        if child.children == [] and not \
                (isinstance(child.strategy, StorageStrategy) or
                 isinstance(child.strategy, PVStrategy) or
                 isinstance(child.strategy, InterAreaAgent)):
            for market in child.parent.past_markets:
                slot = market.time_slot
                if slot.hour not in load_price_lists.keys():
                    load_price_lists[slot.hour] = loads_avg_prices(load=[], price=[])
                if child.name in market.traded_energy:
                    load_price_lists[slot.hour].load.append(abs(market.traded_energy[child.name]))
                    trade_prices = [
                        # Convert from cents to euro
                        t.offer.price / 100.0 / t.offer.energy
                        for t in market.trades
                        if t.buyer == child.name
                    ]
                    load_price_lists[slot.hour].price.extend(trade_prices)
        else:
            load_price_lists = gather_area_loads_and_trade_prices(child, load_price_lists)
    return load_price_lists


def _is_house_node(area):
    return all(child.children == [] for child in area.children)


def _is_load_node(area):
    return isinstance(area.strategy, LoadHoursStrategy)


def _is_producer_node(area):
    return isinstance(area.strategy, PVStrategy) or \
           type(area.strategy) in [CommercialStrategy, FinitePowerPlant, MarketMakerStrategy]


def _is_prosumer_node(area):
    return isinstance(area.strategy, StorageStrategy)


def _is_buffer_node(area):
    return type(area.strategy) == InfiniteBusStrategy


def _generate_produced_energy_entries(accumulated_trades):
    # Create produced energy results (negative axis)
    produced_energy = [{
        "areaName": area_name,
        "energy": area_data["produced"],
        "targetArea": area_name,
        "energyLabel": f"{area_name} produced "
                       f"{str(round_floats_for_ui(abs(area_data['produced'])))} kWh",
        "priceLabel": f"{area_name} earned "
                      f"{str(round_floats_for_ui(abs(area_data['earned'])))} cents",
    } for area_name, area_data in accumulated_trades.items()]
    return sorted(produced_energy, key=lambda a: a["areaName"])


def _generate_self_consumption_entries(accumulated_trades):
    # Create self consumed energy results (positive axis, first entries)
    self_consumed_energy = []
    for area_name, area_data in accumulated_trades.items():
        sc_energy = 0
        sc_money = 0
        if area_name in area_data["consumedFrom"].keys():
            sc_energy = area_data["consumedFrom"].pop(area_name)
            sc_money = area_data["spentTo"].pop(area_name)
        self_consumed_energy.append({
            "areaName": area_name,
            "energy": sc_energy,
            "targetArea": area_name,
            "energyLabel": f"{area_name} consumed "
                           f"{str(round_floats_for_ui(sc_energy))} kWh from {area_name}",
            "priceLabel": f"{area_name} spent {str(round_floats_for_ui(sc_money))} "
                          f"cents on energy from {area_name}",
        })
    return sorted(self_consumed_energy, key=lambda a: a["areaName"])


def _generate_intraarea_consumption_entries(accumulated_trades):
    # Flatten consumedFrom entries from dictionaries to list of tuples, to be able to pop them
    # irregardless of their keys
    copied_accumulated_trades = deepcopy(accumulated_trades)
    for area_name, area_data in copied_accumulated_trades.items():
        area_data["consumedFrom"] = list(area_data["consumedFrom"].items())
        area_data["spentTo"] = list(area_data["spentTo"].items())

    consumption_rows = []
    # Exhaust all consumedFrom entries from all houses
    while not all(not area_data["consumedFrom"]
                  for k, area_data in copied_accumulated_trades.items()):
        consumption_row = []
        for area_name in sorted(copied_accumulated_trades.keys()):
            target_area = area_name
            p_target_area = area_name
            consumption = 0
            spent_to = 0
            if copied_accumulated_trades[area_name]["consumedFrom"]:
                target_area, consumption = \
                    copied_accumulated_trades[area_name]["consumedFrom"].pop()
            if copied_accumulated_trades[area_name]["spentTo"]:
                p_target_area, spent_to = \
                    copied_accumulated_trades[area_name]["spentTo"].pop()
                assert p_target_area == target_area
            consumption_row.append({
                "areaName": area_name,
                "energy": consumption,
                "targetArea": target_area,
                "energyLabel": f"{area_name} consumed {str(round_floats_for_ui(consumption))} kWh "
                               f"from {target_area}",
                "priceLabel": f"{area_name} spent {str(round_floats_for_ui(spent_to))} cents on "
                              f"energy from {p_target_area}"
            })
        consumption_rows.append(sorted(consumption_row, key=lambda x: x["areaName"]))
    return consumption_rows


class MarketPriceEnergyDay:
    def __init__(self, should_export_plots):
        self._price_energy_day = {}
        self.csv_output = {}
        self.redis_output = {}
        self.should_export_plots = should_export_plots

    @classmethod
    def gather_trade_rates(cls, area, price_lists):
        if area.children == []:
            return price_lists

        elif area.current_market is not None:
            cls.gather_rates_one_market(area, area.current_market, price_lists)

        for child in area.children:
            price_lists = cls.gather_trade_rates(child, price_lists)

        return price_lists

    @classmethod
    def gather_rates_one_market(cls, area, market, price_lists):
        if area not in price_lists:
            price_lists[area] = OrderedDict()
        if market.time_slot not in price_lists.keys():
            price_lists[area][market.time_slot] = []
        trade_rates = [
            # Convert from cents to euro
            t.offer.price / 100.0 / t.offer.energy
            for t in market.trades
        ]
        price_lists[area][market.time_slot].extend(trade_rates)

    def update(self, area):
        current_price_lists = self.gather_trade_rates(area, {})

        price_energy_csv_output = {}
        price_energy_redis_output = {}
        self._convert_output_format(
            current_price_lists, price_energy_csv_output, price_energy_redis_output)
        if self.should_export_plots:
            self.csv_output = merge_price_energy_day_results_to_global(
                price_energy_csv_output, self.csv_output)
        else:
            self.redis_output = price_energy_redis_output

    @staticmethod
    def _convert_output_format(price_energy, csv_output, redis_output):
        for node, trade_rates in price_energy.items():
            if node.name not in csv_output:
                csv_output[node.name] = {
                    "price-currency": "Euros",
                    "load-unit": "kWh",
                    "price-energy-day": []
                }
            csv_output[node.name]["price-energy-day"] = [
                {
                    "time": timeslot,
                    "av_price": round_floats_for_ui(mean(trades) if len(trades) > 0 else 0),
                    "min_price": round_floats_for_ui(min(trades) if len(trades) > 0 else 0),
                    "max_price": round_floats_for_ui(max(trades) if len(trades) > 0 else 0),
                } for timeslot, trades in trade_rates.items()
            ]
            redis_output[node.uuid] = deepcopy(csv_output[node.name])
