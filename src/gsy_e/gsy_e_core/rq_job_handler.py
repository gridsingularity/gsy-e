import ast
import logging
import traceback
from copy import deepcopy
from datetime import datetime, date
from typing import Dict, Optional

from gsy_framework.constants_limits import GlobalConfig, ConstSettings
from gsy_framework.enums import ConfigurationType, SpotMarketTypeEnum, CoefficientAlgorithm
from gsy_framework.settings_validators import validate_global_settings
from pendulum import duration, instance, now

import gsy_e.constants
from gsy_e.gsy_e_core.simulation import run_simulation
from gsy_e.gsy_e_core.util import update_advanced_settings
from gsy_e.models.config import SimulationConfig
from gsy_e.gsy_e_core.non_p2p_handler import NonP2PHandler

logging.getLogger().setLevel(logging.ERROR)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# pylint: disable=too-many-branches, too-many-statements
def launch_simulation_from_rq_job(
    scenario: Dict,
    settings: Optional[Dict],
    events: Optional[str],
    aggregator_device_mapping: Dict,
    saved_state: Dict,
    scm_properties: Dict,
    job_id: str,
    connect_to_profiles_db: bool = True,
):
    # pylint: disable=too-many-arguments, too-many-locals
    """Launch simulation from rq job."""

    gsy_e.constants.CONFIGURATION_ID = scenario.pop("configuration_uuid", None)
    try:
        if not gsy_e.constants.CONFIGURATION_ID:
            raise Exception(
                "configuration_uuid was not provided"
            )  # pylint disable=broad-exception-raised

        logger.error(
            "Starting simulation with job_id: %s and configuration id: %s",
            job_id,
            gsy_e.constants.CONFIGURATION_ID,
        )

        settings = _adapt_settings(settings)

        if events is not None:
            events = ast.literal_eval(events)

        _configure_constants_constsettings(scenario, settings, connect_to_profiles_db)

        if gsy_e.constants.RUN_IN_NON_P2P_MODE:
            scenario = NonP2PHandler(scenario).non_p2p_scenario

        slot_length_realtime = (
            duration(seconds=settings["slot_length_realtime"].seconds)
            if "slot_length_realtime" in settings
            else None
        )

        scenario_name = "json_arg"

        kwargs = {"no_export": True, "seed": settings.get("random_seed", 0)}

        if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value:
            kwargs.update({"scm_properties": scm_properties})

        past_slots_sim_state = _handle_scm_past_slots_simulation_run(
            scenario,
            settings,
            events,
            aggregator_device_mapping,
            saved_state,
            job_id,
            scenario_name,
            slot_length_realtime,
            kwargs,
        )

        if past_slots_sim_state is not None:
            saved_state = past_slots_sim_state
            # Fake that the simulation is not in finished, but in running state in order to
            # facilitate the state resume.
            saved_state["general"]["sim_status"] = "running"

        config = _create_config_settings_object(scenario, settings, aggregator_device_mapping)

        if settings.get("type") == ConfigurationType.CANARY_NETWORK.value:
            config.start_date = instance(
                datetime.combine(date.today(), datetime.min.time()), tz=gsy_e.constants.TIME_ZONE
            )

            if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value:
                config.start_date = config.start_date.subtract(
                    hours=settings["scm"]["scm_cn_hours_of_delay"]
                )

        run_simulation(
            setup_module_name=scenario_name,
            simulation_config=config,
            simulation_events=events,
            redis_job_id=job_id,
            saved_sim_state=saved_state,
            slot_length_realtime=slot_length_realtime,
            kwargs=kwargs,
        )

        logger.info(
            "Finishing simulation with job_id: %s and configuration id: %s",
            job_id,
            gsy_e.constants.CONFIGURATION_ID,
        )

    # pylint: disable=broad-except
    except Exception:
        # pylint: disable=import-outside-toplevel
        from gsy_e.gsy_e_core.redis_connections.simulation import publish_job_error_output

        logger.error(
            "Error on jobId, %s, configuration id: %s", job_id, gsy_e.constants.CONFIGURATION_ID
        )
        publish_job_error_output(job_id, traceback.format_exc())
        logger.error(
            "Error on jobId, %s, configuration id: %s: error sent to gsy-web",
            job_id,
            gsy_e.constants.CONFIGURATION_ID,
        )
        raise


def _adapt_settings(settings: Dict) -> Dict:
    if settings is None:
        settings = {}
    else:
        settings = {k: v for k, v in settings.items() if v is not None and v != "None"}

    advanced_settings = settings.get("advanced_settings", None)
    if advanced_settings is not None:
        update_advanced_settings(ast.literal_eval(advanced_settings))

    return settings


def _configure_constants_constsettings(
    scenario: Dict, settings: Dict, connect_to_profiles_db: bool
):
    assert isinstance(scenario, dict)

    GlobalConfig.CONFIG_TYPE = settings.get("type")

    if settings.get("type") == ConfigurationType.COLLABORATION.value:
        gsy_e.constants.EXTERNAL_CONNECTION_WEB = True

    if settings.get("type") in [
        ConfigurationType.CANARY_NETWORK.value,
        ConfigurationType.B2B.value,
    ]:
        gsy_e.constants.EXTERNAL_CONNECTION_WEB = True
        gsy_e.constants.RUN_IN_REALTIME = (
            settings.get("type") == ConfigurationType.CANARY_NETWORK.value
        )

        if settings.get("type") == ConfigurationType.B2B.value:
            ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = True
            # Disable fully automatic trading mode for the template strategies in favor of
            # UI manual and auto modes.
            ConstSettings.ForwardMarketSettings.FULLY_AUTO_TRADING = False

    gsy_e.constants.SEND_EVENTS_RESPONSES_TO_SDK_VIA_RQ = True

    spot_market_type = settings.get("spot_market_type")
    bid_offer_match_algo = settings.get("bid_offer_match_algo")

    if spot_market_type:
        ConstSettings.MASettings.MARKET_TYPE = spot_market_type
    if bid_offer_match_algo:
        ConstSettings.MASettings.BID_OFFER_MATCH_TYPE = bid_offer_match_algo

    ConstSettings.SettlementMarketSettings.RELATIVE_STD_FROM_FORECAST_FLOAT = settings.get(
        "relative_std_from_forecast_percent",
        ConstSettings.SettlementMarketSettings.RELATIVE_STD_FROM_FORECAST_FLOAT,
    )

    ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS = settings.get(
        "settlement_market_enabled",
        ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS,
    )
    gsy_e.constants.CONNECT_TO_PROFILES_DB = connect_to_profiles_db

    if settings.get("p2p_enabled", True) is False:
        ConstSettings.MASettings.MIN_BID_AGE = gsy_e.constants.MIN_OFFER_BID_AGE_P2P_DISABLED
        ConstSettings.MASettings.MIN_OFFER_AGE = gsy_e.constants.MIN_OFFER_BID_AGE_P2P_DISABLED
        gsy_e.constants.RUN_IN_NON_P2P_MODE = True

    if settings.get("scm"):
        ConstSettings.SCMSettings.MARKET_ALGORITHM = CoefficientAlgorithm(
            settings["scm"]["coefficient_algorithm"]
        ).value
        ConstSettings.SCMSettings.GRID_FEES_REDUCTION = settings["scm"]["grid_fees_reduction"]
        ConstSettings.SCMSettings.INTRACOMMUNITY_BASE_RATE_EUR = settings["scm"][
            "intracommunity_rate_base_eur"
        ]
    else:
        assert spot_market_type is not SpotMarketTypeEnum.COEFFICIENTS.value


def _create_config_settings_object(
    scenario: Dict, settings: Dict, aggregator_device_mapping: Dict
) -> SimulationConfig:

    config_settings = {
        "start_date": (
            instance(
                datetime.combine(settings.get("start_date"), datetime.min.time()),
                tz=gsy_e.constants.TIME_ZONE,
            )
            if "start_date" in settings
            else GlobalConfig.start_date
        ),
        "sim_duration": (
            duration(days=settings["duration"].days)
            if "duration" in settings
            else GlobalConfig.sim_duration
        ),
        "slot_length": (
            duration(seconds=settings["slot_length"].seconds)
            if "slot_length" in settings
            else GlobalConfig.slot_length
        ),
        "tick_length": (
            duration(seconds=settings["tick_length"].seconds)
            if "tick_length" in settings
            else GlobalConfig.tick_length
        ),
        "market_maker_rate": settings.get(
            "market_maker_rate", ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE
        ),
        "capacity_kW": settings.get("capacity_kW", ConstSettings.PVSettings.DEFAULT_CAPACITY_KW),
        "grid_fee_type": settings.get("grid_fee_type", GlobalConfig.grid_fee_type),
        "external_connection_enabled": settings.get("external_connection_enabled", False),
        "aggregator_device_mapping": aggregator_device_mapping,
        "hours_of_delay": settings.get("scm", {}).get(
            "hours_of_delay", ConstSettings.SCMSettings.HOURS_OF_DELAY
        ),
    }

    validate_global_settings(config_settings)
    config = SimulationConfig(**config_settings)
    config.area = scenario
    return config


def _handle_scm_past_slots_simulation_run(
    scenario: Dict,
    settings: Optional[Dict],
    events: Optional[str],
    aggregator_device_mapping: Dict,
    saved_state: Dict,
    job_id: str,
    scenario_name: str,
    slot_length_realtime: Optional[duration],
    kwargs: Dict,
) -> Optional[Dict]:
    # pylint: disable=too-many-arguments
    """
    Run an extra simulation before running a CN, in case the scm_past_slots parameter is set.
    Used to pre-populate simulation results from past market slots before starting the CN.
    """
    scm_past_slots = saved_state.pop("scm_past_slots", False)
    if not (settings["type"] == ConfigurationType.CANARY_NETWORK.value and scm_past_slots):
        return None

    # Deepcopy the scenario and settings objects, because they are mutated by the
    # run_simulation function, and we need the original versions for the subsequent
    # Canary Network run.
    scenario_copy = deepcopy(scenario)
    settings_copy = deepcopy(settings)

    config = _create_config_settings_object(
        scenario_copy, settings_copy, aggregator_device_mapping
    )
    # We are running SCM Canary Networks with some days of delay compared to realtime in order to
    # compensate for delays in transmission of the asset measurements.
    # Adding 4 hours of extra time to the SCM past slots simulation duration, in order to
    # compensate for the runtime of the SCM past slots simulation and to not have any results gaps
    # after this simulation run and the following Canary Network launch.
    config.end_date = (
        now(tz=gsy_e.constants.TIME_ZONE).subtract(hours=config.hours_of_delay).add(hours=4)
    )
    config.sim_duration = config.end_date - config.start_date
    GlobalConfig.sim_duration = config.sim_duration
    gsy_e.constants.RUN_IN_REALTIME = False
    simulation_state = run_simulation(
        setup_module_name=scenario_name,
        simulation_config=config,
        simulation_events=events,
        redis_job_id=job_id,
        saved_sim_state=saved_state,
        slot_length_realtime=slot_length_realtime,
        kwargs=kwargs,
    )
    gsy_e.constants.RUN_IN_REALTIME = True
    return simulation_state
