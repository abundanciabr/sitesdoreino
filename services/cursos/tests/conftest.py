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

from io import StringIO
from urllib.parse import quote

import httpx
import pytest
import respx
from django.core.management import call_command
from django.utils import timezone

from apps.core import menu
from apps.cursos.models import Aula, Curso, Pausa, Peca

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
