"""Revisor's HTTP client: no cross-cell imports, database or OpenAI key."""
import http.client
import json

EVIDENCE_KEYS={'value','limit','value_studs','limit_studs','scale_declared','reason'}


def prepare(report, language='en'):
    priority={'blocks':0,'warns':1,'tip':2,None:3}
    rows=sorted(report['checks'],key=lambda r: (priority[r['severity']],r['state']!='unverifiable'))
    # Keep the full deterministic report locally; explanation is bounded.
    checks=[]
    for row in rows[:15]:
        checks.append({'index':len(checks),'code':row['code'],'state':row['state'],
            'severity':row['severity'],'count':row['count'],
            'evidence':{k:v for k,v in row.get('evidence',{}).items() if k in EVIDENCE_KEYS}})
    data={'version':1,'language':language,'profile':report['profile'],'grade':report['grade'],
          'coverage_complete':report['coverage_complete'],'checks':checks,
          'omitted_checks':len(rows)-len(checks)}
    while len(json.dumps(data,ensure_ascii=False).encode())>2500 and len(checks)>1:
        checks.pop(); data['omitted_checks']+=1
    return data


def explain(report, token, language='en'):
    conn=http.client.HTTPConnection('172.16.20.3',8080,timeout=28)
    try:
        conn.request('POST','/api/revisor/v1/explicacao',body=json.dumps(prepare(report,language)),
            headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
        response=conn.getresponse()
        raw=response.read(65537)
        if response.status!=200 or len(raw)>65536: return {'fallback':True}
        return json.loads(raw)
    except (OSError,ValueError,http.client.HTTPException):
        return {'fallback':True}
    finally:
        conn.close()
