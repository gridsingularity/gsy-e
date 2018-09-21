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

    def __init__(self, avg_power_W, hrs_per_day=None, hrs_of_day=None, random_factor=0,
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
        # Random factor to modify buying
        self.random_factor = random_factor
        # Budget for a single day in eur
        self.daily_budget = daily_budget * 100 if daily_budget is not None else None
        # Energy consumed during the day ideally should not exceed daily_energy_required
        self.energy_per_slot_Wh = None
        self.energy_requirement_Wh = 0
        # In ct. / kWh
        self.min_energy_rate = min_energy_rate
        # be a parameter on the constructor or if we want to deal in percentages
        if hrs_per_day is None:
            hrs_per_day = len(hrs_of_day)
        if hrs_of_day is None:
            hrs_of_day = list(range(24))

        self.hrs_of_day = hrs_of_day
        self.hrs_per_day = hrs_per_day

        if not all([0 <= h <= 23 for h in hrs_of_day]):
            raise ValueError("Hrs_of_day list should contain integers between 0 and 23.")

        if len(hrs_of_day) < hrs_per_day:
            raise ValueError("Length of list 'hrs_of_day' must be greater equal 'hrs_per_day'")

    def event_activate(self):
        self.energy_per_slot_Wh = (self.avg_power_W /
                                   (duration(hours=1)/self.area.config.slot_length))
        self.daily_energy_required = self.avg_power_W * self.hrs_per_day
        if self.daily_budget:
            self.max_acceptable_energy_price = (
                self.daily_budget / self.daily_energy_required * 1000
            )
        self._update_energy_requirement()

    def _find_acceptable_offer(self, market):
        offers = market.most_affordable_offers
        return random.choice(offers)

    def _one_sided_market_event_tick(self):
        markets = []
        for time, market in self.area.markets.items():
            if self._allowed_operating_hours(time.hour):
                markets.append(market)
        if not markets:
            return
        if self._allowed_operating_hours(self.area.now.hour):
            try:
                market = list(self.area.markets.values())[0]
                if len(market.sorted_offers) < 1:
                    return
                acceptable_offer = self._find_acceptable_offer(market)
                if acceptable_offer and \
                        self.min_energy_rate <= \
                        acceptable_offer.price / acceptable_offer.energy <= \
                        self.max_energy_rate[market.time_slot_str]:
                    max_energy = self.energy_requirement_Wh / 1000
                    if acceptable_offer.energy > max_energy:
                        self.accept_offer(market, acceptable_offer, energy=max_energy)
                        self.energy_requirement_Wh = 0
                        self.hrs_per_day -= self._operating_hours(max_energy)
                    else:
                        self.accept_offer(market, acceptable_offer)
                        self.energy_requirement_Wh -= acceptable_offer.energy * 1000
                        self.hrs_per_day -= self._operating_hours(acceptable_offer.energy)
            except MarketException:
                self.log.exception("An Error occurred while buying an offer")

    def _double_sided_market_event_tick(self):
        if ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 1:
            assert False and "Cannot call this method using a single sided market."

        if self.energy_requirement_Wh <= 0:
            return

        if self.are_bids_posted(self.area.next_market):
            self.update_posted_bids(self.area.next_market)

    def event_tick(self, *, area):
        if self.energy_requirement_Wh <= 0:
            return

        if ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 2:
            self._double_sided_market_event_tick()
        elif ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 1:
            self._one_sided_market_event_tick()

    def _allowed_operating_hours(self, time):
        return time in self.hrs_of_day and self.hrs_per_day > 0

    def _operating_hours(self, energy):
        return (((energy * 1000) / self.energy_per_slot_Wh)
                * (self.area.config.slot_length / duration(hours=1)))

    def _update_energy_requirement(self):
        self.energy_requirement_Wh = 0
        if self._allowed_operating_hours(self.area.now.hour):
            energy_per_slot = self.energy_per_slot_Wh
            if self.random_factor:
                energy_per_slot += energy_per_slot * random.random() * self.random_factor
            self.energy_requirement_Wh += energy_per_slot
        self.state.record_desired_energy(self.area, self.energy_requirement_Wh)

    def event_market_cycle(self):
        self._update_energy_requirement()
        self.update_market_cycle_bids()
        if ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 2:
            if self.energy_requirement_Wh > 0:
                self.post_first_bid(
                    self.area.next_market,
                    self.energy_requirement_Wh)

    def event_bid_deleted(self, *, market, bid):
        if market != self.area.next_market:
            return
        if bid.buyer != self.owner.name:
            return
        self.remove_bid_from_pending(bid.id, self.area.next_market)

    def event_bid_traded(self, *, market, bid_trade):
        if ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 1:
            # Do not handle bid trades on single sided markets
            assert False and "Invalid state, cannot receive a bid if single sided market" \
                             " is globally configured."

        if bid_trade.buyer != self.owner.name:
            return

        buffered_bid = next(filter(
            lambda b: b.id == bid_trade.offer.id,
            self.get_posted_bids(market)
        ))

        if bid_trade.offer.buyer == buffered_bid.buyer:
            # Update energy requirement and clean up the pending bid buffer
            self.energy_requirement_Wh -= bid_trade.offer.energy * 1000.0
            self.hrs_per_day -= self._operating_hours(bid_trade.offer.energy)
            if not bid_trade.residual or self.energy_requirement_Wh < 0.00001:
                self.remove_bid_from_pending(bid_trade.offer.id, market)
            assert self.energy_requirement_Wh >= -0.00001


class CellTowerLoadHoursStrategy(LoadHoursStrategy):
    pass
