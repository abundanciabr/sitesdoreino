"""As peças que os guardas do portfólio montam, e nenhuma regra.

As fábricas montam estado; quem julga é o banco, e quem afirma é cada teste. Uma
fábrica que decidisse o que é permitido seria o teste medindo a própria resposta.

**Nenhum instante fixo mora aqui.** `criado_em` e `criada_em` são `auto_now_add`
e quem os preenche é o relógio da máquina: uma constante escrita no topo do
arquivo vira bomba-relógio no dia em que o relógio real a ultrapassar
(`armadilhas/323`, medida na célula `encomendas` em 04/09/2026, três horas
depois de o arquivo nascer).
"""

from datetime import datetime, timezone as fuso
from urllib.parse import quote

import httpx
import pytest
import respx

from apps.portfolio.models import EstadoDoAluno, ItemDeConferencia, Peca, Portfolio

SITE = "escola-a"
OUTRO_SITE = "escola-b"

# Os `servers:` dos contratos congelados mais o caminho de cada operação. Ficam
# aqui, escritos por extenso, porque o dublê EXIGE exatamente estes endereços:
# um dublê que aceitasse qualquer caminho testaria metade do cliente, e foi
# assim que um `/alunos` a menos passou por 39 testes verdes no fórum
# (`armadilhas/111`).
IDENTIDADE = "http://identidade:8000/interno"
ALUNOS = "http://alunos:8000/api/alunos"
URL_DA_SESSAO = f"{IDENTIDADE}/sessao/completa"

# O cookie de sessão do site, OPACO para esta célula: o valor não significa
# nada aqui, e é isso que o [INV-P12] exige. Quem prova que ele viaja intacto é
# `tests/test_porta_e_tela_minima.py`.
COOKIE = "meshcraft_sessao=cookie-opaco-de-ana"

ANA = {
    "autenticado": True,
    "id": "p_ana",
    "email": "ana@exemplo.com",
    "nome_exibido": "Ana",
    "papel": "aluno",
}


def agora():
    """O relógio real, nunca um instante escrito à mão (`armadilhas/323`)."""
    return datetime.now(tz=fuso.utc)


def url_da_situacao(email: str) -> str:
    return f"{ALUNOS}/alunos/{quote(email, safe='')}/situacao"


@pytest.fixture
def env_dos_pares(monkeypatch):
    """Os dois pares provisionados, como o env da VPS os terá.

    Sai do `monkeypatch`, e não do ambiente de quem roda a suíte: com estas
    variáveis vindas da máquina, os testes de fail-closed mediriam o computador
    em vez do código.
    """
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-pages-para-identidade")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-pages-para-alunos")


@pytest.fixture
def rede():
    """O dublê de TRANSPORTE. Chamada a URL não registrada levanta na hora.

    Dublar o transporte, e nunca a função do cliente, é o que faz o cliente de
    verdade montar a URL de verdade.
    """
    with respx.mock(assert_all_called=False) as dublagem:
        yield dublagem


def dublar_sessao(rede, corpo=None, *, status: int = 200):
    """A `identidade` responde `corpo` (ou só o status) para qualquer cookie."""
    resposta = httpx.Response(status, json=corpo if corpo is not None else {})
    return rede.get(URL_DA_SESSAO).mock(return_value=resposta)


def dublar_matricula(rede, email: str, categoria: str = "aluno", *, status: int = 200):
    """A `alunos` responde a categoria desta pessoa, no corpo do contrato."""
    corpo = {"categoria": categoria, "na_fila": None} if status == 200 else {}
    return rede.get(url_da_situacao(email)).mock(
        return_value=httpx.Response(status, json=corpo)
    )


@pytest.fixture
def aluna(env_dos_pares, rede, db):
    """Ana, reconhecida pela `identidade` e com matrícula ativa na `alunos`.

    **Ela pede o banco desde o degrau 07**, e não por capricho: quem passa pela
    porta chega na Prancheta, e a Prancheta lê o roteiro da escola do banco. Uma
    aluna sem `db` só voltaria a passar no dia em que a tela dela parasse de
    mostrar o roteiro.
    """
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    return ANA


@pytest.fixture
def criar_portfolio(db):
    """Fábrica de portfólio no estado normal: vitrine desligada, sem apelido.

    O padrão é o do aluno que acabou de abrir a Prancheta pela primeira vez, e é
    de propósito que ele seja o estado privado: a vitrine é opt-in (AC-13).
    """

    def fabrica(aluno_id, *, site_id=SITE, apelido="", publicada=False):
        return Portfolio.objects.create(
            site_id=site_id,
            aluno_id=aluno_id,
            apelido=apelido,
            vitrine_publicada=publicada,
            publicada_em=agora() if publicada else None,
        )

    return fabrica


@pytest.fixture
def criar_peca(db):
    """Fábrica de peça: um link colado, na posição pedida."""

    def fabrica(
        portfolio, *, ordem=1, link="https://exemplo.test/render.png", **campos
    ):
        return Peca.objects.create(
            portfolio=portfolio, ordem=ordem, link=link, **campos
        )

    return fabrica


@pytest.fixture
def criar_item(db):
    """Fábrica de item da lista de conferência, desmarcado."""

    def fabrica(portfolio, *, chave="tres-tipos-escolhidos", etapa=1, **campos):
        return ItemDeConferencia.objects.create(
            portfolio=portfolio, chave=chave, etapa=etapa, **campos
        )

    return fabrica


@pytest.fixture
def criar_estado(db):
    """Fábrica de estado do aluno, na primeira etapa e sem selo."""

    def fabrica(portfolio, **campos):
        return EstadoDoAluno.objects.create(portfolio=portfolio, **campos)

    return fabrica


# O `site_id` desta instalação, como o env da VPS o terá quando a linha
# `SITE_ID` for escrita no `infra/provisionar-pages.sh`. Ele NÃO é lido do
# ambiente de quem roda a suíte: com o valor vindo da máquina, o guarda do
# caso "sem SITE_ID" mediria o computador em vez do código.
SITE_DECLARADO = "escola-a"


@pytest.fixture
def site_declarado(monkeypatch):
    """A instalação sabe de que escola ela é."""
    monkeypatch.setenv("SITE_ID", SITE_DECLARADO)
    return SITE_DECLARADO


@pytest.fixture
def sem_site_declarado(monkeypatch):
    """O estado da VPS de hoje: `provisionar-pages.sh` não escreve `SITE_ID`.

    É o caso que o degrau 07 encontrou e não pôde consertar sozinho (a linha
    mora em `infra/`, caminho CODEOWNERS). A Prancheta continua mostrando o
    roteiro e diz, em português, por que a marcação não abre.
    """
    monkeypatch.delenv("SITE_ID", raising=False)


# QUEM CONFERE O PORTFÓLIO (degrau 11, critério AC-11). A equipe da escola NÃO
# é aluno: ela não tem matrícula ativa, e é por isso que as duas fábricas abaixo
# não dublam a `alunos`. Se alguém puser a fila da equipe atrás da pergunta da
# matrícula, o dublê de transporte levanta na hora por causa de uma chamada a
# URL não registrada, e o teste fica vermelho no lugar certo.
BIA = {
    "autenticado": True,
    "id": "p_bia",
    "email": "bia@exemplo.com",
    "nome_exibido": "Bia",
    "papel": "staff",
}


@pytest.fixture
def da_equipe(env_dos_pares, rede, monkeypatch, db):
    """Bia, reconhecida pela `identidade` e NA lista de quem confere."""
    dublar_sessao(rede, BIA)
    monkeypatch.setenv("IDS_DA_EQUIPE", BIA["id"])
    return BIA


@pytest.fixture
def fora_da_equipe(env_dos_pares, rede, monkeypatch, db):
    """A mesma pessoa, com a lista VAZIA: o estado da VPS enquanto ninguém a escreve.

    Fail-closed sem fail-hard: a célula sobe, as telas do aluno respondem, e só
    a fila fica fechada. Sai do `monkeypatch`, e não do ambiente de quem roda a
    suíte, para o guarda medir o código em vez do computador.
    """
    dublar_sessao(rede, BIA)
    monkeypatch.delenv("IDS_DA_EQUIPE", raising=False)
    return BIA
