"""Deterministic, inspectable local knowledge retrieval (not vector RAG)."""
from opentelemetry import trace
tracer = trace.get_tracer(__name__)
DOCUMENTS = [
 {"id":"POL-SLA-01","text":"Critical open incidents require immediate escalation to the incident commander. SLA breaches require remediation review."},
 {"id":"POL-ACCOUNT-02","text":"Strategic accounts with critical incidents require a customer-success risk review and documented follow-up."},
 {"id":"POL-MONITOR-03","text":"Low-risk accounts should continue routine monitoring and scheduled operational reviews."},
]
def retrieve(risk):
 with tracer.start_as_current_span("rag.retrieve") as span:
  terms = {"critical","sla","escalation"} if risk["level"] == "high" else {"monitoring","review"}
  scored = sorted(((sum(term in doc["text"].lower() for term in terms), doc) for doc in DOCUMENTS),key=lambda x:x[0],reverse=True)
  result=[doc for score,doc in scored if score>0][:2]
  span.set_attribute("rag.documents_returned",len(result))
  return result
