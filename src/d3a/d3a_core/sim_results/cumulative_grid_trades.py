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
from d3a.d3a_core.sim_results.area_statistics import _is_cell_tower_node, _is_load_node, \
    _is_producer_node, \
    _is_prosumer_node, _is_buffer_node, _area_trade_from_parent, \
    generate_area_cumulative_trade_redis, _external_trade_entries
from d3a.d3a_core.util import area_name_from_area_or_iaa_name, add_or_create_key, make_iaa_name, \
    area_sells_to_child, subtract_or_create_key, child_buys_from_area
from d3a.models.strategy.storage import StorageStrategy


class CumulativeGridTrades:
    def __init__(self):
        self.current_trades = {}
        self.current_balancing_trades = {}
        self.accumulated_trades = {}
        self.accumulated_balancing_trades = {}

    def update(self, area):
        self.accumulated_trades, self.current_trades = \
            self.export_cumulative_grid_trades(area, self.accumulated_trades,
                                               "current_market")

        # if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
        #     self.accumulated_balancing_trades, self.current_balancing_trades = \
        #         self.export_cumulative_grid_trades(area, self.accumulated_balancing_trades,
        #                                            "current_balancing_market")

    @staticmethod
    def export_cumulative_grid_trades(area, accumulated_trades_redis, past_market_types):
        accumulated_trades = CumulativeGridTrades.accumulate_grid_trades_all_devices(
            area, accumulated_trades_redis, past_market_types
        )
        return accumulated_trades, \
            CumulativeGridTrades.generate_cumulative_grid_trades_for_all_areas(
                accumulated_trades, area, {}
            )

    @classmethod
    def accumulate_grid_trades_all_devices(cls, area, accumulated_trades, past_market_types):
        for child in area.children:
            if _is_cell_tower_node(child):
                accumulated_trades = CumulativeGridTrades._accumulate_load_trades(
                    child, area, accumulated_trades, is_cell_tower=True,
                    past_market_types=past_market_types
                )
            if _is_load_node(child):
                accumulated_trades = CumulativeGridTrades._accumulate_load_trades(
                    child, area, accumulated_trades, is_cell_tower=False,
                    past_market_types=past_market_types
                )
            if _is_producer_node(child):
                accumulated_trades = CumulativeGridTrades._accumulate_producer_trades(
                    child, area, accumulated_trades,
                    past_market_types=past_market_types
                )
            elif _is_prosumer_node(child) or _is_buffer_node(child):
                accumulated_trades = \
                    CumulativeGridTrades._accumulate_storage_trade(
                        child, area, accumulated_trades, past_market_types
                    )

            elif child.children == []:
                # Leaf node, no need for calculating cumulative trades, continue iteration
                continue
            else:
                accumulated_trades = CumulativeGridTrades._accumulate_area_trades(
                    child, area, accumulated_trades, past_market_types
                )
                accumulated_trades = cls.accumulate_grid_trades_all_devices(
                    child, accumulated_trades, past_market_types
                )
        return accumulated_trades

    @classmethod
    def _accumulate_load_trades(cls, load, grid, accumulated_trades, is_cell_tower,
                                past_market_types):
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
                            accumulated_trades[load.name]["consumedFrom"], sell_id,
                            trade.offer.energy)
                        accumulated_trades[load.name]["spentTo"] = add_or_create_key(
                            accumulated_trades[load.name]["spentTo"], sell_id, trade.offer.price)
            return accumulated_trades

    @classmethod
    def _accumulate_producer_trades(cls, producer, grid, accumulated_trades, past_market_types):
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

    @classmethod
    def _accumulate_storage_trade(cls, storage, area, accumulated_trades, past_market_types):
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
                            accumulated_trades[storage.name]["spentTo"], sell_id,
                            trade.offer.price)
                    elif trade.offer.seller == storage.name:
                        accumulated_trades[storage.name]["produced"] -= trade.offer.energy
                        accumulated_trades[storage.name]["earned"] += trade.offer.price
            return accumulated_trades

    @classmethod
    def _accumulate_area_trades(cls, area, parent, accumulated_trades, past_market_types):
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

    @classmethod
    def generate_cumulative_grid_trades_for_all_areas(cls, accumulated_trades, area, results):
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
            results = cls.generate_cumulative_grid_trades_for_all_areas(accumulated_trades, child,
                                                                        results)
        return results
