"""O ciclo comercial inteiro, passo a passo, contra a aplicação unificada.

Quem usa:

* ``tests/e2e/test_ciclo_comercial.py`` roda cada passo com as células reais
  juntas (bancos Postgres de teste, Redis de teste) e só os provedores
  externos simulados;
* ``roteiro_ciclo.py`` roda o mesmo ciclo no site no ar, com dados marcados
  como teste/sandbox, sem mensagem de verdade e sem pagar.

As células conversam como na produção: HTTP interno (``http://<celula>:8000``,
entregue ao ASGI local por ``internal``), com o token de cada par. As páginas
públicas (quiz, checkout, webhooks) entram pelo ASGI de entrada, com o Host do
site. Nenhum passo lê o banco de outra célula: o que o ciclo quer saber, ele
pergunta pela API.

Só os provedores de fora são simulados: o WhatsApp (``GatewayFalso``, um
servidor HTTP local), o Mercado Pago e a OpenAI (``ProvedoresFalsos``).
Qualquer outra saída para a internet é barrada e anotada.

Falha de um passo é ``FalhaDoCiclo`` (mensagem em português simples).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import itertools
import json
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import import_module
from typing import Any, Callable

import httpx

SITE_PADRAO_OPERACOES = "meshcraft.top"
CPF_DE_TESTE = "52998224725"  # dígitos verificadores corretos; não é de ninguém


class FalhaDoCiclo(AssertionError):
    """Um passo do ciclo não deu o resultado esperado."""


def conferir(condicao: Any, mensagem: str) -> None:
    if not condicao:
        raise FalhaDoCiclo(mensagem)


# ---------------------------------------------------------------------------
# Provedores de fora, simulados
# ---------------------------------------------------------------------------


class GatewayFalso:
    """O gateway do WhatsApp (Evolution) como servidor HTTP local.

    A mensageria fala com ele por urllib; basta apontar ``WHATSAPP_GATEWAY_URL``
    para ``self.url``. Guarda o que "saiu" e nunca sai de verdade.
    """

    def __init__(self) -> None:
        self.enviados: list[dict] = []
        self.chamadas: list[tuple[str, str]] = []
        self.estado = "open"
        self._contador = itertools.count(1)
        self._trava = threading.Lock()
        gateway = self

        class Atendente(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silêncio
                pass

            def _responder(self, status: int, corpo: dict) -> None:
                bruto = json.dumps(corpo).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(bruto)))
                self.end_headers()
                self.wfile.write(bruto)

            def do_GET(self):
                with gateway._trava:
                    gateway.chamadas.append(("GET", self.path))
                if "connectionState" in self.path:
                    return self._responder(200, {"instance": {"state": gateway.estado}})
                self._responder(404, {"erro": "simulado"})

            def do_POST(self):
                tamanho = int(self.headers.get("Content-Length") or 0)
                corpo = json.loads(self.rfile.read(tamanho) or b"{}")
                with gateway._trava:
                    gateway.chamadas.append(("POST", self.path))
                    if "/message/sendText/" in self.path or "/message/sendTemplate/" in self.path:
                        identificador = f"FALSO-{uuid.uuid4().hex[:16]}"  # único por servidor, como o do provedor
                        gateway.enviados.append({
                            "caminho": self.path, "numero": corpo.get("number"),
                            "texto": corpo.get("text"), "modelo": corpo.get("name"),
                            "id": identificador,
                        })
                        return self._responder(201, {"key": {"id": identificador}})
                self._responder(404, {"erro": "simulado"})

        self._servidor = ThreadingHTTPServer(("127.0.0.1", 0), Atendente)
        self._thread = threading.Thread(target=self._servidor.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._servidor.server_address[1]}"

    def para(self, numero: str) -> list[dict]:
        digitos = re.sub(r"\D", "", numero)
        return [e for e in self.enviados if re.sub(r"\D", "", str(e["numero"] or "")) == digitos]

    def parar(self) -> None:
        self._servidor.shutdown()
        self._servidor.server_close()


class MercadoPagoFalso:
    """O Mercado Pago que o ciclo precisa: cria Pix, consulta e aprova."""

    def __init__(self) -> None:
        self.pagamentos: dict[str, dict] = {}
        self.criacoes: list[dict] = []
        # Faixa de 13 dígitos que o Mercado Pago de verdade não usa, e que muda a cada
        # execução: nunca colide com pagamento real nem com o de outra rodada.
        self._contador = itertools.count(9_900_000_000_000 + uuid.uuid4().int % 90_000_000_000)

    def criar(self, corpo: dict) -> dict:
        identificador = str(next(self._contador))
        expira = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        pagamento = {
            "id": int(identificador),
            "status": "pending",
            "status_detail": "pending_waiting_transfer",
            "currency_id": "BRL",
            "transaction_amount": corpo.get("transaction_amount"),
            "external_reference": corpo.get("external_reference"),
            "date_of_expiration": expira,
            "point_of_interaction": {"transaction_data": {
                "qr_code": f"00020126FALSO{identificador}",
                "qr_code_base64": "RkFMU08=",
            }},
        }
        self.pagamentos[identificador] = pagamento
        self.criacoes.append(corpo)
        return pagamento

    def consultar(self, identificador: str) -> dict | None:
        return self.pagamentos.get(str(identificador))

    def aprovar(self, identificador: str) -> None:
        pagamento = self.pagamentos[str(identificador)]
        pagamento["status"], pagamento["status_detail"] = "approved", "accredited"

    def tratar(self, request: httpx.Request) -> httpx.Response:
        caminho = request.url.path
        if request.method == "POST" and caminho == "/v1/payments":
            return httpx.Response(201, json=self.criar(json.loads(request.content or b"{}")),
                                  request=request)
        achado = re.fullmatch(r"/v1/payments/(\d+)", caminho)
        if request.method == "GET" and achado:
            pagamento = self.consultar(achado.group(1))
            if pagamento is None:
                return httpx.Response(404, json={"message": "nao existe"}, request=request)
            return httpx.Response(200, json=pagamento, request=request)
        return httpx.Response(404, json={"message": "rota nao simulada"}, request=request)


class ProvedoresFalsos:
    """Intercepta o httpx: Mercado Pago e OpenAI simulados, resto de fora barrado.

    Entra por cima de ``internal.instalar()``, que já leva as chamadas entre
    células ao ASGI local; o que passa por aqui sem ser interno é provedor.
    """

    def __init__(self, mp: MercadoPagoFalso | None = None) -> None:
        self.mp = mp or MercadoPagoFalso()
        self.openai: list[str] = []
        self.barradas: list[str] = []
        #: Hora que o envio do robô enxerga. Vazio: a de hoje ao meio-dia em São
        #: Paulo se a real estiver fora das 08h-20h do robô; senão, a real.
        self.hora_do_envio = None
        self._ativo = False
        self._sync = None
        self._async = None
        self._agora_original = None

    def _decidir(self, request: httpx.Request) -> httpx.Response | None:
        from internal import SERVICOS

        host = request.url.host
        if host in SERVICOS or host in ("testserver", "127.0.0.1", "localhost"):
            return None
        if host == "api.mercadopago.com":
            return self.mp.tratar(request)
        if host == "api.openai.com":
            self.openai.append(f"{request.method} {request.url.path}")
            return httpx.Response(503, json={"error": {"message": "OpenAI simulada: sem resposta"}},
                                  request=request)
        self.barradas.append(f"{request.method} {request.url}")
        raise httpx.ConnectError(f"saida para fora barrada no ciclo: {host}", request=request)

    def instalar(self) -> "ProvedoresFalsos":
        if self._ativo:
            return self
        self._sync, self._async = httpx.HTTPTransport.handle_request, httpx.AsyncHTTPTransport.handle_async_request
        falsos = self

        def sincrono(transporte, request):
            resposta = falsos._decidir(request)
            return resposta if resposta is not None else falsos._sync(transporte, request)

        async def assincrono(transporte, request):
            resposta = falsos._decidir(request)
            return resposta if resposta is not None else await falsos._async(transporte, request)

        httpx.HTTPTransport.handle_request = sincrono
        httpx.AsyncHTTPTransport.handle_async_request = assincrono
        self._fixar_hora_do_envio()
        self._ativo = True
        return self

    def _fixar_hora_do_envio(self) -> None:
        """O robô só fala entre 08h e 20h; o ciclo roda a qualquer hora.

        Só a hora que a régua do envio enxerga muda; a regra continua a de produção
        (``hora_do_envio`` a exercita fora da janela).
        """
        from django.utils import timezone

        envio = import_module("modules.mensageria.apps.conversas.envio")
        self._agora_original = envio._agora
        original, falsos = envio._agora, self

        def agora():
            if falsos.hora_do_envio is not None:
                return falsos.hora_do_envio
            real = original()
            local = timezone.localtime(real)
            if 8 <= local.hour < 20:
                return real
            return local.replace(hour=12, minute=0, second=0, microsecond=0)

        envio._agora = agora

    def remover(self) -> None:
        if self._ativo:
            httpx.HTTPTransport.handle_request = self._sync
            httpx.AsyncHTTPTransport.handle_async_request = self._async
            import_module("modules.mensageria.apps.conversas.envio")._agora = self._agora_original
            self._ativo = False


# ---------------------------------------------------------------------------
# O mundo onde o ciclo roda
# ---------------------------------------------------------------------------

#: Quem publica na caixa de saída de cada célula (o relay que a produção usa).
RELAYS = (
    ("quiz", "modules.quiz.apps.quiz.tasks"),
    ("checkout", "modules.checkout.apps.pedidos.tasks"),
    ("pagamentos", "modules.pagamentos.pagamentos.core.models"),
    ("mensageria", "modules.mensageria.apps.jornadas.tasks"),
)

#: Quem consome os avisos (app que abriga o comando `consume_eventos`).
CONSUMIDORES = {"leads": "core", "checkout": "pedidos", "mensageria": "eventos"}


def relay_de_todas() -> int:
    from config.runtime import serving

    total = 0
    for servico, modulo in RELAYS:
        with serving(servico):
            total += import_module(modulo).relay_outbox() or 0
    return total


def iniciar_consumidores(servicos: tuple[str, ...] = tuple(CONSUMIDORES)):
    """Liga os consumidores reais (o `consume_eventos` de cada célula) em threads."""
    from workers import Workers

    trabalho = Workers(consumidores={s: CONSUMIDORES[s] for s in servicos}, hueys=())
    for servico in servicos:
        trabalho._thread(f"eventos-{servico}", trabalho._consumir, servico, CONSUMIDORES[servico])
    return trabalho


class _CapturasDeUmEmail:
    """O modelo de captura vendo só as linhas de um e-mail.

    O ciclo no site no ar não pode publicar a captura parada de visitante de
    verdade: ela precisa seguir para o barramento de produção. Por isso a
    publicação roda com este recorte, que só deixa passar as nossas linhas.
    """

    def __init__(self, modelo, email: str) -> None:
        self._modelo, self._email = modelo, email
        outer = self

        class Gerente:
            def filter(self, *args, **kwargs):
                return outer._modelo.objects.filter(lead_email=outer._email).filter(*args, **kwargs)

            def __getattr__(self, nome):
                return getattr(outer._modelo.objects, nome)

        self.objects = Gerente()

    def __getattr__(self, nome):
        return getattr(self._modelo, nome)


def publicar_capturas_paradas(email: str | None = None, minutos: int = 11) -> int:
    """O que o minuto da produção faz: captura sem conclusão vira aviso.

    Com `email`, só a captura dessa pessoa (obrigatório no site no ar).
    """
    from django.utils import timezone as fuso

    from config.runtime import serving

    with serving("quiz"):
        tarefas = import_module("modules.quiz.apps.quiz.tasks")
        original = tarefas.CapturaParcial
        if email:
            tarefas.CapturaParcial = _CapturasDeUmEmail(original, email)
        try:
            return tarefas.publicar_capturas_paradas(agora=fuso.now() + timedelta(minutes=minutos))
        finally:
            tarefas.CapturaParcial = original


@dataclass
class Rotas:
    """Base e token de cada API interna que o ciclo usa."""

    leads: tuple[str, str]
    mensageria: tuple[str, str]
    checkout: tuple[str, str]
    quiz: tuple[str, str]
    leads_admin: tuple[str, str]  # o token do painel: /crm e /perfil

    @classmethod
    def de(cls, leads: str, leads_admin: str, mensageria: str, checkout: str, quiz: str) -> "Rotas":
        return cls(
            leads=("http://leads:8000/api/leads", leads),
            leads_admin=("http://leads:8000/api/leads", leads_admin),
            mensageria=("http://mensageria:8000/api/mensageria", mensageria),
            checkout=("http://checkout:8000/api/checkout", checkout),
            quiz=("http://quiz:8000", quiz),
        )


@dataclass
class Ambiente:
    """O que o ciclo precisa do ambiente, sem saber se é teste ou o ar."""

    rotas: Rotas
    gateway: GatewayFalso
    provedores: ProvedoresFalsos
    token_pagina: str          # o token público das páginas do checkout
    webhook_whatsapp: str      # X-Webhook-Token da mensageria
    mp_segredo: str            # MP_WEBHOOK_SECRET (assina o aviso do provedor)
    instancia: str             # instância do WhatsApp configurada para o site
    drenar: Callable[[], Any] = relay_de_todas
    publicar_paradas: Callable[[str], Any] = publicar_capturas_paradas
    host_operacoes: str = SITE_PADRAO_OPERACOES


@dataclass
class Cena:
    """O site onde o ciclo roda: Host, quizzes e a oferta que a equipe vende."""

    host: str
    site_id: str
    quiz_a: str
    quiz_b: str
    oferta: str                 # slug da oferta do link de compra
    preco_cents: int            # o que o catálogo cobra por ela
    sufixo: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class Pessoa:
    nome: str
    email: str
    telefone: str               # só dígitos, com DDD (ex.: 11999990001)
    de_teste: bool = False
    aceita_whatsapp: bool = False
    lead_id: str = ""
    oportunidades: dict = field(default_factory=dict)  # quiz -> id da oportunidade
    conversa_id: str = ""

    @property
    def whatsapp(self) -> str:
        return "55" + re.sub(r"\D", "", self.telefone)

    @property
    def telefone_digitado(self) -> str:
        d = re.sub(r"\D", "", self.telefone)
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"


# ---------------------------------------------------------------------------
# HTTP pequeno
# ---------------------------------------------------------------------------


def interno(par: tuple[str, str], metodo: str, caminho: str, *, host: str = "",
            params: dict | None = None, corpo: dict | None = None) -> httpx.Response:
    base, token = par
    cabecalhos = {"Authorization": f"Bearer {token}"}
    if host:
        cabecalhos["Host"] = host
    with httpx.Client(trust_env=False, timeout=30) as cliente:
        return cliente.request(
            metodo, base + caminho,
            params={k: v for k, v in (params or {}).items() if v not in (None, "")},
            json=corpo if metodo != "GET" else None, headers=cabecalhos,
        )


def _json(resposta: httpx.Response, esperado: tuple[int, ...] = (200, 201), o_que: str = "") -> Any:
    if resposta.status_code not in esperado:
        raise FalhaDoCiclo(
            f"{o_que or resposta.request.url.path} respondeu {resposta.status_code}: "
            f"{resposta.text[:300]}"
        )
    return resposta.json() if resposta.content else {}


def esperar(condicao: Callable[[], Any], limite: float = 40.0, o_que: str = "") -> Any:
    """Repete até a condição dar algo verdadeiro (os consumidores são threads)."""
    fim = time.monotonic() + limite
    ultimo: Any = None
    while time.monotonic() < fim:
        try:
            ultimo = condicao()
        except FalhaDoCiclo as erro:
            ultimo = str(erro)
        else:
            if ultimo:
                return ultimo
        time.sleep(0.3)
    raise FalhaDoCiclo(f"não aconteceu a tempo: {o_que or 'condição'} (último: {ultimo!r})")


def publico(host: str, sessao: Callable[[httpx.AsyncClient], Any]) -> Any:
    """Roda `sessao` com um cliente que guarda cookies e fala com o ASGI de
    entrada pelo Host do site, como o navegador atrás do proxy (https)."""
    from config.asgi import application

    async def rodar():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url=f"https://{host}",
            headers={"X-Forwarded-Proto": "https"},
            follow_redirects=False, timeout=60,
        ) as cliente:
            return await sessao(cliente)

    return asyncio.run(rodar())


def _campo_csrf(html: str) -> str:
    achado = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', html)
    return achado.group(1) if achado else ""


def _perguntas_do_html(html: str) -> list[dict]:
    """As perguntas do formulário: `pergunta_<id>` e o valor de cada opção."""
    achados: dict[int, list[int]] = {}
    for tag in re.findall(r"<input\b[^>]*>", html):
        nome = re.search(r'name="pergunta_(\d+)"', tag)
        valor = re.search(r'value="(\d+)"', tag)
        if nome and valor:
            achados.setdefault(int(nome.group(1)), []).append(int(valor.group(1)))
    return [{"id": pid, "opcoes": opcoes} for pid, opcoes in achados.items()]


@dataclass
class QuizAberto:
    """Um quiz aberto no navegador: cookies de sessão, CSRF e perguntas."""

    slug: str
    cookies: dict[str, str]
    csrf: str
    perguntas: list[dict]


# ---------------------------------------------------------------------------
# O ciclo
# ---------------------------------------------------------------------------


class Ciclo:
    """Os passos do ciclo comercial, na ordem em que a equipe os vive."""

    def __init__(self, cena: Cena, amb: Ambiente) -> None:
        self.cena, self.amb = cena, amb
        self.pix_do_pedido: dict[str, str] = {}

    # -- quiz ---------------------------------------------------------------

    def abrir_quiz(self, slug: str) -> QuizAberto:
        async def sessao(c: httpx.AsyncClient):
            r = await c.get(f"/quiz/{slug}/")
            conferir(r.status_code == 200, f"abrir o quiz {slug} respondeu {r.status_code}")
            return QuizAberto(slug, dict(c.cookies), _campo_csrf(r.text), _perguntas_do_html(r.text))

        aberto = publico(self.cena.host, sessao)
        conferir(aberto.perguntas, f"o quiz {slug} abriu sem perguntas")
        return aberto

    def _enviar_quiz(self, aberto: QuizAberto, caminho: str, campos: dict) -> httpx.Response:
        async def sessao(c: httpx.AsyncClient):
            c.cookies.update(aberto.cookies)
            return await c.post(
                caminho, data={**campos, "csrfmiddlewaretoken": aberto.csrf},
                headers={"Referer": f"https://{self.cena.host}/quiz/{aberto.slug}/"},
            )

        return publico(self.cena.host, sessao)

    def _contato(self, pessoa: Pessoa) -> dict:
        campos = {"email": pessoa.email, "nome": pessoa.nome, "telefone": pessoa.telefone_digitado}
        if pessoa.aceita_whatsapp:
            campos["aceita_whatsapp"] = "1"
        return campos

    def captura_parcial(self, pessoa: Pessoa, slug: str) -> QuizAberto:
        """Deixa o contato e a primeira resposta, sem concluir; o aviso sai
        quando a captura fica parada (o minuto da produção)."""
        aberto = self.abrir_quiz(slug)
        campos = self._contato(pessoa)
        primeira = aberto.perguntas[0]
        campos[f"pergunta_{primeira['id']}"] = primeira["opcoes"][0]
        resposta = self._enviar_quiz(aberto, f"/quiz/{slug}/captura", campos)
        conferir(resposta.status_code in (200, 201), f"captura parcial respondeu {resposta.status_code}: {resposta.text[:200]}")
        conferir(self.amb.publicar_paradas(pessoa.email) >= 1, "a captura parada não virou aviso")
        self.amb.drenar()
        return aberto

    def concluir_quiz(self, pessoa: Pessoa, slug: str, aberto: QuizAberto | None = None) -> QuizAberto:
        aberto = aberto or self.abrir_quiz(slug)
        campos = self._contato(pessoa)
        for pergunta in aberto.perguntas:
            campos[f"pergunta_{pergunta['id']}"] = pergunta["opcoes"][-1]
        resposta = self._enviar_quiz(aberto, f"/quiz/{slug}/", campos)
        conferir(resposta.status_code == 302, f"concluir o quiz respondeu {resposta.status_code}: {resposta.text[:200]}")
        self.amb.drenar()
        return aberto

    # -- leads --------------------------------------------------------------

    def contato(self, pessoa: Pessoa, *, esperar_ate: float = 40.0) -> dict:
        """O contato no leads (achado pelo e-mail), esperando o consumidor."""
        def achar():
            dados = _json(interno(self.amb.rotas.leads, "GET", "/leads",
                                  params={"q": pessoa.email, "site_id": self.cena.site_id}),
                          o_que="lista de contatos")
            iguais = [i for i in dados["itens"] if i["email"] == pessoa.email]
            return iguais[0] if iguais else None

        item = esperar(achar, esperar_ate, f"contato de {pessoa.email} no leads")
        pessoa.lead_id = item["id"]
        return item

    def ficha(self, pessoa: Pessoa) -> dict:
        return _json(interno(self.amb.rotas.leads_admin, "GET", f"/leads/{pessoa.lead_id}"), o_que="ficha")

    def crm(self, **params) -> dict:
        """O quadro do CRM como o painel pede (`testes=mostrar` traz os de teste junto)."""
        return _json(interno(self.amb.rotas.leads_admin, "GET", "/crm",
                             params={"site_id": self.cena.site_id, "por_pagina": 100, **params}),
                     o_que="quadro do CRM")

    def oportunidades(self, pessoa: Pessoa, **params) -> list[dict]:
        return self.crm(lead_id=pessoa.lead_id, testes="mostrar", **params)["itens"]

    def oportunidade_do_quiz(self, pessoa: Pessoa, slug: str, *, esperar_ate: float = 40.0) -> dict:
        referencia = f"oferta:{slug}"

        def achar():
            for item in self.oportunidades(pessoa):
                if item["fonte"]["referencia_id"] == referencia:
                    return item
            return None

        item = esperar(achar, esperar_ate, f"oportunidade do quiz {slug} de {pessoa.email}")
        pessoa.oportunidades[slug] = item["id"]
        return item

    def oportunidade(self, pessoa: Pessoa, slug: str) -> dict:
        """A oportunidade do quiz agora (sem esperar)."""
        for item in self.oportunidades(pessoa):
            if item["fonte"]["referencia_id"] == f"oferta:{slug}":
                return item
        raise FalhaDoCiclo(f"{pessoa.email} não tem oportunidade do quiz {slug}")

    def gravar_perfil(self, pessoa: Pessoa) -> dict:
        """O analista grava o perfil (sem prova citada: vale como hipótese) e a ficha o mostra."""
        corpo = {
            "resumo": "Quer vender online e tem pouco tempo por dia.",
            "objetivo_declarado": {"texto": "Vender online"},
            "prioridade": {"nivel": "alta", "explicacao": "Respondeu o quiz inteiro"},
            "oferta_indicada": {"oferta_ref": self.cena.oferta, "nome": "Oferta do quiz",
                                "motivo": "É o produto que o quiz indica"},
            "analisado_por": "ciclo-de-prova",
        }
        gravado = _json(interno(self.amb.rotas.leads_admin, "PUT",
                                f"/leads/{pessoa.lead_id}/perfil", corpo=corpo), o_que="gravar perfil")
        lido = _json(interno(self.amb.rotas.leads_admin, "GET", f"/leads/{pessoa.lead_id}/perfil"),
                     o_que="ler perfil")
        conferir(lido["versao"] == gravado["versao"], "o perfil lido não é o gravado")
        return lido

    # -- conversa -----------------------------------------------------------

    def receber_mensagem(self, pessoa: Pessoa, texto: str, identificador: str) -> httpx.Response:
        """A pessoa escreve pelo WhatsApp: o aviso do gateway entra pelo webhook."""
        agora = int(time.time())

        async def sessao(c: httpx.AsyncClient):
            return await c.post(
                "/webhooks/whatsapp",
                headers={"X-Webhook-Token": self.amb.webhook_whatsapp},
                json={"event": "messages.upsert", "instance": self.amb.instancia, "data": {
                    "key": {"remoteJid": f"{pessoa.whatsapp}@s.whatsapp.net", "fromMe": False,
                            "id": identificador},
                    "message": {"conversation": texto}, "messageTimestamp": agora,
                }})

        resposta = publico(self.cena.host, sessao)
        conferir(resposta.status_code == 200, f"webhook do WhatsApp respondeu {resposta.status_code}: {resposta.text[:200]}")
        self.amb.drenar()
        return resposta

    def abrir_conversa(self, pessoa: Pessoa) -> dict:
        """Primeiro contato pela equipe: liga o endereço ao contato."""
        conversa = _json(interno(self.amb.rotas.mensageria, "POST", "/conversas", corpo={
            "site_id": self.cena.site_id, "canal": "whatsapp", "lead_id": pessoa.lead_id,
            "endereco": pessoa.whatsapp}), o_que="abrir conversa")
        pessoa.conversa_id = conversa["id"]
        return conversa

    def conversa_do_contato(self, pessoa: Pessoa) -> dict:
        def achar():
            dados = _json(interno(self.amb.rotas.mensageria, "GET", "/conversas", params={
                "site_id": self.cena.site_id, "lead_id": pessoa.lead_id}), o_que="conversas")
            return dados["itens"][0] if dados["itens"] else None

        conversa = esperar(achar, 20, f"conversa ligada ao contato {pessoa.email}")
        pessoa.conversa_id = conversa["id"]
        return conversa

    def conversas_do_site(self, **params) -> dict:
        """As conversas do site (`ligacao=todas` traz também as não ligadas a contato)."""
        return _json(interno(self.amb.rotas.mensageria, "GET", "/conversas", params={
            "site_id": self.cena.site_id, "ligacao": "todas", "por_pagina": 100, **params}), o_que="conversas do site")

    def consentimento_whatsapp(self, pessoa: Pessoa) -> dict:
        """Pode chamar este número sem ele ter escrito antes? (a mensageria responde)"""
        return _json(interno(self.amb.rotas.mensageria, "GET", "/consentimentos/whatsapp", params={
            "site_id": self.cena.site_id, "telefone": pessoa.whatsapp}), o_que="consentimento")

    def enviar(self, pessoa: Pessoa, texto: str, chave: str) -> dict:
        return _json(interno(self.amb.rotas.mensageria, "POST",
                             f"/conversas/{pessoa.conversa_id}/mensagens", corpo={
                                 "site_id": self.cena.site_id, "texto": texto,
                                 "chave_idempotencia": chave, "autor": "agente"}),
                     o_que="enviar na conversa")

    def mensagens(self, pessoa: Pessoa) -> dict:
        return _json(interno(self.amb.rotas.mensageria, "GET",
                             f"/conversas/{pessoa.conversa_id}/mensagens",
                             params={"site_id": self.cena.site_id}), o_que="mensagens")

    # -- compra -------------------------------------------------------------

    def condicoes_liberadas(self) -> list[str]:
        """Ids das condições que o mantenedor liberou ao agente para a oferta (o link só vale com elas)."""
        corpo = _json(interno(self.amb.rotas.checkout, "GET",
                              f"/interno/ofertas/{self.cena.oferta}/condicoes-agente",
                              host=self.cena.host), o_que="condições liberadas")
        return [c["id"] for c in corpo.get("condicoes", [])]

    def link_de_compra(self, pessoa: Pessoa, slug_do_quiz: str, chave: str) -> dict:
        oportunidade = pessoa.oportunidades[slug_do_quiz]
        return _json(interno(self.amb.rotas.checkout, "POST", "/interno/links-de-compra",
                             host=self.cena.host, corpo={
                                 "chave_idempotencia": chave, "oferta": self.cena.oferta,
                                 "oportunidade_ref": oportunidade, "condicao": "pix",
                                 "contato": {"nome": pessoa.nome, "email": pessoa.email,
                                             "telefone": pessoa.telefone}}),
                     o_que="link de compra")

    def estado_do_pedido(self, pedido_id: str) -> dict:
        return _json(interno(self.amb.rotas.checkout, "GET", f"/interno/pedidos/{pedido_id}/pagamento",
                             host=self.cena.host), o_que="estado do pedido")

    def pedidos_da_oportunidade(self, oportunidade_id: str) -> dict:
        return _json(interno(self.amb.rotas.checkout, "GET", "/interno/pedidos", host=self.cena.host,
                             params={"oportunidade_ref": oportunidade_id}), o_que="pedidos da oportunidade")

    def fechar_pedido_na_pagina(self, pessoa: Pessoa, link: dict) -> dict:
        """O que a página do link faz pela pessoa: abre a sessão do link e fecha o pedido no Pix."""
        cabecalho = {"Authorization": f"Bearer {self.amb.token_pagina}"}

        async def sessao(c: httpx.AsyncClient):
            aberta = await c.post("/api/checkout/sessoes", headers=cabecalho, json={
                "offer_slug": self.cena.oferta, "link": link["link_id"]})
            conferir(aberta.status_code == 201, f"abrir sessão respondeu {aberta.status_code}: {aberta.text[:200]}")
            pedido = await c.post(f"/api/checkout/sessoes/{aberta.json()['id']}/pedido", headers=cabecalho, json={
                "method": "pix", "bump_ids": [],
                "customer": {"name": pessoa.nome, "email": pessoa.email,
                             "phone": re.sub(r"\D", "", pessoa.telefone), "cpf": CPF_DE_TESTE}})
            conferir(pedido.status_code == 201, f"fechar pedido respondeu {pedido.status_code}: {pedido.text[:300]}")
            return pedido.json()

        antes = set(self.amb.provedores.mp.pagamentos)
        pedido = publico(self.cena.host, sessao)
        pedido["id"] = pedido["order_id"]
        conferir(str(pedido["id"]) == str(link["pedido_id"]), "o pedido não nasceu com o id que o link devolveu")
        novos = set(self.amb.provedores.mp.pagamentos) - antes
        conferir(len(novos) == 1, f"fechar o pedido deveria criar 1 Pix no provedor, criou {len(novos)}")
        self.pix_do_pedido[str(pedido["id"])] = novos.pop()
        self.amb.drenar()
        return pedido

    def aviso_do_provedor(self, pagamento_mp: str) -> httpx.Response:
        """O Mercado Pago avisa (assinado) que o pagamento mudou; quem decide é a consulta."""
        identificador = str(pagamento_mp)
        pedido = str(uuid.uuid4())
        ts = str(int(time.time()))
        manifesto = f"id:{identificador.lower()};request-id:{pedido};ts:{ts};"
        assinatura = hmac.new(self.amb.mp_segredo.encode(), manifesto.encode(), hashlib.sha256).hexdigest()

        async def sessao(c: httpx.AsyncClient):
            return await c.post(
                f"/api/pagamentos/mp/webhooks?data.id={identificador}",
                headers={"x-signature": f"ts={ts},v1={assinatura}", "x-request-id": pedido},
                json={"type": "payment", "data": {"id": identificador}})

        resposta = publico(self.amb.host_operacoes, sessao)
        self.amb.drenar()
        return resposta

    # -- descadastro --------------------------------------------------------

    def pedir_para_parar(self, pessoa: Pessoa, identificador: str) -> None:
        self.receber_mensagem(pessoa, "PARAR", identificador)
