import pytest

from d3a.models.market import Offer, Trade
from d3a.models.strategy.storage import StorageStrategy


class FakeArea():
    def __init__(self, count):
        self.appliance = None
        self.name = 'FakeArea'
        self.count = count
        self.past_market = FakeMarket(4)
        self.current_market = FakeMarket(0)

    @property
    def markets(self):
        return {"Fake Market": FakeMarket(self.count)}

    @property
    def cheapest_offers(self):
        offers = [
            [Offer('id', 12, 0.4, 'A', self)],
            [Offer('id', 12, 0.4, 'A', self)],
            [Offer('id', 20, 1, 'A', self)],
            [Offer('id', 20, 5.1, 'A', self)],
            [Offer('id', 20, 5.1, 'A', market=self.current_market)]
        ]
        return offers[self.count]

    @property
    def past_markets(self):
        return {"past market": self.past_market}


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.trade = Trade('id', 'time', Offer('id', 11.8, 0.5, 'FakeArea', self),
                           'FakeArea', 'buyer'
                           )
        self.created_offers = []
        self.offers = {'id': Offer('id', 11.8, 0.5, 'FakeArea', self),
                       'id2': Offer('id2', 20, 0.5, 'A', self),
                       'id3': Offer('id3', 20, 1, 'A', self),
                       'id4': Offer('id4', 19, 5.1, 'A', self)}

    @property
    def sorted_offers(self):
        offers = [
            [Offer('id', 11.8, 0.5, 'A', self)],
            [Offer('id2', 20, 0.5, 'A', self)],
            [Offer('id3', 20, 1, 'A', self)],
            [Offer('id4', 19, 5.1, 'A', self)]
        ]
        return offers[self.count]

    def offer(self, price, energy, seller, market=None):
        offer = Offer('id', price, energy, seller, market)
        self.created_offers.append(offer)
        return offer


"""TEST1"""


# Test if storage buys cheap energy

@pytest.fixture()
def area_test1():
    return FakeArea(0)


@pytest.fixture()
def storage_strategy_test1(area_test1, called):
    s = StorageStrategy()
    s.owner = area_test1
    s.area = area_test1
    s.accept_offer = called
    return s


def test_if_storage_buys_cheap_energy(storage_strategy_test1, area_test1):
    storage_strategy_test1.event_tick(area=area_test1)
    assert storage_strategy_test1.accept_offer.calls[0][0][1] == repr(
        FakeMarket(0).sorted_offers[0])


"""TEST2"""


# Test if storage doesn't buy energy for more than 30ct

@pytest.fixture()
def area_test2():
    return FakeArea(1)


@pytest.fixture()
def storage_strategy_test2(area_test2, called):
    s = StorageStrategy()
    s.owner = area_test2
    s.area = area_test2
    s.accept_offer = called
    return s


def test_if_storage_doesnt_buy_30ct(storage_strategy_test2, area_test2):
    storage_strategy_test2.event_tick(area=area_test2)
    assert len(storage_strategy_test2.accept_offer.calls) == 0


"""TEST3"""


# Test if storage doesn't buy for over avg price

@pytest.fixture()
def area_test3():
    return FakeArea(2)


@pytest.fixture()
def storage_strategy_test3(area_test3, called):
    s = StorageStrategy()
    s.owner = area_test3
    s.area = area_test3
    s.accept_offer = called
    return s


def test_if_storage_doesnt_buy_too_expensive(storage_strategy_test3, area_test3):
    storage_strategy_test3.event_tick(area=area_test3)
    assert len(storage_strategy_test3.accept_offer.calls) == 0


"""TEST4"""


# Test if storage pays respect to its capacity


@pytest.fixture()
def area_test4():
    return FakeArea(3)


@pytest.fixture()
def storage_strategy_test4(area_test4, called):
    s = StorageStrategy()
    s.owner = area_test4
    s.area = area_test4
    s.accept_offer = called
    return s


def test_if_storage_pays_respect_to_capacity_limits(storage_strategy_test4, area_test4):
    storage_strategy_test4.event_tick(area=area_test4)
    assert len(storage_strategy_test4.accept_offer.calls) == 0


"""TEST5"""


# Test if internal storage is handled correctly

@pytest.fixture()
def area_test5():
    return FakeArea(4)


@pytest.fixture()
def storage_strategy_test5(area_test5, called):
    s = StorageStrategy()
    s.owner = area_test5
    s.area = area_test5
    s.sell_energy = called
    area_test5.past_market.offers = {
        'id': Offer('id', 20, 1, 'A', market=area_test5.past_market),
        'id2': Offer('id2', 20, 2.9, 'FakeArea', market=area_test5.past_market),
        'id3': Offer('id3', 100, 1, 'FakeArea', market=area_test5.past_market)
    }
    s.offers.bought_offer(area_test5.past_market.offers['id'], area_test5.past_market)
    s.offers.post(area_test5.past_market.offers['id3'], area_test5.past_market)
    s.offers.post(area_test5.past_market.offers['id2'], area_test5.past_market)
    s.offers.sold_offer('id2', area_test5.past_market)
    return s


def test_if_storage_handles_capacity_correctly(storage_strategy_test5, area_test5):
    storage_strategy_test5.event_market_cycle()
    assert storage_strategy_test5.blocked_storage == -1
    assert storage_strategy_test5.used_storage == 1
    assert storage_strategy_test5.sell_energy.calls[0][1] == {'buying_price': '20.0',
                                                              'energy': '1'}
    assert storage_strategy_test5.offered_storage == -2.9
    assert len(storage_strategy_test5.offers.open_in_market(area_test5.past_market)) == 0
    assert storage_strategy_test5.sell_energy.calls[1][0] == ('94.2951438000943', '1')


"""TEST6"""


# Test if trades are handled correctly

@pytest.fixture()
def area_test6():
    return FakeArea(0)


@pytest.fixture
def market_test6():
    return FakeMarket(0)


@pytest.fixture()
def storage_strategy_test6(area_test6, market_test6, called):
    s = StorageStrategy()
    s.owner = area_test6
    s.area = area_test6
    s.accept_offer = called
    s.offers.post(market_test6.trade.offer, market_test6)
    return s


def test_if_trades_are_handled_correctly(storage_strategy_test6, market_test6):
    storage_strategy_test6.event_trade(market=market_test6, trade=market_test6.trade)
    assert market_test6.trade.offer in \
        storage_strategy_test6.offers.sold_in_market(market_test6)
    assert market_test6.trade.offer not in storage_strategy_test6.offers.open


"""TEST7"""


# Testing the sell energy function
@pytest.fixture()
def area_test7():
    return FakeArea(4)


@pytest.fixture()
def storage_strategy_test7(area_test7):
    s = StorageStrategy()
    s.owner = area_test7
    s.area = area_test7
    s.used_storage = 0
    return s


def test_sell_energy_function(storage_strategy_test7, area_test7: FakeArea):
    energy = 1.3
    storage_strategy_test7.sell_energy(buying_price=10, energy=energy)
    assert storage_strategy_test7.used_storage == -1.3
    assert storage_strategy_test7.offered_storage == 1.3
    assert area_test7.current_market.created_offers[0].energy == 1.3
    assert len(storage_strategy_test7.offers.posted_in_market(area_test7.current_market)) > 0


"""TEST8"""


# Testing the sell energy function
@pytest.fixture()
def area_test8():
    return FakeArea(4)


@pytest.fixture()
def storage_strategy_test8(area_test8):
    s = StorageStrategy()
    s.owner = area_test8
    s.area = area_test8
    s.used_storage = 100
    return s


def test_sell_energy_function_with_stored_capacity(storage_strategy_test8, area_test8: FakeArea):
    storage_strategy_test8.sell_energy(buying_price=10, energy=None)
    assert storage_strategy_test8.used_storage == 0
    assert storage_strategy_test8.offered_storage == 100
    assert area_test8.current_market.created_offers[0].energy == 100
    assert len(storage_strategy_test8.offers.posted_in_market(area_test8.current_market)) > 0
