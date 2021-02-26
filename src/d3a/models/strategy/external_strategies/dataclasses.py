from dataclasses import dataclass


@dataclass
class MarketInfo:
    event: str = None
    simulation_id: str = None
    num_ticks: int = None
    market_slot: str = None
    slot_completion: str = None


@dataclass
class TickInfo(MarketInfo):
    pass
