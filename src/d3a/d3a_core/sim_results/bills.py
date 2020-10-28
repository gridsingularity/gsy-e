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
from copy import deepcopy
from d3a.d3a_core.util import round_floats_for_ui
from d3a.d3a_core.util import area_name_from_area_or_iaa_name
from d3a.d3a_core.sim_results import is_load_node_type, is_pv_node_type
from d3a.constants import LOAD_PENALTY_RATE, PV_PENALTY_RATE
from d3a.d3a_core.sim_results import get_unified_area_type


class CumulativeBills:
    def __init__(self):
        self.cumulative_bills_results = {}

    def _calculate_device_penalties(self, area, area_core_stats):
        if len(area['children']) > 0 or area_core_stats == {}:
            return 0.0

        if is_load_node_type(area):
            return area_core_stats['energy_requirement_kWh']
        elif is_pv_node_type(area):
            return area_core_stats['available_energy_kWh']
        else:
            return 0.0

    @property
    def cumulative_bills(self):
        return {
            uuid: {
                "name": results["name"],
                "spent_total": round_floats_for_ui(results['spent_total']),
                "earned": round_floats_for_ui(results['earned']),
                "penalties": round_floats_for_ui(results['penalties']),
                "total": round_floats_for_ui(results['total'])
            }
            for uuid, results in self.cumulative_bills_results.items()
        }

    def update_cumulative_bills(self, area_dict, core_stats, current_market_time_slot):
        for child in area_dict['children']:
            self.update_cumulative_bills(child, core_stats, current_market_time_slot)

        if area_dict['uuid'] not in self.cumulative_bills_results:
            self.cumulative_bills_results[area_dict['uuid']] = {
                "name": area_dict['name'],
                "spent_total": 0.0,
                "earned": 0.0,
                "penalties": 0.0,
                "penalty_energy": 0.0,
                "total": 0.0,
            }

        if area_dict['type'] == "Area":
            all_child_results = [self.cumulative_bills_results[c['uuid']]
                                 for c in area_dict['children']]
            self.cumulative_bills_results[area_dict['uuid']] = {
                "name": area_dict['name'],
                "spent_total": sum(c["spent_total"] for c in all_child_results),
                "earned": sum(c["earned"] for c in all_child_results),
                "penalties": sum(c["penalties"] for c in all_child_results
                                 if c["penalties"] is not None),
                "penalty_energy": sum(c["penalty_energy"] for c in all_child_results
                                      if c["penalty_energy"] is not None),
                "total": sum(c["total"] for c in all_child_results),
            }
        else:
            parent_area_stats = core_stats.get(area_dict['parent_uuid'], {})
            trades = parent_area_stats.get('trades', [])

            spent_total = sum(trade['price']
                              for trade in trades
                              if trade['buyer'] == area_dict['name']) / 100.0
            earned = sum(trade['price'] - trade['fee_price']
                         for trade in trades
                         if trade['seller'] == area_dict['name']) / 100.0
            penalty_energy = self._calculate_device_penalties(
                area_dict, core_stats.get(area_dict['uuid'], {})
            )

            if is_load_node_type(area_dict):
                penalty_cost = penalty_energy * LOAD_PENALTY_RATE / 100.0
            elif is_pv_node_type(area_dict):
                penalty_cost = penalty_energy * PV_PENALTY_RATE / 100.0
            else:
                penalty_cost = 0.0

            total = spent_total - earned + penalty_cost
            self.cumulative_bills_results[area_dict['uuid']]["spent_total"] += spent_total
            self.cumulative_bills_results[area_dict['uuid']]["earned"] += earned
            self.cumulative_bills_results[area_dict['uuid']]["penalties"] += penalty_cost
            self.cumulative_bills_results[area_dict['uuid']]["penalty_energy"] += penalty_energy
            self.cumulative_bills_results[area_dict['uuid']]["total"] += total


class MarketEnergyBills:
    def __init__(self, is_spot_market=True):
        self.is_spot_market = is_spot_market
        self.bills = {}
        self.bills_results = {}
        self.bills_redis_results = {}
        self.market_fees = {}
        self.cumulative_fee_charged_per_market = 0.
        self.external_trades = {}

    @staticmethod
    def _store_bought_trade(result_dict, trade):
        trade_price = trade['price'] / 100.
        # Division by 100 to convert cents to Euros
        fee_price = trade['fee_price'] / 100. if trade['fee_price'] is not None else 0.
        result_dict['bought'] += trade['energy']
        result_dict['spent'] += trade_price - fee_price
        result_dict['total_cost'] += trade_price
        result_dict['total_energy'] += trade['energy']
        result_dict['market_fee'] += fee_price

    @staticmethod
    def _store_sold_trade(result_dict, trade):
        # Division by 100 to convert cents to Euros
        fee_price = trade['fee_price'] / 100. if trade['fee_price'] is not None else 0.
        result_dict['sold'] += trade['energy']
        result_dict['total_energy'] -= trade['energy']
        trade_price = trade['price'] / 100. - fee_price
        result_dict['earned'] += trade_price
        result_dict['total_cost'] -= trade_price

    def _store_outgoing_external_trade(self, trade, area_dict):
        fee_price = trade['fee_price'] if trade['fee_price'] is not None else 0.
        self.external_trades[area_dict['name']]['sold'] += trade['energy']
        self.external_trades[area_dict['name']]['earned'] += \
            (trade['price'] - fee_price) / 100.
        self.external_trades[area_dict['name']]['total_cost'] -= \
            (trade['price'] - fee_price) / 100.
        self.external_trades[area_dict['name']]['total_energy'] -= trade['energy']
        self.external_trades[area_dict['name']]['market_fee'] += fee_price / 100.

    def _store_incoming_external_trade(self, trade, area_dict):
        trade_price = trade['price'] / 100.
        fee_price = trade['fee_price'] / 100. if trade['fee_price'] is not None else 0.
        self.external_trades[area_dict['name']]['bought'] += trade['energy']
        self.external_trades[area_dict['name']]['spent'] += trade_price - fee_price
        self.external_trades[area_dict['name']]['total_cost'] += trade_price
        self.external_trades[area_dict['name']]['total_energy'] += trade['energy']

    @classmethod
    def _default_area_dict(cls, area_dict):
        area_type = get_unified_area_type(deepcopy(area_dict))
        return dict(bought=0.0, sold=0.0,
                    spent=0.0, earned=0.0,
                    total_energy=0.0, total_cost=0.0,
                    market_fee=0.0,
                    type=area_type)

    def _get_child_data(self, area_dict):
        if area_dict['name'] not in self.bills_results:
            self.bills_results[area_dict['name']] =  \
                {child['name']: self._default_area_dict(child)
                    for child in area_dict['children']}
        else:
            # TODO: find a better way to handle this.
            # is only triggered once:
            # when a child is added to an area both triggered by a live event
            if area_dict['children'] and "bought" in self.bills_results[area_dict['name']]:
                self.bills_results[area_dict['name']] = {}
            for child in area_dict['children']:
                self.bills_results[area_dict['name']][child['name']] = \
                    self._default_area_dict(child) \
                    if child['name'] not in self.bills_results[area_dict['name']] else \
                    self.bills_results[area_dict['name']][child['name']]

        return self.bills_results[area_dict['name']]

    def _energy_bills(self, area_dict, area_core_stats):
        """
        Return a bill for each of area's children with total energy bought
        and sold (in kWh) and total money earned and spent (in cents).
        Compute bills recursively for children of children etc.
        """
        if area_dict['children'] == []:
            return None

        if area_dict['name'] not in self.external_trades:
            self.external_trades[area_dict['name']] = dict(
                bought=0.0, sold=0.0, spent=0.0, earned=0.0,
                total_energy=0.0, total_cost=0.0, market_fee=0.0)

        result = self._get_child_data(area_dict)
        for trade in area_core_stats[area_dict['uuid']]['trades']:
            buyer = area_name_from_area_or_iaa_name(trade['buyer'])
            seller = area_name_from_area_or_iaa_name(trade['seller'])
            if buyer in result:
                self._store_bought_trade(result[buyer], trade)
            if seller in result:
                self._store_sold_trade(result[seller], trade)
            # Outgoing external trades
            if buyer == area_name_from_area_or_iaa_name(area_dict['name']) and seller in result:
                self._store_outgoing_external_trade(trade, area_dict)
            # Incoming external trades
            if seller == area_name_from_area_or_iaa_name(area_dict['name']) and buyer in result:
                self._store_incoming_external_trade(trade, area_dict)
        for child in area_dict['children']:
            child_result = self._energy_bills(child, area_core_stats)
            if child_result is not None:
                result[child['name']]['children'] = child_result

        return result

    def _accumulate_market_fees(self, area_dict, area_core_stats):
        if area_dict['name'] not in self.market_fees:
            self.market_fees[area_dict['name']] = 0.0
        self.market_fees[area_dict['name']] += \
            area_core_stats[area_dict['uuid']]['market_fee'] / 100.0
        for child in area_dict['children']:
            self._accumulate_market_fees(child, area_core_stats)

    def _update_market_fees(self, area_dict, area_core_stats):
        self._accumulate_market_fees(area_dict, area_core_stats)

    def _accumulate_grid_fee_charged(self, area_dict, area_core_stats):
        area_stats = area_core_stats.get(area_dict['uuid'])
        self.cumulative_fee_charged_per_market += area_stats.get('market_fee', 0.) / 100.
        for child in area_dict['children']:
            self._accumulate_grid_fee_charged(child, area_core_stats)

    def update(self, area_dict, area_core_stats):
        self._update_market_fees(area_dict, area_core_stats)
        self._accumulate_grid_fee_charged(area_dict, area_core_stats)
        bills = self._energy_bills(area_dict, area_core_stats)
        flattened = {}
        self._flatten_energy_bills(bills, flattened)
        self.bills_results = self._accumulate_by_children(area_dict, flattened, {})
        self._bills_for_redis(area_dict, deepcopy(self.bills_results))

    @classmethod
    def _flatten_energy_bills(cls, energy_bills, flat_results):
        for k, v in energy_bills.items():
            if "children" in v:
                cls._flatten_energy_bills(v["children"], flat_results)
            flat_results[k] = v
            flat_results[k].pop("children", None)

    def _accumulate_by_children(self, area_dict, flattened, results):
        if not area_dict['children']:
            # This is a device
            results[area_dict['name']] = flattened.get(area_dict['name'],
                                                       self._default_area_dict(area_dict))
        else:
            results[area_dict['name']] = \
                {c['name']: flattened[c['name']] for c in area_dict['children']
                 if c['name'] in flattened}

            results.update(**self._generate_external_and_total_bills(area_dict, results))

            for c in area_dict['children']:
                results.update(
                    **self._accumulate_by_children(c, flattened, results)
                )
        return results

    @staticmethod
    def _write_accumulated_stats(area_dict, results, all_child_results, key_name):
        results[area_dict['name']].update({key_name: {
            'bought': sum(v['bought'] for v in all_child_results),
            'sold': sum(v['sold'] for v in all_child_results),
            'spent': sum(v['spent'] for v in all_child_results),
            'earned': sum(v['earned'] for v in all_child_results),
            'total_energy': sum(v['total_energy'] for v in all_child_results),
            'total_cost': sum(v['total_cost']
                              for v in all_child_results),
            'market_fee': sum(v['market_fee']
                              for v in all_child_results)
        }})

    @staticmethod
    def _market_fee_section(market_fee):
        return {"Market Fees": {
                    "bought": 0,
                    "sold": 0,
                    "spent": 0,
                    "earned": market_fee,
                    "market_fee": 0,
                    "total_energy": 0,
                    "total_cost": -1 * market_fee
                    }}

    def _generate_external_and_total_bills(self, area_dict, results):

        all_child_results = [v for v in results[area_dict['name']].values()]
        self._write_accumulated_stats(area_dict, results, all_child_results, "Accumulated Trades")
        total_market_fee = results[area_dict['name']]["Accumulated Trades"]["market_fee"]
        if area_dict['name'] in self.external_trades:
            # External trades are the trades of the parent area
            external = self.external_trades[area_dict['name']].copy()
            # Should switch spent/earned and bought/sold, to match the perspective of the UI
            spent = external.pop("spent")
            earned = external.pop("earned")
            bought = external.pop("bought")
            sold = external.pop("sold")
            total_external_fee = external.pop("market_fee")
            external.update(**{
                "spent": earned, "earned": spent, "bought": sold,
                "sold": bought, "market_fee": total_external_fee})
            external["total_energy"] = external["bought"] - external["sold"]
            external["total_cost"] = external["spent"] - external["earned"] + total_external_fee
            results[area_dict['name']].update({"External Trades": external})

            total_market_fee += total_external_fee
            results[area_dict['name']].update(self._market_fee_section(total_market_fee))
            totals_child_list = [results[area_dict['name']]["Accumulated Trades"],
                                 results[area_dict['name']]["External Trades"],
                                 results[area_dict['name']]["Market Fees"]]
        else:
            # If root area, Accumulated Trades == Totals
            results[area_dict['name']].update(self._market_fee_section(total_market_fee))
            totals_child_list = [results[area_dict['name']]["Accumulated Trades"],
                                 results[area_dict['name']]["Market Fees"]]

        self._write_accumulated_stats(area_dict, results, totals_child_list, "Totals")
        return results

    def _bills_for_redis(self, area_dict, bills_results):
        if area_dict['name'] in bills_results:
            self.bills_redis_results[area_dict['uuid']] = \
                self._round_area_bill_result_redis(bills_results[area_dict['name']])
        for child in area_dict['children']:
            if child['children']:
                self._bills_for_redis(child, bills_results)
            elif child['name'] in bills_results:
                self.bills_redis_results[child['uuid']] = \
                    self._round_child_bill_results(bills_results[child['name']])

    @classmethod
    def _round_child_bill_results(cls, results):
        results['bought'] = round_floats_for_ui(results['bought'])
        results['sold'] = round_floats_for_ui(results['sold'])
        results['spent'] = round_floats_for_ui(results['spent'])
        results['earned'] = round_floats_for_ui(results['earned'])
        results['total_energy'] = round_floats_for_ui(results['total_energy'])
        results['total_cost'] = round_floats_for_ui(results['total_cost'])
        if "market_fee" in results:
            results["market_fee"] = round_floats_for_ui(results['market_fee'])
        return results

    @classmethod
    def _round_area_bill_result_redis(cls, results):
        for k in results.keys():
            results[k] = cls._round_child_bill_results(results[k])
        return results
