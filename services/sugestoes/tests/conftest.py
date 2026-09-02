"""Fixtures compartilhadas pelos testes-guarda da célula.

Duas metades: o quadro mínimo do modelo de dados (EVO-11) e o **dublê do mundo
lá fora** da porta — três células desde a Fase 3/4 do sininho: a `identidade`
(quem é — `getSessionFull`, com e-mail), a `alunos` (se pode) e a
`notificacoes` (a caixa central de avisos, `DECISAO-fase-2-do-sininho.md` §3 —
`apps/core/avisos.py::sino`/`ver_avisos`/`marcar_lido` leem de lá desde
27/08/2026). O Google saiu daqui junto com o login.

--------------------------------------------------------------------------
NADA AQUI TOCA A REDE — e é isto que torna a suíte executável sem internet
--------------------------------------------------------------------------
As três conversas são dubladas com `respx`, que troca o transporte do `httpx`
por um roteador em memória. A prova é mecânica, não promessa: `respx.mock` sem
`assert_all_called` levanta `AllMockedAssertionError` para QUALQUER requisição
que não tenha sido registrada (armadilhas/054). Se alguém acrescentar amanhã
um salto de rede novo, a suíte estoura em vez de sair para a internet.

O dublê da `identidade` responde POR COOKIE: cada pessoa "logada no site" é um
valor de `meshcraft_sessao` registrado em `Rede.site_reconhece` — o mesmo
mecanismo de produção (a Caixa repassa o cabeçalho `Cookie` opaco; quem o
entende é a outra célula). O dublê da `notificacoes` responde ESPELHANDO o
`Aviso` local — ver o comentário de `_notificacoes_avisos` mais abaixo para o
porquê.
"""

import hashlib
import json
import re
import secrets

import httpx
import pytest
import respx
from django.urls import reverse
from django.utils import timezone

from apps.core import avisos as avisos_mod
from apps.core import sessao as ses
from apps.sugestoes.models import (
    Aviso,
    Categoria,
    Comentario,
    Identidade,
    Quadro,
    Sugestao,
    Voto,
)

# ---------------------------------------------------------------------------
# O quadro mínimo do modelo de dados (EVO-11)
# ---------------------------------------------------------------------------


def id_da_plataforma_de(email: str) -> str:
    """O dublê do `SessionFull.id` — OPACO, como o de verdade.

    Até 26/08/2026 este dublê era `f"idt-{email}"`. No primeiro envelope que
    passou a carregar `ator_id` (Rito de Contrato do sininho), o guarda de
    privacidade `test_nenhum_envelope_carrega_dado_pessoal` acusou um `@`
    vazando no fio — e o vazamento era **do dublê**, não do código: a célula
    `identidade` cunha `secrets.token_urlsafe(16)`, sem nada da pessoa dentro.

    A lição vale mais que o conserto: um dublê com FORMA diferente da real
    responde a outra pergunta. Aqui ele quase transformou um guarda correto num
    alarme falso — e num dia menos atento teria sido "consertado" abrindo uma
    exceção no guarda, que é justamente como se deixa entrar o vazamento
    verdadeiro.

    Determinístico de propósito: a mesma pessoa recebe sempre o mesmo id — é o
    que a `identidade` faz (uma linha por pessoa) e é do que os testes de
    reentrada dependem.
    """
    return "idt-" + hashlib.sha256(email.encode("utf-8")).hexdigest()[:22]


@pytest.fixture
def aluno(db):
    return Identidade.objects.create(
        email="aluno@exemplo.test", nome_exibido="Aluno de Teste"
    )


@pytest.fixture
def outro_aluno(db):
    return Identidade.objects.create(
        email="outro@exemplo.test", nome_exibido="Outro Aluno"
    )


@pytest.fixture
def quadro(db):
    return Quadro.objects.create(site_id="site-de-teste", nome="Quadro de teste")


@pytest.fixture
def categoria(quadro):
    return Categoria.objects.create(quadro=quadro, slug="curso", nome="Curso e aulas")


@pytest.fixture
def sugestao(quadro, categoria, aluno):
    return Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=aluno,
        titulo="Legendas nas aulas",
        problema="Assisto no ônibus e não dá para ouvir.",
    )


# ---------------------------------------------------------------------------
# A porta — o mundo lá fora, de mentira (identidade + alunos)
# ---------------------------------------------------------------------------

IDENTIDADE = "http://identidade.teste/interno"
ALUNOS = "http://alunos.teste/api/alunos"
NOTIFICACOES = "http://notificacoes.teste/api/notificacoes"

MATRICULA_ATIVA = {
    "site_id": "site-de-teste",
    "order_id": "pedido-1",
    "product_id": "curso-1",
    "status": "ativa",
    "enrolled_at": "2026-08-01T12:00:00+00:00",
}

_COOKIE_DO_SITE = re.compile(r"meshcraft_sessao=([^;]+)")


@pytest.fixture
def matricula():
    """Uma matrícula ativa, na forma exata do `contracts/alunos.openapi.yaml`."""
    return dict(MATRICULA_ATIVA)


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    """O env da célula como ele será na VPS — menos os segredos, que são falsos.

    `autouse` porque tudo é lido NO PONTO DE USO: um teste que esqueça de
    montar o ambiente veria uma recusa de configuração ausente e perderia
    tempo. A lista de staff começa VAZIA de propósito — ninguém é staff por
    acidente; o teste que precisa dela a declara.

    Os caches de sessão/matrícula (armadilhas/026: módulo vaza entre testes)
    são limpos ANTES e DEPOIS: uma sessão que vazasse faria um guarda de
    "visitante" passar mostrando o nome de alguém que outro teste logou.
    """
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-sugestoes-identidade")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-sugestoes-alunos")
    # A caixa central de avisos (Fase 3/4 do sininho) — CONFIGURADA por padrão
    # aqui, ao contrário do `funil` (`services/funil/tests/test_sino.py`, que
    # a deixa ausente por padrão porque lá o sino é decoração). Nesta célula
    # `/avisos` É o assunto de boa parte da suíte (test_inv_aviso_e_so_do_dono,
    # test_o_rosto, test_avisos_script_name...), então o padrão que serve à
    # maioria dos testes é "respondendo" — os poucos testes de falha (fail
    # aberta no sino, fail visível na tela) sobrescrevem a rota mockada
    # correspondente (`rede.notificacoes_resumo`/`notificacoes_avisos`
    # `.mock(...)` de novo, mesmo padrão de `Rede.central_responde`) ou tiram
    # a variável com `monkeypatch.delenv`.
    monkeypatch.setenv("NOTIFICACOES_API_URL", NOTIFICACOES)
    monkeypatch.setenv("NOTIFICACOES_API_TOKEN", "token-do-par-sugestoes-notificacoes")
    monkeypatch.delenv("SUGESTOES_STAFF_EMAILS", raising=False)
    # [INV-SUG10] A lista de APROVADORES começa ausente pelo mesmo motivo — e
    # aqui ele é ainda mais duro: sem ela ninguém autoriza desenvolvimento, e é
    # esse o comportamento CERTO (EVO-40, decisão do mantenedor em 25/08/2026).
    # Montá-la por conveniência aqui faria a suíte inteira rodar num regime que
    # a produção não tem, e o guarda de fail-closed nunca reprovaria.
    monkeypatch.delenv("SUGESTOES_APROVADORES", raising=False)
    ses.limpar_caches()
    avisos_mod.limpar_cache_de_resumo()
    yield
    ses.limpar_caches()
    avisos_mod.limpar_cache_de_resumo()


class Rede:
    """As três conversas de fora, sob controle do teste.

    Cada método diz o que o mundo VAI responder; o teste declara só o que
    importa para o invariante que está provando. O que não for declarado
    estoura (armadilhas/054) — é assim que um salto de rede novo aparece.
    """

    def __init__(self, mock: respx.MockRouter) -> None:
        self.mock = mock
        # A identidade de mentira: um dicionário cookie→pessoa. O default é
        # "visitante" para qualquer cookie desconhecido — o estado normal.
        self.sessoes: dict[str, dict] = {}
        # O que a Caixa MANDOU para a fila da `alunos` — na ordem em que saiu.
        self.pedidos: list[dict] = []
        self._central_fora = False
        self.completa = mock.get(f"{IDENTIDADE}/sessao/completa").mock(
            side_effect=self._quem_e
        )
        # A caixa central de avisos, de mentira — ver as quatro rotas e o
        # comentário de `_notificacoes_avisos` logo abaixo para o porquê de
        # ela ESPELHAR o `Aviso` local em vez de guardar estado próprio.
        self.notificacoes_resumo = mock.get(f"{NOTIFICACOES}/resumo").mock(
            side_effect=self._notificacoes_resumo
        )
        self.notificacoes_avisos = mock.get(f"{NOTIFICACOES}/avisos").mock(
            side_effect=self._notificacoes_avisos
        )
        self.notificacoes_marcar_lida = mock.post(f"{NOTIFICACOES}/marcar-lida").mock(
            side_effect=self._notificacoes_marcar_lida
        )
        self.notificacoes_marcar_lidas = mock.post(f"{NOTIFICACOES}/marcar-lidas").mock(
            side_effect=self._notificacoes_marcar_lidas
        )

    # -- identidade ---------------------------------------------------------
    def _quem_e(self, request):
        if self._central_fora:
            raise httpx.ConnectError("connection refused")
        achado = _COOKIE_DO_SITE.search(request.headers.get("cookie", ""))
        corpo = self.sessoes.get(achado.group(1)) if achado else None
        return httpx.Response(200, json=corpo or {"autenticado": False})

    def site_reconhece(
        self,
        valor: str,
        *,
        email: str,
        nome: str = "João",
        com_id: bool = True,
        papel: str = "aluno",
    ) -> None:
        """Registra: quem carregar `meshcraft_sessao=<valor>` é esta pessoa.

        `com_id=False` faz o site responder **sem** o `id` — que o contrato
        declara opcional e nulável (`anyOf: [string, null]`). É o único jeito
        honesto de encenar "a porta não soube dizer quem é": mexer na coluna
        local direto não serve, porque toda requisição passa pela porta e a
        porta REGRAVA o id na reentrada (INV-SUG11). Foi assim que o guarda do
        fail-closed do ator nasceu verde por engano, em 26/08/2026, antes de
        alguém notar que ele não estava encenando falha nenhuma.

        `papel` é o campo de EXIBIÇÃO do contrato (`Session.papel`), e o dublê
        passou a devolvê-lo em 03/09/2026, quando o menu do topo ganhou a
        plateia `staff`. O padrão é `aluno` porque é o que a identidade responde
        para quase todo mundo — um dublê que devolvesse `staff` por descuido
        faria o guarda do item de equipe passar sem medir nada.
        """
        self.sessoes[valor] = {
            "autenticado": True,
            "id": id_da_plataforma_de(email) if com_id else None,
            "nome_exibido": nome,
            "email": email,
            "papel": papel,
        }

    def central_fora_do_ar(self) -> None:
        self._central_fora = True

    def central_responde(self, resposta: httpx.Response) -> None:
        """A forma crua, para os guardas de resposta fora do contrato."""
        self.completa.mock(return_value=resposta)

    # -- alunos -------------------------------------------------------------
    #
    # A porta pergunta a SITUAÇÃO desde 28/08/2026 — antes perguntava "tem
    # matrícula?", sim ou não (`DECISAO-ex-aluno-e-a-porta-que-explica`). Os
    # nomes dos ajudantes ficaram, porque o que eles significam para quem lê um
    # teste não mudou: `alunos_diz(email, [matricula])` continua sendo "esta
    # pessoa é aluna". O que mudou é a pergunta feita na rede.
    def alunos_responde(self, email: str, resposta: httpx.Response):
        return self.mock.get(self._url(email)).mock(return_value=resposta)

    def alunos_situacao(self, email: str, categoria: str):
        """A resposta crua da porta da situação."""
        return self.alunos_responde(
            email, httpx.Response(200, json={"categoria": categoria, "na_fila": None})
        )

    def alunos_diz(self, email: str, matriculas: list[dict]):
        """Compatível com o que os testes já escreviam: lista não-vazia = aluno."""
        return self.alunos_situacao(email, "aluno" if matriculas else "cadastrado")

    def alunos_nao_conhece(self, email: str):
        return self.alunos_situacao(email, "cadastrado")

    def alunos_diz_na_fila(self, email: str, estado: str = "aguardando"):
        """[RECIBO] A `alunos` confirma que existe uma linha esperando.

        Desde 29/08/2026 é a ÚNICA forma de a porta mostrar o recibo do pedido
        (`DECISAO-o-recibo-e-conferido.md`) — antes bastava um cookie no
        navegador, que continuava afirmando o pedido depois de a linha ter sido
        decidida ou apagada.
        """
        return self.alunos_responde(
            email,
            httpx.Response(
                200,
                json={
                    "categoria": "na_fila",
                    "na_fila": {
                        "estado": estado,
                        "esperando_ha_dias": 0 if estado == "aguardando" else None,
                        "motivo_recusa": None,
                    },
                },
            ),
        )

    def alunos_diz_ex_aluno(self, email: str):
        return self.alunos_situacao(email, "ex_aluno")

    def alunos_diz_pausado(self, email: str):
        return self.alunos_situacao(email, "pausado")

    def alunos_diz_reembolsado(self, email: str):
        """[REEMBOLSO] A sexta categoria, nascida em 31/08/2026.

        Existe como dublê PRÓPRIO, e não como `alunos_diz(...)` com um status
        dentro, porque `alunos_diz` é um atalho legado que traduz *"lista
        não-vazia = aluno"* e joga o status fora. Um guarda escrito com ele
        mediria sempre `aluno`, qualquer que fosse a palavra passada.
        """
        return self.alunos_situacao(email, "reembolsado")

    def alunos_diz_reembolsado(self, email: str):
        """[REEMBOLSO] A sexta categoria, nascida em 31/08/2026.

        Existe como dublê PRÓPRIO, e não como `alunos_diz(...)` com um status
        dentro, porque `alunos_diz` é um atalho legado que traduz *"lista
        não-vazia = aluno"* e joga o status fora. Um guarda escrito com ele
        mediria sempre `aluno`, qualquer que fosse a palavra passada.
        """
        return self.alunos_situacao(email, "reembolsado")

    def alunos_fora_do_ar(self, email: str):
        return self.mock.get(self._url(email)).mock(
            side_effect=httpx.ConnectError("connection refused")
        )

    def alunos_demora_demais(self, email: str):
        return self.mock.get(self._url(email)).mock(
            side_effect=httpx.ReadTimeout("timed out")
        )

    # -- a fila de liberação (DECISAO-fila-de-liberacao.md) ------------------
    #
    # A ÚNICA escrita que esta célula faz na `alunos`. O dublê GUARDA o que foi
    # enviado, porque é isso que os guardas de privacidade e de `site_id`
    # precisam medir: não basta a tela responder bonito — o que importa é o que
    # atravessou o fio.

    def alunos_aceita_o_pedido(self, *, status: int = 201):
        """A `alunos` recebe quem pediu entrada. 201 = entrou; 200 = reenvio."""
        return self._fila().mock(
            side_effect=lambda pedido: self._anotar(pedido, status)
        )

    def alunos_ja_tem_matricula(self):
        """409 do contrato: quem já entra não precisa de fila."""
        return self._fila().mock(side_effect=lambda pedido: self._anotar(pedido, 409))

    def alunos_recusa_o_pedido(self, status: int = 500):
        return self._fila().mock(
            side_effect=lambda pedido: self._anotar(pedido, status)
        )

    def alunos_fora_do_ar_no_pedido(self):
        return self._fila().mock(side_effect=httpx.ConnectError("connection refused"))

    def _anotar(self, pedido, status: int) -> httpx.Response:
        self.pedidos.append(json.loads(pedido.content))
        return httpx.Response(status, json={"id": "1", "status": "aguardando"})

    def _fila(self):
        return self.mock.post(f"{ALUNOS}/pre-matriculas")

    @property
    def um_pedido(self) -> dict:
        assert (
            len(self.pedidos) == 1
        ), f"esperava UM pedido de entrada no fio, vieram {len(self.pedidos)}"
        return self.pedidos[0]

    @staticmethod
    def _url(email: str) -> str:
        return f"{ALUNOS}/alunos/{email}/situacao"

    # -- notificacoes ---------------------------------------------------------
    # **Por que este dublê ESPELHA o `Aviso` local em vez de guardar um mundo
    # próprio.** A caixa central de verdade recebe cópia do `Aviso` via a
    # carta `notificacao.devida.v1` (emitida por
    # `apps/sugestoes/eventos.py::emitir_cartas_de_notificacao`, já testado
    # em `tests/test_volume_das_cartas.py` e
    # `tests/test_inv_carta_endereca_pelo_id_da_plataforma.py`) — encenar essa
    # rede inteira de novo aqui só para reconstruir o que o `Aviso` já tem em
    # mãos seria duplicar verdade, o pecado que a Lei 3 proíbe. Em vez disso,
    # o dublê lê e escreve DIRETO na tabela local: é o comportamento
    # OBSERVÁVEL da caixa central (o que `GET /avisos` devolveria depois de
    # a carta chegar e ser lida de volta), sem reimplementar o relay.
    #
    # O `id` opaco do contrato é `str(aviso.pk)` — uma implementação válida
    # do contrato (que só promete "opaco", nunca "não numérico"), e a que
    # deixa os testes existentes (`aviso.id`) funcionarem sem tradução. Os
    # testes NOVOS de fail-open/fail-visível não dependem deste detalhe.
    #
    # `POST /marcar-lida` e `/marcar-lidas` gravam em `Aviso.lido_em` — o
    # MESMO campo que a leitura local usava. Isto é só a forma de o dublê
    # guardar estado; em produção, desde esta migração, `marcar_lido()` NUNCA
    # mais escreve nessa coluna (só a caixa central grava "lido" agora) — ver
    # o comentário de `_meus()` em `apps/core/avisos.py`.
    def _identidade_da_plataforma(self, destinatario_id) -> "Identidade | None":
        if not destinatario_id:
            return None
        return Identidade.objects.filter(id_da_plataforma=destinatario_id).first()

    def _notificacoes_resumo(self, request):
        identidade = self._identidade_da_plataforma(
            request.url.params.get("destinatario_id")
        )
        nao_lidas = (
            Aviso.objects.filter(destinatario=identidade, lido_em__isnull=True).count()
            if identidade
            else 0
        )
        return httpx.Response(200, json={"nao_lidas": nao_lidas})

    def _carta_de(self, aviso: Aviso) -> dict:
        parametros = {
            "suggestion_id": str(aviso.sugestao_id),
            "status_anterior": aviso.status_anterior,
            "status_novo": aviso.status_novo,
        }
        if aviso.nota:
            parametros["nota"] = aviso.nota
        if aviso.vinculo:
            parametros["vinculo"] = aviso.vinculo
        return {
            "id": str(aviso.pk),
            "assunto": "sugestao.status-alterado",
            "parametros": parametros,
            "ator_id": None,
            "lido_em": aviso.lido_em.isoformat() if aviso.lido_em else None,
            "criado_em": aviso.criado_em.isoformat(),
        }

    def _notificacoes_avisos(self, request):
        identidade = self._identidade_da_plataforma(
            request.url.params.get("destinatario_id")
        )
        if identidade is None:
            return httpx.Response(200, json={"itens": [], "proximo_cursor": None})
        avisos = Aviso.objects.filter(destinatario=identidade).order_by(
            "-criado_em", "-id"
        )
        return httpx.Response(
            200,
            json={
                "itens": [self._carta_de(a) for a in avisos],
                "proximo_cursor": None,
            },
        )

    def _notificacoes_marcar_lida(self, request):
        corpo = json.loads(request.content)
        identidade = self._identidade_da_plataforma(corpo.get("destinatario_id"))
        id_bruto = corpo.get("id")
        aviso = (
            Aviso.objects.filter(pk=id_bruto).first()
            if str(id_bruto).isdigit()
            else None
        )
        if (
            aviso is None
            or identidade is None
            or aviso.destinatario_id != identidade.pk
        ):
            # 404, nunca 403 — o mesmo cuidado que a leitura local sempre teve
            # (`apps/core/avisos.py::marcar_lido`): confirmar "existe, mas não
            # é seu" vazaria a existência do aviso alheio a quem chutou um id.
            return httpx.Response(404, json={"detail": "nao encontrado"})
        ja_estava_lido = aviso.lido_em is not None
        if not ja_estava_lido:
            aviso.lido_em = timezone.now()
            aviso.save(update_fields=["lido_em"])
        return httpx.Response(200, json={"ja_estava_lido": ja_estava_lido})

    def _notificacoes_marcar_lidas(self, request):
        corpo = json.loads(request.content)
        identidade = self._identidade_da_plataforma(corpo.get("destinatario_id"))
        if identidade is None:
            return httpx.Response(200, json={"marcados": 0})
        pendentes = Aviso.objects.filter(destinatario=identidade, lido_em__isnull=True)
        marcados = pendentes.count()
        pendentes.update(lido_em=timezone.now())
        return httpx.Response(200, json={"marcados": marcados})


@pytest.fixture
def rede():
    with respx.mock(assert_all_called=False) as mock:
        yield Rede(mock)


class Porta:
    """Uma pessoa diante da porta da Caixa — com (ou sem) a sessão do site.

    `esta_dentro` é medido ABRINDO A PORTA de verdade (um GET em `entrar`), e
    não lendo estado interno: é o que a pessoa veria, que é o que o guarda
    deve medir.
    """

    def __init__(self, client, rede: Rede, email: str = "") -> None:
        self.client = client
        self.rede = rede
        self.email = email.strip().lower()

    def abrir(self):
        return self.client.get(reverse("entrar"))

    @property
    def esta_dentro(self) -> bool:
        resposta = self.abrir()
        return (
            resposta.status_code == 200
            and "Ver o quadro de sugestões" in resposta.content.decode()
        )

    @property
    def identidade(self) -> Identidade:
        """A linha LOCAL desta pessoa — o snapshot casado por e-mail."""
        return Identidade.objects.get(email=self.email)


@pytest.fixture
def porta(client, rede, db):
    """Um visitante sem sessão nenhuma, diante da porta."""
    return Porta(client, rede)


def sessao_do_site(
    rede: Rede,
    *,
    email: str,
    nome: str = "João",
    com_id: bool = True,
    papel: str = "aluno",
):
    """Um `Client` novo já carregando uma sessão VÁLIDA do site.

    O cookie é opaco e registrado no dublê da identidade — exatamente o
    contrato de produção: a Caixa não entende o valor, só o repassa.
    """
    from django.test import Client

    valor = secrets.token_urlsafe(12)
    rede.site_reconhece(valor, email=email, nome=nome, com_id=com_id, papel=papel)
    cliente = Client()
    cliente.cookies["meshcraft_sessao"] = valor
    return Porta(cliente, rede, email=email)


@pytest.fixture
def entrar_como(rede, matricula, db):
    """Uma pessoa com sessão do site E matrícula — o aluno participante.

    A matrícula é dublada porque a autorização continua DESTA célula: sessão
    do site sozinha não participa (há guarda para isso).
    """

    def _entrar(
        email: str = "joao.silva@exemplo.test",
        nome: str = "João",
        papel: str = "aluno",
    ) -> Porta:
        rede.alunos_diz(email, [matricula])
        pessoa = sessao_do_site(rede, email=email, nome=nome, papel=papel)
        assert pessoa.esta_dentro
        return pessoa

    return _entrar


@pytest.fixture
def dentro(entrar_como):
    """Um aluno já dentro — o ponto de partida de todo guarda de participação."""
    return entrar_como()


# ---------------------------------------------------------------------------
# A moderação (EVO-13) — o crachá vem da lista DESTA célula, nunca do contrato
# ---------------------------------------------------------------------------


@pytest.fixture
def lista_da_staff(monkeypatch):
    """Põe um e-mail em `SUGESTOES_STAFF_EMAILS`, acumulando.

    Acumula porque a variável é UMA lista separada por vírgula: um `setenv`
    por pessoa faria a segunda apagar o crachá da primeira. Note que ela nasce
    ausente (fixture `ambiente`): **ninguém é staff por acidente**.
    """
    emails: list[str] = []

    def _incluir(email: str) -> None:
        emails.append(email.strip().lower())
        monkeypatch.setenv("SUGESTOES_STAFF_EMAILS", ",".join(emails))

    return _incluir


@pytest.fixture
def entrar_como_staff(rede, lista_da_staff, db, gestao):
    """Alguém da equipe, pela mesma porta real do aluno.

    Uma diferença que é prova por si: aqui **não se dubla a `alunos`**. A
    checagem de staff acontece antes da de matrícula (herdada da porta
    antiga), e o `respx` estoura em qualquer requisição não registrada
    (armadilhas/054) — se alguém inverter a ordem um dia, esta fixture cai com
    `AllMockedAssertionError`, não com um teste verde de mentira.

    **`pessoa.gestao` é a jornada de moderação de hoje** (desde 30/08/2026): as
    telas de `/moderacao` desta célula foram aposentadas, e quem modera é o
    Admin, pelo contrato. Quem tem crachá ganha o atalho aqui, e só quem tem —
    a porta de máquina continua fechada para o resto da suíte, que é o que faz
    `test_nenhuma_operacao_responde_sem_o_token_do_par` continuar medindo algo.
    """

    def _entrar(
        email: str = "equipe@meshcraft.test",
        nome: str = "Equipe",
        *,
        com_id: bool = True,
    ) -> Porta:
        lista_da_staff(email)
        pessoa = sessao_do_site(rede, email=email, nome=nome, com_id=com_id)
        assert pessoa.esta_dentro
        pessoa.gestao = gestao
        return pessoa

    return _entrar


@pytest.fixture
def equipe(entrar_como_staff):
    """Alguém da equipe já dentro — o ponto de partida dos guardas do EVO-13."""
    return entrar_como_staff()


# ---------------------------------------------------------------------------
# O corredor do ChangeSpec (EVO-40) — o segundo papel, e ele NÃO é o crachá
# ---------------------------------------------------------------------------


@pytest.fixture
def lista_de_aprovadores(monkeypatch):
    """Põe um e-mail em `SUGESTOES_APROVADORES`, acumulando.

    Gêmea da `lista_da_staff`, e separada dela de propósito: moderar é da
    equipe, autorizar desenvolvimento é do aprovador. Uma fixture que fizesse
    as duas coisas ao mesmo tempo apagaria da suíte a diferença que o
    mantenedor decidiu em 25/08/2026 — e o guarda de "staff não basta" ficaria
    verde sem nunca ter medido nada.
    """
    emails: list[str] = []

    def _incluir(email: str) -> None:
        emails.append(email.strip().lower())
        monkeypatch.setenv("SUGESTOES_APROVADORES", ",".join(emails))

    return _incluir


@pytest.fixture
def aprovador(entrar_como_staff, lista_de_aprovadores):
    """Quem pode registrar ChangeSpec: da equipe **e** na lista de aprovadores.

    Os dois papéis, porque a tela mora atrás do crachá e o registro atrás do
    mandato. Na prática de hoje é uma pessoa só (o mantenedor); no dado e no
    código são dois portões, porque um dia pode não ser.
    """
    email = "mantenedor@meshcraft.test"
    lista_de_aprovadores(email)
    return entrar_como_staff(email=email, nome="Mantenedor")


@pytest.fixture
def changespec(aprovador, sugestao):
    """Um ChangeSpec aprovado já registrado — pelo caminho de escrita real.

    Nunca por `ChangeSpecAprovado.objects.create(...)` à mão: o que os guardas
    da trava precisam provar é que a JORNADA abre o corredor, e um `create()`
    continuaria verde no dia em que a porta parasse de conferir qualquer coisa.

    A jornada mudou de porta em 30/08/2026 (a tela de `/moderacao` foi
    aposentada) e **não mudou de portão**: `SUGESTOES_APROVADORES` continua
    sendo quem decide, agora conferido no handler do contrato.
    """
    resposta = aprovador.gestao.assinar(
        aprovador,
        sugestao,
        change_id="CS-SUGESTOES-0001",
        documento="docs/changespecs/CS-SUGESTOES-0001.md",
        aprovado_por="Davi (mantenedor)",
        aprovado_em="2026-08-25",
    )
    assert resposta.status_code == 200, resposta.content
    return sugestao.changespecs.get()


# ---------------------------------------------------------------------------
# Os eventos (EVO-20) — o fio e os quatro fatos, provocados pela jornada REAL
# ---------------------------------------------------------------------------

from unittest import mock as unittest_mock  # noqa: E402  (usado só pelo Fio abaixo)


class Fio:
    """O transporte do relay sob controle do teste: o que saiu no `xadd`.

    O Redis é dublado no transporte (`redis.from_url`), pelo mesmo motivo que
    identidade e `alunos` são dublados acima: uma suíte que precisa de
    container fica vermelha por motivo alheio, e a máquina do mantenedor é
    Windows. O que se prova é o comportamento do relay e a FORMA do que ele
    publica.
    """

    def __init__(self) -> None:
        self.mensagens: list[tuple[str, dict]] = []
        self.cliente = unittest_mock.Mock()
        self.cliente.xadd.side_effect = self._xadd

    def _xadd(self, stream: str, campos: dict) -> None:
        # `json.loads` aqui de propósito: se o relay publicar algo que não é
        # JSON, o teste morre no ponto exato em vez de comparar strings.
        self.mensagens.append((stream, json.loads(campos["json"])))

    @property
    def streams(self) -> list[str]:
        return [stream for stream, _ in self.mensagens]

    def envelopes(self, event: str) -> list[dict]:
        return [
            envelope for _, envelope in self.mensagens if envelope["event"] == event
        ]

    def um_envelope(self, event: str) -> dict:
        achados = self.envelopes(event)
        assert len(achados) == 1, f"esperava 1 {event} no fio, vieram {len(achados)}"
        return achados[0]


@pytest.fixture
def fio(monkeypatch):
    """O relay publicando contra o dublê — e `REDIS_STREAMS_URL` presente.

    A variável é montada aqui e não na fixture `ambiente` de propósito: o relay
    a lê NO PONTO DE USO, e um teste que prove "Redis fora do ar" precisa poder
    tirá-la sem lutar com um `autouse`.
    """
    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://redis.teste:6379/0")
    linha = Fio()
    monkeypatch.setattr("redis.from_url", lambda *a, **k: linha.cliente)
    return linha


# ---------------------------------------------------------------------------
# A jornada de MODERAÇÃO, depois de 30/08/2026 — pelo contrato, do Admin
# ---------------------------------------------------------------------------
#
# As telas de `/moderacao` desta célula foram aposentadas (TAR-023 degrau 4);
# quem move de fase, avalia e assina é `/admin/caixa/`, e ele fala com esta
# célula pela superfície de máquina (`apps/core/api_gestao.py`). Provocar o
# fato POR AQUI é provocá-lo pela jornada REAL de hoje — que é a razão de esta
# suíte não usar `objects.create` para os fatos que importam. Um guarda que
# continuasse chamando a view morta provaria uma jornada que ninguém percorre.

TOKEN_DO_PAR_ADMIN = "token-do-par-admin-sugestoes"
GESTAO = "/interno/gestao/ideias"


class Gestao:
    """O Admin falando com a Caixa — as três escritas da gestão."""

    def __init__(self, client) -> None:
        self.client = client

    @staticmethod
    def quem(pessoa) -> dict:
        """Quem age, na forma do contrato — igual ao `_quem` do Admin.

        Aceita uma `Porta` ou uma `Identidade`: os guardas usam as duas, e
        exigir uma delas só faria cada teste lembrar de qual.
        """
        identidade = getattr(pessoa, "identidade", pessoa)
        return {
            "por_email": identidade.email,
            "por_nome": identidade.nome_exibido,
            # [INV-SUG12] sem ele a Caixa recusa COM INSTRUÇÃO — e há guarda
            # medindo exatamente isso; por isso o dublê o manda quando existe.
            "por_id_da_plataforma": identidade.id_da_plataforma or "",
        }

    def _post(self, caminho: str, corpo: dict):
        return self.client.post(
            caminho,
            data=json.dumps(corpo),
            content_type="application/json",
            headers={"authorization": f"Bearer {TOKEN_DO_PAR_ADMIN}"},
        )

    def mudar_status(self, pessoa, sugestao: Sugestao, status: str, nota: str = ""):
        return self._post(
            f"{GESTAO}/{sugestao.id}/status",
            {**self.quem(pessoa), "status": status, "nota": nota},
        )

    def avaliar(self, pessoa, sugestao: Sugestao, **campos):
        return self._post(
            f"{GESTAO}/{sugestao.id}/avaliacao", {**self.quem(pessoa), **campos}
        )

    def assinar(self, pessoa, sugestao: Sugestao, **campos):
        return self._post(
            f"{GESTAO}/{sugestao.id}/changespec", {**self.quem(pessoa), **campos}
        )

    def corrigir(self, pessoa, sugestao: Sugestao, **campos):
        """A correção de texto (31/08/2026) — o texto INTEIRO, não o pedaço.

        Os campos ausentes viajam com o valor que está gravado agora, que é o
        que a tela faz: ela mostra um formulário já preenchido. Assim um teste
        que só quer trocar o nome escreve `corrigir(..., titulo="…")` sem
        repetir o problema inteiro, e continua exercitando o contrato de
        verdade, que exige os três campos.
        """
        atual = {
            "titulo": sugestao.titulo,
            "problema": sugestao.problema,
            "solucao_proposta": sugestao.solucao_proposta,
        }
        return self._post(
            f"{GESTAO}/{sugestao.id}/texto",
            {**self.quem(pessoa), **atual, **campos},
        )

    def uma_ideia(self, sugestao_id: int):
        return self.client.get(
            f"{GESTAO}/{sugestao_id}",
            headers={"authorization": f"Bearer {TOKEN_DO_PAR_ADMIN}"},
        )


@pytest.fixture
def gestao(client, settings):
    """A porta de máquina aberta para o par do Admin, e só para ele.

    O token entra por `settings` (e não pelo env) porque é assim que
    `apps/core/auth.py` o lê; a fixture existe justamente para o teste NÃO
    montar isso à mão e para nenhum outro teste ganhar a porta aberta por
    acidente — a suíte inteira continua começando com a fronteira trancada.
    """
    settings.TOKENS_ACEITOS = {TOKEN_DO_PAR_ADMIN}
    return Gestao(client)


class Caixa:
    """Os quatro fatos, provocados pelo clique de verdade — nunca pelo ORM.

    Um teste que criasse `Sugestao.objects.create(...)` à mão provaria que o
    construtor de evento funciona, e continuaria verde no dia em que a view
    parasse de chamá-lo. O que interessa é o contrário: que a JORNADA emite.
    """

    def __init__(self, aluno, equipe, gestao: "Gestao") -> None:
        self.aluno = aluno
        self.equipe = equipe
        self.gestao = gestao

    def publicar(self, titulo: str = "Legendas nas aulas", **extra) -> Sugestao:
        resposta = self.aluno.client.post(
            reverse("nova_sugestao"),
            {
                "titulo": titulo,
                "problema": "Assisto no ônibus e não dá para ouvir.",
                "categoria": "curso",
                "publicar": "1",
                **extra,
            },
        )
        assert resposta.status_code == 302, resposta.content
        return Sugestao.objects.get(titulo=titulo)

    def votar(self, sugestao: Sugestao, quem=None):
        return (quem or self.aluno).client.post(reverse("votar", args=[sugestao.id]))

    def desvotar(self, sugestao: Sugestao, quem=None):
        return (quem or self.aluno).client.post(reverse("desvotar", args=[sugestao.id]))

    def mudar_status(self, sugestao: Sugestao, status: str, nota: str = ""):
        """Pelo CONTRATO, como o Admin faz — a tela antiga não existe mais.

        Responde **200** (a ideia, em JSON), e não mais 302: quem chama aqui
        não é um navegador seguindo redirecionamento, é a outra célula.
        """
        return self.gestao.mudar_status(self.equipe, sugestao, status, nota=nota)

    def os_quatro_fatos(self) -> Sugestao:
        """Publicar, votar, desvotar e mudar o status — nesta ordem.

        A ordem não é decorativa: desvotar depois de votar é o único jeito de o
        `voto-removido` existir, e mudar o status por último deixa o
        `HistoricoStatus` contando a história inteira.
        """
        sugestao = self.publicar()
        assert self.votar(sugestao).status_code == 302
        assert self.desvotar(sugestao).status_code == 302
        resposta = self.mudar_status(
            sugestao, Sugestao.Status.PLANEJADO, nota="Entra no próximo ciclo."
        )
        assert resposta.status_code == 200, resposta.content
        return sugestao


@pytest.fixture
def caixa(dentro, equipe, categoria, gestao):
    """Um aluno e alguém da equipe, os dois já dentro pela porta de verdade."""
    return Caixa(dentro, equipe, gestao)


# ---------------------------------------------------------------------------
# O sininho (EVO-21) — um aviso já na caixa de quem está dentro
# ---------------------------------------------------------------------------


@pytest.fixture
def aviso(dentro, sugestao):
    """Um aviso pronto, escrito direto pelo ORM — e isso é deliberado.

    Os guardas que provam COMO o aviso nasce provocam o fato pela jornada de
    verdade, em `test_inv_aviso_nasce_com_o_status.py`. Esta fixture serve aos
    outros — os de quem-vê-o-quê e de idempotência.

    O destinatário é quem a fixture `dentro` abriu a sessão — NÃO o autor da
    fixture `sugestao`, que é outra identidade. É de propósito: o aviso é do
    destinatário, não de quem escreveu a sugestão.
    """
    return Aviso.objects.create(
        destinatario=dentro.identidade,
        sugestao=sugestao,
        status_anterior=Sugestao.Status.EM_ANALISE,
        status_novo=Sugestao.Status.PLANEJADO,
        nota="Entra no próximo ciclo.",
    )


# ---------------------------------------------------------------------------
# A plateia (EVO-42) — gente em volta de uma ideia, em quantidade regulável
# ---------------------------------------------------------------------------


@pytest.fixture
def plateia(db):
    """N pessoas que votaram e M que comentaram numa sugestão.

    **Escrita pelo ORM, e a diferença para a fixture `changespec` — que registra
    pela jornada real — é deliberada e vale explicar.** O que esta fixture
    alimenta são os guardas de VOLUME e de forma do leque: quem eles medem é a
    consulta que o fan-out faz sobre as tabelas `Voto`/`Comentario`, e vinte
    logins de verdade dublados só acrescentariam vinte segundos de suíte à mesma
    medição. Que o clique de verdade escreve nessas tabelas — e portanto entra no
    leque — é provado à parte, pela jornada, em
    `test_a_jornada_de_verdade_bota_quem_votou_e_quem_comentou_no_leque`. As duas
    metades juntas fecham a escada; nenhuma sozinha fecha.

    `bulk_create` nos três: uma plateia de vinte pessoas montada a `create()` faz
    a própria fixture custar sessenta viagens ao banco, e um guarda de desempenho
    que demora não é rodado.
    """

    def _montar(
        sugestao,
        *,
        votantes: int = 0,
        comentaristas: int = 0,
        marca: str = "p",
        na_plataforma: bool = True,
    ):
        """`na_plataforma=False` monta gente COMO ERA ANTES da Fase 1: linha
        local sem o id que atravessa a plataforma. É o estado real de quem não
        voltou ao site desde 25/08/2026, e o que o guarda do pulo das cartas
        precisa para existir. O padrão é `True` porque quem entra hoje ganha o
        id na porta (INV-SUG11), e uma fixture que não reflete o presente faz
        guardas medirem um mundo que não existe mais."""

        def _gente(papel: str, quantos: int) -> list[Identidade]:
            return Identidade.objects.bulk_create(
                [
                    Identidade(
                        email=f"{marca}-{papel}-{n}@exemplo.test",
                        nome_exibido=f"{papel} {n}",
                        id_da_plataforma=(
                            id_da_plataforma_de(f"{marca}-{papel}-{n}@exemplo.test")
                            if na_plataforma
                            else None
                        ),
                    )
                    for n in range(quantos)
                ]
            )

        quem_votou = _gente("voto", votantes)
        quem_comentou = _gente("comentario", comentaristas)
        Voto.objects.bulk_create(
            [Voto(sugestao=sugestao, autor=pessoa) for pessoa in quem_votou]
        )
        Comentario.objects.bulk_create(
            [
                Comentario(sugestao=sugestao, autor=pessoa, texto="Também sinto isso.")
                for pessoa in quem_comentou
            ]
        )
        return {"votaram": quem_votou, "comentaram": quem_comentou}

    return _montar
