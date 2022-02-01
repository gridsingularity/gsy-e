import ast
import json
import logging
import pickle
import traceback
from datetime import datetime, date
from typing import Dict, Optional
from zlib import decompress

from gsy_framework.constants_limits import GlobalConfig, ConstSettings
from gsy_framework.settings_validators import validate_global_settings
from pendulum import duration, instance

import gsy_e.constants
from gsy_e.gsy_e_core.simulation import run_simulation
from gsy_e.gsy_e_core.util import available_simulation_scenarios, update_advanced_settings
from gsy_e.models.config import SimulationConfig

log = logging.getLogger()


def decompress_and_decode_queued_strings(queued_string: bytes) -> Dict:
    """Decompress and decode data sent via redis queue."""
    return pickle.loads(decompress(queued_string))


def launch_simulation_from_rq_job(scenario: bytes, settings: Optional[Dict],
                                  events: Optional[str], aggregator_device_mapping: str,
                                  saved_state: bytes, job_id: str):
    # pylint: disable=too-many-arguments, too-many-locals
    """Launch simulation from rq job."""
    logging.getLogger().setLevel(logging.ERROR)
    scenario = decompress_and_decode_queued_strings(scenario)
    gsy_e.constants.CONFIGURATION_ID = scenario.pop("configuration_uuid")
    if "collaboration_uuid" in scenario:
        gsy_e.constants.EXTERNAL_CONNECTION_WEB = True
        GlobalConfig.IS_CANARY_NETWORK = scenario.pop("is_canary_network", False)
        gsy_e.constants.RUN_IN_REALTIME = GlobalConfig.IS_CANARY_NETWORK
    saved_state = decompress_and_decode_queued_strings(saved_state)
    log.error("Starting simulation with job_id: %s", job_id)

    try:
        if settings is None:
            settings = {}
        else:
            settings = {k: v for k, v in settings.items() if v is not None and v != "None"}

        advanced_settings = settings.get("advanced_settings", None)
        if advanced_settings is not None:
            update_advanced_settings(ast.literal_eval(advanced_settings))
        aggregator_device_mapping = json.loads(aggregator_device_mapping)

        if events is not None:
            events = ast.literal_eval(events)

        config_settings = {
            "start_date":
                instance(datetime.combine(settings.get("start_date"), datetime.min.time()))
                if "start_date" in settings else GlobalConfig.start_date,
            "sim_duration":
                duration(days=settings["duration"].days)
                if "duration" in settings else GlobalConfig.sim_duration,
            "slot_length":
                duration(seconds=settings["slot_length"].seconds)
                if "slot_length" in settings else GlobalConfig.slot_length,
            "tick_length":
                duration(seconds=settings["tick_length"].seconds)
                if "tick_length" in settings else GlobalConfig.tick_length,
            "market_maker_rate":
                settings.get("market_maker_rate",
                             str(ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE)),
            "cloud_coverage": settings.get("cloud_coverage", GlobalConfig.cloud_coverage),
            "pv_user_profile": settings.get("pv_user_profile", None),
            "capacity_kW": settings.get("capacity_kW",
                                        ConstSettings.PVSettings.DEFAULT_CAPACITY_KW),
            "grid_fee_type": settings.get("grid_fee_type", GlobalConfig.grid_fee_type),
            "external_connection_enabled": settings.get("external_connection_enabled", False),
            "aggregator_device_mapping": aggregator_device_mapping
        }

        if GlobalConfig.IS_CANARY_NETWORK:
            config_settings["start_date"] = (
                instance((datetime.combine(date.today(), datetime.min.time()))))

        validate_global_settings(config_settings)

        slot_length_realtime = (
            duration(seconds=settings["slot_length_realtime"].seconds)
            if "slot_length_realtime" in settings else None)

        gsy_e.constants.SEND_EVENTS_RESPONSES_TO_SDK_VIA_RQ = True
        config = SimulationConfig(**config_settings)

        spot_market_type = settings.get("spot_market_type")
        bid_offer_match_algo = settings.get("bid_offer_match_algo")

        if spot_market_type:
            ConstSettings.MASettings.MARKET_TYPE = spot_market_type
        if bid_offer_match_algo:
            ConstSettings.MASettings.BID_OFFER_MATCH_TYPE = bid_offer_match_algo

        ConstSettings.SettlementMarketSettings.RELATIVE_STD_FROM_FORECAST_FLOAT = (
            settings.get(
                "relative_std_from_forecast_percent",
                ConstSettings.SettlementMarketSettings.RELATIVE_STD_FROM_FORECAST_FLOAT
            ))

        ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS = settings.get(
            "settlement_market_enabled",
            ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS
        )

        if scenario is None:
            scenario_name = "default_2a"
        elif scenario in available_simulation_scenarios:
            scenario_name = scenario
        else:
            scenario_name = "json_arg"
            config.area = scenario

        kwargs = {"no_export": True,
                  "pricing_scheme": 0,
                  "seed": settings.get("random_seed", 0)}

        gsy_e.constants.CONNECT_TO_PROFILES_DB = True

        run_simulation(setup_module_name=scenario_name,
                       simulation_config=config,
                       simulation_events=events,
                       redis_job_id=job_id,
                       saved_sim_state=saved_state,
                       slot_length_realtime=slot_length_realtime,
                       kwargs=kwargs)
    # pylint: disable=broad-except
    except Exception:
        # pylint: disable=import-outside-toplevel
        from gsy_e.gsy_e_core.redis_connections.redis_communication import publish_job_error_output
        publish_job_error_output(job_id, traceback.format_exc())
        logging.getLogger().exception("Error on jobId, %s", job_id)
