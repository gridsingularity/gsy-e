import logging
from collections import namedtuple


IncomingRequest = namedtuple('IncomingRequest', ('request_type', 'arguments', 'response_channel'))


def check_for_connected_and_reply(redis, channel_name, is_connected):
    if not is_connected:
        redis.publish_json(
            channel_name, {
                "status": "error",
                "error_message": f"Client should be registered in order to access this area."})
        return False
    return True


def register_area(redis, device_name, is_connected):
    register_response_channel = f'{device_name}/register_participant/response'
    try:
        redis.publish_json(
            register_response_channel,
            {"status": "ready", "registered": True})
        return True
    except Exception as e:
        logging.error(f"Error when registering to area {device_name}: "
                      f"Exception: {str(e)}")
        redis.publish_json(
            register_response_channel,
            {"status": "error",
             "error_message": f"Error when registering to area {device_name}."})
        return is_connected


def unregister_area(redis, device_name, is_connected):
    unregister_response_channel = f'{device_name}/unregister_participant/response'
    if not check_for_connected_and_reply(redis, unregister_response_channel,
                                         is_connected):
        return
    try:
        redis.publish_json(
            unregister_response_channel,
            {"status": "ready", "unregistered": True})
        return False
    except Exception as e:
        logging.error(f"Error when unregistering from area {device_name}: "
                      f"Exception: {str(e)}")
        redis.publish_json(
            unregister_response_channel,
            {"status": "error",
             "error_message": f"Error when unregistering from area {device_name}."})
        return is_connected
