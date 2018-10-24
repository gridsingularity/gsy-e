import pytest

from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market import Offer, Trade
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.greedy_night_storage import NightStorageStrategy


class FakeArea():
    def __init__(self, count):
        self.appliance = None
        self.name = 'FakeArea'
        self.count = count
        self.past_market = FakeMarket(4)
        self.current_market = FakeMarket(0)

    def get_future_market_from_id(self, id):
        return self.current_market

    @property
    def markets(self):
        return {"Fake Market": FakeMarket(self.count)}

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def cheapest_offers(self):
        offers = [
            Offer('id', 30, 1, 'A', self.current_market),
            Offer('id', 10, 1, 'A', self.current_market),
            Offer('id', 20, 1, 'A', self.current_market)
        ]

        return offers

    @property
    def past_markets(self):
        return {"past market": self.past_market}


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.id = count
        self.trade = Trade('id', 'time', Offer('id', 11.8, 0.5, 'FakeArea', self),
                           'FakeArea', 'buyer'
                           )
        self.created_offers = []
        self.time_slot = 0

    @property
    def sorted_offers(self):
        offers = [
            Offer('id', 3, 0.2, 'A', self),  # Energyprice is 15
            Offer('id', 6, 0.4, 'A', self),  # Energyprice is 16
            Offer('id', 10, 0.6, 'A', self),  # Energyprice is 17
            # This offer should be ignored because the seller equals the buyer
            Offer('id', 0.2, 20, 'FakeArea', self),
            Offer('id', 13, 0.8, 'A', self)  # Energyprice is 18
        ]
        return offers

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
    n = NightStorageStrategy()
    n.owner = area_test1
    n.area = area_test1
    n.energy_buying_possible = called
    n.bought_offers = {area_test1.current_market: area_test1.cheapest_offers}
    n.sell_energy = called
    return n


def test_find_avg_cheapest_offers1(storage_strategy_test1, area_test1):
    storage_strategy_test1.event_tick(area=area_test1)
    assert storage_strategy_test1.energy_buying_possible.calls[0][0][0] == '20.0'


"""TEST2"""


# Test if market cycle is handled correctly

@pytest.fixture()
def area_test2():
    return FakeArea(0)


@pytest.fixture()
def storage_strategy_test2(area_test2, called):
    n = NightStorageStrategy()

    n.owner = area_test2

    n.area = area_test2

    n.sell_energy = called

    n.offers.bought_offer(Offer('id', 30, 1, 'A', market=area_test2.past_market),
                          area_test2.past_market)
    n.offers.bought_offer(Offer('id2', 10, 5, 'A', market=area_test2.past_market),
                          area_test2.past_market)
    n.offers.bought_offer(Offer('id3', 20, 20, 'A', market=area_test2.past_market),
                          area_test2.past_market)
    n.offers.bought_offer(Offer('dummy', 1, 1, 'A'), FakeMarket(0))

    n.offers.post(Offer('id4', 11, 4, 'FakeArea', market=area_test2.past_market),
                  area_test2.past_market)
    n.offers.post(Offer('id5', 12, 2, 'FakeArea', market=area_test2.past_market),
                  area_test2.past_market)
    n.offers.post(Offer('id6', 30, 3, 'FakeArea', market=area_test2.past_market),
                  area_test2.past_market)
    n.offers.post(Offer('id7', 10, 4, 'FakeArea', market=area_test2.past_market),
                  area_test2.past_market)
    n.offers.post(Offer('id8', 20, 8, 'FakeArea', market=area_test2.past_market),
                  area_test2.past_market)
    n.offers.post(Offer('dummy2', 1, 1, 'FakeArea'), FakeMarket(0))
    n.offers.post(Offer('dummy3', 1, 1, 'FakeArea'), FakeMarket(0))

    n.offers.sold_offer('id4', area_test2.past_market)
    n.offers.sold_offer('id5', area_test2.past_market)
    n.offers.sold_offer('dummy2', area_test2.past_market)

    return n


def test_event_market_cycle(storage_strategy_test2, area_test2, bought_energy=0,
                            sold_energy=0, offered_energy=0):
    # calculate the amount of energy bought in this market
    for b_offer in storage_strategy_test2.offers.bought_in_market(area_test2.past_market):
        bought_energy += b_offer.energy

    # calculate the amount of energy sold in this market
    for s_offer in storage_strategy_test2.offers.sold_in_market(area_test2.past_market):
        sold_energy += s_offer.energy

    # calculate the amount of energy offered (but not sold) in this market
    for o_offer in storage_strategy_test2.offers.open_in_market(area_test2.past_market):
        offered_energy += o_offer.energy

    # Total expected amount of new selling offers that should be created
    # Consists of all bought offers and all the not sold offers
    selling_offers = (len(storage_strategy_test2.offers.bought_in_market(area_test2.past_market))
                      + len(storage_strategy_test2.offers.open_in_market(area_test2.past_market)))

    # Call the market cycle function
    storage_strategy_test2.state.block_storage(bought_energy + sold_energy + offered_energy + 3)
    storage_strategy_test2.state.fill_blocked_storage(offered_energy + sold_energy)
    storage_strategy_test2.state.offer_storage(offered_energy + sold_energy)

    storage_strategy_test2.event_market_cycle()

    # Checking if storage variables are updated correctly
    assert storage_strategy_test2.state.used_storage == offered_energy + bought_energy
    assert storage_strategy_test2.state.blocked_storage == 3

    # Checking if every bought offer in this market will be sold
    assert len(storage_strategy_test2.sell_energy.calls) == selling_offers
    for i, offer in \
            enumerate(storage_strategy_test2.offers.bought_in_market(area_test2.past_market)):
        assert storage_strategy_test2.sell_energy.calls[i][0][0] == str(offer.price)
        assert storage_strategy_test2.sell_energy.calls[i][0][1] == str(offer.energy)

    # Checking if offered_storage variable is updated correctly
    assert storage_strategy_test2.state.offered_storage == 0

    # Checking if all not sold offers in the past market are offered again in another market
    for i, offer in \
            enumerate(storage_strategy_test2.offers.open_in_market(area_test2.past_market)):
        sell_energy_position_offset = \
            storage_strategy_test2.offers.bought_in_market(area_test2.past_market)
        assert (storage_strategy_test2.
                sell_energy.
                calls[len(sell_energy_position_offset) + i][0][1]
                ) == str(offer.energy)
        assert (storage_strategy_test2.
                sell_energy.
                calls[len(sell_energy_position_offset) + i][0][0]
                # The complex price calculation is needed to get initial buying price of the energy
                ) == str(((offer.price / 1.002) *
                          (1 /
                           (1.05 - (0.5 * (storage_strategy_test2.risk /
                                           ConstSettings.GeneralSettings.MAX_RISK))
                            )
                           )
                          ))


"""TEST3"""


# Test Event Trade

@pytest.fixture()
def area_test3():
    return FakeArea(0)


@pytest.fixture()
def storage_strategy_test3(area_test3, called):
    n = NightStorageStrategy()
    n.owner = area_test3
    n.area = area_test3
    n.sell_energy = called
    # Add Offer that will be traded in the next test to the offers_posted dict
    n.offers.post(area_test3.current_market.trade.offer, area_test3.current_market)
    return n


def test_event_trade(storage_strategy_test3, area_test3):
    storage_strategy_test3.event_trade(market_id=area_test3.current_market.id,
                                       trade=area_test3.current_market.trade
                                       )
    # Check if trade is added to sold_offers dict
    assert (area_test3.current_market.trade.offer in
            storage_strategy_test3.offers.sold_in_market(area_test3.current_market)
            )
    # Check if trade is deleted from offers_posted dict
    assert (area_test3.current_market.trade.offer not in
            storage_strategy_test3.offers.open_in_market(area_test3.current_market)
            )


"""TEST4"""


# Test if energy buy possible

@pytest.fixture()
def area_test4():
    return FakeArea(0)


@pytest.fixture()
def market_test4():
    return FakeMarket(4)


@pytest.fixture()
def storage_strategy_test4(area_test4, called):
    n = NightStorageStrategy()
    n.owner = area_test4
    n.area = area_test4
    n.accept_offer = called
    n.STORAGE_CAPACITY = 1000
    return n


def test_energy_buying_possible(storage_strategy_test4, area_test4, market_test4):
    # Checking if energy is bought for right price
    storage_strategy_test4.energy_buying_possible(max_buying_price=17)
    assert (storage_strategy_test4.accept_offer.calls[0][0][1] ==
            repr(market_test4.sorted_offers[0])
            )
    assert (storage_strategy_test4.accept_offer.calls[1][0][1] ==
            repr(market_test4.sorted_offers[1])
            )
    assert (storage_strategy_test4.accept_offer.calls[2][0][1] ==
            repr(market_test4.sorted_offers[2])
            )
    # Check if storage doesn't buy it's own offer
    assert (storage_strategy_test4.accept_offer.calls[3][0][1] ==
            repr(market_test4.sorted_offers[4])
            )
    with pytest.raises(IndexError):
        storage_strategy_test4.accept_offer.calls[4][0][1]

    # Checking if storage respects it's current load and doesn't buy more than it has capacity
    storage_strategy_test4.used_storage = (ConstSettings.StorageSettings.CAPACITY * 2) + 1
    assert not storage_strategy_test4.energy_buying_possible(max_buying_price=30)


"""TEST5"""


# Test if storage sells energy

@pytest.fixture()
def area_test5():
    return FakeArea(0)


@pytest.fixture()
def market_test5(area_test5, called):
    m = area_test5.current_market
    m.offer = called
    return m


@pytest.fixture()
def storage_strategy_test5(area_test5, called):
    n = NightStorageStrategy()
    n.owner = area_test5
    n.area = area_test5
    n.state.block_storage(1)
    n.state.fill_blocked_storage(1)
    return n


def test_sell_energy(storage_strategy_test5, area_test5, market_test5):
    storage_strategy_test5.sell_energy(buying_price=10, energy=1)
    assert market_test5.offer.calls[0][0][0] == repr(10 * 1.05 * (1.05 - (0.05 * 0.5)))
    assert market_test5.offer.calls[0][0][1] == repr(1)
    assert market_test5.offer.calls[0][0][2] == repr('FakeArea')

    storage_strategy_test5.state.block_storage(2.76)
    storage_strategy_test5.state.fill_blocked_storage(2.76)
    storage_strategy_test5.sell_energy(buying_price=20.2, energy=0)
    assert market_test5.offer.calls[1][0][0] == repr(20.2 * 1.05 * (1.05 - (0.05 * 0.5)) * 2.76)
    assert market_test5.offer.calls[1][0][1] == repr(2.76)
    assert market_test5.offer.calls[1][0][2] == repr('FakeArea')


"""TEST6"""


# Test if cheapest offer price can be found

@pytest.fixture()
def area_test6():
    return FakeArea(0)


@pytest.fixture()
def storage_strategy_test6(area_test6):
    n = NightStorageStrategy()
    n.owner = area_test6
    n.area = area_test6
    return n


def test_find_avg_cheapest_offers2(storage_strategy_test6, area_test6):
    price = storage_strategy_test6.find_avg_cheapest_offers()
    avg_price = (sum((offer.price / offer.energy) for offer in area_test6.cheapest_offers)
                 / max(len(area_test6.cheapest_offers), 1))
    assert price == avg_price
