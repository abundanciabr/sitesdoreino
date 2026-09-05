"""As peças que os testes montam: o esqueleto do curso, e a rede dublada.

**O esqueleto vem do semeador**, pelo `call_command`, e não de linhas escritas à
mão: é o mesmo caminho que a instalação da célula percorre, e um cenário que
gravasse os próprios blocos provaria o modelo contra um curso que ninguém usa.

**A rede é dublada pelo TRANSPORTE (`respx`), nunca pela função**: o cliente de
verdade monta a URL de verdade, e o dublê só responde às URLs do contrato. Um
dublê que aceitasse qualquer caminho testaria metade do cliente: foi assim que
um `/alunos` a menos no caminho passou por 39 testes verdes no fórum
(`armadilhas/111`).

**O que NÃO mora aqui:** nenhuma regra. A fixture monta estado; quem afirma é
cada teste.
"""

from __future__ import annotations

import json
from io import StringIO
from unittest import mock
from urllib.parse import quote

import httpx
import pytest
import respx
from django.core.management import call_command
from django.utils import timezone

from apps.core import menu
from apps.cursos import envio as checkpoint
from apps.cursos.models import (
    Aula,
    Curso,
    Instrumento,
    Pausa,
    Peca,
    Pessoa,
    Progresso,
    RegistroDePausa,
)

SITE = "escola-a"

# Os `servers:` dos contratos congelados mais o caminho de cada operação. Ficam
# aqui, escritos por extenso, porque o dublê EXIGE exatamente estes endereços.
IDENTIDADE = "http://identidade:8000/interno"
ALUNOS = "http://alunos:8000/api/alunos"
CATALOGO = "http://catalogo:8000/api/catalogo"
URL_DA_SESSAO = f"{IDENTIDADE}/sessao/completa"
URL_DO_MENU = f"{CATALOGO}/sites/by-host/testserver"

# O cookie de sessão do site, OPACO para esta célula: o valor não significa
# nada aqui, e o teste prova que ele viaja intacto para a `identidade`.
COOKIE = "meshcraft_sessao=cookie-opaco-de-ana"

ANA = {
    "autenticado": True,
    "id": "p_ana",
    "email": "ana@exemplo.com",
    "nome_exibido": "Ana",
    "papel": "aluno",
}
BETO = {
    "autenticado": True,
    "id": "p_beto",
    "email": "beto@exemplo.com",
    "nome_exibido": "Beto",
    "papel": "aluno",
}


def url_da_situacao(email: str) -> str:
    return f"{ALUNOS}/alunos/{quote(email, safe='')}/situacao"


@pytest.fixture
def esqueleto(db):
    """O curso `meshcraft` do site `escola-a`, com blocos, aulas e instrumentos."""
    call_command("semear_esqueleto", site=SITE, stdout=StringIO())
    return Curso.objects.get(site_id=SITE, slug="meshcraft")


@pytest.fixture
def env_dos_pares(monkeypatch):
    """Os pares provisionados, exceto o do menu (que fica sem par de propósito:
    é o estado real da célula até o passo do mantenedor, e assim nenhum teste
    de tela custa uma ida ao catálogo sem querer)."""
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-cursos-para-identidade")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-cursos-para-alunos")
    monkeypatch.setenv("SITE_ID", SITE)
    monkeypatch.delenv("CATALOGO_API_URL", raising=False)
    monkeypatch.delenv("TOKEN_CATALOGO", raising=False)
    # A segunda lista do plantão (05/09/2026). Sai daqui para que a máquina de
    # quem roda a suíte não decida o veredito: com `ADMIN_EMAILS` no ambiente,
    # os testes de fail-closed passariam a medir o computador, não o código.
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    menu.limpar_cache()
    yield
    menu.limpar_cache()


@pytest.fixture
def rede():
    """O dublê de transporte. Chamada a URL não registrada levanta na hora."""
    with respx.mock(assert_all_called=False) as dublagem:
        yield dublagem


def dublar_sessao(rede, corpo=None, *, status: int = 200):
    """A `identidade` responde `corpo` (ou só o status) para qualquer cookie."""
    resposta = httpx.Response(status, json=corpo if corpo is not None else {})
    return rede.get(URL_DA_SESSAO).mock(return_value=resposta)


def dublar_matricula(rede, email: str, categoria: str = "aluno"):
    """A `alunos` responde a categoria desta pessoa, no corpo do contrato."""
    return rede.get(url_da_situacao(email)).mock(
        return_value=httpx.Response(200, json={"categoria": categoria, "na_fila": None})
    )


@pytest.fixture
def aluna(env_dos_pares, rede, esqueleto):
    """Ana, reconhecida pela `identidade` e com matrícula ativa na `alunos`."""
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    return ANA


AS_16_PECAS = {
    tipo: f"# {tipo}\n\nTexto da peça **{tipo}** para a aula."
    for tipo in Peca.ORDEM_CANONICA
}
AS_2_INTERNAS = {
    Peca.Tipo.ROTEIRO: "SEGREDO-DO-ROTEIRO: abrir o Blender e mostrar o cubo.",
    Peca.Tipo.GUIA_DO_MENTOR: "SEGREDO-DO-MENTOR: o que dizer se a pessoa travar.",
}


def publicar(aula: Aula, **mudancas) -> Aula:
    """Uma aula PUBLICADA, inteira: as 16 peças, as duas internas, duas pausas,
    um quiz de duas perguntas e um vídeo do YouTube. Cada teste muda o que mede."""
    aula.pedido = mudancas.pop("pedido", "Um cubo com bordas suaves para a vitrine.")
    aula.cliente = mudancas.pop("cliente", "Dona Lúcia")
    aula.video_url = mudancas.pop(
        "video_url", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )
    aula.aceito_quando = mudancas.pop("aceito_quando", ["as arestas estão suaves"])
    aula.quiz = mudancas.pop(
        "quiz",
        [
            {
                "pergunta": "O que é um stud?",
                "resposta_modelo": "MODELO-1 a unidade do Roblox.",
            },
            {
                "pergunta": "Para que serve o bevel?",
                "resposta_modelo": "MODELO-2 suavizar arestas.",
            },
        ],
    )
    for campo, valor in mudancas.items():
        setattr(aula, campo, valor)
    aula.estado = Aula.Estado.PUBLICADA
    aula.publicada_em = timezone.now()
    aula.save()
    aula.pecas.all().delete()
    for tipo, texto in {**AS_16_PECAS, **AS_2_INTERNAS}.items():
        Peca.objects.create(aula=aula, tipo=tipo, texto=texto)
    aula.pausas.all().delete()
    Pausa.objects.create(
        aula=aula,
        ordem=1,
        segundo=90,
        tipo=Pausa.Tipo.FACA_AGORA,
        pede="Crie o cubo agora.",
        campos=["o que apareceu na tela"],
    )
    Pausa.objects.create(
        aula=aula,
        ordem=2,
        segundo=240,
        tipo=Pausa.Tipo.ERRO_PRODUTIVO,
        pede="Registre o que deu errado.",
        campos=["o que tentei", "o que aconteceu"],
    )
    return aula


@pytest.fixture
def aula_publicada(esqueleto):
    """A E00 publicada e inteira."""
    return publicar(esqueleto.aulas.get(numero="E00"))


# ---------------------------------------------------------------------------
# O checkpoint (degrau 2.1): a pessoa pronta para entregar, e uma entrega válida
# ---------------------------------------------------------------------------

ARQUIVO = "https://arquivos.exemplo.test/ana/cubo-da-vitrine.blend"
README = "Um cubo com bevel de 0,2. Abra o .blend e olhe a coleção Vitrine."
AUTOAVALIACAO = "As arestas ficaram suaves; eu faria a base mais larga."


def entrega(**mudancas) -> dict:
    """Os três campos de `envio.entregar`, válidos. Cada teste muda o que mede."""
    base = {
        "links": [{"rotulo": "Arquivo", "url": ARQUIVO}],
        "readme": README,
        "laudo_do_aluno": {"texto": AUTOAVALIACAO},
    }
    base.update(mudancas)
    return base


@pytest.fixture
def ana_pronta(aula_publicada):
    """Ana com a E00 em produção e as duas pausas registradas: pode entregar."""
    ana = Pessoa.objects.create(id_da_plataforma=ANA["id"], nome_exibido="Ana")
    progresso = Progresso.objects.create(
        pessoa=ana, aula=aula_publicada, estado=Progresso.Estado.EM_PRODUCAO
    )
    for pausa in aula_publicada.pausas.all():
        RegistroDePausa.objects.create(pessoa=ana, pausa=pausa, respostas={"x": "y"})
    return progresso


# ---------------------------------------------------------------------------
# O laudo (degrau 2.2): um envio na fila, com instrumento de dois critérios
# ---------------------------------------------------------------------------

# O nome dos dois critérios, em ordem alfabética: os testes de laudo dependem
# desta ordem (a mesma regra de `envio.py::criterios_de`).
CRITERIO_1, CRITERIO_2 = "Acabamento", "Proporção"


@pytest.fixture
def instrumento_com_escala(esqueleto):
    """Um dos 13 instrumentos, com dois critérios de 1 a 5 (a mesma forma que
    o Admin grava pela porta de máquina, degrau 1.5)."""
    instrumento = Instrumento.objects.get(slug="rubrica_de_encomenda")
    instrumento.escala = {
        CRITERIO_1: {"minimo": 1, "maximo": 5},
        CRITERIO_2: {"minimo": 1, "maximo": 5},
    }
    instrumento.save(update_fields=["escala"])
    return instrumento


@pytest.fixture
def envio_na_fila(ana_pronta, instrumento_com_escala):
    """O envio 1 de Ana na E00, `recebido`, com a aula usando o instrumento de
    dois critérios: pronto para `apps.cursos.laudo.emitir` ser chamado.

    A autoavaliação do ALUNO (`laudo_do_aluno`) precisa da mesma forma de
    rubrica, porque a aula agora tem instrumento com escala: `envio.entregar`
    exige nota+frase por critério dela também, independente do laudo da
    professora que vem depois.
    """
    aula_da_e00 = ana_pronta.aula
    aula_da_e00.instrumento = instrumento_com_escala
    aula_da_e00.save(update_fields=["instrumento"])
    autoavaliacao = {
        "notas": {
            CRITERIO_1: {"nota": 3, "frase": "Autoavaliação do aluno."},
            CRITERIO_2: {"nota": 3, "frase": "Autoavaliação do aluno."},
        }
    }
    return checkpoint.entregar(ana_pronta, **entrega(laudo_do_aluno=autoavaliacao))


@pytest.fixture
def professora(esqueleto):
    """O espelho mínimo da professora: uma `Pessoa` qualquer, o avaliador dos
    testes de laudo. O acesso ao plantão (`CURSOS_PROFESSORES`) é outro
    guarda (`tests/test_plantao_acesso.py`); este fixture só monta o dado."""
    return Pessoa.objects.create(id_da_plataforma="p_professora", nome_exibido="Dani")


def notas_validas() -> dict:
    """Uma rubrica completa e válida para `instrumento_com_escala`: nota e
    frase em cada um dos dois critérios."""
    return {
        CRITERIO_1: {"nota": 4, "frase": "As bordas ficaram consistentes."},
        CRITERIO_2: {"nota": 5, "frase": "A proporção bateu com a referência."},
    }


def forcas_validas() -> list[str]:
    return [
        "O bevel das arestas ficou uniforme em todo o modelo.",
        "A escala bateu com a referência sem precisar de ajuste.",
        "O README explica o processo passo a passo.",
    ]


def mudanca_valida(aula) -> list[dict]:
    return [{"texto": "Praticar UV na próxima entrega.", "aula_id": aula.id}]


# ---------------------------------------------------------------------------
# O fio: o transporte do relay sob controle do teste (molde: `sugestoes`)
# ---------------------------------------------------------------------------


class Fio:
    """O que saiu no `xadd`. O Redis é dublado no TRANSPORTE (`redis.from_url`),
    pelo mesmo motivo que a `identidade` e a `alunos` são dubladas acima: uma
    suíte que precisa de container fica vermelha por motivo alheio, e a máquina
    do mantenedor é Windows. O que se prova é o comportamento do relay e a
    FORMA do que ele publica."""

    def __init__(self) -> None:
        self.mensagens: list[tuple[str, dict]] = []
        self.cliente = mock.Mock()
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
    """O relay publicando contra o dublê, e `REDIS_STREAMS_URL` presente. A
    variável é montada aqui e não numa fixture `autouse` de propósito: o relay
    a lê NO PONTO DE USO, e um teste que prove "Redis fora do ar" precisa poder
    tirá-la."""
    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://redis.teste:6379/0")
    linha = Fio()
    monkeypatch.setattr("redis.from_url", lambda *a, **k: linha.cliente)
    return linha


# ---------------------------------------------------------------------------
# A REDE DA ANTHROPIC: cortada para TODA a suíte, e dublada onde é medida
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def sem_anthropic(monkeypatch):
    """O corte fail-closed da rede do SDK da Anthropic, em TODO teste.

    **São duas bibliotecas de HTTP nesta célula, e o `respx` acima só corta
    uma.** O `httpx` é por onde a `identidade` e a `alunos` são perguntadas; o
    `httpx2` é outro pacote, instalado junto com o SDK da Anthropic
    (`apps/cursos/agente.py`), e nada em `respx` o alcança. Sem este corte, a
    suíte diria no próprio docstring que não fala com a rede e poderia chamar a
    API PAGA de verdade, com a chave da máquina de quem rodasse os testes: foi
    exatamente o que aconteceu no fórum (`armadilhas/288`).

    O corte é no TRANSPORTE, e não em `Client.post`, por dois motivos: o SDK
    chama `Client.send`, que `post` não intercepta, e cortar no transporte deixa
    `dublar_a_anthropic` trocar esta mesma função por uma resposta de mentira,
    exercitando o SDK de verdade, com o request e a leitura da resposta que a
    produção usa (`armadilhas/061`).
    """
    import httpx2

    def recusa(*args, **kwargs):
        raise httpx2.ConnectError("a suíte da sala de aula não fala com a rede")

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", recusa)


def corpo_da_anthropic(objeto, *, stop_reason: str = "end_turn") -> dict:
    """O JSON que a API da Anthropic devolve, na forma real, com `objeto`
    dentro do bloco de texto. `objeto` pode ser um dicionário (vira JSON) ou uma
    string crua, para os testes que provam o que acontece quando ela vem torta."""
    texto = (
        objeto if isinstance(objeto, str) else json.dumps(objeto, ensure_ascii=False)
    )
    return {
        "id": "msg_de_teste",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-4-5-20251001",
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "content": [{"type": "text", "text": texto}],
        "usage": {"input_tokens": 1200, "output_tokens": 340},
    }


def dublar_a_anthropic(monkeypatch, *, status=200, corpo=None, capturado=None):
    """Troca o TRANSPORTE do `httpx2`, que é por onde o SDK sai para a rede.

    O `sem_anthropic` acima já cortou esta mesma função; aqui ela é trocada de
    novo, por uma que responde. O SDK continua montando o request e lendo a
    resposta como monta e lê em produção, e `capturado` recebe a URL, os
    cabeçalhos e o CORPO REAL que saiu: é dele que sai a prova de que nome
    nenhum viajou.
    """
    import httpx2

    def falso(self, request):
        if capturado is not None:
            capturado["url"] = str(request.url)
            capturado["headers"] = dict(request.headers)
            capturado["corpo"] = json.loads(request.content)
        return httpx2.Response(status, json=corpo or {}, request=request)

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", falso)
