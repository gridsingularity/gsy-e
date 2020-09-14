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
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a.d3a_core.util import area_name_from_area_or_iaa_name, add_or_create_key, \
    make_iaa_name_from_dict, subtract_or_create_key, round_floats_for_ui


def _is_cell_tower_type(area):
    return area['type'] == "CellTowerLoadHoursStrategy"


def _is_load_node_type(area):
    return area['type'] == "LoadHoursStrategy"


def _is_producer_node_type(area):
    return area['type'] in ["PVStrategy", "CommercialStrategy", "FinitePowerPlant",
                            "MarketMakerStrategy"]


def _is_prosumer_node_type(area):
    return area['type'] == "StorageStrategy"


def _is_buffer_node_type(area):
    return area['type'] == "InfiniteBusStrategy"


def area_sells_to_child(trade, area_name, child_names):
    return area_name_from_area_or_iaa_name(trade['seller']) == \
            area_name and area_name_from_area_or_iaa_name(trade['buyer']) in child_names


def child_buys_from_area(trade, area_name, child_names):
    return area_name_from_area_or_iaa_name(trade['buyer']) == \
        area_name and area_name_from_area_or_iaa_name(trade['seller']) in child_names


class CumulativeGridTrades:
    def __init__(self):
        self.current_trades = {}
        self.current_balancing_trades = {}
        self.accumulated_trades = {}
        self.accumulated_balancing_trades = {}

    def update(self, area_dict, flattened_area_core_stats_dict):
        self.accumulated_trades, self.current_trades = \
            self.export_cumulative_grid_trades(
                area_dict, flattened_area_core_stats_dict, self.accumulated_trades
            )

    @staticmethod
    def export_cumulative_grid_trades(area_dict, flattened_area_core_stats_dict,
                                      accumulated_trades_redis):
        accumulated_trades = CumulativeGridTrades.accumulate_grid_trades_all_devices(
            area_dict, flattened_area_core_stats_dict, accumulated_trades_redis
        )
        return accumulated_trades, \
            CumulativeGridTrades.generate_cumulative_grid_trades_for_all_areas(
                accumulated_trades, area_dict, None, {}
            )

    @classmethod
    def accumulate_grid_trades_all_devices(cls, area_dict, flattened_area_core_stats_dict,
                                           accumulated_trades):
        for child_dict in area_dict['children']:
            if _is_cell_tower_type(child_dict):
                accumulated_trades = CumulativeGridTrades._accumulate_load_trades(
                    child_dict, area_dict, flattened_area_core_stats_dict, accumulated_trades,
                    is_cell_tower=True
                )
            if _is_load_node_type(child_dict):
                accumulated_trades = CumulativeGridTrades._accumulate_load_trades(
                    child_dict, area_dict, flattened_area_core_stats_dict, accumulated_trades,
                    is_cell_tower=False
                )
            if _is_producer_node_type(child_dict):
                accumulated_trades = CumulativeGridTrades._accumulate_producer_trades(
                    child_dict, area_dict, flattened_area_core_stats_dict, accumulated_trades
                )
            elif _is_prosumer_node_type(child_dict) or _is_buffer_node_type(child_dict):
                accumulated_trades = \
                    CumulativeGridTrades._accumulate_storage_trade(
                        child_dict, area_dict, flattened_area_core_stats_dict, accumulated_trades
                    )

            elif child_dict['children'] == []:
                # Leaf node, no need for calculating cumulative trades, continue iteration
                continue
            else:
                accumulated_trades = CumulativeGridTrades._accumulate_area_trades(
                    child_dict, area_dict, flattened_area_core_stats_dict, accumulated_trades
                )
                accumulated_trades = cls.accumulate_grid_trades_all_devices(
                    child_dict, flattened_area_core_stats_dict, accumulated_trades
                )
        return accumulated_trades

    @classmethod
    def _accumulate_load_trades(cls, load, grid, flattened_area_core_stats_dict,
                                accumulated_trades, is_cell_tower):
        if load['name'] not in accumulated_trades:
            accumulated_trades[load['name']] = {
                "type": "cell_tower" if is_cell_tower else "load",
                "produced": 0.0,
                "earned": 0.0,
                "consumedFrom": {},
                "spentTo": {},
            }

        area_trades = flattened_area_core_stats_dict.get(grid['uuid'], {}).get('trades', [])
        for trade in area_trades:
            if trade['buyer'] == load['name']:
                sell_id = area_name_from_area_or_iaa_name(trade['seller'])
                accumulated_trades[load['name']]["consumedFrom"] = add_or_create_key(
                    accumulated_trades[load['name']]["consumedFrom"], sell_id,
                    trade['energy'])
                accumulated_trades[load['name']]["spentTo"] = add_or_create_key(
                    accumulated_trades[load['name']]["spentTo"], sell_id,
                    (trade['energy'] * trade['energy_rate']))
        return accumulated_trades

    @classmethod
    def _accumulate_producer_trades(cls, producer, grid, flattened_area_core_stats_dict,
                                    accumulated_trades):
        if producer['name'] not in accumulated_trades:
            accumulated_trades[producer['name']] = {
                "produced": 0.0,
                "earned": 0.0,
                "consumedFrom": {},
                "spentTo": {},
            }

        area_trades = flattened_area_core_stats_dict.get(grid['uuid'], {}).get('trades', [])
        for trade in area_trades:
            if trade['seller'] == producer['name']:
                accumulated_trades[producer['name']]["produced"] -= trade['energy']
                accumulated_trades[producer['name']]["earned"] += \
                    (trade['energy_rate'] * trade['energy'])
        return accumulated_trades

    @classmethod
    def _accumulate_storage_trade(cls, storage, area, flattened_area_core_stats_dict,
                                  accumulated_trades):
        if storage['name'] not in accumulated_trades:
            accumulated_trades[storage['name']] = {
                "type": "Storage" if area['type'] == "StorageStrategy" else "InfiniteBus",
                "produced": 0.0,
                "earned": 0.0,
                "consumedFrom": {},
                "spentTo": {},
            }

        area_trades = flattened_area_core_stats_dict.get(area['uuid'], {}).get('trades', [])
        for trade in area_trades:
            if trade['buyer'] == storage['name']:
                sell_id = area_name_from_area_or_iaa_name(trade['seller'])
                accumulated_trades[storage['name']]["consumedFrom"] = add_or_create_key(
                    accumulated_trades[storage['name']]["consumedFrom"],
                    sell_id, trade['energy'])
                accumulated_trades[storage['name']]["spentTo"] = add_or_create_key(
                    accumulated_trades[storage['name']]["spentTo"], sell_id,
                    (trade['energy_rate'] * trade['energy']))
            elif trade['seller'] == storage['name']:
                accumulated_trades[storage['name']]["produced"] -= trade['energy']
                accumulated_trades[storage['name']]["earned"] += \
                    (trade['energy_rate'] * trade['energy'])
        return accumulated_trades

    @classmethod
    def _accumulate_area_trades(cls, area, parent, flattened_area_core_stats_dict,
                                accumulated_trades):
        if area['name'] not in accumulated_trades:
            accumulated_trades[area['name']] = {
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
        area_IAA_name = make_iaa_name_from_dict(area)
        child_names = [area_name_from_area_or_iaa_name(c['name']) for c in area['children']]
        area_trades = flattened_area_core_stats_dict.get(area['uuid'], {}).get('trades', [])

        for trade in area_trades:
            trade_price = trade['energy'] * trade['energy_rate']
            if area_name_from_area_or_iaa_name(trade['seller']) in child_names and \
                    area_name_from_area_or_iaa_name(trade['buyer']) in child_names:
                # House self-consumption trade
                accumulated_trades[area['name']]["produced"] -= trade['energy']
                accumulated_trades[area['name']]["earned"] += trade_price
                accumulated_trades[area['name']]["consumedFrom"] = \
                    add_or_create_key(accumulated_trades[area['name']]["consumedFrom"],
                                      area['name'], trade['energy'])
                accumulated_trades[area['name']]["spentTo"] = \
                    add_or_create_key(accumulated_trades[area['name']]["spentTo"],
                                      area['name'], trade_price)
            elif trade['buyer'] == area_IAA_name:
                accumulated_trades[area['name']]["earned"] += trade_price
                accumulated_trades[area['name']]["produced"] -= trade['energy']
        # for market in area_markets:
        for trade in area_trades:
            trade_price = trade['energy'] * trade['energy_rate']
            if area_sells_to_child(trade, area['name'], child_names):
                accumulated_trades[area['name']]["consumedFromExternal"] = \
                    subtract_or_create_key(accumulated_trades[area['name']]
                                           ["consumedFromExternal"],
                                           area_name_from_area_or_iaa_name(trade['buyer']),
                                           trade['energy'])
                accumulated_trades[area['name']]["spentToExternal"] = \
                    add_or_create_key(accumulated_trades[area['name']]["spentToExternal"],
                                      area_name_from_area_or_iaa_name(trade['buyer']),
                                      trade_price)
            elif child_buys_from_area(trade, area['name'], child_names):
                accumulated_trades[area['name']]["producedForExternal"] = \
                    add_or_create_key(accumulated_trades[area['name']]["producedForExternal"],
                                      area_name_from_area_or_iaa_name(trade['seller']),
                                      trade['energy'])
                accumulated_trades[area['name']]["earnedFromExternal"] = \
                    add_or_create_key(accumulated_trades[area['name']]["earnedFromExternal"],
                                      area_name_from_area_or_iaa_name(trade['seller']),
                                      trade_price)

        accumulated_trades = CumulativeGridTrades._area_trade_from_parent(
            area, parent, flattened_area_core_stats_dict, accumulated_trades
        )

        return accumulated_trades

    @classmethod
    def generate_cumulative_grid_trades_for_all_areas(cls, accumulated_trades, area,
                                                      parent, results):
        if area['children'] == []:
            return results

        results[area['uuid']] = [CumulativeGridTrades.generate_area_cumulative_trade_redis(
                child, area, accumulated_trades
            )
            for child in area['children']
            if child['name'] in accumulated_trades
        ]
        if parent is not None:
            results[area['uuid']].append(CumulativeGridTrades._external_trade_entries(
                area, accumulated_trades))

        for child in area['children']:
            results = cls.generate_cumulative_grid_trades_for_all_areas(
                accumulated_trades, child, area, results
            )
        return results

    @classmethod
    def _area_trade_from_parent(cls, area, parent, flattened_area_core_stats_dict,
                                accumulated_trades):
        area_IAA_name = make_iaa_name_from_dict(area)
        parent_trades = flattened_area_core_stats_dict.get(parent['uuid'], {}).get('trades', [])

        for trade in parent_trades:
            trade_price = trade['energy'] * trade['energy_rate']
            if trade['buyer'] == area_IAA_name:
                seller_id = area_name_from_area_or_iaa_name(trade['seller'])
                accumulated_trades[area['name']]["consumedFrom"] = \
                    add_or_create_key(accumulated_trades[area['name']]["consumedFrom"],
                                      seller_id, trade['energy'])
                accumulated_trades[area['name']]["spentTo"] = \
                    add_or_create_key(accumulated_trades[area['name']]["spentTo"],
                                      seller_id, trade_price)

        return accumulated_trades

    @classmethod
    def generate_area_cumulative_trade_redis(cls, child, parent, accumulated_trades):
        results = {"areaName": child['name']}
        area_data = accumulated_trades[child['name']]
        results["bars"] = []
        # Producer entries
        if abs(area_data["produced"]) > FLOATING_POINT_TOLERANCE:
            results["bars"].append(
                {"energy": round_floats_for_ui(area_data["produced"]), "targetArea": child['name'],
                 "energyLabel":
                     f"{child['name']} sold "
                     f"{str(round_floats_for_ui(abs(area_data['produced'])))} kWh",
                 "priceLabel":
                     f"{child['name']} earned "
                     f"{str(round_floats_for_ui(area_data['earned']))} cents"}
            )

        # Consumer entries
        for producer, energy in area_data["consumedFrom"].items():
            money = round_floats_for_ui(area_data["spentTo"][producer])
            tag = "external sources" if producer == parent['name'] else producer
            results["bars"].append({
                "energy": round_floats_for_ui(energy),
                "targetArea": producer,
                "energyLabel": f"{child['name']} bought "
                               f"{str(round_floats_for_ui(energy))} kWh from {tag}",
                "priceLabel": f"{child['name']} spent "
                              f"{str(round_floats_for_ui(money))} cents on energy from {tag}",
            })

        return results

    @classmethod
    def _external_trade_entries(cls, child, accumulated_trades):
        results = {"areaName": "External Trades"}
        area_data = accumulated_trades[child['name']]
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
                "targetArea": child['name'],
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
                    "priceLabel": f"{child['name']} spent {earned} cents."
                })
        return results
