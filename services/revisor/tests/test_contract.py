from pathlib import Path
import unittest

import yaml

from revisor.engine import inspect
from fixtures import mesh


class ContractTests(unittest.TestCase):
    def test_contract_report_matches_engine_fields(self):
        contract = yaml.safe_load(Path(__file__).resolve().parents[1].joinpath('revisor/openapi.yaml').read_text('utf-8'))
        schema = contract['components']['schemas']['Report']
        result = inspect({'meshes':[mesh()], 'author_polygons_preserved':False},'game')
        self.assertEqual(set(schema['required']),set(result))
        check_schema = contract['components']['schemas']['Check']
        for row in result['checks']:
            self.assertEqual(set(check_schema['required']),set(row))
            self.assertIn(row['state'],check_schema['properties']['state']['enum'])

    def test_only_first_layer_endpoints_and_student_destination(self):
        contract = yaml.safe_load(Path(__file__).resolve().parents[1].joinpath('revisor/openapi.yaml').read_text('utf-8'))
        self.assertEqual(contract['servers'][0]['url'],'https://meshcraft.top/ferramentas/revisor-de-modelos-3d')
        self.assertFalse(any('admin' in route or 'tutor' in route for route in contract['paths']))
        self.assertEqual(contract['info']['version'],'1.0.0')


if __name__ == '__main__':
    unittest.main()
