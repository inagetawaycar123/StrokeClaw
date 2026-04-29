#!/usr/bin/env python3
import sys
import json
import urllib.request

run_id = sys.argv[1] if len(sys.argv) > 1 else None # AI辅助生成：GLM-5, 2026-04-20
if not run_id:
    print('Usage: python run_icv_on_run.py <run_id>')
    sys.exit(2)

url = f'http://localhost:5011/api/agent/runs/{run_id}'
try:
    with urllib.request.urlopen(url) as r:
        raw = r.read()
        data = json.loads(raw)
except Exception as e:
    print('Failed to fetch run:', e)
    sys.exit(1)

run = data.get('run') or data
planner_output = run.get('planner_output') or {} # AI辅助生成：GLM-5, 2026-04-21

# extract tool_results list
tool_results = run.get('tool_results') or []

# patient_context and analysis_result extracted from completed tool structured_output
patient_context = None
analysis_result = None
for t in tool_results:
    if t.get('tool_name') == 'load_patient_context' and t.get('status') == 'completed':
        patient_context = t.get('structured_output')
    if t.get('tool_name') == 'run_stroke_analysis' and t.get('status') == 'completed':
        analysis_result = t.get('structured_output')

# import icv
try:
    from backend.icv import evaluate_icv
except Exception:
    try:
        from icv import evaluate_icv
    except Exception as e:
        print('Failed to import icv:', e)
        sys.exit(1)

out = evaluate_icv(planner_output=planner_output, tool_results=tool_results, patient_context=patient_context, analysis_result=analysis_result)
print(json.dumps(out, indent=2, ensure_ascii=False))
