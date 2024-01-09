import json

from kafka import KafkaProducer
from kafka.errors import KafkaError

from .kafka_config import KAFKA_AD_TOPIC, KAFKA_BROKER_URL

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER_URL,
)


def produce_message(event: str, data: dict):
    request = {"event": event, "data": data}
    try:
        producer.send(
            topic=KAFKA_AD_TOPIC,
            value=json.dumps(request).encode("utf-8"),
        )
        producer.flush()
    except KafkaError as e:
        print(f"request: {request} and Error sending message: {str(e)}")
