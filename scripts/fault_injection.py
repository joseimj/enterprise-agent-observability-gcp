"""Run repeatable scenario experiments against the local API."""
import argparse
import json
import time
import urllib.request
import urllib.error

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://localhost:8000/risk/analyze')
parser.add_argument('--scenario', choices=['normal','slow_salesforce','jira_failure'], default='jira_failure')
parser.add_argument('--runs', type=int, default=5)
args = parser.parse_args()
for i in range(args.runs):
    payload = json.dumps({'account_id':'ACME','scenario':args.scenario}).encode()
    request = urllib.request.Request(args.url, payload, {'Content-Type':'application/json'})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=25) as r:
            status, result = r.status, json.load(r)
    except urllib.error.HTTPError as e:
        status, result = e.code, json.load(e)
    print(json.dumps({'run':i+1,'scenario':args.scenario,'status':status,'duration_seconds':round(time.monotonic()-start,3),'trace_id':result.get('trace_id')}))
