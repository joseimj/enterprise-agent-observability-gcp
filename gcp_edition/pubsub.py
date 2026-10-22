"""Best-effort notification after SQL commit; SQL outbox remains authoritative."""
import json
import logging
import os

LOG = logging.getLogger(__name__)

def signal_action(tenant: str, run_id: str) -> bool:
    topic = os.getenv('GCP_PUBSUB_TOPIC','')
    if not topic:
        return False
    try:
        from google.cloud import pubsub_v1
        publisher = pubsub_v1.PublisherClient()
        # No business payload/PII; dedupe remains enforced by PostgreSQL.
        payload = json.dumps({'v':1,'event':'OUTBOX_READY','tenant_id':tenant,
                              'run_id':run_id}).encode()
        publisher.publish(topic,payload).result(timeout=5)
        return True
    except Exception:
        LOG.exception('Wake-up signal failed; durable SQL outbox is unaffected')
        return False
