import uuid

import pytest
from gsy_framework.constants_limits import ConstSettings, TIME_ZONE, GlobalConfig
from pendulum import datetime, today, duration

from gsy_e.gsy_e_core.blockchain_interface import NonBlockchainInterface
from gsy_e.models.config import create_simulation_config_from_global_config
from gsy_e.models.market.future import FutureMarkets
from gsy_e.models.market.settlement import SettlementMarket


@pytest.fixture(name="settlement_market")
def settlement_market_fixture():
    """Create a SettlementMarket."""
    return SettlementMarket(bc=NonBlockchainInterface(str(uuid.uuid4())),
                            time_slot=datetime(2021, 1, 1, 00, 00))


@pytest.fixture(name="future_markets")
def future_market_fixture():
    """Return a futures markets object."""
    original_future_market_count = ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS
    ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = 2
    original_market_maker_rate = GlobalConfig.market_maker_rate
    GlobalConfig.market_maker_rate = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE
    config = create_simulation_config_from_global_config()
    config.start_date = today(tz=TIME_ZONE)
    config.slot_length = duration(hours=1)
    future_markets = FutureMarkets(bc=NonBlockchainInterface(str(uuid.uuid4())))
    future_markets.create_future_market_slots(
        current_market_time_slot=today(tz=TIME_ZONE), config=config)
    assert len(future_markets.market_time_slots) == 2
    yield future_markets
    ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = original_future_market_count
    GlobalConfig.market_maker_rate = original_market_maker_rate
