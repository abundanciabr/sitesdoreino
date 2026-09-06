"""Teste-guarda [INV-CUR-P1]: nenhuma tela compara alunos, e nenhuma porta
devolve dois alunos lado a lado.

Lei: `PLANO-CELULA-CURSOS.md` §9; critério de morte da constituição da célula
("ranking ou dois alunos lado a lado"). A sala é da pessoa que a abriu.

O guarda tem três dentes:

1. **Toda rota da célula, percorrida, só fala da pessoa da sessão.** Com DUAS
   pessoas no banco (Ana e Beto, cada um com progresso, registro de pausa e
   autoavaliação próprios), nenhuma resposta a Ana carrega o nome, o id, o
   registro ou a resposta de Beto. E o inverso.
2. **Não existe rota de lista de alunos.** O urlconf real é inventariado por
   igualdade: as rotas de hoje são estas, e nenhuma delas recebe o id de outra
   pessoa nem lista ninguém.
3. **Toda consulta de progresso e de registro nas views é filtrada pela
   pessoa.** Medido no código: nenhum `Progresso.objects`/`RegistroDePausa.objects`
   das views sem `pessoa=` na mesma chamada.

Provado por mutação em 05/09/2026: tirar o `pessoa=` da consulta de progresso
do mapa deixa 2 vermelhos (o estado de Beto aparece para Ana, e o dente 3);
tirar o `pessoa=` da consulta de registros da aula deixa 3 vermelhos (o
registro secreto de Beto vaza, e o dente 3); uma rota `alunos/` nova deixa o
dente 2 vermelho. Restaurado, 8 passed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.urls import get_resolver, reverse

from apps.cursos import progresso as portas
from apps.cursos.models import Aula, Pessoa, Progresso, RegistroDePausa
from tests.conftest import ANA, BETO, COOKIE, dublar_matricula, dublar_sessao

pytestmark = pytest.mark.django_db

AS_ROTAS_DA_CELULA = {
    "estatico",
    "registrar-pausa",
    "gravar-autoavaliacao",
    # O checkpoint (degrau 2.1, TAR-155): o aluno entrega por link, sempre a
    # PORTA da própria sessão (`_porta_aberta`) — o mesmo filtro por pessoa
    # que todas as rotas acima já respeitam.
    "entregar-checkpoint",
    "aula",
    "mapa",
    # O ENDEREÇO DO LIVRO (TAR-212): o mapa de UM curso e a aula com a parte.
    # Nenhuma das duas recebe pessoa: o `curso` é o slug do curso e a `parte` é
    # o número da Parte do livro. A sala continua sendo a de quem a abriu.
    "curso",
    "aula-do-curso",
    # O laudo recebido (degrau 2.2, TAR-156): a mesma porta da sessão, sem
    # parâmetro novo — só `numero`, como `aula`.
    "laudo-recebido",
    # O PLANTÃO (degrau 2.2, TAR-156) é uma AUDIÊNCIA DIFERENTE, de propósito:
    # a fila da professora mostra o envio de VÁRIOS alunos porque revisar em
    # fila É o trabalho dela — [INV-CUR-P1] protege a sala do ALUNO (nenhuma
    # porta do aluno compara alunos), não a tela de quem revisa. O acesso é
    # fail-closed por `CURSOS_PROFESSORES`
    # (`tests/test_plantao_acesso.py`), e é essa porta, não esta, quem
    # impede a pessoa errada de ver a fila.
    "plantao",
    "plantao-ficha",
}


@pytest.fixture
def duas_pessoas(env_dos_pares, rede, aula_publicada):
    """Ana e Beto, ambos com matrícula, cada um com o próprio rastro na E00."""
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    dublar_matricula(rede, BETO["email"], "aluno")
    beto = Pessoa.objects.create(id_da_plataforma=BETO["id"], nome_exibido="Beto")
    progresso = Progresso.objects.create(
        pessoa=beto,
        aula=aula_publicada,
        estado=Progresso.Estado.EM_PRODUCAO,
        autoavaliacao={"respostas": ["RESPOSTA-SECRETA-DE-BETO", "outra"]},
    )
    RegistroDePausa.objects.create(
        pessoa=beto,
        pausa=aula_publicada.pausas.get(ordem=1),
        respostas={"o que apareceu na tela": "REGISTRO-SECRETO-DE-BETO"},
    )
    return progresso


def _telas(client) -> list[tuple[str, str]]:
    """Toda tela GET da célula que renderiza conteúdo, aberta como Ana."""
    telas = []
    for endereco in (
        reverse("curso", args=["profissional"]),
        reverse("aula-do-curso", args=["profissional", 1, "E00"]),
        reverse("curso", args=["profissional"]),
        reverse("aula-do-curso", args=["profissional", 1, "E00"]),
    ):
        resposta = client.get(endereco, HTTP_COOKIE=COOKIE)
        assert resposta.status_code == 200, endereco
        telas.append((endereco, resposta.content.decode()))
    return telas


def test_nenhuma_tela_fala_de_outra_pessoa(duas_pessoas, client):
    for endereco, corpo in _telas(client):
        for pedaco in (
            "Beto",
            BETO["id"],
            "RESPOSTA-SECRETA-DE-BETO",
            "REGISTRO-SECRETO-DE-BETO",
        ):
            assert pedaco not in corpo, f"{endereco} vazou {pedaco!r} de outra pessoa"


def test_o_mapa_conta_so_as_portas_da_propria_pessoa(duas_pessoas, client):
    """Beto está em produção na E00; para Ana a E00 nasce disponível, e é
    isso que o mapa dela mostra, não o estado dele."""
    corpo = client.get(
        reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE
    ).content.decode()
    assert ">Disponível<" in corpo
    assert ">Em produção<" not in corpo


def test_a_aula_mostra_so_os_registros_da_propria_pessoa(duas_pessoas, client):
    """Beto já registrou a pausa 1; para Ana ela continua com formulário."""
    corpo = client.get(
        reverse("aula-do-curso", args=["profissional", 1, "E00"]), HTTP_COOKIE=COOKIE
    ).content.decode()
    assert 'action="' + reverse("registrar-pausa", args=["E00", 1]) in corpo
    assert "Registrada." not in corpo


def test_o_gesto_de_uma_pessoa_nunca_toca_a_linha_da_outra(duas_pessoas, client):
    client.post(
        reverse("registrar-pausa", args=["E00", 1]),
        {"campo_0": "o cubo de Ana"},
        HTTP_COOKIE=COOKIE,
    )
    client.post(
        reverse("gravar-autoavaliacao", args=["E00"]),
        {"resposta_0": "de Ana", "resposta_1": "também"},
        HTTP_COOKIE=COOKIE,
    )
    de_beto = Progresso.objects.get(pessoa__id_da_plataforma=BETO["id"])
    assert de_beto.autoavaliacao["respostas"][0] == "RESPOSTA-SECRETA-DE-BETO"
    assert RegistroDePausa.objects.filter(
        pessoa__id_da_plataforma=BETO["id"]
    ).get().respostas == {"o que apareceu na tela": "REGISTRO-SECRETO-DE-BETO"}
    assert RegistroDePausa.objects.count() == 2


def test_nao_existe_rota_de_lista_de_alunos():
    """Inventário por igualdade do urlconf real: rota nova passa por aqui."""
    nomes = {
        padrao.name
        for padrao in get_resolver().url_patterns
        if getattr(padrao, "name", None)
    }
    assert nomes == AS_ROTAS_DA_CELULA
    caminhos = " ".join(str(p.pattern) for p in get_resolver().url_patterns)
    for proibido in ("alunos", "ranking", "turma", "pessoas", "colegas"):
        assert proibido not in caminhos, proibido


def test_nenhuma_rota_recebe_o_id_de_outra_pessoa():
    """Os parâmetros de rota são a aula, a pausa e o arquivo de estilo; a
    pessoa é sempre a da sessão. `envio_id` (plantão) é a EXCEÇÃO nomeada:
    identifica um ENVIO, nunca uma pessoa por id, e só a professora
    (`CURSOS_PROFESSORES`, fail-closed) chega a essa rota.

    `curso` e `parte` (TAR-212) são o endereço do livro: o slug do curso e o
    número da Parte. Nenhum dos dois identifica gente."""
    parametros = set()
    for padrao in get_resolver().url_patterns:
        parametros |= set(re.findall(r"<(?:\w+:)?(\w+)>", str(padrao.pattern)))
    assert parametros == {"numero", "ordem", "caminho", "envio_id", "curso", "parte"}


def test_toda_consulta_de_progresso_nas_views_e_filtrada_pela_pessoa():
    """Medido no código das telas: `Progresso.objects…` e
    `RegistroDePausa.objects…` sempre com `pessoa=` na mesma chamada."""
    views = (
        Path(__file__).resolve().parents[1] / "apps" / "core" / "views.py"
    ).read_text(encoding="utf-8")
    chamadas = re.findall(
        r"(?:Progresso|RegistroDePausa)\.objects\.\w+\((?:[^()]|\([^()]*\))*\)", views
    )
    assert chamadas, "as views deixaram de consultar progresso; o guarda não mede nada"
    sem_pessoa = [c for c in chamadas if "pessoa=" not in c]
    assert sem_pessoa == [], sem_pessoa


def test_o_servico_de_progresso_tambem_nao_lista_ninguem():
    fonte = Path(portas.__file__).read_text(encoding="utf-8")
    assert "Pessoa.objects" not in fonte
    assert ".all()" not in fonte.replace("pausas.values_list", "")
