from typing import Dict
from d3a import limit_float_precision
from d3a_interface.utils import create_or_update_subdict

FILL_VALUE = None


class DeviceStatistics:

    def __init__(self, should_export_plots):
        self.device_stats_dict = {}
        self.current_stats_dict = {}
        self.current_stats_time_str = {}
        self.should_export_plots = should_export_plots

    @staticmethod
    def _calc_min_max_from_sim_dict(subdict: Dict, key: str):

        min_trade_stats_daily = {}
        max_trade_stats_daily = {}
        indict = subdict[key]

        trade_stats_daily = dict((k, []) for k, v in indict.items())
        for time, value in indict.items():
            value = [] if value is None else value
            value = [value] if not isinstance(value, list) else value
            trade_stats_daily[time] += value

        for time_str, value in trade_stats_daily.items():
            min_trade_stats_daily[time_str] = limit_float_precision(min(value)) \
                if len(value) > 0 else FILL_VALUE
            max_trade_stats_daily[time_str] = limit_float_precision(max(value)) \
                if len(value) > 0 else FILL_VALUE

        min_trade_stats = dict((time, min_trade_stats_daily[time])
                               for time in indict.keys())
        max_trade_stats = dict((time, max_trade_stats_daily[time])
                               for time in indict.keys())

        create_or_update_subdict(subdict, f"min_{key}", min_trade_stats)
        create_or_update_subdict(subdict, f"max_{key}", max_trade_stats)

    @classmethod
    def _device_price_stats(cls, area: Dict, subdict: Dict, core_stats, current_market_time_slot):
        key_name = "trade_price_eur"
        if core_stats[area['uuid']] == {}:
            return
        area_core_trades = core_stats[area['uuid']].get('trades', [])
        trade_price_list = []
        for t in area_core_trades:
            if t['seller'] == area['name'] or t['buyer'] == area['name']:
                trade_price_list.append(t['energy_rate'] / 100.0)
        if trade_price_list:
            create_or_update_subdict(
                subdict, key_name,
                {current_market_time_slot: trade_price_list})
        else:
            create_or_update_subdict(
                subdict, key_name,
                {current_market_time_slot: FILL_VALUE})

        cls._calc_min_max_from_sim_dict(subdict, key_name)

    @classmethod
    def _device_energy_stats(cls, area: Dict, subdict: Dict, core_stats: Dict,
                             current_market_time_slot):
        if area["type"] == "InfiniteBusStrategy":
            cls.calculate_stats_for_infinite_bus(area, subdict, core_stats,
                                                 current_market_time_slot)
        else:
            cls.calculate_stats_for_device(area, subdict, core_stats, current_market_time_slot)

    @classmethod
    def calculate_stats_for_device(cls, area, subdict, core_stats, current_market_time_slot):
        key_name = "trade_energy_kWh"
        if core_stats[area['uuid']] == {}:
            return
        area_core_trades = core_stats[area['uuid']].get('trades', [])

        traded_energy = 0
        for t in area_core_trades:
            if t['seller'] == area['name']:
                traded_energy -= t['energy']
            if t['buyer'] == area['name']:
                traded_energy += t['energy']

        create_or_update_subdict(
            subdict, key_name,
            {current_market_time_slot: traded_energy})
        cls._calc_min_max_from_sim_dict(subdict, key_name)

    @classmethod
    def calculate_stats_for_infinite_bus(cls, area, subdict, core_stats, current_market_time_slot):
        sold_key_name = "sold_trade_energy_kWh"
        bought_key_name = "bought_trade_energy_kWh"
        sold_traded_energy = 0
        bought_traded_energy = 0
        if core_stats[area['uuid']] == {}:
            return
        area_core_trades = core_stats[area['uuid']].get('trades', [])

        for t in area_core_trades:
            if t['seller'] == area['name']:
                sold_traded_energy += t['energy']
            if t['buyer'] == area['name']:
                bought_traded_energy += t['energy']
        create_or_update_subdict(
            subdict, sold_key_name,
            {current_market_time_slot: sold_traded_energy})
        cls._calc_min_max_from_sim_dict(subdict, sold_key_name)
        create_or_update_subdict(
            subdict, bought_key_name,
            {current_market_time_slot: bought_traded_energy})
        cls._calc_min_max_from_sim_dict(subdict, bought_key_name)

    @classmethod
    def _pv_production_stats(cls, area: Dict, subdict: Dict, core_stats={},
                             current_market_time_slot=None):
        key_name = "pv_production_kWh"
        if core_stats[area['uuid']] == {}:
            return

        create_or_update_subdict(
            subdict, key_name,
            {current_market_time_slot: core_stats[area["uuid"]][key_name]})

        cls._calc_min_max_from_sim_dict(subdict, key_name)

    @classmethod
    def _soc_stats(cls, area: Dict, subdict: Dict, core_stats={}, current_market_time_slot=None):
        key_name = "soc_history_%"
        if core_stats[area['uuid']] == {}:
            return
        create_or_update_subdict(
            subdict, key_name,
            {current_market_time_slot: core_stats[area["uuid"]][key_name]})

        cls._calc_min_max_from_sim_dict(subdict, key_name)

    @classmethod
    def _load_profile_stats(cls, area: Dict, subdict: Dict, core_stats={},
                            current_market_time_slot=None):
        key_name = "load_profile_kWh"
        if core_stats[area['uuid']] == {}:
            return
        create_or_update_subdict(
            subdict, key_name,
            {current_market_time_slot: core_stats[area["uuid"]][key_name]}
        )

        cls._calc_min_max_from_sim_dict(subdict, key_name)

    def update(self, area, area_result_dict={}, core_stats={}, current_market_time_slot=None):
        if self.should_export_plots:
            self.gather_device_statistics(
                area_result_dict, self.device_stats_dict, {}, core_stats,
                current_market_time_slot)
        else:
            self.gather_device_statistics(
                area_result_dict, {}, self.current_stats_dict, core_stats,
                current_market_time_slot)

    @classmethod
    def gather_device_statistics(cls, area: Dict, subdict: Dict,
                                 flat_result_dict: Dict,
                                 core_stats={}, current_market_time_slot=None):
        for child in area['children']:
            if child['name'] not in subdict.keys():
                subdict.update({child['name']: {}})
            if child['children'] == [] and core_stats != {}:
                cls._gather_device_statistics(
                    child, subdict[child['name']], flat_result_dict,
                    core_stats, current_market_time_slot)
            else:
                cls.gather_device_statistics(
                    child, subdict[child['name']], flat_result_dict,
                    core_stats, current_market_time_slot)

    @classmethod
    def _gather_device_statistics(cls, area: Dict, subdict: Dict,
                                  flat_result_dict: Dict,
                                  core_stats={}, current_market_time_slot=None):
        if core_stats.get(area['uuid'], {}) == {}:
            return
        if area['type'] != "Area":
            cls._device_price_stats(area, subdict, core_stats, current_market_time_slot)
            cls._device_energy_stats(area, subdict, core_stats, current_market_time_slot)

        if area['type'] in ["PVStrategy", "PVUserProfileStrategy",
                            "PVPredefinedStrategy"]:
            cls._pv_production_stats(area, subdict, core_stats, current_market_time_slot)

        elif area['type'] == "StorageStrategy":
            cls._soc_stats(area, subdict, core_stats, current_market_time_slot)

        elif area['type'] in ["LoadHoursStrategy", "DefinedLoadStrategy",
                              "CellTowerLoadHoursStrategy"]:
            cls._load_profile_stats(area, subdict, core_stats, current_market_time_slot)

        elif area['type'] == "FinitePowerPlant":
            create_or_update_subdict(
                subdict, "production_kWh",
                {current_market_time_slot: core_stats[area["uuid"]]["production_kWh"]}
            )
            cls._calc_min_max_from_sim_dict(subdict, "production_kWh")

        flat_result_dict[area["uuid"]] = subdict.copy()
