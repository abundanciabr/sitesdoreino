from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

from revisor.engine import inspect, measure, rules
from revisor.importer_blender import validate_envelope
from fixtures import FACES, VERTICES, glb, mesh


TODAY = date(2026,10,14)


class EngineTests(unittest.TestCase):
    def report(self, value, **kwargs):
        return inspect({'meshes':[value], 'author_polygons_preserved':True}, 'game', today=TODAY, **kwargs)

    def test_clean_closed_tetrahedron(self):
        result = measure(mesh())
        self.assertEqual(result['triangles'],4)
        for key in ['open_edges','non_manifold','winding','inverted_component','duplicate_faces','degenerate_faces','loose_vertices','ngons']:
            self.assertEqual(result[key],0,key)

    def test_missing_face(self):
        self.assertEqual(measure(mesh(faces=FACES[:-1]))['open_edges'],3)

    def test_inverted_whole_component(self):
        result = measure(mesh(faces=[tuple(reversed(f)) for f in FACES]))
        self.assertEqual(result['inverted_component'],1)
        self.assertEqual(result['winding'],0)

    def test_one_face_flipped(self):
        result = measure(mesh(faces=[FACES[0][::-1],*FACES[1:]]))
        self.assertEqual(result['winding'],3)
        self.assertEqual(result['inverted_component'],0)

    def test_nonmanifold_and_duplicate_face(self):
        result = measure(mesh(faces=[*FACES,FACES[0]]))
        self.assertEqual(result['non_manifold'],3)
        self.assertEqual(result['duplicate_faces'],1)

    def test_degenerate_and_loose_vertex(self):
        value = mesh(faces=[*FACES,(0,0,1)],vertices=[*VERTICES,(7,7,7)])
        result = measure(value)
        self.assertEqual(result['degenerate_faces'],1)
        self.assertEqual(result['loose_vertices'],1)

    def test_ngon_preserved(self):
        value = mesh(vertices=[(0,0,0),(1,0,0),(2,1,0),(1,2,0),(0,1,0)],faces=[(0,1,2,3,4)])
        result = self.report(value)
        self.assertTrue(any(c['code']=='ngons' and c['state']=='fail' for c in result['checks']))

    def test_glb_never_claims_original_ngons_absent(self):
        result = inspect({'meshes':[mesh()], 'author_polygons_preserved':False},'game',today=TODAY)
        row = next(c for c in result['checks'] if c['code']=='ngons')
        self.assertEqual(row['state'],'unverifiable')
        self.assertFalse(result['coverage_complete'])
        self.assertNotEqual(result['grade'],'ready')

    def test_material_and_texture_limits(self):
        value = mesh(materials=['A','B'],textures=[{'size':[8192,2048],'missing':False},{'size':[0,0],'missing':True}])
        codes = {c['code'] for c in self.report(value)['findings']}
        self.assertTrue({'multiple_materials','texture_budget','missing_texture'} <= codes)

    def test_1024_is_not_universal_rejection(self):
        result = self.report(mesh(textures=[{'size':[2048,2048],'missing':False}]))
        self.assertFalse(any(c['code']=='texture_budget' for c in result['findings']))

    def test_layered_dimensions_declared_scale(self):
        result = inspect({'meshes':[mesh()], 'author_polygons_preserved':True},'layered',studs_per_unit=9,today=TODAY)
        self.assertTrue(any(c['code']=='dimensions' for c in result['findings']))
        self.assertTrue(any(c['code']=='rig' and c['state']=='unverifiable' for c in result['checks']))

    def test_unknown_pivot_and_transform_are_not_guessed(self):
        for code in ['origin','author_transforms','names','supplied_normals']:
            row = next(c for c in self.report(mesh())['checks'] if c['code']==code)
            self.assertEqual(row['state'],'unverifiable')

    def test_multi_mesh_and_triangle_scope(self):
        data = {'meshes':[mesh(faces=FACES*500),mesh(faces=FACES*500)],'author_polygons_preserved':True}
        result = inspect(data,'rigid',today=TODAY)
        budget = next(c for c in result['checks'] if c['code']=='triangle_budget')
        self.assertEqual(budget['state'],'pass')  # Exactly 4000.
        data['meshes'][1]['faces'].append(FACES[0])
        budget = next(c for c in inspect(data,'rigid',today=TODAY)['checks'] if c['code']=='triangle_budget')
        self.assertEqual(budget['state'],'fail')
        self.assertEqual(budget['severity'],'blocks')

    def test_severity_order_and_no_invented_lesson(self):
        result = self.report(mesh(faces=[*FACES,FACES[0]]))
        severities = [f['severity'] for f in result['findings']]
        self.assertEqual(severities,sorted(severities,key={'blocks':0,'warns':1,'tip':2}.get))
        self.assertTrue(all(c['lesson'] is None for c in result['checks']))

    def test_invalid_coordinates_and_indices(self):
        for value in [mesh(vertices=[(float('nan'),0,0),*VERTICES[1:]]),mesh(faces=[(0,1,99)])]:
            with self.assertRaises(ValueError): measure(value)

    def test_rules_freshness_boundary(self):
        self.assertTrue(rules(TODAY+timedelta(days=180)))
        for day in [TODAY-timedelta(days=1),TODAY+timedelta(days=181)]:
            with self.assertRaises(ValueError): rules(day)

    def test_actual_table_is_current(self):
        self.assertTrue(rules())  # Intentionally expires rather than freezing the clock in CI.

    def test_real_glb_and_corrupted_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'clean.glb'
            glb(path)
            self.assertEqual(validate_envelope(path),'.glb')
            path.write_bytes(b'corrupted')
            with self.assertRaises(ValueError): validate_envelope(path)


if __name__ == '__main__':
    unittest.main()
