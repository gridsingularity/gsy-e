from logging import getLogger

from cached_property import cached_property

from d3a.util import TaggedLogWrapper

log = getLogger(__name__)


class AreaBehaviorBase:
    """Base class used by area behaviour defining classes (`BaseStrategy`, `BaseAppliance`)"""
    def __init__(self):
        # `area` is the area we trade in
        self.area = None  # type: ".area.Area"
        # `owner` is the area of which we are the strategy, usually a child of `area`
        self.owner = None  # type: ".area.Area"

    @cached_property
    def _log(self):
        return TaggedLogWrapper(log, "{s.owner.name}:{s.__class__.__name__}".format(s=self))

    @property
    def log(self):
        if not self.owner:
            log.warning("Logging without area in %s, using default logger",
                        self.__class__.__name__, stack_info=True)
            return log
        return self._log
