from statistics import mean
from typing import Dict
from pendulum import DateTime

from d3a.constants import DATE_TIME_FORMAT, TIME_FORMAT
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.area import Area
from d3a.d3a_core.util import generate_market_slot_list

FILL_VALUE = None


def _calc_min_max_from_sim_dict(indict: Dict[DateTime, list]) -> tuple((Dict, Dict)):

    min_trade_stats_daily = {}
    max_trade_stats_daily = {}

    trade_stats_daily = dict((k.format(TIME_FORMAT), []) for k, v in indict.items())

    for time, value in indict.items():
        if len(value) != 0:
            trade_stats_daily[time.format(TIME_FORMAT)] += value

    for time_str, value in trade_stats_daily.items():
        min_trade_stats_daily[time_str] = min(value) if len(value) > 0 else FILL_VALUE
        max_trade_stats_daily[time_str] = max(value) if len(value) > 0 else FILL_VALUE

    min_trade_stats = dict((time.format(DATE_TIME_FORMAT),
                            min_trade_stats_daily[time.format(TIME_FORMAT)])
                           for time in indict.keys())
    max_trade_stats = dict((time.format(DATE_TIME_FORMAT),
                            max_trade_stats_daily[time.format(TIME_FORMAT)])
                           for time in indict.keys())

    return min_trade_stats, max_trade_stats


def _device_price_stats(area: Area) -> Dict:

    trade_price_dict = {}
    for market in area.parent.past_markets:
        if market.time_slot not in trade_price_dict:
            trade_price_dict[market.time_slot] = []
        for t in market.trades:
            if t.seller == area.name or t.buyer == area.name:
                trade_price_dict[market.time_slot].append(t.offer.price / 100.0 / t.offer.energy)

    trade_price = {}
    for time, value in trade_price_dict.items():
        if value != []:
            trade_price[time.format(DATE_TIME_FORMAT)] = mean(value)
        else:
            trade_price[time.format(DATE_TIME_FORMAT)] = FILL_VALUE

    min_trade_price, max_trade_price = _calc_min_max_from_sim_dict(trade_price_dict)

    return {"trade_price_eur": trade_price,
            "min_trade_price_eur": min_trade_price,
            "max_trade_price_eur": max_trade_price}


def _device_energy_stats(area: Area) -> Dict:

    trade_energy_dict = {}
    for market in area.parent.past_markets:
        if market.time_slot not in trade_energy_dict:
            trade_energy_dict[market.time_slot] = [0.]
        for t in market.trades:
            if t.seller == area.name:
                trade_energy_dict[market.time_slot][0] -= t.offer.energy
            if t.buyer == area.name:
                trade_energy_dict[market.time_slot][0] += t.offer.energy

    trade_energy = dict((k.format(DATE_TIME_FORMAT), v[0]) for k, v in trade_energy_dict.items())

    min_trade_energy, max_trade_energy = _calc_min_max_from_sim_dict(trade_energy_dict)

    return {"trade_energy_kWh": trade_energy,
            "min_trade_energy_kWh": min_trade_energy,
            "max_trade_energy_kWh": max_trade_energy}


def _pv_production_stats(area: Area) -> Dict:
    pv_production_dict = dict((k, [v])
                              for k, v in area.strategy.energy_production_forecast_kWh.items())
    pv_production = dict((k.format(DATE_TIME_FORMAT), v[0]) for k, v in pv_production_dict.items())

    min_pv_production, max_pv_production = _calc_min_max_from_sim_dict(pv_production_dict)

    return {"pv_production_kWh": pv_production,
            "min_pv_production_kWh": min_pv_production,
            "max_pv_production_kWh": max_pv_production}


def _soc_stats(area: Area) -> Dict:
    soc_hist_dict = dict((k, [v]) for k, v in area.strategy.state.charge_history.items())
    soc_hist = dict((k.format(DATE_TIME_FORMAT), v[0]) for k, v in soc_hist_dict.items())

    min_soc, max_soc = _calc_min_max_from_sim_dict(soc_hist_dict)

    return {"soc_hist": soc_hist,
            "min_soc_hist": min_soc,
            "max_soc_hist": max_soc}


def _load_profile_stats(area: Area) -> Dict:
    load_profile_dict = dict(
        (slot_time, [0]) for slot_time in generate_market_slot_list(area))

    for k, v in area.strategy.energy_requirement_history_kWh.items():
        load_profile_dict[k] = [v]

    load_profile = dict((k.format(DATE_TIME_FORMAT), v[0]) for k, v in load_profile_dict.items())

    min_load_profile, max_load_profile = _calc_min_max_from_sim_dict(load_profile_dict)

    return {"load_profile_kWh": load_profile,
            "min_load_profile_kWh": min_load_profile,
            "max_load_profile_kWh": max_load_profile}


def gather_device_statistics(area: Area, dev_stats_dict: Dict) -> Dict:

    for child in area.children:
        if child.children == []:
            if len(child.parent.past_markets) == 0:
                continue

            if isinstance(child.strategy, PVStrategy):

                trade_price_dict = _device_price_stats(child)
                trade_energy_dict = _device_energy_stats(child)
                pv_prod_dict = _pv_production_stats(child)

                leaf_dict = {**trade_price_dict,
                             **trade_energy_dict,
                             **pv_prod_dict}

            elif isinstance(child.strategy, StorageStrategy):

                soc_dict = _soc_stats(child)
                trade_price_dict = _device_price_stats(child)
                trade_energy_dict = _device_energy_stats(child)
                leaf_dict = {**trade_price_dict,
                             **trade_energy_dict,
                             **soc_dict}

            elif isinstance(child.strategy, LoadHoursStrategy):

                load_profile_dict = _load_profile_stats(child)
                trade_price_dict = _device_price_stats(child)
                trade_energy_dict = _device_energy_stats(child)
                leaf_dict = {**trade_price_dict,
                             **trade_energy_dict,
                             **load_profile_dict}

            elif isinstance(child.strategy, CommercialStrategy):
                trade_price_dict = _device_price_stats(child)
                trade_energy_dict = _device_energy_stats(child)

                if isinstance(child.strategy, FinitePowerPlant):
                    production_dict = dict((market.time_slot.format(DATE_TIME_FORMAT),
                                            child.strategy.energy_per_slot_kWh)
                                           for market in child.parent.past_markets)
                    leaf_dict = {**trade_price_dict,
                                 **trade_energy_dict,
                                 "production_kWh": production_dict}
                else:
                    leaf_dict = {**trade_price_dict,
                                 **trade_energy_dict}

            else:
                continue

            dev_stats_dict[child.name] = leaf_dict

        else:
            dev_stats_dict[child.name] = {}
            dev_stats_dict[child.name] = gather_device_statistics(child,
                                                                  dev_stats_dict[child.name])

    return dev_stats_dict
