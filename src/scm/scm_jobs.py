import logging
from os import environ, getpid

from gsy_framework.data_serializer import DataSerializer
from gsy_framework.redis_channels import QueueNames
from pendulum import now
from redis import Redis
from rq import Connection, Worker, get_current_job
from rq.decorators import job

logger = logging.getLogger()


@job("scm")
def start(payload):
    """Start a simulation with a Redis job."""
    # pylint: disable-next=import-outside-toplevel
    from scm.area_deserializer import AreaDeserializer
    from scm.scm_manager import SCMManager
    current_job = get_current_job()
    current_job.save_meta()
    payload = DataSerializer.decompress_and_decode(payload)
    # scenario: Dict,
    # settings: Optional[Dict],
    # events: Optional[str],
    # aggregator_device_mapping: Dict,
    # saved_state: Dict,
    # scm_properties: Dict,
    # job_id: str,
    # connect_to_profiles_db: bool = True

    scenario = payload["scenario"]
    scm_properties = payload["scm_properties"]
    current_time_slot = payload["time_slot"]
    deserializer = AreaDeserializer(area_dict=scenario, energy_values_kWh={}, fee_properties=scm_properties)
    scm_manager = SCMManager(deserializer.root_area, current_time_slot)
    deserializer.root_area.calculate_home_after_meter_data(current_time_slot, scm_manager)
    scm_manager.calculate_community_after_meter_data()
    deserializer.root_area.trigger_energy_trades(scm_manager)
    scm_manager.accumulate_community_trades()

    # if ConstSettings.SCMSettings.MARKET_ALGORITHM == CoefficientAlgorithm.DYNAMIC.value:
    #     self.area.change_home_coefficient_percentage(scm_manager)
    #
    # # important: SCM manager has to be updated before sending the results
    # results.update_scm_manager(scm_manager)
    # results.update_and_send_results()


def main():
    """Main entrypoint for running the exchange jobs."""
    with Connection(
            Redis.from_url(environ.get("REDIS_URL", "redis://localhost"), retry_on_timeout=True)):
        worker = Worker(
            [QueueNames().gsy_e_queue_name],
            name=f"simulation.{getpid()}.{now().timestamp()}", log_job_description=False
        )
        try:
            worker.work(max_jobs=1, burst=True, logging_level="ERROR")
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(ex)
            worker.kill_horse()
            worker.wait_for_horse()


if __name__ == "__main__":
    main()
