"""Fixtures compartilhadas: o quadro mínimo do modelo e o dublê de identidade e alunos.
Nada toca a rede: `respx.mock` estoura em qualquer requisição não registrada."""

import hashlib
import json
import re
import secrets

import httpx
import pytest
import respx
from django.urls import reverse

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

# O quadro mínimo do modelo de dados


def id_da_plataforma_de(email: str) -> str:
    """Dublê do `SessionFull.id`: opaco e determinístico, sem dado da pessoa."""
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


# A porta: o mundo lá fora, de mentira (identidade + alunos)

IDENTIDADE = "http://identidade.teste/interno"
ALUNOS = "http://alunos.teste/api/alunos"

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
    """Monta o env da célula com valores falsos e limpa os caches de sessão.
    As listas de staff e de aprovadores começam vazias."""
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-sugestoes-identidade")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-sugestoes-alunos")
    monkeypatch.delenv("SUGESTOES_STAFF_EMAILS", raising=False)
    # A lista de aprovadores começa ausente: sem ela ninguém autoriza desenvolvimento.
    monkeypatch.delenv("SUGESTOES_APROVADORES", raising=False)
    ses.limpar_caches()
    yield
    ses.limpar_caches()


class Rede:
    """As conversas de fora, sob controle do teste; requisição não declarada estoura."""

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
        """Registra que quem carregar `meshcraft_sessao=<valor>` é esta pessoa.
        `com_id=False` responde sem o `id`; `papel` é o campo de exibição."""
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

    # -- alunos: a porta pergunta a situação da pessoa --
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
        """A `alunos` confirma que existe uma linha esperando (recibo do pedido)."""
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
        """Dublê próprio de `reembolsado`, sem o atalho `alunos_diz`."""
        return self.alunos_situacao(email, "reembolsado")

    def alunos_diz_reembolsado(self, email: str):
        """Dublê próprio de `reembolsado`, sem o atalho `alunos_diz`."""
        return self.alunos_situacao(email, "reembolsado")

    def alunos_fora_do_ar(self, email: str):
        return self.mock.get(self._url(email)).mock(
            side_effect=httpx.ConnectError("connection refused")
        )

    def alunos_demora_demais(self, email: str):
        return self.mock.get(self._url(email)).mock(
            side_effect=httpx.ReadTimeout("timed out")
        )

    # -- a fila de liberação: a única escrita da célula na `alunos` --
    # O dublê guarda o que foi enviado, para os guardas medirem o que atravessou o fio.

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


@pytest.fixture
def rede():
    with respx.mock(assert_all_called=False) as mock:
        yield Rede(mock)


class Porta:
    """Uma pessoa diante da porta da Caixa, com ou sem sessão do site.
    `esta_dentro` abre a porta de verdade em vez de ler estado interno."""

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
    """Um `Client` novo com cookie de sessão do site válido, registrado no dublê."""
    from django.test import Client

    valor = secrets.token_urlsafe(12)
    rede.site_reconhece(valor, email=email, nome=nome, com_id=com_id, papel=papel)
    cliente = Client()
    cliente.cookies["meshcraft_sessao"] = valor
    return Porta(cliente, rede, email=email)


@pytest.fixture
def entrar_como(rede, matricula, db):
    """Uma pessoa com sessão do site e matrícula dublada: o aluno participante."""

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


# A moderação: o crachá vem da lista desta célula, nunca do contrato


@pytest.fixture
def lista_da_staff(monkeypatch):
    """Põe um e-mail em `SUGESTOES_STAFF_EMAILS`, acumulando os anteriores."""
    emails: list[str] = []

    def _incluir(email: str) -> None:
        emails.append(email.strip().lower())
        monkeypatch.setenv("SUGESTOES_STAFF_EMAILS", ",".join(emails))

    return _incluir


@pytest.fixture
def entrar_como_staff(rede, lista_da_staff, db, gestao):
    """Alguém da equipe pela porta real, sem dublar a `alunos`.
    `pessoa.gestao` é o atalho para a moderação pelo contrato do Admin."""

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
    """Alguém da equipe já dentro."""
    return entrar_como_staff()


# O segundo papel: aprovador de ChangeSpec, que não é o crachá da equipe


@pytest.fixture
def lista_de_aprovadores(monkeypatch):
    """Põe um e-mail em `SUGESTOES_APROVADORES`, acumulando os anteriores."""
    emails: list[str] = []

    def _incluir(email: str) -> None:
        emails.append(email.strip().lower())
        monkeypatch.setenv("SUGESTOES_APROVADORES", ",".join(emails))

    return _incluir


@pytest.fixture
def aprovador(entrar_como_staff, lista_de_aprovadores):
    """Quem pode registrar ChangeSpec: da equipe e na lista de aprovadores."""
    email = "mantenedor@meshcraft.test"
    lista_de_aprovadores(email)
    return entrar_como_staff(email=email, nome="Mantenedor")


@pytest.fixture
def changespec(aprovador, sugestao):
    """Um ChangeSpec aprovado, registrado pela jornada de escrita real."""
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


# Os eventos: o fio e os quatro fatos, provocados pela jornada real

from unittest import mock as unittest_mock  # noqa: E402  (usado só pelo Fio abaixo)


class Fio:
    """O transporte do relay sob controle do teste: o que saiu no `xadd`.
    O Redis é dublado no transporte (`redis.from_url`)."""

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
    """O relay publicando contra o dublê, com `REDIS_STREAMS_URL` presente."""
    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://redis.teste:6379/0")
    linha = Fio()
    monkeypatch.setattr("redis.from_url", lambda *a, **k: linha.cliente)
    return linha


# A jornada de moderação é pelo contrato do Admin (`apps/core/api_gestao.py`).
# Provocar o fato por aqui é percorrer a jornada real, sem `objects.create`.

TOKEN_DO_PAR_ADMIN = "token-do-par-admin-sugestoes"
GESTAO = "/interno/gestao/ideias"


class Gestao:
    """O Admin falando com a Caixa — as três escritas da gestão."""

    def __init__(self, client) -> None:
        self.client = client

    @staticmethod
    def quem(pessoa) -> dict:
        """Quem age, na forma do contrato; aceita uma `Porta` ou uma `Identidade`."""
        identidade = getattr(pessoa, "identidade", pessoa)
        return {
            "por_email": identidade.email,
            "por_nome": identidade.nome_exibido,
            # Sem o id da plataforma a Caixa recusa; o dublê o manda quando existe.
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
        """Corrige o texto inteiro; os campos ausentes viajam com o valor gravado."""
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
    """A porta de máquina aberta só para o par do Admin.
    O token entra por `settings`, de onde `apps/core/auth.py` o lê."""
    settings.TOKENS_ACEITOS = {TOKEN_DO_PAR_ADMIN}
    return Gestao(client)


class Caixa:
    """Os quatro fatos, provocados pelo clique de verdade e nunca pelo ORM."""

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
        """Muda o status pelo contrato, como o Admin faz; responde 200 em JSON."""
        return self.gestao.mudar_status(self.equipe, sugestao, status, nota=nota)

    def os_quatro_fatos(self) -> Sugestao:
        """Publicar, votar, desvotar e mudar o status, nesta ordem."""
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


# O sininho: um aviso já na caixa de quem está dentro


@pytest.fixture
def aviso(dentro, sugestao):
    """Um aviso pronto, escrito pelo ORM, para quem a fixture `dentro` abriu a sessão.
    O autor da fixture `sugestao` é outra identidade."""
    return Aviso.objects.create(
        destinatario=dentro.identidade,
        sugestao=sugestao,
        status_anterior=Sugestao.Status.EM_ANALISE,
        status_novo=Sugestao.Status.PLANEJADO,
        nota="Entra no próximo ciclo.",
    )


# A plateia: gente em volta de uma ideia, em quantidade regulável


@pytest.fixture
def plateia(db):
    """N pessoas que votaram e M que comentaram numa sugestão, criadas em lote."""

    def _montar(
        sugestao,
        *,
        votantes: int = 0,
        comentaristas: int = 0,
        marca: str = "p",
        na_plataforma: bool = True,
    ):
        """`na_plataforma=False` monta gente sem o id da plataforma."""

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
