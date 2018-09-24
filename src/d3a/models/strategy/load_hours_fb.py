import random
from pendulum import duration
from typing import Union

from d3a.exceptions import MarketException
from d3a.models.state import LoadState
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.update_frequency import BidUpdateFrequencyMixin
from d3a.models.strategy.mixins import ReadProfileMixin
from d3a.models.strategy.mixins import InputProfileTypes


class LoadHoursStrategy(BaseStrategy, BidUpdateFrequencyMixin):
    parameters = ('avg_power_W', 'hrs_per_day', 'hrs_of_day', 'max_energy_rate')

    def __init__(self, avg_power_W, hrs_per_day=None, hrs_of_day=None,
                 daily_budget=None, min_energy_rate=ConstSettings.LOAD_MIN_ENERGY_RATE,
                 max_energy_rate: Union[float, dict, str]=ConstSettings.LOAD_MAX_ENERGY_RATE):
        BaseStrategy.__init__(self)
        self.max_energy_rate = ReadProfileMixin.read_arbitrary_profile(InputProfileTypes.RATE,
                                                                       max_energy_rate)
        BidUpdateFrequencyMixin.__init__(self,
                                         initial_rate=min_energy_rate,
                                         final_rate=list(self.max_energy_rate.values())[0])
        self.state = LoadState()
        self.avg_power_W = avg_power_W

        # consolidated_cycle is KWh energy consumed for the entire year
        self.daily_energy_required = None
        # Budget for a single day in eur
        self.daily_budget = daily_budget * 100 if daily_budget is not None else None
        # Energy consumed during the day ideally should not exceed daily_energy_required
        self.energy_per_slot_Wh = None
        self.energy_requirement_Wh = {}  # type: Dict[Time, float]
        # In ct. / kWh
        self.min_energy_rate = min_energy_rate
        # be a parameter on the constructor or if we want to deal in percentages
        if hrs_per_day is None:
            hrs_per_day = len(hrs_of_day)
        if hrs_of_day is None:
            hrs_of_day = list(range(24))

        self.hrs_of_day = hrs_of_day
        self.hrs_per_day = hrs_per_day
        self.active_markets = []

        if not all([0 <= h <= 23 for h in hrs_of_day]):
            raise ValueError("Hrs_of_day list should contain integers between 0 and 23.")

        if len(hrs_of_day) < hrs_per_day:
            raise ValueError("Length of list 'hrs_of_day' must be greater equal 'hrs_per_day'")

    def _get_active_markets(self):
        markets = []
        for time, market in self.area.markets.items():
            if self._allowed_operating_hours(time.hour):
                markets.append(market)
        self.active_markets = markets

    def event_activate(self):
        self._get_active_markets()
        self.energy_per_slot_Wh = (self.avg_power_W /
                                   (duration(hours=1)/self.area.config.slot_length))

        for slot_time in [
                    self.area.now + (self.area.config.slot_length * i)
                    for i in range(
                        (
                                    self.area.config.duration
                                    + (
                                            self.area.config.market_count *
                                            self.area.config.slot_length)
                        ) // self.area.config.slot_length)
                    ]:
            if self._allowed_operating_hours(slot_time.hour):
                self.energy_requirement_Wh[slot_time] = self.energy_per_slot_Wh
                self.state.desired_energy_Wh[slot_time] = self.energy_per_slot_Wh

    def _find_acceptable_offer(self, market):
        offers = market.most_affordable_offers
        return random.choice(offers)

    def _one_sided_market_event_tick(self, market):
        try:
            if len(market.sorted_offers) < 1:
                return
            acceptable_offer = self._find_acceptable_offer(market)
            if acceptable_offer and \
                    self.min_energy_rate <= \
                    acceptable_offer.price / acceptable_offer.energy <= \
                    self.max_energy_rate[market.time_slot_str]:
                max_energy = self.energy_requirement_Wh[market.time_slot] / 1000
                if acceptable_offer.energy > max_energy:
                    self.accept_offer(market, acceptable_offer, energy=max_energy)
                    self.energy_requirement_Wh[market.time_slot] = 0
                    self.hrs_per_day -= self._operating_hours(max_energy)
                else:
                    self.accept_offer(market, acceptable_offer)
                    self.energy_requirement_Wh[market.time_slot] -= acceptable_offer.energy * 1000
                    self.hrs_per_day -= self._operating_hours(acceptable_offer.energy)

        except MarketException:
            self.log.exception("An Error occurred while buying an offer")

    def _double_sided_market_event_tick(self, market):
        if self.are_bids_posted(market):
            self.update_posted_bids(market)

    def event_tick(self, *, area):
        if ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 1:
            for market in self.active_markets:
                if market.time_slot not in self.energy_requirement_Wh:
                    continue
                if self.energy_requirement_Wh[market.time_slot] <= 0:
                    continue
                self._one_sided_market_event_tick(market)

        elif ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 2:
            # TODO: Evaluate, whether the bid price should be in creased on future markets as well,
            # TODO: if so, please move the following command into the loop above
            self._double_sided_market_event_tick(self.area.next_market)

    def _allowed_operating_hours(self, time):
        return time in self.hrs_of_day and self.hrs_per_day > 0

    def _operating_hours(self, energy):
        return (((energy * 1000) / self.energy_per_slot_Wh)
                * (self.area.config.slot_length / duration(hours=1)))

    def event_market_cycle(self):
        self._get_active_markets()
        for market in self.active_markets:
            if ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 2:
                self.update_market_cycle_bids()
                if self.energy_requirement_Wh[market.time_slot] > 0:
                    poset_bid = self.post_first_bid(
                        market,
                        self.energy_requirement_Wh[market.time_slot])
                    self.energy_requirement_Wh[market.time_slot] -= poset_bid.energy * 1000

    def event_bid_deleted(self, *, market, bid):
        if market != self.area.next_market:
            return
        if bid.buyer != self.owner.name:
            return
        self.remove_bid_from_pending(bid.id, market)
        # If the bid was not traded, add energy to self.energy_requirement_Wh again
        if bid.id not in [trades.offer.id for trades in market.trades]:
            self.energy_requirement_Wh[market.time_slot] += bid.energy * 1000

    def event_bid_traded(self, *, market, bid_trade):
        if bid_trade.buyer != self.owner.name:
            return

        buffered_bid = next(filter(
            lambda b: b.id == bid_trade.offer.id,
            self.get_posted_bids(market)
        ))

        if bid_trade.offer.buyer == buffered_bid.buyer:
            self.hrs_per_day -= self._operating_hours(bid_trade.offer.energy)
            if not bid_trade.residual or self.energy_requirement_Wh[market.time_slot] < 0.00001:
                self.remove_bid_from_pending(bid_trade.offer.id, market)
            assert self.energy_requirement_Wh[market.time_slot] >= -0.00001

            
class CellTowerLoadHoursStrategy(LoadHoursStrategy):
    pass
