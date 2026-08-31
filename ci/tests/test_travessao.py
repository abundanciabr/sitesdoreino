"""A MURALHA DO TRAVESSÃO — e as três formas de ela falhar como instrumento.

A regra que este portão impõe é do mantenedor (30/08/2026): todo texto escrito
para ser publicado online sai sem travessão. Um portão de ESCRITA é fácil de
escrever e fácil de estragar, e os três estragos têm nome:

    ficar cego     — não ver o travessão que está na tela (`&mdash;`, uma
                     célula nova, uma tela nova numa célula que já existe);
    ficar cínico   — deixar a dívida herdada crescer, ou tratar lista ausente
                     como lista vazia e chamar isso de "tudo em ordem";
    ficar chato    — reprovar por hífen de palavra composta, ou por travessão
                     dentro de comentário que leitor nenhum recebe.

O terceiro é o menos óbvio e o mais perigoso. Um portão que dá falso vermelho é
desligado por quem trabalha — e um portão desligado não protege texto nenhum.
Por isso metade desta suíte prova o que ele NÃO reprova.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import travessao  # noqa: E402
from _nucleo import ErroDeInstrumentacao, Estado  # noqa: E402


# ---------------------------------------------------------------------------
# Um repositório de mentira, com a forma mínima que o detector precisa.
# ---------------------------------------------------------------------------
def _cenario(
    tmp_path: Path,
    arquivos: dict[str, str],
    herdados: str = "",
    bastidor: str = "",
) -> Path:
    raiz = tmp_path / "repo"
    (raiz / "ci").mkdir(parents=True)
    (raiz / "services").mkdir(parents=True)
    for nome, conteudo in arquivos.items():
        destino = raiz / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8")
    (raiz / travessao.LISTA_DE_HERDADOS).write_text(herdados, encoding="utf-8")
    (raiz / travessao.LISTA_DE_BASTIDOR).write_text(bastidor, encoding="utf-8")
    return raiz


# ---------------------------------------------------------------------------
# 1. NÃO FICAR CEGO — o que ele tem de enxergar.
# ---------------------------------------------------------------------------
def test_travessao_em_pagina_publica_reprova(tmp_path: Path) -> None:
    raiz = _cenario(
        tmp_path,
        {
            "services/loja/templates/loja/home.html": "<p>Ele só queria uma coisa — paz.</p>\n"
        },
    )
    relatorio = travessao.rodar(raiz)
    assert relatorio.estado is Estado.FAIL
    assert "home.html" in relatorio.render()


def test_a_recusa_ensina_as_quatro_trocas(tmp_path: Path) -> None:
    """A alternativa executável vem na MESMA tela — a linha de precisão da casa.

    Um portão que só diz "não" manda quem trabalha procurar a regra em outro
    arquivo, e é assim que a regra vira folclore.
    """
    raiz = _cenario(
        tmp_path,
        {"services/loja/templates/loja/home.html": "<p>Uma coisa — paz.</p>\n"},
    )
    texto = travessao.rodar(raiz).render()
    for pista in ("VÍRGULA", "PARÊNTESES", "DOIS-PONTOS", "ASPAS"):
        assert pista in texto


@pytest.mark.parametrize(
    "escrita",
    ["—", "–", "―", "&mdash;", "&ndash;", "&#8212;", "&#8211;", "&#x2014;", "&#x2013;"],
)
def test_toda_forma_de_risca_conta(tmp_path: Path, escrita: str) -> None:
    """Escrever `&mdash;` põe a mesma risca na tela — e escapava de um grep ingênuo."""
    raiz = _cenario(
        tmp_path,
        {
            "services/loja/templates/loja/home.html": f"<p>Uma coisa {escrita} paz.</p>\n"
        },
    )
    assert travessao.rodar(raiz).estado is Estado.FAIL


def test_celula_nova_entra_sozinha_na_superficie(tmp_path: Path) -> None:
    """A superfície é DERIVADA. Célula nova não espera ninguém lembrar dela.

    É a Classe 8 do plano mestre (mapa velho) evitada por construção: uma lista
    de caminhos mantida à mão envelheceria em silêncio, e o texto da célula
    recém-nascida ficaria fora da regra sem que nada apitasse.
    """
    raiz = _cenario(
        tmp_path,
        {
            "services/celula-que-nasceu-hoje/apps/x/templates/x/pagina.html": "<p>a — b</p>\n"
        },
    )
    assert travessao.rodar(raiz).estado is Estado.FAIL


def test_documentos_e_traducoes_tambem_sao_texto_publico(tmp_path: Path) -> None:
    raiz = _cenario(
        tmp_path,
        {
            "documentos/como-entrar.md": "O acesso é seu — para sempre.\n",
            "services/loja/traducoes/home.yaml": 'titulo:\n  pt-br: "Entrar — Meshcraft"\n',
        },
    )
    relatorio = travessao.rodar(raiz)
    assert relatorio.estado is Estado.FAIL
    saida = relatorio.render()
    assert "como-entrar.md" in saida and "home.yaml" in saida


# ---------------------------------------------------------------------------
# 2. NÃO FICAR CHATO — o que ele NÃO pode reprovar.
# ---------------------------------------------------------------------------
def test_hifen_de_palavra_composta_passa(tmp_path: Path) -> None:
    """`guarda-chuva` é letra, não pontuação. Um portão que o caçasse recusaria
    português correto, e seria desligado na primeira semana."""
    raiz = _cenario(
        tmp_path,
        {
            "services/loja/templates/loja/home.html": (
                "<p>Guarda-chuva, segunda-feira, bem-vindo, e-mail, 2026-08-30.</p>\n"
            )
        },
    )
    assert travessao.rodar(raiz).estado is Estado.PASS


@pytest.mark.parametrize(
    "corpo",
    [
        "{% comment %}\nnota de quem escreveu — some na renderização\n{% endcomment %}\n<p>ok</p>\n",
        '{% comment "rotulo" %}texto — interno{% endcomment %}\n<p>ok</p>\n',
        "{# nota rápida — interna #}\n<p>ok</p>\n",
        "<!-- lembrete — para o próximo agente -->\n<p>ok</p>\n",
    ],
)
def test_comentario_nao_e_texto_publicado(tmp_path: Path, corpo: str) -> None:
    """Sem esta poda a dívida medida seria quatro vezes maior e quase toda falsa.

    Medido no repositório real em 30/08/2026: 400+ travessões na contagem crua
    contra 125 de verdade publicados. Um portão que mede a coisa errada com
    precisão treina todo mundo a ignorá-lo.
    """
    raiz = _cenario(tmp_path, {"services/loja/templates/loja/home.html": corpo})
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_comentario_de_yaml_nao_conta_mas_o_texto_da_linha_conta(
    tmp_path: Path,
) -> None:
    """`#` fora de aspas é nota; dentro de aspas é o texto que o site publica."""
    raiz = _cenario(
        tmp_path,
        {
            "services/loja/traducoes/a.yaml": '# nota — interna\ntitulo:\n  pt-br: "limpo"\n',
            "services/loja/traducoes/b.yaml": 'titulo:\n  pt-br: "Promoção # 2 — hoje"\n',
        },
    )
    saida = travessao.rodar(raiz).render()
    assert "b.yaml" in saida and "a.yaml" not in saida


@pytest.mark.parametrize(
    "corpo",
    [
        "<script>\n/* nota do programador — some no navegador */\nvar a = 1;\n</script>\n",
        "<script>\n// nota curta — interna\nvar a = 1;\n</script>\n",
        "<style>\n/* o porquê deste padding — interno */\n.a { padding: 1px }\n</style>\n",
    ],
)
def test_comentario_de_js_e_de_css_nao_e_texto_publicado(
    tmp_path: Path, corpo: str
) -> None:
    """Reprovar comentário de código é a definição de portão chato.

    Achado em 30/08/2026, ao pagar a dívida: três dos 37 travessões "publicados"
    eram a nota de um programador dentro de `/* … */` no checkout. Texto que
    nenhum visitante recebe, e que teria sido reescrito para agradar o portão.
    """
    raiz = _cenario(tmp_path, {"services/loja/templates/loja/home.html": corpo})
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_o_texto_dentro_do_script_continua_valendo(tmp_path: Path) -> None:
    """A poda é dos COMENTÁRIOS, não do bloco. Rótulo montado em JS vai na tela.

    O caso real: `x-text="\\`${bump.name} — R$ ${preco}\\`"` no checkout é o nome
    do produto que a pessoa lê antes de pagar. Se a poda comesse o bloco todo, o
    portão ficaria cego justamente onde o texto é mais caro.
    """
    raiz = _cenario(
        tmp_path,
        {
            "services/loja/templates/loja/home.html": (
                "<script>\n"
                "  const rotulo = `${nome} — R$ ${preco}`;\n"
                "  const url = 'https://exemplo.test/a';\n"
                "</script>\n"
            )
        },
    )
    relatorio = travessao.rodar(raiz)
    assert relatorio.estado is Estado.FAIL
    assert "R$" in relatorio.render()


def test_barra_dupla_de_url_nao_corta_a_linha(tmp_path: Path) -> None:
    """`https://` não é comentário. Confundir os dois cegaria o resto da linha."""
    raiz = _cenario(
        tmp_path,
        {
            "services/loja/templates/loja/home.html": (
                "<script>\n  const a = 'https://x.test'; const b = `oi — tchau`;\n</script>\n"
            )
        },
    )
    assert travessao.rodar(raiz).estado is Estado.FAIL


def test_o_bastidor_declarado_fica_de_fora(tmp_path: Path) -> None:
    raiz = _cenario(
        tmp_path,
        {
            "services/admin/templates/admin/painel.html": "<p>só o dono lê — isto aqui</p>\n"
        },
        bastidor="services/admin/templates/admin/painel.html :: tela de administração, atrás da porta\n",
    )
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_linha_de_bastidor_sem_motivo_e_ERROR(tmp_path: Path) -> None:
    """Tirar um texto da regra exige dizer por quê. Carimbo não é motivo."""
    raiz = _cenario(
        tmp_path,
        {"services/admin/templates/admin/painel.html": "<p>a — b</p>\n"},
        bastidor="services/admin/templates/admin/painel.html :: sei la\n",
    )
    assert travessao.rodar(raiz).estado is Estado.ERROR


# ---------------------------------------------------------------------------
# 3. NÃO FICAR CÍNICO — a catraca da dívida.
# ---------------------------------------------------------------------------
def test_divida_declarada_passa(tmp_path: Path) -> None:
    raiz = _cenario(
        tmp_path,
        {"services/loja/templates/loja/home.html": "<p>a — b</p>\n"},
        herdados="services/loja/templates/loja/home.html :: 1\n",
    )
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_divida_que_cresce_reprova(tmp_path: Path) -> None:
    """Estar na lista não é licença para escrever travessão novo no mesmo arquivo."""
    raiz = _cenario(
        tmp_path,
        {"services/loja/templates/loja/home.html": "<p>a — b — c</p>\n"},
        herdados="services/loja/templates/loja/home.html :: 1\n",
    )
    relatorio = travessao.rodar(raiz)
    assert relatorio.estado is Estado.FAIL
    assert "CRESCEU" in relatorio.render()


def test_divida_que_encolhe_pede_o_numero_novo(tmp_path: Path) -> None:
    """Encolher é o objetivo — e precisa APARECER no diff, ou a lista vira ficção."""
    raiz = _cenario(
        tmp_path,
        {"services/loja/templates/loja/home.html": "<p>a, b</p>\n"},
        herdados="services/loja/templates/loja/home.html :: 2\n",
    )
    relatorio = travessao.rodar(raiz)
    assert relatorio.estado is Estado.FAIL
    assert "services/loja/templates/loja/home.html :: 0" in relatorio.render()


def test_divida_apontando_para_o_nada_reprova(tmp_path: Path) -> None:
    """Linha órfã parece garantia e não é: o arquivo sumiu, a proteção também."""
    raiz = _cenario(
        tmp_path,
        {"services/loja/templates/loja/home.html": "<p>limpo</p>\n"},
        herdados="services/loja/templates/loja/apagada.html :: 3\n",
    )
    relatorio = travessao.rodar(raiz)
    assert relatorio.estado is Estado.FAIL
    assert "apagada.html" in relatorio.render()


@pytest.mark.parametrize(
    "lista", [travessao.LISTA_DE_HERDADOS, travessao.LISTA_DE_BASTIDOR]
)
def test_lista_ausente_e_ERROR_nunca_PASS(tmp_path: Path, lista: str) -> None:
    """Lista ausente não é lista vazia. "Não consegui medir" nunca vira verde."""
    raiz = _cenario(
        tmp_path, {"services/loja/templates/loja/home.html": "<p>a — b</p>\n"}
    )
    (raiz / lista).unlink()
    assert travessao.rodar(raiz).estado is Estado.ERROR


def test_contagem_sem_numero_e_ERROR(tmp_path: Path) -> None:
    raiz = _cenario(
        tmp_path,
        {"services/loja/templates/loja/home.html": "<p>a — b</p>\n"},
        herdados="services/loja/templates/loja/home.html :: varios\n",
    )
    assert travessao.rodar(raiz).estado is Estado.ERROR


# ---------------------------------------------------------------------------
# 5. OS COMANDOS DE GESTÃO — os únicos `.py` da superfície.
# ---------------------------------------------------------------------------
SEMEADOR = "services/loja/apps/loja/management/commands/semear_areas.py"


def test_texto_que_o_semeador_publica_conta(tmp_path: Path) -> None:
    """O buraco que este bloco fecha era REAL, e tinha morador.

    A descrição das áreas do fórum nasce em `semear_areas.py` e aparece em
    `meshcraft.top/forum`. Enquanto a superfície era só `templates/`, esse texto
    ficava fora da regra — e a lei dizia, errado, que `.py` não tinha morador.
    """
    raiz = _cenario(tmp_path, {SEMEADOR: 'AREAS = [("a", "Mostre — seu trabalho")]\n'})
    relatorio = travessao.rodar(raiz)
    assert relatorio.estado is Estado.FAIL
    assert "semear_areas.py" in relatorio.render()


@pytest.mark.parametrize(
    "corpo",
    [
        '"""Cria as áreas do fórum — para ele não nascer vazio."""\nAREAS = []\n',
        "# nota de quem escreveu — interna\nAREAS = []\n",
        'def f():\n    """O porquê disto — só para quem programa."""\n    return 1\n',
    ],
)
def test_docstring_e_comentario_do_semeador_nao_contam(
    tmp_path: Path, corpo: str
) -> None:
    """A peneira é o que separa este portão de um `grep` no `.py`.

    Medido em 30/08/2026: 160 strings de `.py` com travessão nas células
    públicas; depois da peneira, 5 — e só uma delas vai mesmo para a tela.
    Sem isso a regra seria ruído puro e ninguém a respeitaria.
    """
    raiz = _cenario(tmp_path, {SEMEADOR: corpo})
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_py_que_nao_e_semeador_fica_de_fora(tmp_path: Path) -> None:
    """A superfície cresceu para uma CLASSE estreita, não para `.py` em geral."""
    raiz = _cenario(
        tmp_path,
        {
            "services/loja/apps/loja/views.py": 'MSG = "erro de validação — para quem programa"\n'
        },
    )
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_semeador_com_sintaxe_quebrada_nao_inventa_achado(tmp_path: Path) -> None:
    """Quem cobra sintaxe é o CI da célula. Aqui, arquivo ilegível não é violação."""
    raiz = _cenario(tmp_path, {SEMEADOR: "def (((\n"})
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_comando_que_nao_se_chama_semear_tambem_conta(tmp_path: Path) -> None:
    """A fronteira era o NOME do arquivo, e o nome deixou conteúdo de fora.

    Achado pelo mantenedor em 30/08/2026, olhando o site: `seed_sugestoes.py`
    cria as categorias e o quadro que o aluno lê na Caixa, e escapava do portão
    por começar com `seed` em vez de `semear`. Régua que depende de alguém
    escolher o prefixo certo do nome do arquivo não é régua.
    """
    raiz = _cenario(
        tmp_path,
        {
            "services/loja/apps/loja/management/commands/seed_categorias.py": 'N = ["Preço — justo"]\n'
        },
    )
    relatorio = travessao.rodar(raiz)
    assert relatorio.estado is Estado.FAIL
    assert "seed_categorias.py" in relatorio.render()


def test_o_init_da_pasta_de_comandos_nao_entra(tmp_path: Path) -> None:
    """`__init__.py` é encanamento do Python, nunca conteúdo."""
    raiz = _cenario(
        tmp_path,
        {"services/loja/apps/loja/management/commands/__init__.py": 'X = "a — b"\n'},
    )
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_o_seed_real_da_caixa_esta_na_superficie() -> None:
    """Prova de fora: o arquivo que o portão deixava escapar agora está dentro."""
    publicos = {p.relative_to(RAIZ).as_posix() for p in travessao.superficie(RAIZ)}
    assert (
        "services/sugestoes/apps/sugestoes/management/commands/seed_sugestoes.py"
        in publicos
    )


def test_o_semeador_real_do_forum_esta_na_superficie() -> None:
    """Prova de fora: contra o repositório, não contra um cenário amigo."""
    publicos = {p.relative_to(RAIZ).as_posix() for p in travessao.superficie(RAIZ)}
    assert "services/forum/apps/forum/management/commands/semear_areas.py" in publicos


# ---------------------------------------------------------------------------
# 4. A PROVA DE FORA — contra o repositório REAL, não contra um cenário amigo.
# ---------------------------------------------------------------------------
def test_a_superficie_real_pega_o_site_e_poupa_o_bastidor() -> None:
    """O padrão "prova de fora" da RETROSPECTIVA-FASE-D, aplicado à fronteira.

    Cenário de mentira prova a mecânica; só o repositório real prova que a
    fronteira caiu onde o mantenedor a colocou. As duas telas citadas aqui são
    o caso difícil: as duas moram na célula `admin`, e SÓ UMA é bastidor —
    `/docs/…` é rota isenta na porta, que qualquer visitante alcança.
    """
    publicos = {p.relative_to(RAIZ).as_posix() for p in travessao.superficie(RAIZ)}
    assert "services/admin/apps/core/templates/admin/doc_publico.html" in publicos
    assert "services/admin/apps/core/templates/admin/visao_geral.html" not in publicos
    # `/mapa/` não está em CAMINHOS_ISENTOS da porta: é tela de dentro, como a
    # visão geral. Classificá-la como pública foi o erro de 30/08/2026, corrigido
    # antes de entrar — e este assert é o que impede a volta.
    assert "services/admin/apps/core/templates/admin/mapa_do_site.html" not in publicos
    assert any(c.startswith("documentos/") for c in publicos)


def test_o_portao_esta_verde_no_repositorio_real() -> None:
    """Se este teste ficar vermelho, é texto público com travessão a mais."""
    relatorio = travessao.rodar(RAIZ)
    assert relatorio.estado is Estado.PASS, relatorio.render()


# ---------------------------------------------------------------------------
# 9. O TEXTO DE TELA QUE MORA EM CÓDIGO (31/08/2026, TAR-087, `armadilhas/254`)
#
# O portão passou a enxergar duas classes de `.py` que antes escapavam: quem
# declara `Choices` com rótulo escrito (automático, e só o RÓTULO é medido) e
# quem se declara com a marca `ci:texto-publicado` (o arquivo inteiro).
#
# A metade que estes guardas mais protegem é a NEGATIVA. Crescer a superfície
# para todo `.py` seria pior que o buraco: medido em 31/08/2026, 2758 strings e
# 94 travessões nas células públicas, quase todos em mensagem de erro que só um
# programador lê, e vários no próprio painel de travessões do Admin, que lista
# as riscas como DADO. Os testes de "fica de fora" abaixo não são zelo: são o
# desenho.
# ---------------------------------------------------------------------------
RISCA = "—"

MODELO_COM_ROTULO = "\n".join(
    [
        "from django.db import models",
        "",
        "",
        "class Sugestao(models.Model):",
        "    class Status(models.TextChoices):",
        f'        EM_ANALISE = "em_analise", "Em análise {RISCA} a equipe ainda olha"',
        '        PLANEJADO = "planejado", "Planejado"',
        "",
    ]
)


def test_rotulo_de_textchoices_reprova(tmp_path: Path) -> None:
    """O caso que motivou tudo: texto de tela morando em `models.py`."""
    raiz = _cenario(tmp_path, {"services/loja/apps/loja/models.py": MODELO_COM_ROTULO})
    relatorio = travessao.rodar(raiz)
    assert relatorio.estado is Estado.FAIL
    assert "models.py" in relatorio.render()


def test_o_valor_do_textchoices_nao_e_medido(tmp_path: Path) -> None:
    """O primeiro elemento da tupla é contrato, não frase.

    Ele viaja em contrato congelado, migration e banco. Medi-lo faria o portão
    mandar reescrever um identificador, que é mudança de contrato e tem Rito
    próprio.
    """
    fonte = "\n".join(
        [
            "from django.db import models",
            "",
            "",
            "class A(models.Model):",
            "    class Status(models.TextChoices):",
            f'        X = "em{RISCA}analise", "Em análise"',
            "",
        ]
    )
    raiz = _cenario(tmp_path, {"services/loja/apps/loja/models.py": fonte})
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_docstring_e_comentario_de_models_nao_contam(tmp_path: Path) -> None:
    fonte = "\n".join(
        [
            f'"""A camada de dados {RISCA} escrita para quem programa."""',
            "from django.db import models",
            "",
            "",
            "class A(models.Model):",
            "    class Status(models.TextChoices):",
            f"        # o rótulo abaixo {RISCA} este comentário não é texto de tela",
            '        X = "x", "Em análise"',
            "",
        ]
    )
    raiz = _cenario(tmp_path, {"services/loja/apps/loja/models.py": fonte})
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_py_sem_choices_e_sem_marca_fica_de_fora(tmp_path: Path) -> None:
    """A metade negativa do desenho, e a mais importante das duas.

    Se este teste ficar VERMELHO um dia, é porque alguém cresceu a superfície
    para todo `.py` — e o portão morre afogado no próprio ruído. É o `.py` comum
    que precisa ficar de fora, não o `models.py` que precisa entrar.
    """
    fonte = f'ERRO = "não consegui abrir o arquivo {RISCA} tente de novo"\n'
    raiz = _cenario(tmp_path, {"services/loja/apps/loja/servicos.py": fonte})
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_a_marca_poe_o_arquivo_inteiro_sob_o_portao(tmp_path: Path) -> None:
    fonte = "\n".join(
        [
            "# ci:texto-publicado",
            f'FRASES = {{"a": "A ideia chegou {RISCA} e ainda não foi decidida"}}',
            "",
        ]
    )
    raiz = _cenario(tmp_path, {"services/loja/apps/loja/textos.py": fonte})
    relatorio = travessao.rodar(raiz)
    assert relatorio.estado is Estado.FAIL
    assert "textos.py" in relatorio.render()


def test_a_marca_vence_o_choices(tmp_path: Path) -> None:
    """Arquivo com as duas coisas é medido INTEIRO, não só nos rótulos.

    Quem se declarou inteiro público está dizendo que tem mais texto de tela do
    que os rótulos. Obedecer só à metade mais fraca da declaração seria escolher,
    entre duas leituras, a que mede menos.
    """
    fonte = "\n".join(
        [
            "# ci:texto-publicado",
            "from django.db import models",
            "",
            "",
            "class A(models.Model):",
            "    class Status(models.TextChoices):",
            '        X = "x", "Em análise"',
            "",
            "",
            f'AVISO = "Espere a janela virar {RISCA} e vote nas outras"',
            "",
        ]
    )
    raiz = _cenario(tmp_path, {"services/loja/apps/loja/models.py": fonte})
    assert travessao.rodar(raiz).estado is Estado.FAIL


def test_choices_sem_rotulo_escrito_nao_entra(tmp_path: Path) -> None:
    """`X = "x"` sozinho não tem frase: o Django deriva o rótulo do nome."""
    fonte = "\n".join(
        [
            "from django.db import models",
            "",
            "",
            "class A(models.Model):",
            "    class Status(models.TextChoices):",
            '        PUBLICA = "publica"',
            "",
            "",
            f'ERRO = "falhou {RISCA} tente de novo"',
            "",
        ]
    )
    raiz = _cenario(tmp_path, {"services/loja/apps/loja/models.py": fonte})
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_migrations_ficam_de_fora(tmp_path: Path) -> None:
    """O rótulo numa migration é fotografia do modelo naquele dia.

    Corrigi-la não muda tela nenhuma, e um portão que exigisse isso mandaria
    reescrever história por um texto que ninguém mais lê.
    """
    fonte = "\n".join(
        [
            "# ci:texto-publicado",
            f'CHOICES = [("publica", "Pública {RISCA} qualquer um lê")]',
            "",
        ]
    )
    raiz = _cenario(
        tmp_path, {"services/loja/apps/loja/migrations/0001_initial.py": fonte}
    )
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_o_bastidor_tira_o_py_tambem(tmp_path: Path) -> None:
    """A lista curta do bastidor vale para código, não só para template."""
    raiz = _cenario(
        tmp_path,
        {"services/admin/apps/core/models.py": MODELO_COM_ROTULO},
        bastidor=(
            "services/admin/apps/core/models.py :: tela de administração, "
            "só o mantenedor lê estes rótulos\n"
        ),
    )
    assert travessao.rodar(raiz).estado is Estado.PASS


def test_neste_repo_o_texto_em_codigo_esta_sob_o_portao() -> None:
    """Prova sobre o repositório REAL, e não sobre um cenário de mentira.

    Os cenários de `tmp_path` acima provam a REGRA; este prova que ela alcança
    os moradores concretos que a `armadilhas/254` descreve. Sem ele a regra
    poderia estar certa e não pegar nada aqui dentro, que é a lição da
    `armadilhas/131`: um dublê com forma diferente da real responde a outra
    pergunta.
    """
    publicos = {p.relative_to(RAIZ).as_posix() for p in travessao.superficie(RAIZ)}
    assert "services/sugestoes/apps/sugestoes/models.py" in publicos
    assert "services/forum/apps/forum/models.py" in publicos
    assert "services/sugestoes/apps/core/participacao.py" in publicos
