import unittest
from copy import deepcopy
from io import BytesIO
from app import Application, PATH, STATES, allowed, current_state, render, CONTENT

IDENTITY = {'autenticado': True, 'id': 'fixture-one', 'email': 'fixture@example.invalid'}
COURSE = {'site_id': 'school', 'produto_id': 'course-product'}
ENROLLMENTS = [{'site_id': 'school', 'product_id': 'course-product'}]
PROGRESS = {'caminho': 'ugc', 'atual': {'ordem': 4, 'nome': 'Vermelha'},
            'proxima': {'ordem': 5, 'nome': 'Verde', 'conquista': 'Alterar e salvar a cor de uma parte do acessório.'}}


class Provider:
    def __init__(self, identity=None, enrollments=None):
        self.identity = IDENTITY if identity is None else identity
        self.enrollments = ENROLLMENTS if enrollments is None else enrollments
        self.progress_calls = []

    def access(self, cookie):
        return self.identity, self.enrollments, COURSE

    def progress(self, person, site):
        self.progress_calls.append((person, site))
        return deepcopy(PROGRESS)


def request(provider, **overrides):
    env = {'PATH_INFO': PATH, 'REQUEST_METHOD': 'GET', 'QUERY_STRING': '', 'HTTP_COOKIE': 'opaque-fixture'} | overrides
    result = {}
    def start(status, headers):
        result.update(status=int(status.split()[0]), headers=dict(headers))
    result['body'] = b''.join(Application(provider)(env, start)).decode()
    return result


class AccessTests(unittest.TestCase):
    def test_visitor_receives_login_without_manual_or_progress(self):
        p = Provider({'autenticado': False})
        r = request(p)
        self.assertEqual(r['status'], 401)
        self.assertIn('Entrar na minha conta', r['body'])
        self.assertNotIn('Seu percurso em seis passos', r['body'])
        self.assertFalse(p.progress_calls)

    def test_other_course_and_other_school_cannot_read_content(self):
        for rows in ([], [{'site_id': 'school', 'product_id': 'different'}],
                     [{'site_id': 'another', 'product_id': 'course-product'}],
                     [{'site_id': 'school', 'product_id': ''}]):
            with self.subTest(rows=rows):
                p = Provider(enrollments=rows)
                r = request(p, QUERY_STRING='pessoa=other&produto=course-product&admin=1')
                self.assertEqual(r['status'], 403)
                self.assertNotIn('Um passo de cada vez.', r['body'])
                self.assertFalse(p.progress_calls)

    def test_course_access_and_identity_are_both_required(self):
        self.assertTrue(allowed(IDENTITY, ENROLLMENTS, COURSE))
        self.assertFalse(allowed(IDENTITY | {'id': ''}, ENROLLMENTS, COURSE))
        self.assertFalse(allowed(IDENTITY | {'autenticado': False}, ENROLLMENTS, COURSE))
        self.assertFalse(allowed(IDENTITY, ENROLLMENTS, COURSE | {'produto_id': ''}))

    def test_staff_role_does_not_bypass_enrollment(self):
        r = request(Provider(IDENTITY | {'papel': 'admin'}, []))
        self.assertEqual(r['status'], 403)

    def test_authorized_content_uses_only_session_person(self):
        p = Provider()
        r = request(p, QUERY_STRING='pessoa_id=another&site_id=another&caminho=jogo')
        self.assertEqual(r['status'], 200)
        self.assertEqual(p.progress_calls, [('fixture-one', 'school')])
        self.assertIn('consultando outro caminho', r['body'])
        self.assertIn('Visual do jogo', r['body'])

    def test_service_failure_is_closed(self):
        p = Provider()
        p.access = lambda cookie: (_ for _ in ()).throw(RuntimeError('private response'))
        r = request(p)
        self.assertEqual(r['status'], 503)
        self.assertNotIn('private response', r['body'])
        self.assertFalse(p.progress_calls)

    def test_revocation_checked_again_on_each_request(self):
        p = Provider()
        self.assertEqual(request(p)['status'], 200)
        p.enrollments = []
        self.assertEqual(request(p)['status'], 403)

    def test_no_shared_cache_on_every_access_result(self):
        for provider in (Provider(), Provider({'autenticado': False}), Provider(enrollments=[])):
            r = request(provider)
            self.assertIn('no-store', r['headers']['Cache-Control'])
            self.assertEqual(r['headers']['Vary'], 'Cookie')
            self.assertIn('noindex', r['headers']['X-Robots-Tag'])

    def test_write_methods_and_unrecognized_paths_do_not_read_progress(self):
        p = Provider()
        self.assertEqual(request(p, REQUEST_METHOD='POST')['status'], 405)
        self.assertEqual(request(p, PATH_INFO=PATH + '/content.json')['status'], 404)
        self.assertFalse(p.progress_calls)


class ContentTests(unittest.TestCase):
    def test_three_blocks_six_steps_and_four_paths(self):
        self.assertEqual(len(CONTENT['steps']), 6)
        for step in CONTENT['steps'][3:]:
            self.assertEqual(set(step['variants']), {'freelancer', 'ugc', 'jogo', 'aprender'})
        for path in ('freelancer', 'ugc', 'jogo', 'aprender'):
            text = render(PROGRESS | {'caminho': path})
            self.assertEqual(text.count('class="step"'), 6)
            self.assertIn('BLOCO 1', text)
            self.assertIn('BLOCO 2', text)
            self.assertIn('BLOCO 3', text)
            self.assertNotIn('[CONFERIR', text)
            self.assertNotIn('[objetivo registrado]', text)
            self.assertIn('admin incluir os links', text)

    def test_dynamic_text_is_escaped(self):
        p = deepcopy(PROGRESS)
        p['atual']['nome'] = '<script>bad()</script>'
        self.assertNotIn('<script>bad()', render(p))

    def test_five_states_follow_evidence(self):
        self.assertEqual(current_state(PROGRESS), STATES[0])
        self.assertEqual(current_state(PROGRESS | {'pending': {'5': {'estado': 'pendente'}}}), STATES[1])
        p = deepcopy(PROGRESS)
        p['proxima']['avaliacao_resultado'] = 'incompleta'
        self.assertEqual(current_state(p), STATES[2])
        p['proxima']['avaliacao_resultado'] = 'falha'
        self.assertEqual(current_state(p), STATES[3])
        self.assertEqual(current_state(PROGRESS | {'proxima': None}), STATES[4])

    def test_pending_does_not_concede_next_belt(self):
        p = deepcopy(PROGRESS)
        p['pending'] = {'5': {'estado': 'pendente'}}
        self.assertIn('Aguardando análise', render(p))
        self.assertIn('Vermelha', render(p))
        self.assertEqual(p['atual']['ordem'], 4)

    def test_sandbox_technical_failure_is_not_rejection(self):
        p = PROGRESS | {'caminho': 'freelancer', 'sandbox_avaliacoes': [{'atual': True, 'estado': 'falha'}]}
        self.assertEqual(current_state(p), STATES[3])
        p['sandbox_avaliacoes'][0]['estado'] = 'processando'
        self.assertEqual(current_state(p), STATES[1])


if __name__ == '__main__':
    unittest.main()
