"""Pure deterministic measurements, before display centering or auto-cleanup."""
from collections import Counter, defaultdict
from datetime import date
import math
from pathlib import Path

import yaml

from revisor import ENGINE_VERSION


def rules(today=None):
    data = yaml.safe_load(Path(__file__).with_name('limites_roblox.yaml').read_text('utf-8'))
    age = ((today or date.today()) - date.fromisoformat(data['verified_on'])).days
    if not 0 <= age <= 180:
        raise ValueError('rules_expired')
    if not data.get('version') or any(not u.startswith('https://create.roblox.com/') for u in data['sources'].values()):
        raise ValueError('invalid_rules')
    return data


def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def measure(mesh):
    vertices, faces = mesh['vertices'], mesh['faces']
    if not vertices or len(vertices) > 300000 or len(faces) > 200000:
        raise ValueError('geometry_budget')
    if any(len(v) != 3 or any(not math.isfinite(x) for x in v) for v in vertices):
        raise ValueError('invalid_vertex')
    if any(len(f) < 3 or any(type(i) is not int or not 0 <= i < len(vertices) for i in f) for f in faces):
        raise ValueError('invalid_face')
    # Exact coordinates reconnect UV/normal splits without tolerance welding.
    # Coincident disconnected surfaces can be ambiguous and are reported below.
    canonical = {p: i for i, p in enumerate(dict.fromkeys(tuple(v) for v in vertices))}
    ids = [canonical[tuple(v)] for v in vertices]
    edges, adjacency = defaultdict(list), defaultdict(set)
    signatures, used, degenerate = Counter(), set(), []
    triangles, face_volumes = 0, []
    for fi, face in enumerate(faces):
        used.update(face)
        sequence = [ids[i] for i in face]
        signatures[tuple(sorted(sequence))] += 1
        triangles += len(face)-2
        areas, volumes = [], []
        a = vertices[face[0]]
        for j in range(1, len(face)-1):
            b, c = vertices[face[j]], vertices[face[j+1]]
            areas.append(math.sqrt(dot(cross(sub(b, a), sub(c, a)), cross(sub(b, a), sub(c, a))))/2)
            volumes.append(dot(a, cross(b, c))/6)
        if len(set(sequence)) < 3 or sum(areas) <= 1e-12:
            degenerate.append(fi)
        face_volumes.append(sum(volumes))
        for a_id, b_id in zip(sequence, sequence[1:]+sequence[:1]):
            if a_id != b_id:
                edges[tuple(sorted((a_id, b_id)))].append((fi, a_id < b_id))
    for entries in edges.values():
        anchor = entries[0][0]
        for fi, _ in entries[1:]:
            adjacency[fi].add(anchor)
            adjacency[anchor].add(fi)
    components, unseen = [], set(range(len(faces)))
    while unseen:
        todo, component = [unseen.pop()], set()
        while todo:
            fi = todo.pop()
            component.add(fi)
            neighbors = adjacency[fi] & unseen
            unseen.difference_update(neighbors)
            todo.extend(neighbors)
        components.append(component)
    open_count = sum(len(e) == 1 for e in edges.values())
    nonmanifold = sum(len(e) > 2 for e in edges.values())
    winding = sum(len(e) == 2 and e[0][1] == e[1][1] for e in edges.values())
    component_of = {fi: ci for ci, component in enumerate(components) for fi in component}
    closed = [True]*len(components)
    for entries in edges.values():
        if len(entries) != 2 or entries[0][1] == entries[1][1]:
            closed[component_of[entries[0][0]]] = False
    inverted = [min(component) for ci, component in enumerate(components)
                if closed[ci] and sum(face_volumes[i] for i in component) < -1e-12]
    bounds = [[min(v[i] for v in vertices), max(v[i] for v in vertices)] for i in range(3)]
    return {
        'vertices': len(vertices), 'polygons': len(faces), 'triangles': triangles,
        'open_edges': open_count, 'non_manifold': nonmanifold, 'winding': winding,
        'inverted_component': len(inverted), 'duplicate_faces': sum(n-1 for n in signatures.values()),
        'degenerate_faces': len(degenerate), 'loose_vertices': len(vertices)-len(used),
        'ngons': sum(len(f)>4 for f in faces), 'components': len(components),
        'bounds': bounds, 'dimensions': [hi-lo for lo, hi in bounds],
        'locations': {'degenerate_faces': degenerate[:100], 'inverted_component': inverted[:100]},
        'coincident_vertices': len(vertices)-len(canonical),
    }


def inspect(data, profile, studs_per_unit=None, today=None):
    table = rules(today)
    policy = table['profiles'][profile]
    if studs_per_unit is not None and (not math.isfinite(studs_per_unit) or not 0 < studs_per_unit <= 10000):
        raise ValueError('invalid_scale')
    meshes = data['meshes']
    if not isinstance(meshes, list) or not 1 <= len(meshes) <= 256:
        raise ValueError('mesh_budget')
    findings, checks, measurements = [], [], []

    def check(code, count, severity='warns', mesh=None, source=None, status=None, evidence=None):
        state = status or ('fail' if count else 'pass')
        row = {'code': code, 'mesh': mesh, 'state': state, 'severity': severity if state == 'fail' else None,
               'count': count, 'evidence': evidence or {}, 'source': table['sources'][source or policy['source']],
               'lesson': None, 'pedagogy': 'pending_livia'}
        checks.append(row)
        if state == 'fail':
            findings.append(row)

    for mi, mesh in enumerate(meshes):
        metrics = measure(mesh)
        measurements.append({'mesh': mi, 'name': str(mesh.get('name', ''))[:120], **metrics})
        for code, rule in table['rules'].items():
            if code not in metrics:
                continue
            if code == 'ngons' and not data.get('author_polygons_preserved'):
                check(code, None, mesh=mi, status='unverifiable', evidence={'reason':'export_triangulated'})
            else:
                check(code, metrics[code], rule['severity'], mi, rule['source'])
        if policy['triangle_scope'] == 'mesh':
            check('triangle_budget', int(metrics['triangles'] > policy['triangle_limit']), 'blocks', mi,
                  evidence={'value': metrics['triangles'], 'limit': policy['triangle_limit']})
        materials = mesh.get('materials', [])
        check('multiple_materials', int(len(materials)>1), 'blocks', mi, 'texture', evidence={'value':len(materials)})
        for texture in mesh.get('textures', []):
            check('missing_texture', int(texture.get('missing', False)), 'blocks', mi, 'texture')
            if not texture.get('missing'):
                dimensions = texture.get('size', [])
                if len(dimensions) != 2 or any(type(x) is not int or x < 1 for x in dimensions):
                    raise ValueError('invalid_texture')
                check('texture_budget', int(max(dimensions)>policy['texture_limit']), 'blocks', mi, 'texture',
                      evidence={'value':dimensions, 'limit':policy['texture_limit']})
        dimensions = metrics['dimensions']
        check('dimensions', None, mesh=mi, status='unverifiable', evidence={'reason':'import_scale_required'})
        if studs_per_unit is not None:
            checks.pop()
            values = [x*studs_per_unit for x in dimensions]
            limits = policy['dimensions_studs']
            check('dimensions', int(any(x>y for x,y in zip(values,limits))) if limits else None,
                  'blocks', mi, status=None if limits else 'unverifiable',
                  evidence={'value_studs':values, 'limit_studs':limits, 'scale_declared':studs_per_unit,
                            'reason':None if limits else 'destination_specific_box'})
        check('author_transforms', None, mesh=mi, status='unverifiable', evidence={'reason':'original_blender_state_unknown'})
        check('origin', None, mesh=mi, status='unverifiable', evidence={'reason':'destination_pivot_not_specified'})
        check('names', None, mesh=mi, status='unverifiable', evidence={'reason':'no_universal_name_rule'})
        check('supplied_normals', None, mesh=mi, status='unverifiable', evidence={'reason':'importer_may_recalculate'})
    total = sum(m['triangles'] for m in measurements)
    if policy['triangle_scope'] == 'asset':
        check('triangle_budget', int(total > policy['triangle_limit']), 'blocks', evidence={'value':total, 'limit':policy['triangle_limit']})
    check('multiple_meshes', int(len(meshes)>1 and policy['single_mesh']), 'blocks', evidence={'value':len(meshes)})
    for code in policy.get('uncovered', []):
        check(code, None, status='unverifiable', evidence={'reason':'outside_initial_scope'})
    priority = {'blocks':0, 'warns':1, 'tip':2}
    findings.sort(key=lambda f: priority[f['severity']])
    # Original topology/attachment/rig coverage is essential: incomplete != clean.
    incomplete = any(c['state'] == 'unverifiable' and c['code'] in {'ngons','dimensions','rig','inner_cage','outer_cage','supplied_normals'} for c in checks)
    grade = 'needs_work' if any(f['severity']=='blocks' for f in findings) else 'almost' if findings or incomplete else 'ready'
    return {'engine_version':ENGINE_VERSION, 'rules_version':table['version'], 'profile':profile,
            'grade':grade, 'coverage_complete':not incomplete, 'checks':checks, 'findings':findings,
            'metrics':measurements, 'triangles':total, 'pedagogy':'pending_livia'}
