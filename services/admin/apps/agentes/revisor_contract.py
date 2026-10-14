"""Provider-owned, versioned text-only contract. No student identity or geometry."""
import json
import math
import re

CODES = frozenset('open_edges non_manifold winding inverted_component duplicate_faces degenerate_faces loose_vertices ngons triangle_budget multiple_materials missing_texture texture_budget dimensions author_transforms origin names supplied_normals multiple_meshes rig inner_cage outer_cage'.split())
REASONS = frozenset('export_triangulated import_scale_required destination_specific_box original_blender_state_unknown destination_pivot_not_specified no_universal_name_rule importer_may_recalculate outside_initial_scope'.split())
FIELDS = frozenset('value limit value_studs limit_studs scale_declared reason'.split())
INSTRUCTIONS = '''Explain only the supplied deterministic checks, in the requested language.
Be an encouraging teacher: explain why the measured issue matters and ask a short
question guiding a Blender correction. Do not claim to be Livia. Her pedagogy is pending.
Never invent measurements, requirements, lessons, links, approval or publication.
An unverifiable check is unknown, not a pass. Exports can lose original topology,
transforms and normals. Do not claim you saw geometry. Do not write numbers or URLs:
the site displays authoritative measurements separately. Return one explanation
per supplied check, using its exact index. Omitted checks remain in the technical report.'''
SCHEMA = {'type':'object', 'additionalProperties':False, 'required':['summary','explanations'],
 'properties':{'summary':{'type':'string'}, 'explanations':{'type':'array','items':{
 'type':'object','additionalProperties':False,'required':['index','text','question'],
 'properties':{'index':{'type':'integer'},'text':{'type':'string'},'question':{'type':'string'}}}}}}
FORMAT = {'type':'json_schema','name':'revisor_explanation_v1','strict':True,'schema':SCHEMA}


def number(value):
    if value is None:
        return
    if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>1e12:
        raise ValueError('number')


def validate(data):
    if not isinstance(data,dict) or set(data) != {'version','language','profile','grade','coverage_complete','omitted_checks','checks'}:
        raise ValueError('fields')
    if data['version']!=1 or data['language'] not in ('en','pt-br','es') or data['profile'] not in ('game','rigid','layered'):
        raise ValueError('enum')
    if data['grade'] not in ('ready','almost','needs_work') or type(data['coverage_complete']) is not bool:
        raise ValueError('grade')
    if type(data['omitted_checks']) is not int or not 0<=data['omitted_checks']<=100000:
        raise ValueError('omitted')
    if not isinstance(data['checks'],list) or not 1<=len(data['checks'])<=15:
        raise ValueError('checks')
    for i,row in enumerate(data['checks']):
        if not isinstance(row,dict) or set(row)!={'index','code','state','severity','count','evidence'}:
            raise ValueError('check_fields')
        if type(row['index']) is not int or row['index']!=i or row['code'] not in CODES:
            raise ValueError('check_id')
        if row['state'] not in ('fail','pass','unverifiable') or row['severity'] not in (None,'blocks','warns','tip'):
            raise ValueError('check_state')
        if (row['state']=='fail') != (row['severity'] is not None):
            raise ValueError('severity')
        number(row['count'])
        ev=row['evidence']
        if not isinstance(ev,dict) or set(ev)-FIELDS:
            raise ValueError('evidence')
        for key,value in ev.items():
            if key=='reason':
                if value is not None and value not in REASONS: raise ValueError('reason')
            elif isinstance(value,list):
                if len(value)>3: raise ValueError('dimensions')
                for n in value: number(n)
            else: number(value)
    if len(json.dumps(data,ensure_ascii=False).encode())>3500:
        raise ValueError('payload_limit')
    return data


def validate_output(text, data):
    result=json.loads(text)
    if not isinstance(result,dict) or set(result)!={'summary','explanations'}:
        raise ValueError('output')
    rows=result['explanations']
    if not isinstance(rows,list) or len(rows)!=len(data['checks']): raise ValueError('coverage')
    strings=[result['summary']]
    for i,row in enumerate(rows):
        if not isinstance(row,dict) or set(row)!={'index','text','question'} or type(row['index']) is not int or row['index']!=i:
            raise ValueError('index')
        strings.extend([row['text'],row['question']])
    for value in strings:
        if not isinstance(value,str) or not 1<=len(value)<=1200 or re.search(r'[\d<>]|https?://|www\.',value):
            raise ValueError('untrusted_prose')
    return result
