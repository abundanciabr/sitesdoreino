"""Public production preparation beside the existing sandbox checkout.

All installation receipts and credentials belong to the isolated copy. The
approved payment source, primary environments and edge routes are not edited.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BASE = "/checkout/curso-primeiros-passos-no-blender"
PANEL = BASE + "/producao"
OLD_PANEL = BASE + "/admin/producao"
FLOW_COOKIE = "meshcraft_appmax_instalacao"
ORIGIN = "https://meshcraft.top"
AUTH = "https://auth.appmax.com.br/oauth2/token"
API = "https://api.appmax.com.br"
SITE = "cc06b8c3-043b-4c06-92c5-5ea624e00586"
LIMIT = 65536


def read_env(path: Path) -> dict:
    out = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        key, sep, value = line.partition("=")
        if sep:
            out[key.strip()] = value.strip().strip("\"'")
    return out


def private_write(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".preparando-" + secrets.token_hex(8))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def vendor(url: str, body: dict, token: str = "", *, form: bool = False) -> dict:
    # Secrets are sent only in the request to the official provider; no body is logged.
    if url not in {AUTH, API + "/app/authorize", API + "/app/client/generate", API + "/v1/payments/installments"}:
        raise RuntimeError("Endereço da Appmax não reconhecido")
    content = urllib.parse.urlencode(body) if form else json.dumps(body)
    import httpx
    headers = {"User-Agent": "curl/8.5.0", "Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        result = httpx.post(url, content=content.encode(), headers=headers, timeout=20, follow_redirects=False)
    except httpx.HTTPError:
        raise RuntimeError("A Appmax não respondeu; a preparação anterior foi preservada") from None
    if result.status_code not in {200, 201}:
        raise RuntimeError("Appmax respondeu HTTP " + str(result.status_code))
    parsed = result.json()
    if not isinstance(parsed, dict):
        raise RuntimeError("Resposta da Appmax não reconhecida")
    return parsed


def flow_cookie(header: str) -> str:
    # Unrelated analytics cookies must not invalidate the installation cookie.
    values = []
    for item in header.split(';'):
        name, separator, value = item.strip().partition('=')
        if separator and name == FLOW_COOKIE:
            value = value.strip('"')
            if len(value) == 64 and all(c in '0123456789abcdef' for c in value):
                values.append(value)
    return values[0] if values and len(set(values)) == 1 else ''


class ProductionAdmin:
    def __init__(self, fallback, assets: Path, root: Path, api_call=vendor):
        self.fallback, self.assets, self.root = fallback, assets, root
        self.api_call = api_call
        self.lock = threading.RLock()
        self.process = None

    def state(self):
        return json.loads((self.root / "instalacao.json").read_text())

    def save(self, state):
        with self.lock:
            path = self.root / "instalacao.json"
            # Keep issued receipts, including failures, instead of starting again.
            if path.exists():
                backup = path.with_name("instalacao-anterior-" + str(time.time_ns()) + ".privado")
                private_write(backup, path.read_bytes())
            private_write(path, json.dumps(state, ensure_ascii=False).encode())

    def csrf(self, cookie, stamp=None):
        stamp = int(time.time()) if stamp is None else stamp
        key = (self.root / "controle.privado").read_bytes()
        digest = hmac.new(key, (str(stamp) + "\0" + cookie).encode(), hashlib.sha256).hexdigest()
        return str(stamp) + "." + digest

    def valid_csrf(self, cookie, supplied):
        try:
            stamp = int(supplied.split(".", 1)[0])
            return 0 <= time.time() - stamp < 3600 and hmac.compare_digest(supplied, self.csrf(cookie, stamp))
        except Exception:
            return False

    def app_token(self):
        env = read_env(self.root / "env/pagamentos.env")
        data = self.api_call(AUTH, {"grant_type": "client_credentials",
                                   "client_id": env["APPMAX_APP_CLIENT_ID"],
                                   "client_secret": env["APPMAX_APP_CLIENT_SECRET"]}, form=True)
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("A autenticação do aplicativo não foi concluída")
        return token

    def begin(self, form, cookie):
        state = self.state()
        if state.get("merchant"):
            self.finish(None)
            return PANEL
        app_uuid = str(uuid.UUID(state["app_uuid"]))
        numerical = state["app_id"]
        if not numerical.isdecimal() or int(numerical) < 1:
            raise RuntimeError("Copie o ID numérico do aplicativo já existente")
        token = self.app_token()
        pending = {"app_uuid": app_uuid, "app_id": numerical,
                   "external_key": "meshcraft-producao-" + secrets.token_hex(16),
                   "external_id": "", "created_at": int(time.time()),
                   "cookie_hash": hashlib.sha256(cookie.encode()).hexdigest()}
        state.update(pending)
        state["status"] = "autorizacao"
        self.save(state)
        data = self.api_call(API + "/app/authorize", {
            "app_id": app_uuid, "external_key": pending["external_key"],
            "url_callback": ORIGIN + PANEL + "/retorno", "domain_name": "meshcraft.top"}, token)
        ticket = data.get("data", {}).get("token")
        if not isinstance(ticket, str) or not ticket.isalnum() or len(ticket) > 128:
            raise RuntimeError("A Appmax não devolveu o endereço de autorização")
        state["ticket"] = ticket
        self.save(state)
        return "https://admin.appmax.com.br/appstore/integration/" + ticket

    def health(self, payload):
        with self.lock:
            state = self.state()
            if state.get("status") != "gerando" or time.time() - state.get("created_at", 0) > 3600:
                raise RuntimeError("Não existe instalação em andamento nesta cópia")
            if str(payload.get("app_id")) != state.get("app_id"):
                raise RuntimeError("Aplicativo diferente da instalação preparada")
            external_key = payload.get("external_key") or payload.get("client_key")
            if external_key and external_key != state.get("external_key"):
                raise RuntimeError("Instalação diferente da preparação atual")
            state["external_id"] = str(uuid.uuid4())
            self.save(state)
            return {"external_id": state["external_id"], "alias": "Meshcraft — produção"}

    def finish(self, ticket):
        state = self.state()
        merchant = state.get("merchant")
        if not merchant:
            if not ticket or ticket != state.get("ticket"):
                raise RuntimeError("Volte pelo botão de autorização desta preparação")
            state["status"] = "gerando"
            self.save(state)
            result = self.api_call(API + "/app/client/generate", {"token": ticket}, self.app_token())
            merchant = result.get("data", {}).get("client")
            if not isinstance(merchant, dict) or not all(isinstance(merchant.get(k), str) and merchant[k] for k in ("client_id", "client_secret")):
                raise RuntimeError("A Appmax não emitiu as credenciais do lojista")
            # Persist the one-time pair BEFORE any subsequent provider call.
            state = self.state()
            state["merchant"] = {k: merchant[k] for k in ("client_id", "client_secret")}
            state["status"] = "credenciais_recebidas"
            self.save(state)
        if not state.get("external_id"):
            raise RuntimeError("A URL de validação deve apontar para esta cópia isolada")
        auth = self.api_call(AUTH, {"grant_type": "client_credentials", **merchant}, form=True)
        token = auth.get("access_token")
        if not token:
            raise RuntimeError("Credenciais preservadas; a autenticação do lojista está pendente")
        self.api_call(API + "/v1/payments/installments", {"installments": 12, "total_value": 2700, "settings": True}, token)
        for name in ("pagamentos", "checkout"):
            path = self.root / "env" / (name + ".env")
            values = read_env(path)
            values.update({"APPMAX_MERCHANT_CLIENT_ID": merchant["client_id"],
                           "APPMAX_MERCHANT_CLIENT_SECRET": merchant["client_secret"],
                           "APPMAX_EXTERNAL_ID": state["external_id"],
                           "APPMAX_INSTALACOES": json.dumps({state["app_id"]: {"alias": "Meshcraft", "sites": [SITE], "app_uuid": state["app_uuid"]}})})
            private_write(path, ("\n".join(k + "=" + v for k, v in values.items()) + "\n").encode())
        state["status"] = "preparada"
        state.pop("ticket", None)
        self.save(state)

    def preview(self):
        state = self.state()
        document = (self.assets / "checkout.html").read_text()
        # Before consent, show the actual checkout layout without a payment action.
        import re
        document = re.sub(r'<script\b[^>]*>.*?</script>', '', document, flags=re.S | re.I)
        document = document.replace(BASE + "/assets/", PANEL + "/assets/")
        document = re.sub(r'<(input|select|button)\b', r'<\1 disabled', document, flags=re.I)
        document = re.sub(r'(<[^>]+id="product-price"[^>]*>).*?(</[^>]+>)', r'\1R$ 27,00 à vista\2', document, flags=re.S)
        document = re.sub(r'(<[^>]+id="order-total"[^>]*>).*?(</[^>]+>)', r'\1R$ 27,00\2', document, flags=re.S)
        document = re.sub(r'(<button[^>]+id="purchase-button"[^>]*>).*?(</button>)', r'\1Prévia sem cobrança\2', document, flags=re.S)
        document = document.replace('<body>', '<body><div style="padding:16px;background:#fff2cf;text-align:center">Prévia pública de produção — nenhuma cobrança.<br><a href="' + PANEL + '">Voltar à instalação da Appmax</a></div>')
        return document.encode()

    def ensure_runtime(self):
        if self.state().get("status") != "preparada":
            raise RuntimeError("A loja ainda precisa ser autorizada em produção")
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                env = dict(os.environ)
                env.update({"APLICACAO_ENV_DIR": str(self.root / "env"), "APPMAX_PRODUCTION_CHILD": "1", "PYTHONDONTWRITEBYTECODE": "1"})
                self.process = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn", "production_runtime:application", "--host", "127.0.0.1", "--port", "8001", "--no-access-log"], cwd=self.assets.parent, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8001/estado", timeout=1) as response:
                    if response.status == 200:
                        return
            except Exception:
                time.sleep(.1)
        raise RuntimeError("A instalação foi preservada; o checkout de produção ainda está iniciando")

    def proxy(self, path, method, content, headers):
        self.ensure_runtime()
        safe_headers = {"Host": "meshcraft.top"}
        for name in (b"authorization", b"content-type"):
            if name in headers:
                safe_headers[name.decode()] = headers[name]
        request = urllib.request.Request("http://127.0.0.1:8001" + path, data=content if method == "POST" else None, method=method, headers=safe_headers)
        try:
            response = urllib.request.urlopen(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            data = response.read()
            content_type = response.headers.get("Content-Type", "application/json")
            if "text/html" in content_type or "javascript" in content_type:
                data = data.replace(BASE.encode(), (PANEL + "/checkout").encode())
            return response.status, data, content_type

    def panel(self, cookie, message=""):
        state = self.state()
        status = {"preparacao": "Aplicativo reaproveitado. Falta autorizar a loja em produção.",
                  "autorizacao": "Conclua a autorização da loja no painel da Appmax.",
                  "gerando": "Aguardando a validação da instalação pela Appmax.",
                  "credenciais_recebidas": "Credenciais emitidas e preservadas. Falta conferir a instalação.",
                  "preparada": "Instalação de produção concluída. Cobranças continuam desabilitadas nesta prévia."}.get(state.get("status"), "Preparação em andamento")
        esc = html.escape
        urls = {"Host e URL de webhook": ORIGIN + PANEL + "/webhooks", "URL do sistema": ORIGIN + PANEL, "URL de validação": ORIGIN + PANEL + "/validacao", "Retorno da autorização": ORIGIN + PANEL + "/retorno"}
        fields = ''.join('<p><strong>' + name + '</strong><br><code>' + value + '</code></p>' for name, value in urls.items())
        action = "Conferir a instalação já autorizada" if state.get("merchant") else "Autorizar minha loja na Appmax de produção"
        return ('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Appmax de produção · Meshcraft</title>'
                '<style>body{font:17px/1.6 system-ui;background:#f3f5fa;color:#182037;margin:0}main{max-width:820px;margin:40px auto;padding:30px;background:white;border-radius:18px}h1{line-height:1.2}code{overflow-wrap:anywhere}input{display:block;width:95%;padding:12px;margin:8px 0 20px;border:1px solid #acb5c9;border-radius:8px}button,.link{display:inline-block;padding:13px 20px;border:0;border-radius:8px;background:#164bd5;color:white;text-decoration:none;cursor:pointer}.notice{padding:18px;background:#edf3ff;border-radius:10px}.error{color:#ad2831}small{color:#56617a}</style><main>'
                '<a href="/curso-primeiros-passos-no-blender">← Página do produto</a><h1>Appmax de produção</h1><p>Curso Primeiros Passos com 3D no Blender · <strong>R$ 27,00</strong></p>'
                '<p class="notice">' + esc(status) + '</p><p class="error">' + esc(message) + '</p>'
                '<p>As credenciais do aplicativo já estão guardadas. Esta preparação usa uma cópia isolada e preserva o Mercado Pago aprovado.</p>'
                '<p><a class="link" href="' + PANEL + '/checkout">Abrir prévia do checkout de R$ 27</a></p>'
                '<h2>O passo para autorizar a loja</h2><p>Abra o aplicativo já existente em <a href="https://appstore.appmax.com.br" target="_blank" rel="noreferrer">https://appstore.appmax.com.br</a>. Em Desenvolver, confira os endereços desta cópia:</p>' + fields +
                '<p>Use o UUID e o ID numérico desse mesmo aplicativo. Clique no botão abaixo e, na Appmax, selecione a loja de produção que você já possui e confirme a instalação. O retorno salva as credenciais automaticamente; não é preciso copiá-las.</p>'
                '<form method="post" action="' + PANEL + '/autorizar"><input type="hidden" name="csrf" value="' + self.csrf(cookie) + '"><label>UUID público do aplicativo existente<input name="app_uuid" value="' + esc(state.get("app_uuid", "")) + '" readonly></label><label>ID numérico do mesmo aplicativo<input name="app_id" value="' + esc(state.get("app_id", "")) + '" readonly></label><button>' + action + '</button></form>'
                '<p><small>Esta tela não cria compras. O produto e o checkout públicos continuam como estão até a autorização para disponibilizar produção à homologação.</small></p></main></html>').encode()

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        old_path = path == OLD_PANEL or path.startswith(OLD_PANEL + "/")
        if scope.get("type") != "http" or not (old_path or path == PANEL or path.startswith(PANEL + "/")):
            return await self.fallback(scope, receive, send)
        headers = {k.lower(): v.decode("latin1") for k, v in scope.get("headers", [])}
        method = scope.get("method")
        cookie = flow_cookie(headers.get(b"cookie", ""))
        async def reply(status, body=b"", content_type="text/html; charset=utf-8", location=None, new_cookie=None):
            response = [(b"content-type", content_type.encode()), (b"cache-control", b"no-store"), (b"referrer-policy", b"no-referrer"), (b"x-content-type-options", b"nosniff"), (b"x-robots-tag", b"noindex, nofollow")]
            if location:
                response.append((b"location", location.encode()))
            if new_cookie:
                response.append((b"set-cookie", (FLOW_COOKIE + "=" + new_cookie + "; Path=" + PANEL + "; Max-Age=7200; Secure; HttpOnly; SameSite=Lax").encode()))
            await send({"type": "http.response.start", "status": status, "headers": response})
            await send({"type": "http.response.body", "body": body})
        if old_path:
            query = scope.get("query_string", b"")
            location = PANEL + path[len(OLD_PANEL):] + ("?" + query.decode() if query else "")
            return await reply(307, location=location)
        async def body():
            data = bytearray()
            while True:
                msg = await receive()
                if msg.get("type") != "http.request":
                    raise RuntimeError("Requisição interrompida")
                data.extend(msg.get("body", b""))
                if len(data) > LIMIT:
                    raise RuntimeError("Requisição muito grande")
                if not msg.get("more_body"):
                    return bytes(data)
        if path in {PANEL + "/validacao", PANEL + "/webhooks"} and method == "GET":
            return await reply(200, json.dumps({"url": ORIGIN + path, "metodo": "POST", "login_necessario": False}).encode(), "application/json")
        if path == PANEL + "/validacao" and method == "POST":
            try:
                result = self.health(json.loads(await body()))
                return await reply(200, json.dumps(result).encode(), "application/json")
            except Exception:
                return await reply(422, b'{"erro":"instalacao_nao_preparada"}', "application/json")
        if path == PANEL + "/webhooks":
            if method != "POST" or self.state().get("status") != "preparada":
                return await reply(409, b'{"erro":"instalacao_pendente"}', "application/json")
            try:
                result = await asyncio.to_thread(self.proxy, "/api/pagamentos/appmax/webhooks", method, await body(), headers)
                return await reply(*result)
            except Exception:
                return await reply(503, b'{"erro":"confirmacao_indisponivel"}', "application/json")
        if method == "GET" and (path in {PANEL, PANEL + "/autorizar"} or (path == PANEL + "/retorno" and not scope.get("query_string"))):
            new_cookie = None if cookie else secrets.token_hex(32)
            return await reply(200, self.panel(cookie or new_cookie), new_cookie=new_cookie)
        if path == PANEL + "/checkout" and method == "GET":
            return await reply(200, self.preview())
        prefix = PANEL + "/checkout/"
        if path.startswith(prefix):
            suffix = path[len(PANEL + "/checkout"):]
            if (method == "POST" and suffix != "/api/sessoes") or method not in {"GET", "POST"}:
                return await reply(409, b'{"erro":"previa_sem_cobrancas"}', "application/json")
            try:
                result = await asyncio.to_thread(self.proxy, BASE + suffix, method, await body() if method == "POST" else b"", headers)
                return await reply(*result)
            except Exception:
                return await reply(503, b'{"erro":"instalacao_pendente"}', "application/json")
        if path == PANEL + "/assets/checkout.css" and method == "GET":
            return await reply(200, (self.assets / "checkout.css").read_bytes(), "text/css; charset=utf-8")
        if path == PANEL + "/retorno" and method == "GET":
            query = urllib.parse.parse_qs(scope.get("query_string", b"").decode())
            state = self.state()
            if not cookie or state.get("cookie_hash") != hashlib.sha256(cookie.encode()).hexdigest():
                return await reply(200, self.panel(cookie, "Volte pelo navegador que iniciou a instalação na Appmax."))
            try:
                await asyncio.to_thread(self.finish, query.get("token", [None])[0])
                return await reply(303, location=PANEL)
            except Exception as error:
                message = str(error) if isinstance(error, RuntimeError) else "A instalação não foi concluída. A preparação e as credenciais recebidas foram preservadas."
                return await reply(200, self.panel(cookie, message))
        if path == PANEL + "/autorizar" and method == "POST":
            form = {k: v[0] for k, v in urllib.parse.parse_qs((await body()).decode()).items()}
            if not cookie or headers.get(b"origin") != ORIGIN or not self.valid_csrf(cookie, form.get("csrf", "")):
                reason = 'cookie_ausente' if not cookie else 'origem_incompativel' if headers.get(b'origin') != ORIGIN else 'formulario_vencido_ou_incompleto'
                private_write(self.root/'ultimo-formulario.json', json.dumps({'motivo': reason, 'cookie_recebido': bool(cookie), 'origem_correta': headers.get(b'origin') == ORIGIN, 'codigo_formulario_recebido': bool(form.get('csrf')), 'horario': int(time.time())}).encode())
                return await reply(403, b"Abra novamente a tela de instalacao.")
            try:
                location = await asyncio.to_thread(self.begin, form, cookie)
                return await reply(303, location=location)
            except Exception as error:
                message = str(error) if isinstance(error, RuntimeError) else "Confira o UUID e o ID numérico do aplicativo existente."
                return await reply(200, self.panel(cookie, message))
        return await reply(409, b"Esta previa nao cria pedidos nem cobrancas.")


def wrap(fallback, assets):
    root = Path("/appmax-producao")
    if not (root / "instalacao.json").is_file():
        return fallback
    return ProductionAdmin(fallback, assets, root)
