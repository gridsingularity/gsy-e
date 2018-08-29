from d3a.area_statistics import export_cumulative_grid_trades, export_cumulative_loads, \
    export_price_energy_day
from d3a.export_unmatched_loads import export_unmatched_loads
from d3a.stats import energy_bills
from d3a.util import make_iaa_name
from d3a import TIME_FORMAT
from collections import OrderedDict
from statistics import mean
from itertools import chain, repeat
from operator import itemgetter


_NO_VALUE = {
    'min': None,
    'avg': None,
    'max': None
}


class SimulationEndpointBuffer:
    def __init__(self, job_id, initial_params):
        self.job_id = job_id
        self.random_seed = initial_params["seed"] if initial_params["seed"] is not None else ''
        self.status = {}
        self.unmatched_loads = {}
        self.cumulative_loads = {}
        self.price_energy_day = {}
        self.cumulative_grid_trades = {}
        self.tree_summary = {}
        self.bills = {}
        self.results = {}
        self.markets = {}
        self.market = {}
        self.area = {}

    def generate_result_report(self):
        return {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            **self.unmatched_loads,
            "cumulative_loads": self.cumulative_loads,
            "price_energy_day": self.price_energy_day,
            "cumulative_grid_trades": self.cumulative_grid_trades,
            "bills": self.bills,
            "tree_summary": self.tree_summary,
            "status": self.status
        }

    def update(self, area, simulation_status):
        self.status = simulation_status
        self.unmatched_loads = {"unmatched_loads": export_unmatched_loads(area)}
        self.cumulative_loads = {
            "price-currency": "Euros",
            "load-unit": "kWh",
            "cumulative-load-price": export_cumulative_loads(area)
        }
        self.price_energy_day = {
            "price-currency": "Euros",
            "load-unit": "kWh",
            "price-energy-day": export_price_energy_day(area)
        }
        self.cumulative_grid_trades = export_cumulative_grid_trades(area)
        self._update_bills(area)
        self._update_tree_summary(area)
        # Disabling buffering these expensive endpoints for now, since the UI does not use them
        # self._update_results(area)
        # self._update_markets(area)
        # self._update_market(area)
        # self._update_area(area)

    def _update_tree_summary(self, area):
        price_energy_list = export_price_energy_day(area)

        def calculate_prices(key, functor):
            # Need to convert to euro cents to avoid having to change the backend
            # TODO: Both this and the frontend have to remove the recalculation
            energy_prices = [price_energy[key] for price_energy in price_energy_list]
            return round(100 * functor(energy_prices), 2) if len(energy_prices) > 0 else 0.0

        self.tree_summary[area.slug] = {
            "min_trade_price": calculate_prices("min_price", min),
            "max_trade_price": calculate_prices("max_price", max),
            "avg_trade_price": calculate_prices("av_price", mean),
        }
        for child in area.children:
            if child.children != []:
                self._update_tree_summary(child)

    def _update_bills(self, area):
        result = energy_bills(area)
        self.bills = OrderedDict(sorted(result.items()))

    def _update_results(self, area):
        market = area.current_market
        if market is None:
            return {'error': 'no results yet'}
        self.results[area.slug] = {
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
                child.slug: self._get_child_traded_energy(market, child)
                for child in area.children
            },
            'slots': [
                {
                    'volume': sum(trade.offer.energy for trade in slot_market.trades),
                }
                for slot_market in area.past_markets.values()
            ]
        }
        [self._update_results(child) for child in area.children if child.children != []]

    @staticmethod
    def _get_child_traded_energy(market, child):
        # TODO: Try to reuse traded_energy for endpoints that use this information
        return market.traded_energy.get(
            child.name,
            market.traded_energy.get(make_iaa_name(child), '-')
        )

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def _total_traded(market):
        return sum(trade.offer.energy for trade in market.trades) if market.trades else 0

    @staticmethod
    def _ious(market):
        return {
            buyer: {
                seller: round(total, 4)
                for seller, total
                in seller_total.items()
            }
            for buyer, seller_total in list(market.ious.items())
        }

    def _update_markets(self, area):
        self.markets[area.slug] = [
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
                'ious': self._ious(market),
                'energy_aggregate': self._energy_aggregate(market),
                'total_traded': self._total_traded(market),
                'trade_count': len(market.trades),
                'offer_count': len(market.offers),
                'type': type_,
                'time_slot': market.time_slot.format(TIME_FORMAT),
                # 'url': url_for('market', area_slug=area.slug, market_time=market.time_slot),
            }
            for type_, (time, market)
            in self._market_progression(area)
        ]
        [self._update_markets(child) for child in area.children]

    def _update_market(self, area):
        self.market[area.slug] = {}
        market_iterable = area.past_markets.values()
        # market_iterable.extend(list(self.markets.values()))
        if market_iterable:
            for market in market_iterable:
                if market not in self.market[area.slug].keys():
                    self.market[area.slug][market] = {
                        'time_slot': market.time_slot.format(TIME_FORMAT),
                        # 'url': url_for('market', area_slug=area.slug,
                        #                market_time=market.time_slot),
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
                        'energy_aggregate': self._energy_aggregate(market),
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
                            for time, acct_dict in
                            sorted(market.actual_energy.items(), key=itemgetter(0))
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
                        'ious': self._ious(market)
                    }
        [self._update_market(child) for child in area.children]

    def _update_area(self, area):
        self.area[area.slug] = {
            'name': area.name,
            'slug': area.slug,
            'active': area.active,
            'strategy': area.strategy.__class__.__name__ if area.strategy else None,
            'appliance': area.appliance.__class__.__name__ if area.appliance else None,
            # 'market_overview_url': url_for('markets', area_slug=area.slug),
            'available_triggers': {
                trigger.name: {
                    'name': trigger.name,
                    'state': trigger.state,
                    'help': trigger.help,
                    # 'url': url_for('area_trigger', area_slug=area.slug,
                    #                 trigger_name=trigger.name),
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
                    # 'url': url_for('market', area_slug=area.slug,
                    #                market_time=time),
                    'trade_count': len(market.trades),
                    'offer_count': len(market.offers)
                }
                for type_, (time, market)
                in self._market_progression(area)
            ],
        }
        [self._update_area(child) for child in area.children]
