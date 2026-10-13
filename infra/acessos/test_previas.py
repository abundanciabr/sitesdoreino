import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('previas',Path(__file__).with_name('previas.py'))
p=importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class RestrictedPreviewTests(unittest.TestCase):
    def plan(self):
        return {'runtime':'node','files':{'index.html':'infra/previas/exemplos/index.html','tests/check.cjs':'infra/previas/exemplos/check.cjs'},'test':'tests/check.cjs','page':'index.html'}

    def test_commands_cannot_be_shell(self):
        for args in [['exec','id'], ['aplicar','trilha','a'*40,'nova','--privileged'], ['aplicar','../x','a'*40,'nova'], ['consultar','/etc/shadow']]:
            self.assertFalse(p.valid(args))

    def test_frozen_secret_traversal_sources_denied(self):
        for source in ['services/aplicacao/app.py','services/checkout/main.py','packages/site_errors/a.py','services/funil/.env','services/funil/config/settings.py','services/cursos/satisfacao.py','services/funil/../checkout/a.py']:
            plan=self.plan();plan['files']['index.html']=source
            self.assertFalse(p.plan_valid(plan),source)

    def test_target_traversal_and_arguments_denied(self):
        for target in ['/etc/x.py','../x.py','a//b.py','node_modules/x.js','a;id.js']:
            plan=self.plan();plan['files'][target]='infra/previas/exemplos/check.cjs'
            self.assertFalse(p.plan_valid(plan))
        plan=self.plan();plan['test']='--eval';self.assertFalse(p.plan_valid(plan))

    def test_plan_and_idempotent_resume_conflict(self):
        self.assertTrue(p.plan_valid(self.plan()))
        with tempfile.TemporaryDirectory() as temp,patch.object(p,'ROOT',Path(temp)):
            args=['aplicar','operacao','a'*40,'nova']
            one=p.dispatch(args)
            self.assertEqual(one,p.dispatch(args))
            self.assertEqual(one,p.dispatch(['retomar',one['id']]))
            self.assertEqual(p.dispatch(['aplicar','outra','b'*40,'nova'])['motivo'],'operacao_em_andamento')

    def test_failed_test_restores_actual_active_pointer_and_keeps_backup(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(p,'ROOT',Path(temp)),patch.object(p,'CONFIG',Path(temp)/'cfg'):
            old='f'*24
            (p.ROOT/'releases'/old).mkdir(parents=True)
            (p.ROOT/'releases'/old/'index.html').write_text('anterior')
            p.atomic(p.ROOT/'active.json',{'operacao':old})
            record=p.dispatch(['aplicar','operacao','a'*40,old])
            def fetch(c,path):
                import json
                return json.dumps(self.plan()).encode() if 'candidatas' in path else b'candidate'
            def fail(r,plan,stage):
                self.assertEqual(p.read(p.ROOT/'active.json')['operacao'],r['id'])
                return 1
            with patch.object(p,'fetch',side_effect=fetch),patch.object(p,'sandbox',side_effect=fail):
                p.execute(record)
            self.assertEqual(p.read(p.ROOT/'active.json')['operacao'],old)
            self.assertEqual(record['estado'],'recuperada')
            self.assertEqual((Path(record['backup'])/'codigo/index.html').read_text(),'anterior')

    def test_interrupted_activation_recovers_without_rerunning_candidate(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(p,'ROOT',Path(temp)),patch.object(p,'sandbox') as test:
            r=p.dispatch(['aplicar','operacao','b'*40,'nova'])
            r['estado']='testando';p.atomic(p.ROOT/'active.json',{'operacao':r['id']})
            p.execute(r)
            self.assertEqual(r['estado'],'recuperada');test.assert_not_called()
            self.assertNotIn('operacao',p.read(p.ROOT/'active.json'))


if __name__=='__main__':
    unittest.main()
