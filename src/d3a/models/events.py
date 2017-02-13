from enum import Enum
from typing import Union, List  # noqa

from functools import reduce

from attr import attrs, attrib
from copy import copy


class OfferEvent(Enum):
    DELETED = 1
    ACCEPTED = 2


class MarketEvent(Enum):
    OFFER = 1
    OFFER_CHANGED = 4
    OFFER_DELETED = 2
    TRADE = 3


class AreaEvent(Enum):
    TICK = 1
    MARKET_CYCLE = 2
    ACTIVATE = 3


class EventMixin:
    def event_listener(self, event_type: Union[AreaEvent, MarketEvent], **kwargs):
        self.log.debug("Dispatching event %s", event_type.name)
        getattr(self, "event_{}".format(event_type.name.lower()))(**kwargs)

    def event_tick(self, *, area):
        pass

    def event_market_cycle(self):
        pass

    def event_activate(self):
        pass

    def event_offer(self, *, market, offer):
        pass

    def event_offer_changed(self, *, market, existing_offer, new_offer):
        pass

    def event_offer_deleted(self, *, market, offer):
        pass

    def event_trade(self, *, market, trade):
        pass


@attrs
class Trigger:
    name = attrib()
    params = attrib(default={})
    state_getter = attrib(default=None)
    help = attrib(default="")
    _source = attrib(default=None)

    @property
    def state(self):
        if self.state_getter is None or self._source is None:
            return None
        return self.state_getter(self._source)


class TriggerMeta(type):
    def __new__(mcs, name, bases, dict_, **kwargs):
        triggers = dict_.get('available_triggers', [])
        for base in bases:
            base_triggers = getattr(base, 'available_triggers', [])
            if base_triggers and not hasattr(base, '_trigger_names'):
                # Base class that hasn't bee treated by the metaclass yet (e.g. mixin)
                triggers.extend(base_triggers)
        if triggers:
            trigger_names = reduce(
                lambda a, b: a | b,
                (
                    getattr(base, '_trigger_names', set())
                    for base in bases
                ),
                set()
            )
            for trigger in triggers:
                if not isinstance(trigger, Trigger):
                    raise TypeError("'available_triggers' must be of type 'Trigger'.")
                if trigger.name in trigger_names:
                    raise TypeError("Trigger named '{}' is already defined.".format(trigger.name))
                trigger_handler = 'trigger_{}'.format(trigger.name)
                if (
                    trigger_handler not in dict_
                    and not any(hasattr(base, trigger_handler) for base in bases)
                ):
                    raise TypeError("Trigger handler '{}' for trigger '{}' is missing.".format(
                        trigger_handler, trigger.name
                    ))
                trigger_names.add(trigger.name)
            dict_['_trigger_names'] = trigger_names
        # Merge triggers from parent(s)
        dict_['available_triggers'] = list(reversed(
            sum(
                (
                    getattr(base, 'available_triggers', [])
                    for base in bases
                ),
                triggers
            )
        ))

        return super().__new__(mcs, name, bases, dict_, **kwargs)


class TriggerMixin(metaclass=TriggerMeta):
    available_triggers = []  # type: List[Trigger]

    def __init__(self):
        super().__init__()
        triggers = []
        for trigger in reversed(self.available_triggers):
            trigger = copy(trigger)
            triggers.append(trigger)
            trigger._source = self
        self.available_triggers = triggers

    def fire_trigger(self, name, **params):
        if name not in self._trigger_names:
            raise RuntimeError("Unknown trigger '{}'".format(name))
        self.log.debug("Firing trigger '%s'", name)
        return getattr(self, 'trigger_{}'.format(name))(**params)
