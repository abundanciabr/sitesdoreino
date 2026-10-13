import asyncio
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('production_admin', Path(__file__).with_name('production_admin.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProductionPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'env').mkdir()
        (self.root / 'controle.privado').write_bytes(b'test-key')
        (self.root / 'instalacao.json').write_text(json.dumps({'status': 'preparacao', 'app_id': '1888', 'app_uuid': 'c682b36a-7687-402f-a94d-7e87f31adaba'}))
        (self.root / 'env/pagamentos.env').write_text('APPMAX_APP_CLIENT_ID=application-key\nAPPMAX_APP_CLIENT_SECRET=private-application-key\n')
        (self.root / 'env/checkout.env').write_text('')
        self.calls = []
        self.fallback_calls = []
        async def fallback(scope, receive, send):
            self.fallback_calls.append(scope['path'])
        self.app = module.ProductionAdmin(fallback, Path(__file__).with_name('assets'), self.root, api_call=self.provider)
        self.nonce = 'a' * 64
        self.cookie = module.FLOW_COOKIE + '=' + self.nonce

    def tearDown(self):
        self.temp.cleanup()

    def provider(self, url, body, token='', **kwargs):
        self.calls.append(url)
        if url == module.AUTH:
            return {'access_token': 'temporary-test-token'}
        if url.endswith('/app/authorize'):
            return {'data': {'token': 'singleuseticket'}}
        if url.endswith('/app/client/generate'):
            self.app.health({'app_id': 1888, 'external_key': self.app.state()['external_key']})
            return {'data': {'client': {'client_id': 'merchant-key', 'client_secret': 'private-merchant-key'}}}
        if url.endswith('/installments'):
            return {'data': {'parcels': {'1': 27}}}
        raise AssertionError('Unexpected provider operation')

    def request(self, path, *, cookie='', method='GET', body=b'', origin='', query=b''):
        result = []
        async def receive():
            return {'type': 'http.request', 'body': body}
        async def send(message):
            result.append(message)
        headers = [(b'cookie', cookie.encode()), (b'origin', origin.encode())]
        asyncio.run(self.app({'type': 'http', 'path': path, 'method': method, 'headers': headers, 'query_string': query}, receive, send))
        return result

    def test_all_published_urls_open_without_login(self):
        self.assertNotIn('/admin/', module.PANEL)
        for suffix in ('', '/homologacao', '/checkout', '/assets/checkout.css', '/autorizar', '/retorno', '/validacao', '/webhooks'):
            result = self.request(module.PANEL + suffix)
            self.assertEqual(result[0]['status'], 200, suffix)
            self.assertNotIn(b'/login', result[1]['body'])
        self.assertFalse(self.calls)

    def test_support_handoff_has_no_credentials_and_never_starts_installation(self):
        self.app.begin({}, self.nonce)
        self.app.finish('singleuseticket')
        self.calls.clear()
        before = (self.root/'instalacao.json').read_bytes()
        result = self.request(module.PANEL+'/homologacao')
        self.assertEqual(result[0]['status'], 200)
        self.assertEqual((self.root/'instalacao.json').read_bytes(), before)
        self.assertFalse(self.calls)
        page = result[1]['body']
        for value in ('private-application-key', 'private-merchant-key', 'merchant-key', 'singleuseticket', self.nonce):
            self.assertNotIn(value.encode(), page)
        self.assertIn(b'homologacao@appmax.com.br', page)
        self.assertNotIn(b'<form', page)

    def test_public_panel_has_existing_ids_and_no_secrets(self):
        result = self.request(module.PANEL)
        self.assertEqual(result[0]['status'], 200)
        page = result[1]['body'].decode()
        self.assertIn('c682b36a-7687-402f-a94d-7e87f31adaba', page)
        self.assertNotIn('private-application-key', page)
        self.assertIn('R$ 27,00', page)
        self.assertNotIn('/admin/', page)
        response_cookie = dict(result[0]['headers'])[b'set-cookie'].decode()
        self.assertTrue(module.flow_cookie(response_cookie))
        self.assertIn('Secure; HttpOnly; SameSite=Lax', response_cookie)
        self.assertEqual(dict(result[0]['headers'])[b'referrer-policy'], b'same-origin')

    def test_authorization_redirect_and_callback_do_not_refer_the_ticket(self):
        import urllib.parse
        data = urllib.parse.urlencode({'csrf': self.app.csrf(self.nonce)}).encode()
        redirect = self.request(module.PANEL+'/autorizar', cookie=self.cookie, method='POST', body=data, origin=module.ORIGIN)
        self.assertEqual(redirect[0]['status'], 303)
        self.assertEqual(dict(redirect[0]['headers'])[b'referrer-policy'], b'no-referrer')
        callback = self.request(module.PANEL+'/retorno', query=b'token=singleuseticket')
        self.assertEqual(dict(callback[0]['headers'])[b'referrer-policy'], b'no-referrer')

    def test_preview_cannot_submit_personal_or_card_data(self):
        page = self.app.preview().decode()
        self.assertNotIn('checkout.js', page)
        self.assertNotIn('__CHECKOUT_CONFIG__', page)
        self.assertIn('R$ 27,00', page)
        self.assertIn('homologacao.js', page)
        import re
        for tag in re.findall(r'<(?:select|button)\b[^>]*>', page):
            if 'homologacao-conferir' in tag:
                continue
            self.assertIn('disabled', tag)
        for tag in re.findall(r'<input\b[^>]*id="card-[^"]+"[^>]*>', page):
            self.assertIn('disabled', tag)

    def test_pending_conference_is_public_and_does_not_call_provider(self):
        result = self.request(module.PANEL+'/conferencia')
        self.assertEqual(result[0]['status'], 200)
        value = json.loads(result[1]['body'])
        self.assertFalse(value['instalacao_concluida'])
        self.assertFalse(value['pagamentos_ativados'])
        self.assertFalse(self.calls)

    def test_production_conference_only_authenticates_and_calculates(self):
        self.app.begin({}, self.nonce)
        self.app.finish('singleuseticket')
        self.calls.clear()
        result = self.request(module.PANEL+'/conferencia')
        self.assertEqual(result[0]['status'], 200)
        value = json.loads(result[1]['body'])
        self.assertTrue(value['autenticacao_lojista'])
        self.assertTrue(value['parcelas_conferidas'])
        self.assertFalse(value['pagamentos_ativados'])
        self.assertNotIn(b'private-merchant-key', result[1]['body'])
        self.assertEqual(self.calls, [module.AUTH, module.API+'/v1/payments/installments'])
        self.request(module.PANEL+'/conferencia')
        self.assertEqual(len(self.calls), 2)

    def test_foreign_origin_still_cannot_start_installation(self):
        import urllib.parse
        data = urllib.parse.urlencode({'csrf': self.app.csrf(self.nonce)}).encode()
        for origin in ('https://another-site.invalid', '', 'null'):
            result = self.request(module.PANEL+'/autorizar', cookie=self.cookie, method='POST', body=data, origin=origin)
            self.assertEqual(result[0]['status'], 403)
        self.assertFalse(self.calls)

    def test_order_and_payment_creation_blocked_before_provider(self):
        for operation in ('/api/sessoes/11111111-1111-4111-8111-111111111111/pedido', '/api/pedidos/22222222-2222-4222-8222-222222222222/cartao'):
            result = self.request(module.PANEL + '/checkout' + operation, method='POST')
            self.assertEqual(result[0]['status'], 409)
        self.assertFalse(self.calls)

    def test_authorization_retains_form_integrity_without_site_login(self):
        result = self.request(module.PANEL + '/autorizar', cookie=self.cookie, method='POST', body=b'csrf=invalid', origin=module.ORIGIN)
        self.assertEqual(result[0]['status'], 403)
        self.assertFalse(self.calls)

    def test_unrelated_cookie_format_cannot_break_installation(self):
        mixed = 'analytics={x:1}; ' + self.cookie + '; other=value'
        self.assertEqual(module.flow_cookie(mixed), self.nonce)
        self.assertEqual(module.flow_cookie(self.cookie + '; ' + module.FLOW_COOKIE + '=' + 'b'*64), '')

    def test_failure_diagnostic_has_no_cookie_or_form_secret(self):
        self.request(module.PANEL+'/autorizar', cookie=self.cookie, method='POST', body=b'csrf=invalid', origin=module.ORIGIN)
        data = (self.root/'ultimo-formulario.json').read_text()
        self.assertNotIn(self.nonce, data)
        self.assertNotIn('invalid', data)
        self.assertEqual(json.loads(data)['motivo'], 'formulario_vencido_ou_incompleto')

    def test_installation_preserves_pair_and_reuses_it(self):
        self.app.begin({}, self.nonce)
        self.app.finish('singleuseticket')
        self.assertEqual(self.app.state()['status'], 'preparada')
        self.assertEqual(self.app.state()['merchant']['client_secret'], 'private-merchant-key')
        self.app.finish(None)
        self.assertEqual(self.calls.count(module.API + '/app/client/generate'), 1)
        self.assertEqual(self.calls.count(module.API + '/app/authorize'), 1)
        self.assertIn('private-merchant-key', (self.root / 'env/pagamentos.env').read_text())
        page = self.request(module.PANEL)[1]['body']
        self.assertNotIn(b'private-merchant-key', page)
        self.assertNotIn(b'merchant-key', page)

    def test_public_authorization_form_uses_only_existing_application(self):
        import urllib.parse
        data = urllib.parse.urlencode({'csrf': self.app.csrf(self.nonce), 'app_uuid': 'unrelated-application', 'app_id': '9999'}).encode()
        result = self.request(module.PANEL + '/autorizar', cookie=self.cookie, method='POST', body=data, origin=module.ORIGIN)
        self.assertEqual(result[0]['status'], 303)
        self.assertEqual(self.app.state()['app_id'], '1888')
        self.assertEqual(self.app.state()['app_uuid'], 'c682b36a-7687-402f-a94d-7e87f31adaba')

    def test_old_links_redirect_without_login_and_preserve_callback(self):
        result = self.request(module.OLD_PANEL + '/validacao', method='POST')
        self.assertEqual(result[0]['status'], 307)
        self.assertEqual(dict(result[0]['headers'])[b'location'], (module.PANEL + '/validacao').encode())

    def test_callback_without_origin_browser_cannot_generate_credentials(self):
        self.app.begin({}, self.nonce)
        self.calls.clear()
        result = self.request(module.PANEL + '/retorno', query=b'token=singleuseticket')
        self.assertEqual(result[0]['status'], 200)
        self.assertFalse(self.calls)
        self.assertNotIn(b'singleuseticket', result[1]['body'])

    def test_health_cannot_change_installation_without_active_generation(self):
        result = self.request(module.PANEL + '/validacao', method='POST', body=b'{"app_id":1888}')
        self.assertEqual(result[0]['status'], 422)
        self.assertFalse(self.app.state().get('external_id'))

    def test_existing_public_checkout_still_uses_original_handler(self):
        self.request(module.BASE)
        self.assertEqual(self.fallback_calls, [module.BASE])


if __name__ == '__main__':
    unittest.main()
