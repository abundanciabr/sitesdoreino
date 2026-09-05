"""Nenhuma tela redefine uma classe da moldura (05/09/2026).

**O defeito que este guarda fecha, medido na tela do mantenedor.** Ele abriu
`/admin/caixa/analise/` e mandou a foto: os selos das ideias apareciam como
pastilhas minúsculas com o texto vazando por cima do resto da página, e a barra
de votos era um retângulo escuro vazio do tamanho da tela.

A causa não era o CSS da aba estar errado. Era o CSS da aba estar CERTO e
perder: `admin/base.html` já usava três daqueles nomes para outra coisa.

    base.html:  .marca { width: 9px; height: 9px; }      ← um quadradinho de legenda
    a aba:      .marca { padding: 3px 10px; ... }        ← uma pastilha com texto dentro

    base.html:  .barra { display:flex; padding:14px 20px; background: ... }  ← a faixa do topo
    a aba:      .barra { height: 6px; ... }               ← a régua de votos

A cascata resolveu do jeito dela, e o resultado é uma tela que nenhum teste
enxergava: os 1051 guardas da célula continuavam verdes, porque todos mediam
TEXTO, e o que quebrou foi a forma.

**É primo do `test_toda_cor_usada_tem_dono`**, e pelo mesmo motivo: nome que
existe noutro lugar não dá erro nenhum: dá outra aparência. Aquele guarda
pergunta "esta cor tem dono?"; este pergunta "este nome já tem dono?".

**O que este guarda NÃO faz:** julgar aparência. Ele responde uma pergunta só,
mecanicamente — uma tela que herda a moldura define, sozinha, uma classe que a
moldura já define? Modificador (`.editor.encomenda`) e descendente
(`.editor .rotulo`) continuam livres, porque não é disso que a tela morre: são
formas de ESPECIALIZAR o que a moldura deu, e a casa já as usa de propósito.
"""

import re
from pathlib import Path

TEMPLATES = (
    Path(__file__).resolve().parents[1] / "apps" / "core" / "templates" / "admin"
)
MOLDURA = TEMPLATES / "base.html"

COMENTARIOS = re.compile(
    r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}|<!--.*?-->|/\*.*?\*/", re.DOTALL
)
# Uma classe declarada SOZINHA: `.foo {` no começo da regra, sem um segundo
# `.bar` colado (modificador) e sem espaço antes da chave (descendente).
CLASSE_NUA = re.compile(
    r"^\s*\.([a-z][a-z0-9-]*)\s*(?:,\s*\.[a-z][a-z0-9-]*\s*)*\{", re.M
)
ESTILO = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.DOTALL | re.IGNORECASE)


def _sem_comentarios(texto: str) -> str:
    return COMENTARIOS.sub(lambda m: "\n" * m.group(0).count("\n"), texto)


def _classes_nuas(css: str) -> set[str]:
    nuas = set()
    for linha in _sem_comentarios(css).splitlines():
        casado = CLASSE_NUA.match(linha)
        if casado:
            # A regra pode listar vários seletores; só os NUS contam.
            cabeca = linha.split("{")[0]
            for parte in cabeca.split(","):
                parte = parte.strip()
                if re.fullmatch(r"\.[a-z][a-z0-9-]*", parte):
                    nuas.add(parte[1:])
    return nuas


def test_nenhuma_tela_redefine_uma_classe_da_moldura():
    da_moldura = _classes_nuas(MOLDURA.read_text(encoding="utf-8"))
    assert (
        da_moldura
    ), "não achei classe nenhuma em base.html — o guarda mediria o vazio"

    achados = []
    for template in sorted(TEMPLATES.glob("*.html")):
        if template.name == "base.html":
            continue
        texto = template.read_text(encoding="utf-8")
        # Só quem HERDA a moldura corre o risco: `base_publico.html` é outra
        # folha-mãe, e as classes dela não disputam cascata com esta.
        if 'extends "admin/base.html"' not in texto:
            continue
        for bloco in ESTILO.findall(texto):
            for nome in sorted(_classes_nuas(bloco) & da_moldura):
                achados.append(f"{template.name}: .{nome}")

    assert not achados, (
        "tela redefinindo classe que a moldura já usa — a cascata decide, e o "
        "resultado é uma tela torta que nenhum teste de texto enxerga. Dê um "
        "nome próprio à sua, ou especialize a da moldura com um modificador "
        "(`.classe.minha`):\n  " + "\n  ".join(achados)
    )
