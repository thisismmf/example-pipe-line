import json
import time
import logging
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
JSON_PATH = '/app/data/sample.json'
KAFKA_TOPIC = 'test_pipeline'
KAFKA_SERVER = 'kafka:9092'

def load_json_data():
    logger.info(f"Attempting to read data from {JSON_PATH}")
    try:
        with open(JSON_PATH, 'r') as file:
            data = json.load(file)
            logger.info(f"Successfully loaded {len(data)} records from JSON file")
            return data
    except FileNotFoundError:
        logger.error(f"File not found: {JSON_PATH}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON data: {e}")
        raise

def create_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_SERVER,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        retries=5
    )

def send_data(producer, topic, data):
    for record in data:
        try:
            future = producer.send(topic, value=record)
            # Wait for message to be delivered
            record_metadata = future.get(timeout=10)
            logger.info(f"Sent record to topic {topic}, partition {record_metadata.partition}, offset {record_metadata.offset}")
            time.sleep(1)  # Delay between messages
        except KafkaError as e:
            logger.error(f"Failed to send record: {e}")
            raise

if __name__ == '__main__':
    try:
        data = load_json_data()
        producer = create_producer()
        send_data(producer, KAFKA_TOPIC, data)
        producer.flush()
        producer.close()
        logger.info("Successfully completed sending all records")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise