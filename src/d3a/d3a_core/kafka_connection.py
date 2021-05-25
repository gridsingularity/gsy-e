import os
import ssl
import logging
from kafka import KafkaProducer


LOCAL_KAFKA = 'localhost:9092'
BOOTSTRAP_SERVERS = os.environ.get('BOOTSTRAP_SERVERS')
SASL_PLAIN_USERNAME = os.environ.get('SASL_PLAIN_USERNAME')
SASL_PLAIN_PASSWORD = os.environ.get('SASL_PLAIN_PASSWORD')
SECURITY_PROTOCOL = os.environ.get('SECURITY_PROTOCOL', 'SASL_SSL')
SASL_MECHANISM = os.environ.get('SASL_MECHANISM', 'SCRAM-SHA-512')

# Create a new context using system defaults, disable all but TLS1.2
context = ssl.create_default_context()
context.options &= ssl.OP_NO_TLSv1
context.options &= ssl.OP_NO_TLSv1_1


def kafka_connection_factory():
    try:
        return KafkaConnection()
    except Exception:
        logging.info("Running without Kafka connection for simulation results.")
        return DisabledKafkaConnection()


class DisabledKafkaConnection:
    def __init__(self):
        pass

    def publish(self, endpoint_buffer):
        pass

    @staticmethod
    def is_enabled():
        return False


class KafkaConnection:
    def __init__(self):
        if BOOTSTRAP_SERVERS != LOCAL_KAFKA:
            kwargs = {'bootstrap_servers': BOOTSTRAP_SERVERS,
                      'sasl_plain_username': SASL_PLAIN_USERNAME,
                      'sasl_plain_password': SASL_PLAIN_PASSWORD,
                      'security_protocol': SECURITY_PROTOCOL,
                      'ssl_context': context, 'sasl_mechanism': SASL_MECHANISM,
                      'api_version': (0, 10), 'retries': 5, 'buffer_memory': 2048000000,
                      'max_request_size': 2048000000}
        else:
            kwargs = {'bootstrap_servers': BOOTSTRAP_SERVERS}

        self.producer = KafkaProducer(**kwargs)

    def publish(self, endpoint_buffer):
        results = endpoint_buffer.prepare_results_for_publish()
        if results is None:
            return

        self.producer.send('d3a-results', value=results, key=endpoint_buffer.job_id)

    @staticmethod
    def is_enabled():
        return True
