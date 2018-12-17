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
from collections import namedtuple, defaultdict, OrderedDict
from statistics import mean
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.area_agents.one_sided_agent import InterAreaAgent
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.load_hours import CellTowerLoadHoursStrategy, LoadHoursStrategy
from d3a.d3a_core.util import area_name_from_area_or_iaa_name, make_iaa_name

loads_avg_prices = namedtuple('loads_avg_prices', ['load', 'price'])
prices_pv_stor_energy = namedtuple('prices_pv_stor_energy', ['price', 'pv_energ', 'stor_energ'])


def get_area_type_string(area):
    if isinstance(area.strategy, CellTowerLoadHoursStrategy):
        return "cell_tower"
    elif area.children is None:
        return "unknown"
    elif area.children != [] and all(child.children == [] for child in area.children):
        return "house"
    else:
        return "unknown"


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


def gather_prices_pv_stor_energ(area, price_energ_lists):
    for child in area.children:
        for market in child.parent.past_markets:
            slot = market.time_slot
            slot_time_str = "%02d:00" % slot.hour
            if slot_time_str not in price_energ_lists.keys():
                price_energ_lists[slot_time_str] = prices_pv_stor_energy(price=[],
                                                                         pv_energ=[],
                                                                         stor_energ=[])
            trade_prices = [
                # Convert from cents to euro
                t.offer.price / 100.0 / t.offer.energy
                for t in market.trades
                if t.buyer == child.name
            ]
            price_energ_lists[slot_time_str].price.extend(trade_prices)

            if child.children == [] and isinstance(child.strategy, PVStrategy):
                traded_energy = [
                    t.offer.energy
                    for t in market.trades
                    if t.seller == child.name
                ]
                price_energ_lists[slot_time_str].pv_energ.extend(traded_energy)

            if child.children == [] and \
                    (isinstance(child.strategy, StorageStrategy)):
                traded_energy = []

                for t in market.trades:
                    if t.seller == child.name:
                        traded_energy.append(-t.offer.energy)
                    elif t.buyer == child.name:
                        traded_energy.append(t.offer.energy)
                price_energ_lists[slot_time_str].stor_energ.extend(traded_energy)

        if child.children != []:
            price_energ_lists = gather_prices_pv_stor_energ(child, price_energ_lists)
    return price_energ_lists


def export_cumulative_loads(area):
    load_price_lists = gather_area_loads_and_trade_prices(area, {})
    return [
        {
            "time": hour,
            "load": round(sum(load_price.load), 3) if len(load_price.load) > 0 else 0,
            "price": round(mean(load_price.price), 2) if len(load_price.price) > 0 else 0
        } for hour, load_price in load_price_lists.items()
    ]


def _is_house_node(area):
    return all(child.children == [] for child in area.children)


def _is_cell_tower_node(area):
    return isinstance(area.strategy, CellTowerLoadHoursStrategy)


def _is_load_node(area):
    return isinstance(area.strategy, LoadHoursStrategy)


def _is_producer_node(area):
    return isinstance(area.strategy, (PVStrategy, CommercialStrategy))


def _is_prosumer_node(area):
    return isinstance(area.strategy, StorageStrategy)


def _accumulate_load_trades(load, grid, accumulated_trades, is_cell_tower):
    accumulated_trades[load.name] = {
        "type": "cell_tower" if is_cell_tower else "load",
        "id": load.area_id,
        "produced": 0.0,
        "earned": 0.0,
        "consumedFrom": defaultdict(int),
        "spentTo": defaultdict(int),
    }
    for market in grid.past_markets:
        for trade in market.trades:
            if trade.buyer == load.name:
                sell_id = area_name_from_area_or_iaa_name(trade.seller)
                accumulated_trades[load.name]["consumedFrom"][sell_id] += trade.offer.energy
                accumulated_trades[load.name]["spentTo"][sell_id] += trade.offer.price
    return accumulated_trades


def _accumulate_producer_trades(load, grid, accumulated_trades):
    accumulated_trades[load.name] = {
        "id": load.area_id,
        "produced": 0.0,
        "earned": 0.0,
        "consumedFrom": defaultdict(int),
        "spentTo": defaultdict(int),
    }
    for market in grid.past_markets:
        for trade in market.trades:
            if trade.offer.seller == load.name:
                accumulated_trades[load.name]["produced"] += trade.offer.energy
                accumulated_trades[load.name]["earned"] += trade.offer.price
    return accumulated_trades


def _accumulate_house_trades(house, grid, accumulated_trades, past_market_types):
    if house.name not in accumulated_trades:
        accumulated_trades[house.name] = {
            "type": "house",
            "id": house.area_id,
            "produced": 0.0,
            "earned": 0.0,
            "consumedFrom": defaultdict(int),
            "spentTo": defaultdict(int),
        }
    house_IAA_name = make_iaa_name(house)
    child_names = [c.name for c in house.children]
    for market in getattr(house, past_market_types):
        for trade in market.trades:
            if area_name_from_area_or_iaa_name(trade.seller) in child_names and \
                    area_name_from_area_or_iaa_name(trade.buyer) in child_names:
                # House self-consumption trade
                accumulated_trades[house.name]["produced"] -= trade.offer.energy
                accumulated_trades[house.name]["earned"] += trade.offer.price
                accumulated_trades[house.name]["consumedFrom"][house.name] += trade.offer.energy
                accumulated_trades[house.name]["spentTo"][house.name] += trade.offer.price
            elif trade.buyer == house_IAA_name:
                accumulated_trades[house.name]["earned"] += trade.offer.price
                accumulated_trades[house.name]["produced"] -= trade.offer.energy

    for market in getattr(grid, past_market_types):
        for trade in market.trades:
            if trade.buyer == house_IAA_name and trade.buyer != trade.offer.seller:
                seller_id = area_name_from_area_or_iaa_name(trade.seller)
                accumulated_trades[house.name]["consumedFrom"][seller_id] += trade.offer.energy
                accumulated_trades[house.name]["spentTo"][seller_id] += trade.offer.price
    return accumulated_trades


def _accumulate_grid_trades(area, accumulated_trades, past_market_types):
    for child in area.children:
        if _is_cell_tower_node(child):
            accumulated_trades = _accumulate_load_trades(
                child, area, accumulated_trades, is_cell_tower=True
            )
        elif _is_house_node(child):
            accumulated_trades = \
                _accumulate_house_trades(child, area, accumulated_trades, past_market_types)
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
                child, area, accumulated_trades, is_cell_tower=True
            )
        if _is_load_node(child):
            accumulated_trades = _accumulate_load_trades(
                child, area, accumulated_trades, is_cell_tower=False
            )
        if _is_producer_node(child):
            accumulated_trades = _accumulate_producer_trades(
                child, area, accumulated_trades)

        elif child.children == []:
            # Leaf node, no need for calculating cumulative trades, continue iteration
            continue
        else:
            accumulated_trades = _accumulate_house_trades(
                child, area, accumulated_trades, past_market_types
            )
            accumulated_trades = _accumulate_grid_trades_all_devices(
                child, accumulated_trades, past_market_types
            )
    return accumulated_trades


def _generate_produced_energy_entries(accumulated_trades):
    # Create produced energy results (negative axis)
    produced_energy = [{
        "x": area_name,
        "y": area_data["produced"],
        "target": area_name,
        "label": f"{area_name} Produced {str(round(abs(area_data['produced']), 3))} kWh",
        "priceLabel": f"{area_name} Earned {str(round(abs(area_data['earned']), 3))} cents",
    } for area_name, area_data in accumulated_trades.items()]
    return sorted(produced_energy, key=lambda a: a["x"])


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
            "x": area_name,
            "y": sc_energy,
            "target": area_name,
            "label": f"{area_name} Consumed {str(round(sc_energy, 3))} kWh from {area_name}",
            "priceLabel": f"{area_name} Spent {str(round(sc_money, 3))} cents on "
                          f"energy from {area_name}",
        })
    return sorted(self_consumed_energy, key=lambda a: a["x"])


def _generate_intraarea_consumption_entries(accumulated_trades):
    # Flatten consumedFrom entries from dictionaries to list of tuples, to be able to pop them
    # irregardless of their keys
    for area_name, area_data in accumulated_trades.items():
        area_data["consumedFrom"] = list(area_data["consumedFrom"].items())
        area_data["spentTo"] = list(area_data["spentTo"].items())

    consumption_rows = []
    # Exhaust all consumedFrom entries from all houses
    while not all(not area_data["consumedFrom"] for k, area_data in accumulated_trades.items()):
        consumption_row = []
        for area_name in sorted(accumulated_trades.keys()):
            target_area = area_name
            p_target_area = area_name
            consumption = 0
            spent_to = 0
            if accumulated_trades[area_name]["consumedFrom"]:
                target_area, consumption = accumulated_trades[area_name]["consumedFrom"].pop()
            if accumulated_trades[area_name]["spentTo"]:
                p_target_area, spent_to = accumulated_trades[area_name]["spentTo"].pop()
                assert p_target_area == target_area
            consumption_row.append({
                "x": area_name,
                "y": consumption,
                "target": target_area,
                "label": f"{area_name} Consumed {str(round(consumption, 3))} kWh "
                         f"from {target_area}",
                "priceLabel": f"{area_name} Spent {str(round(spent_to, 3))} cents on "
                              f"energy from {p_target_area}"
            })
        consumption_rows.append(sorted(consumption_row, key=lambda x: x["x"]))
    return consumption_rows


def generate_inter_area_trade_details(area, past_market_types):
    accumulated_trades = _accumulate_grid_trades_all_devices(area, {}, past_market_types)
    trade_details = dict()
    for area_name, area_data in accumulated_trades.items():
        total_energy = 0
        for name, energy in area_data["consumedFrom"].items():
            total_energy += energy
        for name, energy in area_data["consumedFrom"].items():
            area_data["consumedFrom"][name] = str((energy / total_energy) * 100) + "%"
        trade_details[area_name] = area_data
    return trade_details


def export_cumulative_grid_trades(area, past_market_types, all_devices=False):
    accumulated_trades = _accumulate_grid_trades_all_devices(area, {}, past_market_types) \
        if all_devices \
        else _accumulate_grid_trades(area, {}, past_market_types)
    return {
        "unit": "kWh",
        "areas": sorted(accumulated_trades.keys()),
        "cumulative-grid-trades": [
            # Append first produced energy for all areas
            _generate_produced_energy_entries(accumulated_trades),
            # Then self consumption energy for all areas
            _generate_self_consumption_entries(accumulated_trades),
            # Then consumption entries for intra-house trades
            *_generate_intraarea_consumption_entries(accumulated_trades)]
    }


def export_price_energy_day(area):
    price_lists = gather_prices_pv_stor_energ(area, OrderedDict())
    return [
        {
            "timeslot": ii,
            "time": hour,
            "av_price": round(mean(trades.price) if len(trades.price) > 0 else 0, 2),
            "min_price": round(min(trades.price) if len(trades.price) > 0 else 0, 2),
            "max_price": round(max(trades.price) if len(trades.price) > 0 else 0, 2),
            "cum_pv_gen": round(-1 * sum(trades.pv_energ), 2),
            "cum_stor_prof": round(sum(trades.stor_energ), 2)
        } for ii, (hour, trades) in enumerate(price_lists.items())
    ]
