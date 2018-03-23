import pytest

from d3a.models.market import Trade
from d3a.stats import bills, primary_unit_prices, recursive_current_markets, total_avg_trade_price


class FakeArea:
    def __init__(self, name, children=None, markets=None):
        self.name = name
        self.children = children
        self.markets = markets

    @property
    def current_market(self):
        return 'market %s' % self.name if self.children else None

    @property
    def slug(self):
        return self.name


class FakeMarket:
    def __init__(self, trades):
        self.trades = trades


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
                 markets=[FakeMarket((_trade(2, 'fridge', 2, 'pv'),
                                      _trade(3, 'fridge', 1, 'iaa'))),
                          FakeMarket((_trade(1, 'fridge', 2, 'pv'),))]),
        FakeArea('house2',
                 children=[FakeArea('e-car')],
                 markets=[FakeMarket((_trade(1, 'e-car', 4, 'iaa'),
                                      _trade(1, 'e-car', 8, 'iaa'),
                                      _trade(3, 'iaa', 5, 'e-car'))),
                          FakeMarket((_trade(1, 'e-car', 1, 'iaa'),))]),
        FakeArea('commercial')
    ], markets=[
        FakeMarket((_trade(2, 'house2', 12, 'commercial'),)),
        FakeMarket((_trade(1, 'house2', 1, 'commercial'),))
    ])


def test_bills(grid):
    result = bills(grid)
    assert result['house2']['bought'] == result['commercial']['sold'] == 13
    assert result['house2']['spent'] == result['commercial']['earned'] == 3
    assert result['commercial']['spent'] == result['commercial']['bought'] == 0
    result1 = result['house1']['children']
    assert result1['fridge']['bought'] == 5 and result1['fridge']['spent'] == 6
    assert result1['pv']['sold'] == 4 and result1['pv']['earned'] == 3
    assert 'children' not in result1
