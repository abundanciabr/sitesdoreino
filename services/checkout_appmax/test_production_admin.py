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
            return {'data': {'parcels': {}}}
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
        for suffix in ('', '/checkout', '/assets/checkout.css', '/autorizar', '/retorno', '/validacao', '/webhooks'):
            result = self.request(module.PANEL + suffix)
            self.assertEqual(result[0]['status'], 200, suffix)
            self.assertNotIn(b'/login', result[1]['body'])
        self.assertFalse(self.calls)

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

    def test_preview_cannot_submit_personal_or_card_data(self):
        page = self.app.preview().decode()
        self.assertNotIn('<script', page)
        self.assertNotIn('__CHECKOUT_CONFIG__', page)
        self.assertIn('R$ 27,00', page)
        import re
        for tag in re.findall(r'<(?:input|select|button)\b[^>]*>', page):
            self.assertIn('disabled', tag)

    def test_order_and_payment_creation_blocked_before_provider(self):
        for operation in ('/api/sessoes/11111111-1111-4111-8111-111111111111/pedido', '/api/pedidos/22222222-2222-4222-8222-222222222222/cartao'):
            result = self.request(module.PANEL + '/checkout' + operation, method='POST')
            self.assertEqual(result[0]['status'], 409)
        self.assertFalse(self.calls)

    def test_authorization_retains_form_integrity_without_site_login(self):
        result = self.request(module.PANEL + '/autorizar', cookie=self.cookie, method='POST', body=b'csrf=invalid', origin=module.ORIGIN)
        self.assertEqual(result[0]['status'], 403)
        self.assertFalse(self.calls)

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
