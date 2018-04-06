from collections import namedtuple
from statistics import mean
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.inter_area import InterAreaAgent
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.greedy_night_storage import NightStorageStrategy


loads_avg_prices = namedtuple('loads_avg_prices', ['load', 'price'])


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
    return {
        hour: {
            "load": sum(load_price.load) if len(load_price.load) > 0 else 0,
            "price": mean(load_price.price) if len(load_price.price) > 0 else 0
        }
        for hour, load_price in area_raw_results.items()}
