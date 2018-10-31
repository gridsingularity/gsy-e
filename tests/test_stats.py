import pytest
from unittest.mock import MagicMock

from d3a.models.market.market_structures import Trade
from d3a.stats import (
    energy_bills, primary_unit_prices, recursive_current_markets, total_avg_trade_price
)
from d3a.util import make_iaa_name
from d3a.models.strategy.base import BaseStrategy


class FakeArea:
    def __init__(self, name, children=None, past_markets=None):
        self.name = name
        self.children = children
        self.past_markets = past_markets
        self.strategy = MagicMock(spec=BaseStrategy)

    @property
    def current_market(self):
        return 'market %s' % self.name if self.children else None


class FakeMarket:
    def __init__(self, trades):
        self.trades = trades
        self.time_slot = 15


class FakeOffer:
    def __init__(self, price, energy, seller):
        self.price = price
        self.energy = energy
        self.seller = seller


def _trade(price, buyer, energy=1, seller=None):
    return Trade('id', 0, FakeOffer(price, energy, seller), 'seller', buyer, None)


@pytest.fixture
def area():
    return FakeArea('parent',
                    [FakeArea('child1'),
                     FakeArea('child2', [FakeArea('grandchild1', [FakeArea('-')])]),
                     FakeArea('child3', [FakeArea('grandchild2')])])


def test_recursive_current_markets(area):
    markets = list(recursive_current_markets(area))
    assert len(markets) == 4
    assert all(market in markets for market in (
        'market parent', 'market child2', 'market grandchild1', 'market child3'
    ))


@pytest.fixture
def markets():
    """Example with all equal energy prices"""
    return (
        FakeMarket((_trade(5, 'Fridge'), _trade(3, 'PV'), _trade(10, 'IAA 1'))),
        FakeMarket((_trade(1, 'Storage'), _trade(4, 'Fridge'), _trade(6, 'Fridge'),
                    _trade(2, 'Fridge'))),
        FakeMarket((_trade(11, 'IAA 3'), _trade(20, 'IAA 9'), _trade(21, 'IAA 3')))
    )


@pytest.fixture
def markets2():
    """Example with different energy prices to test weighted averaging"""
    return(
        FakeMarket((_trade(11, 'Fridge', 11), _trade(4, 'Storage', 4), _trade(1, 'IAA 1', 10))),
        FakeMarket((_trade(3, 'ECar', 1), _trade(9, 'Fridge', 3), _trade(3, 'Storage', 1)))
    )


def test_total_avg_trade_price(markets, markets2):
    assert total_avg_trade_price(markets) == 3.5
    assert total_avg_trade_price(markets2) == 1.5


def test_primary_unit_prices(markets2):
    prices = list(primary_unit_prices(markets2))
    assert min(prices) == 1
    assert max(prices) == 3


@pytest.fixture
def grid():
    return FakeArea('grid', children=[
        FakeArea('house1',
                 children=[FakeArea('fridge'), FakeArea('pv')],
                 past_markets=[FakeMarket((_trade(2, 'fridge', 2, 'pv'),
                                           _trade(3, 'fridge', 1, 'iaa'))),
                               FakeMarket((_trade(1, 'fridge', 2, 'pv'),))]),
        FakeArea('house2',
                 children=[FakeArea('e-car')],
                 past_markets=[FakeMarket((_trade(1, 'e-car', 4, 'iaa'),
                                           _trade(1, 'e-car', 8, 'iaa'),
                                           _trade(3, 'iaa', 5, 'e-car'))),
                               FakeMarket((_trade(1, 'e-car', 1, 'iaa'),))]),
        FakeArea('commercial')
    ], past_markets=[
        FakeMarket((_trade(2, 'house2', 12, 'commercial'),)),
        FakeMarket((_trade(1, 'house2', 1, 'commercial'),))
    ])


def test_energy_bills(grid):
    result = energy_bills(grid)
    assert result['house2']['bought'] == result['commercial']['sold'] == 13
    assert result['house2']['spent'] == result['commercial']['earned'] == 3
    assert result['commercial']['spent'] == result['commercial']['bought'] == 0
    result1 = result['house1']['children']
    assert result1['fridge']['bought'] == 5 and result1['fridge']['spent'] == 6
    assert result1['pv']['sold'] == 4 and result1['pv']['earned'] == 3
    assert 'children' not in result1


@pytest.fixture
def grid2():
    house1 = FakeArea('house1')
    house2 = FakeArea('house2')
    return FakeArea(
        'street',
        children=[house1, house2],
        past_markets=[FakeMarket(
            (_trade(2, make_iaa_name(house1), 3, make_iaa_name(house2)),)
        )]
    )


def test_energy_bills_finds_iaas(grid2):
    result = energy_bills(grid2)
    assert result['house1']['bought'] == result['house2']['sold'] == 3
