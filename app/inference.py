"""Bedrock optional; offline deterministic generation by default."""
import json, os
from opentelemetry import trace
from prometheus_client import Counter
tracer=trace.get_tracer(__name__)
INFERENCES=Counter("risk_inference_total","Inference calls",["provider","outcome"])
def explain(risk, documents):
 provider=os.getenv("INFERENCE_PROVIDER","offline").lower()
 if provider not in {"offline","bedrock"}: raise ValueError("INFERENCE_PROVIDER must be offline or bedrock")
 with tracer.start_as_current_span("gen_ai.generate") as span:
  span.set_attribute("gen_ai.operation.name","chat")
  span.set_attribute("gen_ai.provider.name", "aws.bedrock" if provider=="bedrock" else "offline")
  span.set_attribute("risk.evidence_count",len(documents))
  if provider=="offline":
   INFERENCES.labels(provider,"success").inc()
   return {"provider":"offline","narrative":risk["summary"]+". "+risk["recommendation"],"citations":[d["id"] for d in documents],"usage":None}
  try:
   import boto3
   model=os.environ["BEDROCK_MODEL_ID"]
   span.set_attribute("gen_ai.request.model",model)
   client=boto3.client("bedrock-runtime",region_name=os.getenv("AWS_REGION","us-east-1"))
   policy="Use only the provided risk facts and policies. Never invent incident IDs. Provide a concise summary."
   prompt=json.dumps({"risk":risk,"policies":documents})
   response=client.converse(modelId=model,system=[{"text":policy}],messages=[{"role":"user","content":[{"text":prompt}]}],inferenceConfig={"maxTokens":400,"temperature":0})
   usage=response.get("usage",{})
   for key in ("inputTokens","outputTokens"):
    if key in usage: span.set_attribute("gen_ai.usage."+("input_tokens" if key=="inputTokens" else "output_tokens"),usage[key])
   INFERENCES.labels(provider,"success").inc()
   return {"provider":"bedrock","narrative":" ".join(part.get("text","") for part in response["output"]["message"]["content"]),"citations":[d["id"] for d in documents],"usage":usage}
  except Exception as exc:
   span.record_exception(exc)
   INFERENCES.labels(provider,"error").inc()
   raise
