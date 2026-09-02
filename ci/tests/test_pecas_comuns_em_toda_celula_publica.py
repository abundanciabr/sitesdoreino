"""Toda célula que serve página a gente desenha o menu do topo e o rodapé.

O DEFEITO, MEDIDO EM 02/09/2026
-------------------------------
O mantenedor abriu `https://meshcraft.top/conquistas/` e viu a única área do
site sem menu e sem rodapé. Medido na página no ar, antes de qualquer conserto:
`<footer` zero ocorrências, `barra-do-site` zero ocorrências — num dia em que
`/`, `/cadastro` e `/forum/` traziam as duas peças.

A pergunta dele foi a certa: *"como podemos configurar para que em todas as
páginas tenha o menu e o rodapé, exceto nas páginas que já configuramos para
nelas não tenha?"* A resposta honesta era que **não havia como**. As duas peças
nasceram em 31/08/2026 nas células que já tinham molde compartilhado (`funil` e
`forum`), e a cobertura delas nunca foi medida contra a lista de páginas do
site — só contra a memória de quem escreveu.

POR QUE OS GUARDAS QUE JÁ EXISTIAM NÃO PEGARAM
-----------------------------------------------
`services/forum/tests/test_rodape.py` varre o urlconf REAL e reprova rota nova
sem decisão de rodapé. Ele estava verde e correto no dia em que `/conquistas/`
estava sem rodapé — porque ele não sabe que a `gamificacao` existe. A cura da
`armadilhas/242` é POR CÉLULA; este arquivo é a mesma cura um andar acima
(`armadilhas/286`), no único lugar de onde dá para ver o site inteiro.

COMO ELE MEDE
-------------
A lista de células públicas sai de `painel/mapa-do-site.json`, que é a lista
única de endereços do projeto e já tem varredor próprio provando que ela não
mente sobre o roteamento (`ci/mapa_do_site.py`). Célula nova com página pública
entra nesta conta **sozinha**, no dia em que a rota nascer — que é exatamente o
que faltou em 01/09, quando as Conquistas foram ao ar.

Uma célula "desenha a peça" quando tem o MOTOR e alguma tela dela USA o motor.
Só a presença do arquivo não bastaria: uma célula poderia tê-lo sem nunca
chamar, e o guarda passaria verde sobre uma peça que ninguém vê. As duas formas
de ligar o motor contam, porque as duas existem em produção:

  · processador de contexto (`forum`, `gamificacao`, e o rodapé da `funil`)
  · tag de template (`funil/apps/core/templatetags/menu.py` — lá a chave da
    página sai do `resolver_match`, e a tag é chamada no `base_mobile.html`)

FAIL-CLOSED DE INSTRUMENTAÇÃO ([INV-CI01])
------------------------------------------
Mapa ausente, mapa sem endereço público, lista de dívida ausente ou nenhuma
célula encontrada **reprovam**, em vez de o teste passar por não ter o que
medir. "Não consegui olhar" nunca é "está limpo" — e neste guarda esse é o modo
de falha mais provável, porque tudo que ele mede vem de arquivos que outra
pessoa pode mover.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "painel" / "mapa-do-site.json"
DIVIDA = RAIZ / "ci" / "pecas-comuns-em-falta.txt"
SERVICES = RAIZ / "services"

# Quem lê uma página aqui é gente, e é por isso que ela precisa das peças. A
# `equipe` e a `maquina` ficam de fora: a primeira é bastidor, a segunda não é
# página nenhuma.
QUEM_LE_PAGINA = frozenset({"visitante", "aluno"})

# A marca de que uma TELA usa a peça. É o nome da variável que o motor entrega
# ao template — se ela não aparece em template nenhum da célula, o motor pode
# até existir, mas ninguém desenha nada.
MARCA_NA_TELA = {
    "menu": "menu_do_topo",
    "rodape": "rodape.variante",
}

TAMANHO_MINIMO_DO_MOTIVO = 20


def _mapa() -> list[dict]:
    assert MAPA.is_file(), (
        f"{MAPA} não existe. Este guarda não tem o que medir, e isso não é um "
        "OK — [INV-CI01]."
    )
    dados = json.loads(MAPA.read_text(encoding="utf-8"))
    enderecos = dados.get("enderecos")
    assert enderecos, "o mapa do site não tem endereço nenhum."
    return enderecos


def celulas_publicas() -> set[str]:
    """As células que servem página a gente, MEDIDAS do mapa do site."""
    achadas = {
        entrada["celula"]
        for entrada in _mapa()
        if entrada.get("alcance") == "publico"
        and not entrada.get("gesto")
        and entrada.get("para_quem") in QUEM_LE_PAGINA
    }
    assert achadas, (
        "não achei célula pública NENHUMA no mapa do site — isto é falha de "
        "medição, não notícia boa: o guarda passaria verde com o conjunto "
        "vazio ([INV-CI01])."
    )
    return achadas


def _templates_da_celula(celula: str) -> str:
    """Todo o texto de template da célula, num pedaço só.

    Ler o conteúdo, e não a lista de arquivos, é o que faz a medição ser sobre
    o que a tela DESENHA — o nome do arquivo não prova nada.
    """
    raiz = SERVICES / celula
    pedacos = []
    for caminho in raiz.rglob("*.html"):
        pedacos.append(caminho.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(pedacos)


def _tem_motor(celula: str, peca: str) -> bool:
    """As duas formas de ligar o motor, porque as duas existem em produção."""
    core = SERVICES / celula / "apps" / "core"
    return (core / f"{peca}.py").is_file() or (
        core / "templatetags" / f"{peca}.py"
    ).is_file()


def desenha(celula: str, peca: str) -> bool:
    """A célula tem o motor E alguma tela dela usa o motor."""
    if not _tem_motor(celula, peca):
        return False
    return MARCA_NA_TELA[peca] in _templates_da_celula(celula)


def divida_declarada() -> dict[str, str]:
    """`{"celula/peca": motivo}`, lido do arquivo de dívida."""
    assert DIVIDA.is_file(), (
        f"{DIVIDA} não existe. Sem ele o guarda não sabe distinguir buraco de "
        "exceção declarada, e passaria verde sobre os dois — [INV-CI01]."
    )
    linhas = {}
    for numero, bruta in enumerate(
        DIVIDA.read_text(encoding="utf-8").splitlines(), start=1
    ):
        linha = bruta.strip()
        if not linha or linha.startswith("#"):
            continue
        assert "::" in linha, (
            f"{DIVIDA.name}:{numero}: falta o `::` que separa a peça do motivo. "
            f"Formato: `<celula>/<peca> :: <por que ainda não tem>`."
        )
        chave, motivo = (parte.strip() for parte in linha.split("::", 1))
        assert chave.count("/") == 1, (
            f"{DIVIDA.name}:{numero}: {chave!r} não está na forma "
            f"`<celula>/<peca>`."
        )
        _, peca = chave.split("/")
        assert peca in MARCA_NA_TELA, (
            f"{DIVIDA.name}:{numero}: peça {peca!r} não existe. As que existem "
            f"são {sorted(MARCA_NA_TELA)}."
        )
        assert len(motivo) >= TAMANHO_MINIMO_DO_MOTIVO, (
            f"{DIVIDA.name}:{numero}: o motivo tem {len(motivo)} caracteres, e "
            f"o mínimo é {TAMANHO_MINIMO_DO_MOTIVO}. Carimbo não é motivo — "
            f"quem ler isto daqui a três meses precisa da razão."
        )
        assert chave not in linhas, (
            f"{DIVIDA.name}:{numero}: {chave!r} aparece duas vezes, com motivos "
            f"que podem discordar. Deixe uma linha só."
        )
        linhas[chave] = motivo
    return linhas


# ---------------------------------------------------------------------------
# O guarda, nos DOIS sentidos
# ---------------------------------------------------------------------------
def test_toda_celula_publica_desenha_as_pecas_ou_declara_a_divida():
    """Célula pública sem a peça precisa estar DITA, com motivo escrito.

    O silêncio nunca significa "esta área não precisa de menu": significa que
    ninguém decidiu, e foi assim que `/conquistas/` passou um dia e meio no ar
    sozinha no meio do site.
    """
    em_falta = {
        f"{celula}/{peca}"
        for celula in celulas_publicas()
        for peca in MARCA_NA_TELA
        if not desenha(celula, peca)
    }
    declaradas = set(divida_declarada())
    nao_declaradas = em_falta - declaradas
    assert not nao_declaradas, (
        f"estas células servem página a gente e NÃO desenham a peça: "
        f"{sorted(nao_declaradas)}.\n"
        f"Ou a célula ganha a peça (o molde está em `armadilhas/242`, e o "
        f"exemplo vivo é `services/gamificacao`), ou a falta entra em "
        f"`ci/pecas-comuns-em-falta.txt` com o motivo escrito."
    )


def test_nenhuma_divida_declarada_esta_podre():
    """Linha para uma peça que JÁ existe é pior que linha nenhuma.

    Ela diz ao próximo leitor que ainda há um buraco ali, e manda alguém gastar
    uma sessão procurando o que já foi consertado. É a mesma catraca das outras
    dívidas da casa: encolher também reprova, até o número novo aparecer no diff.
    """
    podres = {chave for chave in divida_declarada() if desenha(*chave.split("/"))}
    assert not podres, (
        f"estas linhas de `ci/pecas-comuns-em-falta.txt` são sobre peças que a "
        f"célula JÁ desenha: {sorted(podres)}.\nApague a linha no MESMO PR que "
        f"deu a peça à célula."
    )


@pytest.mark.parametrize("celula", ["funil", "forum", "gamificacao"])
def test_as_tres_celulas_que_ja_tem_tudo_continuam_tendo(celula):
    """O controle positivo dos dois guardas acima.

    Sem ele, um dia em que a varredura parasse de achar qualquer motor (nome de
    arquivo mudou, pasta mudou, o `rglob` deixou de casar) deixaria os dois
    lados vazios e iguais — verde por não medir nada, que é o modo de falha nº 1
    desta casa.
    """
    for peca in MARCA_NA_TELA:
        assert desenha(celula, peca), (
            f"a célula {celula} deveria desenhar {peca!r} e a varredura não "
            f"achou. Se a forma de ligar a peça mudou, ensine este guarda a "
            f"nova — não relaxe a asserção."
        )


def test_o_guarda_tem_dentes():
    """Prova que a medição REPROVA uma célula sem a peça.

    Guarda que nunca fica vermelho é decoração. A `checkout` é o caso real e
    parado: ela serve três páginas públicas e não desenha nem menu nem rodapé.
    """
    assert not desenha("checkout", "menu")
    assert not desenha("checkout", "rodape")
    assert "checkout" in celulas_publicas()
    assert "checkout/menu" in divida_declarada()
