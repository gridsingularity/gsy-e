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
from d3a.models.strategy.load_hours import CellTowerLoadHoursStrategy, LoadHoursStrategy
from d3a.d3a_core.util import area_name_from_area_or_iaa_name, make_iaa_name, \
    round_floats_for_ui, add_or_create_key, subtract_or_create_key, \
    area_sells_to_child, child_buys_from_area
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a_interface.constants_limits import ConstSettings
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


def _is_cell_tower_node(area):
    return isinstance(area.strategy, CellTowerLoadHoursStrategy)


def _is_load_node(area):
    return isinstance(area.strategy, LoadHoursStrategy)


def _is_producer_node(area):
    return isinstance(area.strategy, PVStrategy) or \
           type(area.strategy) in [CommercialStrategy, FinitePowerPlant, MarketMakerStrategy]


def _is_prosumer_node(area):
    return isinstance(area.strategy, StorageStrategy)


def _is_buffer_node(area):
    return type(area.strategy) == InfiniteBusStrategy


def _accumulate_storage_trade(storage, area, accumulated_trades, past_market_types):
    if storage.name not in accumulated_trades:
        accumulated_trades[storage.name] = {
            "type": "Storage" if type(area.strategy) == StorageStrategy else "InfiniteBus",
            "produced": 0.0,
            "earned": 0.0,
            "consumedFrom": {},
            "spentTo": {},
        }

    markets = getattr(area, past_market_types)
    if markets is None:
        return accumulated_trades
    else:
        if type(markets) != list:
            markets = [markets]
        for market in markets:
            for trade in market.trades:
                if trade.buyer == storage.name:
                    sell_id = area_name_from_area_or_iaa_name(trade.seller)
                    accumulated_trades[storage.name]["consumedFrom"] = add_or_create_key(
                        accumulated_trades[storage.name]["consumedFrom"],
                        sell_id, trade.offer.energy)
                    accumulated_trades[storage.name]["spentTo"] = add_or_create_key(
                        accumulated_trades[storage.name]["spentTo"], sell_id, trade.offer.price)
                elif trade.offer.seller == storage.name:
                    accumulated_trades[storage.name]["produced"] -= trade.offer.energy
                    accumulated_trades[storage.name]["earned"] += trade.offer.price
        return accumulated_trades


def _accumulate_load_trades(load, grid, accumulated_trades, is_cell_tower, past_market_types):
    if load.name not in accumulated_trades:
        accumulated_trades[load.name] = {
            "type": "cell_tower" if is_cell_tower else "load",
            "produced": 0.0,
            "earned": 0.0,
            "consumedFrom": {},
            "spentTo": {},
        }

    markets = getattr(grid, past_market_types)
    if markets is None:
        return accumulated_trades
    else:
        if type(markets) != list:
            markets = [markets]
        for market in markets:
            for trade in market.trades:
                if trade.buyer == load.name:
                    sell_id = area_name_from_area_or_iaa_name(trade.seller)
                    accumulated_trades[load.name]["consumedFrom"] = add_or_create_key(
                        accumulated_trades[load.name]["consumedFrom"], sell_id, trade.offer.energy)
                    accumulated_trades[load.name]["spentTo"] = add_or_create_key(
                        accumulated_trades[load.name]["spentTo"], sell_id, trade.offer.price)
        return accumulated_trades


def _accumulate_producer_trades(producer, grid, accumulated_trades, past_market_types):
    if producer.name not in accumulated_trades:
        accumulated_trades[producer.name] = {
            "produced": 0.0,
            "earned": 0.0,
            "consumedFrom": {},
            "spentTo": {},
        }

    markets = getattr(grid, past_market_types)
    if markets is None:
        return accumulated_trades
    else:
        if type(markets) != list:
            markets = [markets]

        for market in markets:
            for trade in market.trades:
                if trade.offer.seller == producer.name:
                    accumulated_trades[producer.name]["produced"] -= trade.offer.energy
                    accumulated_trades[producer.name]["earned"] += trade.offer.price
        return accumulated_trades


def _area_trade_from_parent(area, parent, accumulated_trades, past_market_types):
    area_IAA_name = make_iaa_name(area)
    parent_markets = getattr(parent, past_market_types)
    if parent_markets is not None:
        if type(parent_markets) != list:
            parent_markets = [parent_markets]

        for market in parent_markets:
            for trade in market.trades:
                if trade.buyer == area_IAA_name:
                    seller_id = area_name_from_area_or_iaa_name(trade.seller)
                    accumulated_trades[area.name]["consumedFrom"] = \
                        add_or_create_key(accumulated_trades[area.name]["consumedFrom"],
                                          seller_id, trade.offer.energy)
                    accumulated_trades[area.name]["spentTo"] = \
                        add_or_create_key(accumulated_trades[area.name]["spentTo"],
                                          seller_id, trade.offer.price)

    return accumulated_trades


def _accumulate_area_trades(area, parent, accumulated_trades, past_market_types):
    if area.name not in accumulated_trades:
        accumulated_trades[area.name] = {
            "type": "house",
            "produced": 0.0,
            "earned": 0.0,
            "consumedFrom": {},
            "spentTo": {},
            "producedForExternal": {},
            "earnedFromExternal": {},
            "consumedFromExternal": {},
            "spentToExternal": {},
        }
    area_IAA_name = make_iaa_name(area)
    child_names = [area_name_from_area_or_iaa_name(c.name) for c in area.children]
    area_markets = getattr(area, past_market_types)
    if area_markets is not None:
        if type(area_markets) != list:
            area_markets = [area_markets]
        for market in area_markets:
            for trade in market.trades:
                if area_name_from_area_or_iaa_name(trade.seller) in child_names and \
                        area_name_from_area_or_iaa_name(trade.buyer) in child_names:
                    # House self-consumption trade
                    accumulated_trades[area.name]["produced"] -= trade.offer.energy
                    accumulated_trades[area.name]["earned"] += trade.offer.price
                    accumulated_trades[area.name]["consumedFrom"] = \
                        add_or_create_key(accumulated_trades[area.name]["consumedFrom"],
                                          area.name, trade.offer.energy)
                    accumulated_trades[area.name]["spentTo"] = \
                        add_or_create_key(accumulated_trades[area.name]["spentTo"],
                                          area.name, trade.offer.price)
                elif trade.buyer == area_IAA_name:
                    accumulated_trades[area.name]["earned"] += trade.offer.price
                    accumulated_trades[area.name]["produced"] -= trade.offer.energy
        for market in area_markets:
            for trade in market.trades:
                if area_sells_to_child(trade, area.name, child_names):
                    accumulated_trades[area.name]["consumedFromExternal"] = \
                        subtract_or_create_key(accumulated_trades[area.name]
                                               ["consumedFromExternal"],
                                               area_name_from_area_or_iaa_name(trade.buyer),
                                               trade.offer.energy)
                    accumulated_trades[area.name]["spentToExternal"] = \
                        add_or_create_key(accumulated_trades[area.name]["spentToExternal"],
                                          area_name_from_area_or_iaa_name(trade.buyer),
                                          trade.offer.price)
                elif child_buys_from_area(trade, area.name, child_names):
                    accumulated_trades[area.name]["producedForExternal"] = \
                        add_or_create_key(accumulated_trades[area.name]["producedForExternal"],
                                          area_name_from_area_or_iaa_name(trade.seller),
                                          trade.offer.energy)
                    accumulated_trades[area.name]["earnedFromExternal"] = \
                        add_or_create_key(accumulated_trades[area.name]["earnedFromExternal"],
                                          area_name_from_area_or_iaa_name(trade.seller),
                                          trade.offer.price)

    accumulated_trades = \
        _area_trade_from_parent(area, parent, accumulated_trades, past_market_types)

    return accumulated_trades


def _accumulate_grid_trades(area, accumulated_trades, past_market_types):
    for child in area.children:
        if _is_cell_tower_node(child):
            accumulated_trades = _accumulate_load_trades(
                child, area, accumulated_trades, is_cell_tower=True,
                past_market_types=past_market_types
            )
        elif _is_house_node(child):
            accumulated_trades = \
                _accumulate_area_trades(child, area, accumulated_trades, past_market_types)
        elif child.children == []:
            # Leaf node, no need for calculating cumulative trades, continue iteration
            continue
        else:
            accumulated_trades = _accumulate_grid_trades(
                child, accumulated_trades, past_market_types
            )
    return accumulated_trades


def _accumulate_grid_trades_all_devices(area, accumulated_trades, past_market_types):
    for child in area.children:
        if _is_cell_tower_node(child):
            accumulated_trades = _accumulate_load_trades(
                child, area, accumulated_trades, is_cell_tower=True,
                past_market_types=past_market_types
            )
        if _is_load_node(child):
            accumulated_trades = _accumulate_load_trades(
                child, area, accumulated_trades, is_cell_tower=False,
                past_market_types=past_market_types
            )
        if _is_producer_node(child):
            accumulated_trades = _accumulate_producer_trades(
                child, area, accumulated_trades,
                past_market_types=past_market_types
            )
        elif _is_prosumer_node(child) or _is_buffer_node(child):
            accumulated_trades = \
                _accumulate_storage_trade(child, area, accumulated_trades, past_market_types)

        elif child.children == []:
            # Leaf node, no need for calculating cumulative trades, continue iteration
            continue
        else:
            accumulated_trades = _accumulate_area_trades(
                child, area, accumulated_trades, past_market_types
            )
            accumulated_trades = _accumulate_grid_trades_all_devices(
                child, accumulated_trades, past_market_types
            )
    return accumulated_trades


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


def _external_trade_entries(child, accumulated_trades):
    results = {"areaName": "External Trades"}
    area_data = accumulated_trades[child.name]
    results["bars"] = []
    incoming_energy = 0
    spent = 0
    # External Trades entries
    if "consumedFromExternal" in area_data:
        for k, v in area_data["consumedFromExternal"].items():
            incoming_energy += round_floats_for_ui(area_data["consumedFromExternal"][k])
            spent += round_floats_for_ui(area_data["spentToExternal"][k])
        results["bars"].append({
            "energy": incoming_energy,
            "targetArea": child.name,
            "energyLabel": f"External sources sold "
                           f"{abs(round_floats_for_ui(incoming_energy))} kWh",
            "priceLabel": f"External sources earned {abs(round_floats_for_ui(spent))} cents"

        })

    if "producedForExternal" in area_data:
        for k, v in area_data["producedForExternal"].items():
            outgoing_energy = round_floats_for_ui(area_data["producedForExternal"][k])
            earned = round_floats_for_ui(area_data["earnedFromExternal"][k])
            results["bars"].append({
                "energy": outgoing_energy,
                "targetArea": k,
                "energyLabel": f"External sources bought {abs(outgoing_energy)} kWh "
                               f"from {k}",
                "priceLabel": f"{child.name} spent {earned} cents."
            })
    return results


def generate_area_cumulative_trade_redis(child, accumulated_trades):
    results = {"areaName": child.name}
    area_data = accumulated_trades[child.name]
    results["bars"] = []
    # Producer entries
    if abs(area_data["produced"]) > FLOATING_POINT_TOLERANCE:
        results["bars"].append(
            {"energy": round_floats_for_ui(area_data["produced"]), "targetArea": child.name,
             "energyLabel":
                 f"{child.name} sold "
                 f"{str(round_floats_for_ui(abs(area_data['produced'])))} kWh",
             "priceLabel":
                 f"{child.name} earned "
                 f"{str(round_floats_for_ui(area_data['earned']))} cents"}
        )

    # Consumer entries
    for producer, energy in area_data["consumedFrom"].items():
        money = round_floats_for_ui(area_data["spentTo"][producer])
        tag = "external sources" if producer == child.parent.name else producer
        results["bars"].append({
            "energy": round_floats_for_ui(energy),
            "targetArea": producer,
            "energyLabel": f"{child.name} bought "
                           f"{str(round_floats_for_ui(energy))} kWh from {tag}",
            "priceLabel": f"{child.name} spent "
                          f"{str(round_floats_for_ui(money))} cents on energy from {tag}",
        })

    return results


def generate_cumulative_grid_trades_for_all_areas(accumulated_trades, area, results):
    if area.children == []:
        return results

    results[area.uuid] = [
        generate_area_cumulative_trade_redis(child, accumulated_trades)
        for child in area.children
        if child.name in accumulated_trades
    ]
    if area.parent is not None:
        results[area.uuid].append(_external_trade_entries(area, accumulated_trades))

    for child in area.children:
        results = generate_cumulative_grid_trades_for_all_areas(accumulated_trades, child, results)
    return results


def export_cumulative_grid_trades(area, accumulated_trades, past_market_types, all_devices=False):
    accumulated_trades = _accumulate_grid_trades_all_devices(area, accumulated_trades,
                                                             past_market_types) \
        if all_devices else _accumulate_grid_trades(area, {}, past_market_types)

    return accumulated_trades, {
        "unit": "kWh",
        "areas": sorted(accumulated_trades.keys()),
        "cumulative-grid-trades": [
            # Append first produced energy for all areas
            _generate_produced_energy_entries(accumulated_trades),
            # Then self consumption energy for all areas
            _generate_self_consumption_entries(accumulated_trades),
            # Then consumption entries for intra-house trades
            *_generate_intraarea_consumption_entries(accumulated_trades)
        ]
    }


def export_cumulative_grid_trades_redis(area, accumulated_trades_redis, past_market_types):
    accumulated_trades = \
        _accumulate_grid_trades_all_devices(area, accumulated_trades_redis, past_market_types)
    return accumulated_trades, generate_cumulative_grid_trades_for_all_areas(accumulated_trades,
                                                                             area, {})


class MarketPriceEnergyDay:
    def __init__(self):
        self._price_energy_day = {}
        self.csv_output = {}
        self.redis_output = {}

    @classmethod
    def gather_trade_rates(cls, area, price_lists, use_last_past_market=False):
        if area.children == []:
            return price_lists

        if use_last_past_market is False:
            markets = area.past_markets
        elif area.current_market is not None:
            markets = [area.current_market]
        else:
            markets = []

        for market in markets:
            cls.gather_rates_one_market(area, market, price_lists)

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
        current_price_lists = self.gather_trade_rates(
            area, {},
            use_last_past_market=not ConstSettings.GeneralSettings.KEEP_PAST_MARKETS
        )

        price_energy_csv_output = {}
        price_energy_redis_output = {}
        self._convert_output_format(
            current_price_lists, price_energy_csv_output, price_energy_redis_output)

        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            self.csv_output = price_energy_csv_output
            self.redis_output = price_energy_redis_output
        else:
            self.csv_output = merge_price_energy_day_results_to_global(
                price_energy_csv_output, self.csv_output)
            self.redis_output = price_energy_redis_output

    def _convert_output_format(self, price_energy, csv_output, redis_output):
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
