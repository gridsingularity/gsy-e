from itertools import chain, repeat
from operator import itemgetter
from collections import OrderedDict
import pendulum

# TODO: Potentially remove URLs from endpoints
from flask.helpers import url_for as url_for_original
from flask import abort

from d3a.constants import TIME_FORMAT
from d3a.d3a_core.util import make_iaa_name, format_interval
from d3a.d3a_core.sim_results.stats import energy_bills


def area_endpoint_stats(area):
    return {
        'name': area.name,
        'slug': area.slug,
        'active': area.active,
        'strategy': area.strategy.__class__.__name__ if area.strategy else None,
        'appliance': area.appliance.__class__.__name__ if area.appliance else None,
        'market_overview_url': url_for('markets', area_slug=area.slug),
        'available_triggers': {
            trigger.name: {
                'name': trigger.name,
                'state': trigger.state,
                'help': trigger.help,
                'url': url_for('area_trigger', area_slug=area.slug, trigger_name=trigger.name),
                'parameters': [
                    {
                        'name': name,
                        'type': type_.__name__,
                    }
                    for name, type_ in trigger.params.items()
                ]
            }
            for trigger in area.available_triggers.values()
        },
        'markets': [
            {
                'type': type_,
                'time_slot': time.format(TIME_FORMAT),
                'url': url_for('market', area_slug=area.slug,
                               market_time=time),
                'trade_count': len(market.trades),
                'offer_count': len(market.offers)
            }
            for type_, (time, market)
            in _market_progression(area)
        ],
    }


def market_endpoint_stats(area, market_time):
    market, type_ = _get_market(area, market_time)
    return {
        'type': type_,
        'time_slot': market.time_slot.format(TIME_FORMAT),
        'url': url_for('market', area_slug=area.slug, market_time=market.time_slot),
        'prices': {
            'trade': {
                'min': market.min_trade_price,
                'avg': market.avg_trade_price,
                'max': market.max_trade_price,
            } if market.trades else _NO_VALUE,
            'offer': {
                'min': market.min_offer_price,
                'avg': market.avg_offer_price,
                'max': market.max_offer_price,
            } if market.offers else _NO_VALUE
        },
        'energy_aggregate': _energy_aggregate(market),
        'energy_accounting': [
            {
                'time': time.format("%H:%M:%S"),
                'reports': [
                    {
                        'actor': actor,
                        'value': value
                    }
                    for actor, value in acct_dict.items()
                ]
            }
            for time, acct_dict in sorted(market.actual_energy.items(), key=itemgetter(0))
        ],
        'trades': [
            {
                'id': t.id,
                'time': str(t.time),
                'seller': t.seller,
                'buyer': t.buyer,
                'energy': t.offer.energy,
                'price': t.offer.price / t.offer.energy
            }
            for t in market.trades
        ],
        'offers': [
            {
                'id': o.id,
                'seller': o.seller,
                'energy': o.energy,
                'price': o.price / o.energy
            }
            for o in market.offers.values()
        ],
        'ious': _ious(market)
    }


def markets_endpoints_stats(area):
    return [
        {
            'prices': {
                'trade': {
                    'min': market.min_trade_price,
                    'avg': market.avg_trade_price,
                    'max': market.max_trade_price,
                } if market.trades else _NO_VALUE,
                'offer': {
                    'min': market.min_offer_price,
                    'avg': market.avg_offer_price,
                    'max': market.max_offer_price,
                } if market.offers else _NO_VALUE
            },
            'ious': _ious(market),
            'energy_aggregate': _energy_aggregate(market),
            'total_traded': _total_traded(market),
            'trade_count': len(market.trades),
            'offer_count': len(market.offers),
            'type': type_,
            'time_slot': market.time_slot.format(TIME_FORMAT),
            'url': url_for('market', area_slug=area.slug, market_time=market.time_slot),
        }
        for type_, (time, market)
        in _market_progression(area)
    ]


def market_results_endpoint_stats(area, market):
    if market is None:
        return {'error': 'no results yet'}
    return {
        'summary': {
            'avg_trade_price': market.avg_trade_price,
            'max_trade_price': market.max_trade_price,
            'min_trade_price': market.min_trade_price
        },
        'balance': {
            child.slug: market.total_earned(child.slug) - market.total_spent(child.slug)
            for child in area.children
        },
        'energy_balance': {
            child.slug: _get_child_traded_energy(market, child)
            for child in area.children
        },
        'slots': [
            {
                'volume': sum(trade.offer.energy for trade in slot_market.trades),
            }
            for slot_market in area.past_markets.values()
        ]
    }


def bills_endpoint_stats(area, from_slot, to_slot):
    result = energy_bills(area, from_slot, to_slot)
    result = OrderedDict(sorted(result.items()))
    if from_slot:
        result['from'] = str(from_slot)
    if to_slot:
        result['to'] = str(to_slot)
    return result


def simulation_info(simulation):
    current_time = format_interval(
        simulation.area.current_tick * simulation.area.config.tick_length,
        show_day=False
    )
    return {
        'config': simulation.area.config.as_dict(),
        'finished': simulation.finished,
        'aborted': simulation.is_stopped,
        'current_tick': simulation.area.current_tick,
        'current_time': current_time,
        'current_date': simulation.area.now.format('%Y-%m-%d'),
        'paused': simulation.paused,
        'slowdown': simulation.slowdown
    }


_NO_VALUE = {
    'min': None,
    'avg': None,
    'max': None
}


def _get_market(area, market_time):
    if market_time == 'current':
        market = list(area.past_markets.values())[-1]
        type_ = 'current'
    elif market_time.isdigit():
        market = list(area.markets.values())[int(market_time)]
        type_ = 'open'
    elif market_time[0] == '-' and market_time[1:].isdigit():
        market = list(area.past_markets.values())[int(market_time)]
        type_ = 'closed'
    else:
        time = pendulum.parse(market_time)
        try:
            market = area.markets[time]
            type_ = 'open'
        except KeyError:
            try:
                market = area.past_markets[time]
            except KeyError:
                return abort(404)
            type_ = 'closed'
            if market.time_slot == list(area.past_markets.keys())[-1]:
                type_ = 'current'
    return market, type_


def url_for(target, **kwargs):
    return url_for_original(target, **{**kwargs, '_external': True})


def _market_progression(area):
    return chain(
        zip(
            chain(
                repeat('closed', times=len(area.past_markets) - 1),
                ('current',)
            ),
            list(area.past_markets.items())
        ),
        zip(
            repeat('open'),
            list(area.markets.items())
        )
    )


def _energy_aggregate(market):
    return {
        'traded': {
            actor: round(value, 4)
            for actor, value
            in list(market.traded_energy.items())
            if abs(value) > 0.0000
        },
        'actual': {
            actor: round(value, 4)
            for actor, value
            in list(market.actual_energy_agg.items())
        }
    }


def _total_traded(market):
    return sum(trade.offer.energy for trade in market.trades) if market.trades else 0


def _ious(market):
    return {
        buyer: {
            seller: round(total, 4)
            for seller, total
            in seller_total.items()
            }
        for buyer, seller_total in list(market.ious.items())
        }


def _get_child_traded_energy(market, child):
    return market.traded_energy.get(
        child.name,
        market.traded_energy.get(make_iaa_name(child), '-')
    )
