"""Read-only Vertex AI Gemini explanation of sanitized workflow metadata.

LLM output is never used as an authorization, risk score, or action directive.
The base LangGraph graph continues to run deterministic fixture assessment.
"""
import os


def build_safe_context(run: dict) -> str:
    statuses = sorted({str(row.get('status','UNKNOWN'))[:30] for row in run.get('outbox',[])})
    approved = str(run.get('approval') or 'UNKNOWN')[:30]
    return f"Approval: {approved}. Outbox statuses: {', '.join(statuses) or 'none'}. " \
           f"Awaiting graph approval: {bool(run.get('awaiting_graph_approval'))}."


def explain_run(run: dict) -> dict:
    context = build_safe_context(run)
    if os.getenv('GCP_INFERENCE_PROVIDER','offline') == 'offline':
        return {'provider':'offline','explanation':context,'model_used':False}
    if os.getenv('GCP_INFERENCE_PROVIDER') != 'vertex':
        raise RuntimeError('Unsupported inference provider')
    project = os.environ['GOOGLE_CLOUD_PROJECT']
    location = os.getenv('GOOGLE_CLOUD_LOCATION','us-central1')
    model = os.getenv('GCP_GEMINI_MODEL','gemini-2.5-flash')
    from google import genai
    from google.genai import types
    with genai.Client(vertexai=True,project=project,location=location,
                      http_options=types.HttpOptions(api_version='v1')) as client:
        response = client.models.generate_content(
            model=model,
            contents=('Summarize this execution status for an engineer in at most 70 words. '
                      'Do not advise or authorize actions. Only use supplied facts. '\
                      + context),
            config=types.GenerateContentConfig(temperature=0.0,max_output_tokens=170),
        )
    return {'provider':'vertex','explanation':response.text or '', 'model_used':True}
