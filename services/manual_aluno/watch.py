"""Observe the new route after activation; recover code routing only, never databases."""
import json
import os
from pathlib import Path
import sys
import time
from deploy import ROUTE, BASE, response

backup = Path(sys.argv[1])
failures = 0
for i in range(120):
    time.sleep(10)
    try:
        status, body, headers = response('https://meshcraft.top/manual-do-aluno-primeiros-dolares')
        ok = status == 401 and 'Entrar na minha conta' in body and 'no-store' in headers.get('Cache-Control', '')
    except Exception:
        ok = False
    failures = 0 if ok else failures + 1
    (BASE / 'acompanhamento.json').write_text(json.dumps({'checks': i + 1, 'healthy': ok, 'failures': failures}))
    if failures >= 3:
        if ROUTE.exists():
            os.replace(ROUTE, backup / 'rota-retirada-pelo-acompanhamento.json')
        (BASE / 'acompanhamento.json').write_text(json.dumps({'checks': i + 1, 'healthy': False, 'route_recovered': True, 'database_restored': False}))
        break
