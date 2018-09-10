from collections import defaultdict
from typing import Dict  # noqa

from pendulum import duration

from d3a.models.area import Area
from d3a.util import make_iaa_name


class BudgetKeeper:
    """
    Budget constraint for Area.

    Watch over an area's energy consumption and disable trading for
    selected child areas to keep it from overspending. The area's
    children can be assigned priorities to control which should and
    should not be disabled.
    """
    parameters = ('budget', 'days_per_period')

    def __init__(self, budget: float, days_per_period: int, area: Area = None):
        if area is not None:
            self.area = area
        else:
            self._area = None
        self.budget = budget
        self.days_per_period = days_per_period
        self.period_end = None
        self.priority = defaultdict(lambda: 100)
        self.history = defaultdict(list)
        self.forecast = {}  # type: Dict[Area, float]
        self.enabled = set()

    @property
    def area(self):
        return self._area

    @area.setter
    def area(self, new_area):
        self._area = new_area
        self._iaa = make_iaa_name(new_area)

    def set_priority(self, child, new_priority):
        if child in self.area.children:
            self.priority[child] = new_priority
        else:
            self.area.log.warning("Area {} not in range, priority setting will be ignored."
                                  .format(child))

    def activate(self):
        assert self.area is not None, "Area not set"
        self.begin_period()

    def process_market_cycle(self):
        self.compute_remaining()
        if self.area.now >= self.period_end:
            self.begin_period()
            self.area.log.info("End of budget period, {} of {} spent."
                               .format(self.budget - self.remaining, self.budget))
        else:
            self.update_forecast()
            self.decide()

    def update_forecast(self):
        consumed = defaultdict(float)
        for trade in self._sold():
            consumed[trade.buyer] += trade.offer.price
        for child in self.area.children:
            self.history[child].append(consumed[child.name])
            self.forecast[child] = sum(self.history[child]) / float(len(self.history[child]))

    def compute_remaining(self):
        self.remaining -= sum(trade.offer.price for trade in self._sold())

    def _sold(self):
        if self.area.current_market is None:
            return []
        else:
            return (t for t in self.area.current_market.trades if t.seller == self._iaa)

    def decide(self):
        slot_cost_estimate = sum(self.forecast[child] for child in self.enabled)
        slots_left = (self.period_end - self.area.now) / self.area.config.slot_length
        acceptable = self.remaining / slots_left
        self.area.log.error('Consumption forecast: {} expected, {} acceptable'
                            .format(slot_cost_estimate, acceptable))
        if slot_cost_estimate > acceptable:
            for child in sorted(self.enabled,
                                key=lambda c: (self.priority[c], -self.forecast[c])):
                self._disable(child)
                slot_cost_estimate -= self.forecast[child]
                if slot_cost_estimate <= acceptable:
                    break

    def begin_period(self):
        self.period_end = self.area.now + duration(self.days_per_period)
        self.remaining = self.budget
        for child in self.area.children:
            self._enable(child)

    def _disable(self, child):
        self.enabled.remove(child)
        child._fire_trigger('disable')
        self.area.log.error('BudgetKeeper disabled {}'.format(child.name))

    def _enable(self, child):
        self.enabled.add(child)
        child._fire_trigger('enable')
