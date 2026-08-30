"""Estilo não volta para a marcação (30/08/2026).

**Por que isto é um guarda e não uma preferência de estilo.** A política de
segurança desta área BLOQUEIA estilo embutido. A folha do `<head>` volta a
valer por hash (`armadilhas/199`), mas um atributo `style="..."` solto não tem
esse conserto: o padrão exigiria `'unsafe-hashes'` mais o hash de CADA valor,
o que não escala e afrouxaria a política para qualquer valor igual injetado.

Ou seja: um `style=` novo num template desta célula **não chega ao navegador do
dono**. E ele não quebra nada visivelmente — a página responde 200, o HTML sai
inteiro, e só aquele ajuste some. Foi assim que 39 deles se acumularam sem
ninguém notar.

Este teste é o mecanismo que a `RETROSPECTIVA-FASE-D` §2 cobra: a regra
"escreva no `base.html`, não na marcação" só vale enquanto algo a impuser.
"""

import re
from pathlib import Path

TEMPLATES = (
    Path(__file__).resolve().parents[1] / "apps" / "core" / "templates" / "admin"
)
ATRIBUTO = re.compile(r'\bstyle\s*=\s*"')

# Comentário é PROSA, e prosa fala sobre o defeito sem cometê-lo — este próprio
# guarda é explicado num comentário que cita `style="..."`. Apagar os
# comentários antes de procurar evita o falso-positivo; trocá-los por linhas
# vazias do mesmo tamanho mantém o número da linha certo no relatório.
COMENTARIOS = re.compile(
    r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}|<!--.*?-->|/\*.*?\*/", re.DOTALL
)


def _sem_comentarios(texto: str) -> str:
    return COMENTARIOS.sub(lambda m: "\n" * m.group(0).count("\n"), texto)


def test_nenhum_template_da_area_escreve_estilo_na_marcacao():
    achados = []
    for arquivo in sorted(TEMPLATES.glob("*.html")):
        corpo = _sem_comentarios(arquivo.read_text(encoding="utf-8"))
        for numero, linha in enumerate(corpo.splitlines(), start=1):
            if ATRIBUTO.search(linha):
                achados.append(f"{arquivo.name}:{numero}  {linha.strip()[:70]}")
    assert not achados, (
        "atributo `style=` na marcação — ele NÃO chega ao navegador do dono "
        "(a política bloqueia estilo embutido, e para atributo não há hash que "
        "resolva). Ponha a regra em `admin/base.html` e use uma classe:\n  "
        + "\n  ".join(achados)
    )


def test_as_classes_que_substituiram_os_atributos_existem_na_folha():
    """Trocar o atributo por uma classe que ninguém definiu é perder o ajuste
    do mesmo jeito — só que silenciosamente, e sem a política para culpar."""
    folha = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    nascidas_em_30_08 = (
        "espaco-8",
        "espaco-14",
        "espaco-16",
        "espaco-20",
        "espaco-26",
        "espaco-28",
        "espaco-34",
        "espaco-abaixo-10",
        "espaco-abaixo-20",
        "titulo-de-bloco",
        "mais-afastado",
        "titulo-de-lista",
        "titulo-da-conta",
        "texto-maior",
        "recado-fraco",
        "verde",
        "amarelo",
        "borda-vermelha",
        "borda-amarela",
        "vazio-da-coluna",
    )
    ausentes = [
        c for c in nascidas_em_30_08 if f".{c} " not in folha and f".{c}." not in folha
    ]
    assert not ausentes, f"classe usada na marcação e ausente da folha: {ausentes}"


def test_a_barra_proporcional_tem_um_passo_para_cada_decimo():
    """A barra de "quem espera" virou passos de 10% quando deixou de ser
    `style="width:N%"`. Faltar um passo deixa uma barra sem largura, e a tela
    diria "ninguém está esperando" para uma fila cheia."""
    folha = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    for passo in range(11):
        assert f".barra-gente.passo-{passo} " in folha, f"falta o passo {passo}"
