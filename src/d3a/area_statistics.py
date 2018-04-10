from collections import namedtuple, defaultdict
from statistics import mean
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.inter_area import InterAreaAgent
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.greedy_night_storage import NightStorageStrategy
from d3a.models.strategy.load_hours_fb import CellTowerLoadHoursStrategy
from d3a.util import area_name_from_area_or_iaa_name, make_iaa_name


loads_avg_prices = namedtuple('loads_avg_prices', ['load', 'price'])


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
                 isinstance(child.strategy, InterAreaAgent) or
                 isinstance(child.strategy, NightStorageStrategy)):
            for slot, market in child.parent.past_markets.items():
                if slot.hour not in load_price_lists.keys():
                    load_price_lists[slot.hour] = loads_avg_prices(load=[], price=[])
                load_price_lists[slot.hour].load.append(market.traded_energy[child.name])
                trade_prices = [
                    t.offer.price / t.offer.energy
                    for t in market.trades
                    if t.buyer == child.name
                ]
                load_price_lists[slot.hour].price.extend(trade_prices)
        else:
            load_price_lists = gather_area_loads_and_trade_prices(child, load_price_lists)
    return load_price_lists


def export_cumulative_loads(area):
    load_price_lists = {}
    area_raw_results = gather_area_loads_and_trade_prices(area, load_price_lists)
    return [
        {
            "time": hour,
            "load": sum(load_price.load) if len(load_price.load) > 0 else 0,
            "price": mean(load_price.price) if len(load_price.price) > 0 else 0
        } for hour, load_price in area_raw_results.items()
    ]


def _is_house_node(area):
    return all(child.children == [] for child in area.children)


def _is_cell_tower_node(area):
    return isinstance(area.strategy, CellTowerLoadHoursStrategy)


def _accumulate_cell_tower_trades(cell_tower, grid, accumulated_trades):
    accumulated_trades[cell_tower.name] = {
        "type": "cell_tower",
        "id": cell_tower.area_id,
        "produced": 0.0,
        "consumedFrom": defaultdict(int)
    }
    for slot, market in grid.past_markets.items():
        for trade in market.trades:
            if trade.buyer == cell_tower.name:
                sell_id = area_name_to_id(area_name_from_area_or_iaa_name(trade.seller), grid)
                accumulated_trades[cell_tower.name]["consumedFrom"][sell_id] += trade.offer.energy
    return accumulated_trades


def _accumulate_house_trades(house, grid, accumulated_trades):
    if house.name not in accumulated_trades:
        accumulated_trades[house.name] = {
            "type": "house",
            "id": house.area_id,
            "produced": 0.0,
            "consumedFrom": defaultdict(int)
        }
    house_IAA_name = make_iaa_name(house)
    child_names = [c.name for c in house.children]
    for slot, market in house.past_markets.items():
        for trade in market.trades:
            if area_name_from_area_or_iaa_name(trade.seller) in child_names and \
                    area_name_from_area_or_iaa_name(trade.buyer) in child_names:
                # House self-consumption trade
                accumulated_trades[house.name]["produced"] -= trade.offer.energy
                accumulated_trades[house.name]["consumedFrom"][house.area_id] += trade.offer.energy
            elif trade.buyer == house_IAA_name:
                accumulated_trades[house.name]["produced"] -= trade.offer.energy

    for slot, market in grid.past_markets.items():
        for trade in market.trades:
            if trade.buyer == house_IAA_name:
                sell_id = area_name_to_id(area_name_from_area_or_iaa_name(trade.seller), grid)
                accumulated_trades[house.name]["consumedFrom"][sell_id] += trade.offer.energy
    return accumulated_trades


def _accumulate_grid_trades(area, accumulated_trades):
    for child in area.children:
        if _is_cell_tower_node(child):
            accumulated_trades = _accumulate_cell_tower_trades(child, area, accumulated_trades)
        elif _is_house_node(child):
            accumulated_trades = _accumulate_house_trades(child, area, accumulated_trades)
        elif child.children == []:
            # Leaf node, no need for calculating cumulative trades, continue iteration
            continue
        else:
            accumulated_trades = _accumulate_grid_trades(child, accumulated_trades)
    return accumulated_trades


def area_name_to_id(area_name, grid):
    for child in grid.children:
        if child.name == area_name:
            return child.area_id
        elif child.children == []:
            continue
        else:
            res = area_name_to_id(area_name, child)
            if res is not None:
                return res
    return None


def export_cumulative_grid_trades(area):
    return _accumulate_grid_trades(area, {})
