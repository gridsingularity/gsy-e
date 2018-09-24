import pytest
import logging
from pendulum import Duration
from pendulum import DateTime
from logging import getLogger
from math import isclose

# from d3a.models.area import DEFAULT_CONFIG
from d3a.models.strategy import ureg, Q_
from d3a.models.market import Offer, Trade
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.const import ConstSettings
from d3a.models.config import SimulationConfig
from d3a import TIME_FORMAT


class FakeArea():
    def __init__(self, count):
        self.appliance = None
        self.name = 'FakeArea'
        self.count = count
        self.current_tick = 0
        self.past_market = FakeMarket(4)
        self.current_market = FakeMarket(0)
        self._markets_return = {"Fake Market": FakeMarket(self.count)}
        self.next_market = list(self.markets.values())[0]

    log = getLogger(__name__)

    @property
    def markets(self):
        return self._markets_return

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
    def market_with_most_expensive_offer(self):
        return self.current_market

    @property
    def past_markets(self):
        return {"past market": self.past_market}

    @property
    def now(self):
        return DateTime.now().start_of('day') + (
            self.config.tick_length * self.current_tick
        )

    @property
    def historical_avg_rate(self):
        return 30

    @property
    def config(self):
        return SimulationConfig(
                duration=Duration(hours=24),
                market_count=4,
                slot_length=Duration(minutes=15),
                tick_length=Duration(seconds=15),
                cloud_coverage=ConstSettings.DEFAULT_PV_POWER_PROFILE,
                market_maker_rate=ConstSettings.DEFAULT_MARKET_MAKER_RATE,
                iaa_fee=ConstSettings.INTER_AREA_AGENT_FEE_PERCENTAGE
                )


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

    @property
    def time_slot(self):
        return DateTime.now().start_of('day')

    @property
    def time_slot_str(self):
        return self.time_slot.strftime(TIME_FORMAT)

    def delete_offer(self, offer_id):
        return

    def offer(self, price, energy, seller, market=None):
        offer = Offer('id', price, energy, seller, market)
        self.created_offers.append(offer)
        return offer

    def bid(self, price, energy, buyer, seller):
        pass


"""TEST1"""


# Test if storage buys cheap energy

@pytest.fixture()
def area_test1():
    return FakeArea(0)


@pytest.fixture()
def storage_strategy_test1(area_test1, called):
    s = StorageStrategy(max_abs_battery_power=2.01)
    s.owner = area_test1
    s.area = area_test1
    s.accept_offer = called
    return s


def test_if_storage_buys_cheap_energy(storage_strategy_test1, area_test1):
    storage_strategy_test1.event_activate()
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
    s = StorageStrategy(max_abs_battery_power=2.01)
    s.owner = area_test2
    s.area = area_test2
    s.accept_offer = called
    return s


def test_if_storage_doesnt_buy_30ct(storage_strategy_test2, area_test2):
    storage_strategy_test2.event_activate()
    storage_strategy_test2.event_tick(area=area_test2)
    assert len(storage_strategy_test2.accept_offer.calls) == 0


def test_if_storage_doesnt_buy_above_break_even_point(storage_strategy_test2, area_test2):
    storage_strategy_test2.event_activate()
    storage_strategy_test2.break_even_buy = Q_(10.0, (ureg.EUR_cents / ureg.kWh))
    area_test2.current_market.offers = {'id': Offer('id', 10.1, 1,
                                                    'FakeArea',
                                                    area_test2.current_market)}
    storage_strategy_test2.event_tick(area=area_test2)
    assert len(storage_strategy_test2.accept_offer.calls) == 0
    area_test2.current_market.offers = {'id': Offer('id', 9.9, 1,
                                                    'FakeArea',
                                                    area_test2.current_market)}
    storage_strategy_test2.event_tick(area=area_test2)
    assert len(storage_strategy_test2.accept_offer.calls) == 0


"""TEST3"""


# Test if storage doesn't buy for over avg price

@pytest.fixture()
def area_test3():
    return FakeArea(2)


@pytest.fixture()
def storage_strategy_test3(area_test3, called):
    s = StorageStrategy(max_abs_battery_power=2.01)
    s.owner = area_test3
    s.area = area_test3
    s.accept_offer = called
    return s


def test_if_storage_doesnt_buy_too_expensive(storage_strategy_test3, area_test3):
    storage_strategy_test3.break_even = {"00:00": (20, 25)}
    storage_strategy_test3.event_activate()
    storage_strategy_test3.event_tick(area=area_test3)
    assert len(storage_strategy_test3.accept_offer.calls) == 0


@pytest.fixture()
def storage_strategy_test_buy_energy(area_test3, called):
    s = StorageStrategy(max_abs_battery_power=20.01)
    s.owner = area_test3
    s.area = area_test3
    s.accept_offer = called
    return s


def test_if_storage_buys_below_break_even(storage_strategy_test_buy_energy, area_test3):
    storage_strategy_test_buy_energy.event_activate()
    storage_strategy_test_buy_energy.buy_energy()

    assert len(storage_strategy_test_buy_energy.accept_offer.calls) == 1


"""TEST4"""


# Test if storage pays respect to its capacity


@pytest.fixture()
def area_test4():
    return FakeArea(3)


@pytest.fixture()
def storage_strategy_test4(area_test4, called):
    s = StorageStrategy(initial_capacity=2.1,
                        initial_rate_option=2,
                        battery_capacity=2.1)
    s.owner = area_test4
    s.area = area_test4
    s.accept_offer = called
    return s


def test_if_storage_pays_respect_to_capacity_limits(storage_strategy_test4, area_test4):
    storage_strategy_test4.event_activate()
    storage_strategy_test4.event_tick(area=area_test4)
    assert len(storage_strategy_test4.accept_offer.calls) == 0


def test_if_storage_max_sell_rate_is_one_unit_less_than_market_maker_rate(storage_strategy_test4,
                                                                          area_test4):
    storage_strategy_test4.event_activate()
    assert storage_strategy_test4._max_selling_rate(area_test4.current_market) \
        == (area_test4.config.market_maker_rate[area_test4.current_market.time_slot_str])


"""TEST5"""


# Test if internal storage is handled correctly

@pytest.fixture()
def area_test5():
    return FakeArea(4)


@pytest.fixture()
def storage_strategy_test5(area_test5, called):
    s = StorageStrategy(initial_capacity=5, battery_capacity=5.01)
    s.owner = area_test5
    s.area = area_test5
    s.sell_energy = called
    area_test5.past_market.offers = {
        'id': Offer('id', 20, 1, 'A', market=area_test5.past_market),
        'id2': Offer('id2', 20, 3, 'FakeArea', market=area_test5.past_market),
        'id3': Offer('id3', 100, 1, 'FakeArea', market=area_test5.past_market)
    }
    s.offers.bought_offer(area_test5.past_market.offers['id'], area_test5.past_market)
    s.offers.post(area_test5.past_market.offers['id3'], area_test5.past_market)
    s.offers.post(area_test5.past_market.offers['id2'], area_test5.past_market)
    s.offers.sold_offer('id2', area_test5.past_market)
    s.state.block_storage(1)
    s.state.offer_storage(5)
    return s


def test_if_storage_handles_capacity_correctly(storage_strategy_test5, area_test5):
    storage_strategy_test5.event_activate()
    storage_strategy_test5.event_market_cycle()
    assert storage_strategy_test5.state.blocked_storage == 0
    assert storage_strategy_test5.state.used_storage == 1
    assert storage_strategy_test5.sell_energy.calls[0][1] == {'energy': '1'}
    assert storage_strategy_test5.state.offered_storage == 2
    assert len(storage_strategy_test5.offers.open_in_market(area_test5.past_market)) == 0
    assert storage_strategy_test5.sell_energy.calls[1][0] == ('1', )


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
    s = StorageStrategy(initial_capacity=3.0, battery_capacity=3.01, max_abs_battery_power=5.21,
                        initial_rate_option=2, break_even=(31, 32))
    s.owner = area_test7
    s.area = area_test7
    return s


def test_sell_energy_function(storage_strategy_test7, area_test7: FakeArea):
    storage_strategy_test7.event_activate()
    energy = 1.3
    storage_strategy_test7.state.traded_energy_per_slot(area_test7.now)
    storage_strategy_test7.sell_energy(energy=energy)
    assert storage_strategy_test7.state.used_storage == 1.7
    assert storage_strategy_test7.state.offered_storage == 1.3
    assert area_test7._markets_return["Fake Market"].created_offers[0].energy == 1.3
    assert len(storage_strategy_test7.offers.posted_in_market(
        area_test7._markets_return["Fake Market"])
    ) > 0
    assert storage_strategy_test7.state.traded_energy_per_slot(
        area_test7.current_market.time_slot
    ) == energy


def test_calculate_initial_sell_energy_rate_lower_bound(storage_strategy_test7):
    storage_strategy_test7.event_activate()
    market = storage_strategy_test7.area.current_market
    break_even_sell = storage_strategy_test7.break_even[market.time_slot_str][1]
    assert storage_strategy_test7.calculate_selling_rate(market) == break_even_sell


@pytest.fixture()
def storage_strategy_test7_1(area_test7):
    s = StorageStrategy(initial_capacity=3.0, battery_capacity=3.01, max_abs_battery_power=5.21,
                        initial_rate_option=2, break_even=(26, 27))
    s.owner = area_test7
    s.area = area_test7
    return s


def test_calculate_initial_sell_energy_rate_upper_bound(storage_strategy_test7_1):
    storage_strategy_test7_1.event_activate()
    market = storage_strategy_test7_1.area.current_market
    market_maker_rate = \
        storage_strategy_test7_1.area.config.market_maker_rate[market.time_slot_str]
    assert storage_strategy_test7_1.calculate_selling_rate(market) == market_maker_rate


@pytest.fixture()
def storage_strategy_test7_2(area_test7):
    s = StorageStrategy(initial_capacity=3.0, battery_capacity=3.01, max_abs_battery_power=5.21,
                        initial_rate_option=1, break_even=(16, 17))
    s.owner = area_test7
    s.area = area_test7
    s.offers.posted = {Offer('id', 30, 1, 'FakeArea',
                             market=area_test7.current_market): area_test7.current_market}
    return s


@pytest.mark.parametrize("risk", [10.0, 25.0, 95.0])
def test_calculate_risk_factor(storage_strategy_test7_2, area_test7, risk):
    storage_strategy_test7_2.risk = risk
    storage_strategy_test7_2.event_activate()
    old_offer = list(storage_strategy_test7_2.offers.posted.keys())[0]
    storage_strategy_test7_2._decrease_offer_price(
        area_test7.current_market,
        storage_strategy_test7_2._calculate_price_decrease_rate(area_test7.current_market))
    new_offer = list(storage_strategy_test7_2.offers.posted.keys())[0]
    price_dec_per_slot = (area_test7.historical_avg_rate) * (1 - storage_strategy_test7_2.risk /
                                                             ConstSettings.MAX_RISK)
    price_updates_per_slot = int(area_test7.config.slot_length.seconds
                                 / storage_strategy_test7_2._decrease_price_every_nr_s.m)
    price_dec_per_update = price_dec_per_slot / price_updates_per_slot
    assert new_offer.price == old_offer.price - (old_offer.energy * price_dec_per_update)


def test_calculate_energy_amount_to_sell_respects_max_power(storage_strategy_test7, area_test7):
    storage_strategy_test7.event_activate()
    max_energy = storage_strategy_test7.state._battery_energy_per_slot
    expected_energy = storage_strategy_test7.calculate_energy_to_sell((max_energy + 1),
                                                                      area_test7.current_market)
    assert expected_energy == max_energy


@pytest.fixture()
def storage_strategy_test7_3(area_test7):
    s = StorageStrategy(initial_capacity=1.0, battery_capacity=5.01, max_abs_battery_power=5.21,
                        initial_rate_option=1, break_even=(16, 17))
    s.owner = area_test7
    s.area = area_test7
    s.offers.posted = {Offer('id', 30, 1, 'FakeArea',
                             market=area_test7.current_market): area_test7.current_market}
    return s


def test_calculate_energy_amount_to_sell_respects_min_allowed_soc(storage_strategy_test7_3,
                                                                  area_test7):
    storage_strategy_test7_3.event_activate()
    energy = \
        storage_strategy_test7_3.calculate_energy_to_sell(energy=0.6,
                                                          target_market=area_test7.current_market)
    target_energy = \
        storage_strategy_test7_3.state.used_storage + \
        storage_strategy_test7_3.state.offered_storage -\
        storage_strategy_test7_3.state.capacity * ConstSettings.STORAGE_MIN_ALLOWED_SOC
    assert energy == target_energy


def test_clamp_energy_to_buy(storage_strategy_test7_3):
    storage_strategy_test7_3.event_activate()
    storage_strategy_test7_3.state._battery_energy_per_slot = 0.5
    assert storage_strategy_test7_3.state.clamp_energy_to_buy_kWh() == 0.5

    # Reduce used storage below battery_energy_per_slot
    storage_strategy_test7_3.state._used_storage = 4.6
    assert isclose(storage_strategy_test7_3.state.free_storage, 0.41)
    assert isclose(storage_strategy_test7_3.state.clamp_energy_to_buy_kWh(), 0.41)


"""TEST8"""


# Testing the sell energy function
@pytest.fixture()
def area_test8():
    return FakeArea(4)


@pytest.fixture()
def storage_strategy_test8(area_test8):
    s = StorageStrategy(initial_capacity=100, battery_capacity=101, max_abs_battery_power=401)
    s.owner = area_test8
    s.area = area_test8
    return s


def test_sell_energy_function_with_stored_capacity(storage_strategy_test8, area_test8: FakeArea):
    storage_strategy_test8.event_activate()
    storage_strategy_test8.sell_energy(energy=None)
    assert abs(storage_strategy_test8.state.used_storage -
               storage_strategy_test8.state.capacity *
               ConstSettings.STORAGE_MIN_ALLOWED_SOC) < 0.0001
    assert storage_strategy_test8.state.offered_storage == \
        100 - storage_strategy_test8.state.capacity * ConstSettings.STORAGE_MIN_ALLOWED_SOC
    assert area_test8._markets_return["Fake Market"].created_offers[0].energy == \
        100 - storage_strategy_test8.state.capacity * ConstSettings.STORAGE_MIN_ALLOWED_SOC
    assert len(storage_strategy_test8.offers.posted_in_market(
        area_test8._markets_return["Fake Market"])
    ) > 0


"""TEST9"""


# Test if initial capacity is sold
def test_first_market_cycle_with_initial_capacity(storage_strategy_test8: StorageStrategy,
                                                  area_test8: FakeArea):
    storage_strategy_test8.event_activate()
    storage_strategy_test8.event_market_cycle()
    assert storage_strategy_test8.state.offered_storage == \
        100.0 - storage_strategy_test8.state.capacity * ConstSettings.STORAGE_MIN_ALLOWED_SOC
    assert len(storage_strategy_test8.offers.posted_in_market(
        area_test8._markets_return["Fake Market"])
    ) > 0


"""TEST10"""


# Handling of initial_charge parameter
def test_initial_charge(caplog):
    with caplog.at_level(logging.WARNING):
        storage = StorageStrategy(initial_capacity=1, initial_soc=60)
    assert any('initial_capacity' in record.msg for record in caplog.records)
    assert storage.state.used_storage == 0.6 * storage.state.capacity


def test_storage_constructor_rejects_incorrect_parameters():
    with pytest.raises(ValueError):
        StorageStrategy(risk=101)
    with pytest.raises(ValueError):
        StorageStrategy(risk=-1)
    with pytest.raises(ValueError):
        StorageStrategy(battery_capacity=-1)
    with pytest.raises(ValueError):
        StorageStrategy(battery_capacity=100, initial_capacity=101)
    with pytest.raises(ValueError):
        StorageStrategy(initial_soc=101)
    with pytest.raises(ValueError):
        StorageStrategy(initial_soc=-1)
    with pytest.raises(ValueError):
        StorageStrategy(break_even=(1, .99))
    with pytest.raises(ValueError):
        StorageStrategy(break_even=(-1, 2))
    with pytest.raises(ValueError):
        StorageStrategy(break_even="asdsadsad")
    with pytest.raises(ValueError):
        StorageStrategy(break_even={0: (1, .99), 12: (.99, 1)})
    with pytest.raises(ValueError):
        StorageStrategy(break_even={0: (-1, 2), 12: (.99, 1)})


def test_free_storage_calculation_takes_into_account_storage_capacity(storage_strategy_test1):
    for capacity in [50.0, 100.0, 1000.0]:
        storage_strategy_test1.state._used_storage = 12.0
        storage_strategy_test1.state._blocked_storage = 13.0
        storage_strategy_test1.state._offered_storage = 14.0
        storage_strategy_test1.state.capacity = capacity

        assert storage_strategy_test1.state.free_storage == \
            storage_strategy_test1.state.capacity \
            - storage_strategy_test1.state._used_storage \
            - storage_strategy_test1.state._offered_storage \
            - storage_strategy_test1.state._blocked_storage


"""TEST11"""


@pytest.fixture()
def area_test11():
    return FakeArea(0)


@pytest.fixture()
def storage_strategy_test11(area_test11, called):
    s = StorageStrategy(battery_capacity=100, initial_capacity=50, max_abs_battery_power=25)
    s.owner = area_test11
    s.area = area_test11
    s.accept_offer = called
    return s


def test_storage_buys_partial_offer_and_respecting_battery_power(storage_strategy_test11,
                                                                 area_test11):
    storage_strategy_test11.event_activate()
    storage_strategy_test11.buy_energy()
    te = storage_strategy_test11.state.traded_energy_per_slot(area_test11.current_market.time_slot)
    assert te == -float(storage_strategy_test11.accept_offer.calls[0][1]['energy'])
    assert len(storage_strategy_test11.accept_offer.calls) >= 1


def test_storage_populates_break_even_profile_correctly():
    from d3a.models.strategy.read_user_profile import default_profile_dict
    s = StorageStrategy(break_even=(22, 23))
    assert all([be[0] == 22 and be[1] == 23 for _, be in s.break_even.items()])
    assert set(s.break_even.keys()) == set(default_profile_dict().keys())

    s = StorageStrategy(break_even={0: (22, 23), 10: (24, 25), 20: (27, 28)})
    assert set(s.break_even.keys()) == set(default_profile_dict().keys())
    assert all([s.break_even[f"{i:02}:00"] == (22, 23) for i in range(10)])
    assert all([s.break_even[f"{i:02}:00"] == (24, 25) for i in range(10, 20)])
    assert all([s.break_even[f"{i:02}:00"] == (27, 28) for i in range(20, 24)])


"""TEST12"""


@pytest.fixture()
def area_test12():
    return FakeArea(0)


@pytest.fixture
def market_test7():
    return FakeMarket(0)


@pytest.fixture()
def storage_strategy_test12(area_test12):
    s = StorageStrategy(battery_capacity=5, initial_capacity=2.5,
                        max_abs_battery_power=5,
                        break_even=(16.99, 17.01),
                        cap_price_strategy=True)
    s.owner = area_test12
    s.area = area_test12
    return s


def test_storage_capacity_dependant_sell_rate(storage_strategy_test12, market_test7):
    storage_strategy_test12.event_activate()
    market_maker_rate = list(storage_strategy_test12.area.config.market_maker_rate.values())[0]
    BE_sell = list(storage_strategy_test12.break_even.values())[0][1]
    used_storage = storage_strategy_test12.state.used_storage
    battery_capacity = storage_strategy_test12.state.capacity
    soc = used_storage / battery_capacity
    actual_rate = storage_strategy_test12.calculate_selling_rate(market_test7)
    expected_rate = market_maker_rate - (market_maker_rate - BE_sell) * soc
    assert actual_rate == expected_rate


"""TEST13"""


@pytest.fixture()
def area_test13():
    return FakeArea(0)


@pytest.fixture
def market_test13():
    return FakeMarket(0)


@pytest.fixture()
def storage_strategy_test13(area_test13, called):
    s = StorageStrategy(battery_capacity=5, initial_capacity=2.5,
                        max_abs_battery_power=5, break_even=(34, 35.1))
    s.owner = area_test13
    s.area = area_test13
    s.accept_offer = called
    return s


def test_storage_only_buys_and_sells_in_the_power_limit(storage_strategy_test13, market_test13):
    ConstSettings.MAX_OFFER_TRAVERSAL_LENGTH = 4
    storage_strategy_test13.event_activate()
    storage_strategy_test13.sell_energy(energy=5)
    traded_energy = storage_strategy_test13.state._traded_energy_per_slot[market_test13.time_slot]
    storage_strategy_test13.sell_energy(energy=5)
    assert storage_strategy_test13.state._traded_energy_per_slot[market_test13.time_slot] == \
        traded_energy
    storage_strategy_test13.buy_energy()
    bought_energy = market_test13.sorted_offers[0].energy
    assert storage_strategy_test13.state._traded_energy_per_slot[market_test13.time_slot] == \
        traded_energy - bought_energy
