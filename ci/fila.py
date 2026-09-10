"""A FILA DE TRABALHO — tarefa é coisa registrada, e estado é uma conta.

    python ci/fila.py criar --titulo "..." --toca admin --move compras-no-mes \
        --evidencia-exigida "..." \
        --despacho "..." [--depende-de TAR-001] [--origem "..."]
    python ci/fila.py listar [--ao-vivo]     # estados calculados; --ao-vivo soma reservas e PRs
    python ci/fila.py pegar TAR-001 --quem "sessao-x"    # trava no servidor + evento
    python ci/fila.py zelar --quem "zelador-da-fila"    # rotula reivindicações órfãs
    python ci/fila.py soltar TAR-001 --quem "sessao-x"   # devolve à fila
    python ci/fila.py bloquear TAR-001 --quem "sessao-x" --motivo "..." \
        --espera mantenedor|fila                         # trava, com o porquê e quem destrava
    python ci/fila.py concluir TAR-001 --quem "sessao-x" --evidencia URL
    python ci/fila.py reconciliar TAR-001 --quem "maestro" \
        --aceite-registro painel/registros/AAAAMMDD-NNN-slug.js
    python ci/fila.py explicar TAR-001 --quem "sessao-x" \
        --o-que-e "..." --o-que-muda "..." --exemplo "..." --importancia 85
    python ci/fila.py validar                # fail-closed; roda na muralha
    python ci/fila.py imutabilidade          # nenhuma tarefa que já existia foi editada

Nascida da fase 2 do plano aprovado em 29/08/2026 (veredito em
`docs/consultorias/central-de-orquestracao/VEREDITO.md`). O que os três
consultores pediram e aqui vira mecanismo:

- **Estado calculado, nunca campo editado.** Não existe campo `status` em
  lugar nenhum: o arquivo da tarefa nunca muda depois de criado, e a coluna
  do quadro é sempre calculada da cadeia de eventos + reservas + PRs.
- **Trava atômica com prazo.** `pegar` NÃO inventa trava própria: chama o
  almoxarife (`ci/reservar.py`), que cria uma referência no servidor do
  GitHub — quem chega segundo recebe recusa DO SERVIDOR, na hora, e a
  reserva expira sozinha se a sessão morrer.
- **Concluir exige evidência.** Sem prova, `concluir` recusa — a mesma lei
  do verde do livro (`painel/LEIA-ME.md`).
- **O comprovante nasce na bancada, nunca no espelho** (30/08/2026, TAR-018).
  `criar`/`pegar`/`concluir` RECUSAM no clone principal, e `validar` diz em
  voz alta quando acha comprovante que o Git não conhece — ver a seção
  "Onde o comprovante nasce", mais abaixo.

O molde é o do livro: fonte multiescritor (um arquivo por tarefa em
`fila/tarefas/`, um arquivo por acontecimento em `fila/eventos/` — imune a
conflito por construção), nada se edita, corrigir é acrescentar.

Dialeto de exit (RETROSPECTIVA-FASE-D §1): 0 = OK · 1 = recusa/violação ·
2 = ERROR (não consegui medir — e não medir nunca é passar).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

CI = Path(__file__).resolve().parent
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import reservar  # noqa: E402
import responsabilidades  # noqa: E402
import estado_da_entrega  # noqa: E402
import revisor_de_pouso  # noqa: E402
from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    configurar_saida,
    executar,
    raiz_do_repo,
)

# Quem sabe distinguir espelho de bancada é a muralha da pasta compartilhada, e
# ela sabe desde 26/08/2026: no worktree o `.git` é ARQUIVO, no clone principal
# é PASTA. Importar é de propósito — duas leituras do mesmo fato divergiriam no
# primeiro dia em que alguém mexesse numa só (a lei anti-duplicação, no código).
from muralha_pasta_compartilhada import raiz_do_checkout  # noqa: E402

# O ciclo de vida inteiro. Fechado de propósito: evento fora desta lista é
# arquivo inválido, não "vocabulário novo" — vocabulário muda por PR, aqui.
EVENTOS_DE_CICLO = ("reivindicada", "devolvida", "bloqueada", "reivindicacao_expirada")
EVENTOS_TERMINAIS = ("concluida", "cancelada")

# A EXPLICAÇÃO PARA GENTE — o evento que não é ciclo nem fim (06/09/2026)
#
# Medido em 06/09/2026: o mantenedor abriu `/admin/caixa/robos/`, viu 22 tarefas
# paradas e não entendeu NENHUMA. Os cinco campos que a tarefa tinha (`titulo`,
# `toca`, `despacho`, `origem`, `evidencia_exigida`) foram escritos por robô para
# robô, e nos 214 arquivos de tarefa da fila não havia um só campo dirigido a
# quem paga a conta. Ele pediu duas coisas: o que a tarefa é em português com um
# exemplo, e um jeito de saber o que vem antes.
#
# `explicada` é de uma terceira espécie, de propósito, e é isso que faz o verbo
# funcionar:
#   - NÃO é ciclo: não muda o estado calculado. Explicar não pega, não devolve,
#     não trava. `calcular_estados` só olha `EVENTOS_DE_CICLO` para saber o
#     último gesto, e por isso a explicação passa por ela sem tocar em nada.
#   - NÃO é terminal, e é o ÚNICO evento que PODE VIR DEPOIS DO FIM. A regra do
#     silêncio existe para que ninguém reescreva o que ACONTECEU com a tarefa;
#     a explicação diz o que a tarefa É, e isso não muda por ela ter terminado.
#     Uma tarefa concluída que ninguém entende continua ilegível no histórico.
#   - É o único verbo que PODE REPETIR, e a última vence. É assim que se
#     conserta um texto ruim: o arquivo da tarefa não se edita (`armadilhas/356`
#     e o guarda `cmd_imutabilidade`, mais abaixo), então corrigir é
#     acrescentar, como em todo o resto desta casa.
EXPLICADA = "explicada"

EVENTOS_VALIDOS = EVENTOS_DE_CICLO + EVENTOS_TERMINAIS + (EXPLICADA, "submetida")

# Os quatro campos, e só eles. O contrato é fechado aqui porque a célula `admin`
# o consome pelo `estados.json` que `listar --json` gera no build: campo novo
# entra por PR neste arquivo, nunca por invenção num JSON.
CAMPOS_DA_EXPLICACAO = ("o_que_e", "o_que_muda", "exemplo", "importancia")
TEXTOS_DA_EXPLICACAO = ("o_que_e", "o_que_muda", "exemplo")
IMPORTANCIA_MINIMA = 0
IMPORTANCIA_MAXIMA = 100

# Os estados que `listar` calcula. Ninguém escreve isto em arquivo nenhum.
NA_FILA = "na fila"
REIVINDICADA = "reivindicada"
EM_EXECUCAO = "em execução"
BLOQUEADA = "bloqueada"
CONCLUIDA = "concluída"
CANCELADA = "cancelada"

CAMPOS_DA_TAREFA = {
    "arquivo": str,
    "id": str,
    "titulo": str,
    "toca": list,
    "evidencia_exigida": str,
    "despacho": str,
    "origem": str,
    "criada_em": str,
}
# `cria`: as pastas que ESTA tarefa traz à existência. Só a tarefa de gênese
# precisa dele, e ele existe para que um `toca` legítimo possa nomear uma célula
# que ainda não nasceu. Quem lê e o que isso muda: `ci/conferencia_do_toca.py`,
# em `areas_criadas` — UMA definição só, para as duas leituras não divergirem.
# `move`: que NÚMERO do placar esta tarefa pretende mover. É o elo entre o
# trabalho e a estratégia (degrau 19 do `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`,
# a peça nova do quinto documento do Scale OS: "toda tarefa deve responder que
# resultado estratégico ela move"). TRÊS estados, diferentes de propósito:
#   ausente                  → NINGUÉM DECLAROU. Não é o mesmo que "não move nada",
#                              e é o estado das 123 tarefas anteriores a 04/09/2026.
#   ["manutencao"]           → declarado: mantém a fábrica de pé, não move número.
#   ["compras-no-mes", ...]  → move estes cartões de `painel/cartoes/`.
# O nome tem de ser de um cartão que EXISTE: o `toca` já ensinou nesta casa que
# campo de texto livre vira erro de digitação silencioso. Opcional aqui e
# obrigatório em `criar` (`--move`): campo que nasce opcional no balcão nasce vazio.
MANUTENCAO = "manutencao"
CAMPOS_OPCIONAIS_DA_TAREFA = {
    "depende_de": list,
    "responsabilidade": str,
    "responsabilidade_obrigatoria": bool,
    "notas": str,
    "cria": list,
    "move": list,
    "medicao_fase4": dict,
}

CAMPOS_DA_MEDICAO_FASE4 = {
    "piloto", "condicao", "tipo", "complexidade", "natureza", "componentes",
    "fronteiras_integracao", "migracao", "risco", "escopo_publicacao",
    "revisao_instrumento",
}

CAMPOS_DO_EVENTO = {
    "arquivo": str,
    "tarefa": str,
    "evento": str,
    "quando": str,
    "quem": str,
}
CAMPOS_OPCIONAIS_DO_EVENTO = {
    "pr": str,
    "revisao": str,
    "arvore": str,
    "detalhe": str,
    "evidencia": str,
    "verificado_em": str,
    "espera": str,
    # Só em `explicada`, e `carregar_eventos` cobra isso: campo fora do evento a
    # que pertence é história escrita no lugar errado (a mesma lei do `espera`).
    "o_que_e": str,
    "o_que_muda": str,
    "exemplo": str,
    "importancia": int,
}

# QUEM DESTRAVA UMA TAREFA PARADA — o campo que faltava (06/09/2026)
#
# "Bloqueada" sempre significou duas coisas incompatíveis no mesmo balde, e a
# tela do dono pagava a conta: em 06/09/2026 o quadro tinha 27 paradas, e ele
# precisava abrir os 27 cartões e ler o motivo de cada um para descobrir que
# SEIS esperavam uma decisão dele e as outras 21 não esperavam ninguém.
#
# Metade da resposta já era calculada e se perdia: `calcular_estados` distingue
# o bloqueio por DEPENDÊNCIA ABERTA (13 das 27 naquele dia — a fila andando,
# ninguém precisa fazer nada) do bloqueio por EVENTO ESCRITO. O que não existia
# era a segunda metade: dentro dos escritos, quem destrava.
#
# Ler isso do texto do `detalhe` foi considerado e RECUSADO. Seria adivinhar
# por palavra ("espera mandato", "só o mantenedor pode") uma resposta que o
# robô que bloqueou SABE na hora de bloquear — e `robos.py` já proíbe o palpite
# com todas as letras: uma segunda definição de "o que espera por você" nasceria
# concorrendo com a que o livro calcula. Quem sabe, declara.
#
# Dois valores, e só dois, porque a pergunta é binária: dá para um robô resolver
# sozinho, ou não dá? Terceiro valor sempre viraria "mais ou menos", e a tela
# não tem terceiro lugar para pôr isso.
ESPERA_O_MANTENEDOR = "mantenedor"
ESPERA_A_FILA = "fila"
QUEM_DESTRAVA = (ESPERA_O_MANTENEDOR, ESPERA_A_FILA)

RE_ID = re.compile(r"^TAR-(\d{3,})$")
RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Como um PR diz a que tarefa ele atende: citando `TAR-NNN` no título ou no
# ramo. UMA definição só — `ci/conferencia_do_toca.py` lê o mesmo fato para
# saber de quem é o `toca` que vai conferir, e duas leituras do mesmo fato
# divergiriam no primeiro dia em que alguém mexesse numa só.
RE_CITACAO = re.compile(r"TAR-\d{3,}")
PREFIXO_DA_RESERVA = "tarefa-"  # refs/reservas/tarefa-TAR-001
RE_REGISTRO_DE_ACEITE = re.compile(
    r"painel/registros/\d{8}-\d{3}-[a-z0-9-]+\.js"
)
RE_URL = re.compile(r"https?://[^\s<>\"']+")
CAMINHOS_POSTERIORES_PERMITIDOS = ("fila/eventos/", "painel/registros/")


class RecusaDeReconciliacao(ValueError):
    """A medição terminou e encontrou uma entrega que ainda não pode fechar."""


# ---------------------------------------------------------------------------
# Onde o comprovante nasce — a cura da armadilhas/192 (TAR-018, 30/08/2026)
#
# O buraco medido: a ordem de partida dos despachos mandava pegar a tarefa no
# balcão ANTES de criar o worktree. O evento de reivindicação nascia então no
# CLONE PRINCIPAL — pasta onde a muralha do RITOS §1 impede commitar qualquer
# coisa — e NADA acusava: com o arquivo fora, `validar` respondia "✅ Fila
# válida", exit 0. A tarefa chegava à `main` com `concluida` e sem
# `reivindicada`, e o histórico de quem pegou o trabalho sumia. A muralha da
# pasta compartilhada não pegava porque ela cobre `Edit`/`Write` e git de
# estado — não escrita feita por dentro de um script (fronteira que a própria
# `armadilhas/135` declara).
#
# A cura tem duas peças, com AUTORIDADE DIFERENTE de propósito:
#
#   1. RECUSA (exit 1) nos gestos que escrevem: o arquivo simplesmente não
#      nasce no lugar errado. Não é portão de CI — nenhum PR reprova por isto;
#      é um comando interativo se recusando a produzir lixo, e o conserto custa
#      um `git worktree add`. Aviso em sombra aqui não curaria nada: o arquivo
#      já teria nascido, e o robô nem consegue apagá-lo (medido em 30/08/2026 —
#      o classificador de permissão recusou a limpeza ao robô da TAR-014).
#   2. SOMBRA no `validar`: comprovante que o Git não conhece é DITO em voz
#      alta, e o veredito não muda. É aqui que mora o portão de CI
#      (`ci/muralha-da-fila.sh`), e é aqui que vale a lei do Sistema
#      Imunológico — regra nova nasce em sombra, dizendo o que teria feito.
# ---------------------------------------------------------------------------

# Quem exige bancada é cada comando, chamando `_parar_se_for_o_espelho` na sua
# primeira linha: `criar`, `pegar`, `bloquear`, `cancelar` e `concluir`.
# `listar` e `validar` só leem. `soltar` escreve, e continua livre no espelho
# de propósito: devolver à fila uma tarefa presa é gesto de emergência, e
# emergência não pode depender de ter worktree — o evento perdido custa menos
# que a tarefa travada (decisão do despacho da TAR-018).
#
# Houve aqui uma tupla `GESTOS_QUE_EXIGEM_BANCADA` que ninguém lia, e ela já
# tinha apodrecido: nasceu sem `bloquear`, que passou a recusar no espelho em
# 04/09/2026 sem que ela soubesse. Lista que nenhum código executa não é
# documentação, é uma segunda verdade esperando a vez de mentir.

RITO_DO_WORKTREE = (
    "git fetch origin && git worktree add ../wt-<area>-<tarefa> "
    "-b agent/<area>/<tarefa> origin/main"
)


def _parar_se_for_o_espelho(gesto: str, raiz: Path) -> str | None:
    """O motivo da recusa (quem chama devolve exit 1), ou None para seguir.

    Três estados, como todo portão deste projeto:
      - bancada (worktree, `.git` ARQUIVO) ou pasta que não é checkout git ..... None
      - espelho (clone principal, `.git` PASTA) ................ o motivo, e ele ENSINA
      - não deu para medir onde estamos ....... ErroDeInstrumentacao (exit 2, INV-CI01)

    Pasta sem `.git` nenhum não é "não consegui medir": é medição que deu
    "não há repositório aqui" — e sem repositório não há PR para o comprovante
    perder. É o caso dos próprios testes, e ele passa.
    """
    try:
        encontrado = raiz_do_checkout(raiz)
    except Exception as erro:  # pragma: no cover - defesa, não caminho
        raise ErroDeInstrumentacao(
            f"não consegui medir em que pasta `{gesto}` está rodando",
            f"{erro.__class__.__name__}: {erro}\n"
            "Sem essa medição eu escreveria o comprovante às cegas, e ele já "
            "nasceu órfão uma vez (armadilhas/192). 'Não medi' nunca vira "
            "permissão de escrever.",
        )
    if encontrado is None:
        return None
    checkout, e_o_clone_principal = encontrado
    if not e_o_clone_principal:
        return None
    return (
        f"🧱 RECUSADO NO ESPELHO: `fila.py {gesto}` está rodando dentro do CLONE\n"
        "   PRINCIPAL —\n"
        f"     {checkout}\n"
        "   e o comprovante nasceria numa pasta onde você não pode commitar nada\n"
        "   (RITOS.md §1, a muralha da pasta compartilhada). Ele ficaria órfão, e\n"
        "   o seu PR iria sem ele.\n"
        "\n"
        f"   ISTO NÃO É RECUSA DA TAREFA — ela continua livre, e a reserva no\n"
        "   servidor do GitHub NÃO depende da pasta. Inverta a ordem e o MESMO\n"
        "   comando passa:\n"
        "\n"
        f"     {RITO_DO_WORKTREE}\n"
        "     cd ../wt-<area>-<tarefa>\n"
        f"     python ci/fila.py {gesto} ...        # o mesmo comando, aqui dentro\n"
        "\n"
        "   Por quê: em 30/08/2026 o comprovante da TAR-016 nasceu no espelho,\n"
        "   ninguém avisou, e `validar` respondeu '✅ Fila válida' com ele fora\n"
        "   (armadilhas/192). No espelho continuam livres `listar`, `validar` e\n"
        "   `soltar`."
    )


def comprovantes_que_o_git_nao_conhece(raiz: Path) -> list[str] | None:
    """Arquivos de `fila/eventos/` que o Git não rastreia — o comprovante que
    existe no disco e NÃO vai viajar em PR nenhum.

    `None` = não deu para medir (git ausente ou mudo). Pasta sem `.git` devolve
    lista vazia: sem repositório não há PR a perder.
    """
    if not (raiz / ".git").exists():
        return []
    try:
        proc = subprocess.run(
            ["git", "-C", str(raiz), "ls-files", "--others", "--exclude-standard",
             "--", "fila/eventos"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return sorted(linha.strip() for linha in proc.stdout.splitlines() if linha.strip())


AVISO_DE_SOMBRA = (
    "   (SOMBRA: esta regra AVISA e não reprova — regra nova nasce em sombra,\n"
    "    autoridade proporcional à certeza. O dia em que ela passar a reprovar\n"
    "    entra por PR, com teste-guarda.)"
)


def dizer_os_comprovantes_soltos(raiz: Path) -> None:
    """A peça em SOMBRA: fala alto sobre comprovante fora do Git, e não muda
    veredito nenhum. Chamada por `validar` — o gesto que a muralha do CI roda
    e o que um robô roda antes de pedir pouso."""
    achados = comprovantes_que_o_git_nao_conhece(raiz)
    if achados is None:
        print()
        print("⚠️  NÃO CONSEGUI CONFERIR se algum comprovante de fila/eventos/ ficou")
        print("   fora do Git (o git não respondeu). Não medi — e isso se diz, não")
        print("   se esconde (armadilhas/192).")
        print(AVISO_DE_SOMBRA)
        return
    if not achados:
        return
    try:
        encontrado = raiz_do_checkout(raiz)
    except Exception:  # pragma: no cover - defesa do aviso, que nunca trava
        encontrado = None
    no_espelho = bool(encontrado and encontrado[1])
    print()
    if no_espelho:
        print(f"🧱 COMPROVANTE ÓRFÃO — {len(achados)} arquivo(s) de fila/eventos/ que o Git")
        print("   não conhece, e esta pasta é o CLONE PRINCIPAL: aqui não se commita")
        print("   nada (RITOS.md §1). Eles não vão viajar em PR nenhum, e o histórico")
        print("   de quem pegou o trabalho some (armadilhas/192).")
    else:
        print(f"⚠️  {len(achados)} comprovante(s) de fila/eventos/ ainda fora do Git — o")
        print("   evento viaja no PR do trabalho (RITOS.md §5). Commite antes de pedir")
        print("   pouso, senão o PR vai sem ele (armadilhas/192).")
    for arquivo in achados:
        print(f"     - {arquivo}")
    if no_espelho:
        print("   Conserto: mova cada um para a sua bancada e commite lá —")
        print("     mv <arquivo> ../wt-<area>-<tarefa>/fila/eventos/")
    else:
        print("   Conserto: git add fila/eventos && git commit")
    print("   Confira sempre com: git diff --name-only origin/main...HEAD")
    print(AVISO_DE_SOMBRA)


def tarefas_citadas(texto: str) -> list[str]:
    """Os ids de tarefa citados num texto livre (título de PR, nome de ramo)."""
    return RE_CITACAO.findall(texto or "")


def pasta_tarefas(raiz: Path) -> Path:
    return raiz / "fila" / "tarefas"


def pasta_eventos(raiz: Path) -> Path:
    return raiz / "fila" / "eventos"


def _ler_json(caminho: Path, erros: list[str]) -> dict | None:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        erros.append(f"{caminho.name}: não é JSON válido ({erro})")
        return None
    if not isinstance(dados, dict):
        erros.append(f"{caminho.name}: o conteúdo precisa ser um objeto JSON")
        return None
    return dados


def _conferir_campos(
    nome: str,
    dados: dict,
    obrigatorios: dict,
    opcionais: dict,
    erros: list[str],
) -> None:
    for campo, tipo in obrigatorios.items():
        if campo not in dados:
            erros.append(f"{nome}: falta o campo obrigatório '{campo}'")
        elif not isinstance(dados[campo], tipo):
            erros.append(f"{nome}: '{campo}' deveria ser {tipo.__name__}")
        elif tipo is str and not str(dados[campo]).strip():
            erros.append(f"{nome}: '{campo}' está vazio")
    conhecidos = set(obrigatorios) | set(opcionais)
    for campo in dados:
        if campo not in conhecidos:
            erros.append(
                f"{nome}: campo desconhecido '{campo}' — vocabulário novo entra "
                "por PR neste arquivo, não por invenção num JSON"
            )
    for campo, tipo in opcionais.items():
        if campo in dados and dados[campo] is not None and not isinstance(dados[campo], tipo):
            erros.append(f"{nome}: '{campo}' deveria ser {tipo.__name__} ou null")


def problemas_da_explicacao(
    o_que_e: str, o_que_muda: str, exemplo: str, importancia
) -> list[str]:
    """O que impede esta explicação de existir, uma frase por problema.

    UMA definição só, de propósito: o balcão a chama em `explicar` e em `criar`
    (antes de gastar número do almoxarife), e `carregar_eventos` cobra o mesmo
    contrato no arquivo já gravado. Duas réguas para o mesmo campo divergiriam
    no primeiro dia em que alguém mexesse numa só.
    """
    problemas: list[str] = []
    for campo, texto in zip(TEXTOS_DA_EXPLICACAO, (o_que_e, o_que_muda, exemplo)):
        if not str(texto or "").strip():
            problemas.append(
                f"'{campo}' está vazio — os três textos são o que ele vai LER na "
                "tela, e explicação pela metade não explica nada"
            )
    if isinstance(importancia, bool) or not isinstance(importancia, int):
        problemas.append(
            f"'importancia' precisa ser um número inteiro de {IMPORTANCIA_MINIMA} a "
            f"{IMPORTANCIA_MAXIMA} (veio {importancia!r})"
        )
    elif not IMPORTANCIA_MINIMA <= importancia <= IMPORTANCIA_MAXIMA:
        problemas.append(
            f"'importancia' é {importancia}, e a faixa é de {IMPORTANCIA_MINIMA} a "
            f"{IMPORTANCIA_MAXIMA} — fora dela a ordem da tela deixa de ser comparável"
        )
    return problemas


def cartoes_do_placar(raiz: Path) -> set[str] | None:
    """Os nomes de `painel/cartoes/`. `None` quando a pasta não existe."""
    pasta = raiz / "painel" / "cartoes"
    if not pasta.is_dir():
        return None
    return {c.stem for c in pasta.glob("*.json")}


def _conferir_move(nome: str, move: list, raiz: Path, erros: list[str]) -> None:
    """O elo com o placar, fail-closed: nome de cartão que não existe reprova."""
    if not move:
        erros.append(
            f"{nome}: 'move' vazio não diz nada — para dizer que a tarefa mantém "
            f"a fábrica de pé, escreva [\"{MANUTENCAO}\"]; para não declarar nada, "
            "tire o campo (ausência e manutenção são coisas diferentes)"
        )
        return
    if not all(isinstance(m, str) and m.strip() for m in move):
        erros.append(f"{nome}: 'move' precisa ser lista de textos não vazios")
        return
    if MANUTENCAO in move and len(move) > 1:
        erros.append(
            f"{nome}: '{MANUTENCAO}' não se mistura com número do placar — ou a "
            "tarefa move algum número, ou ela mantém a fábrica de pé"
        )
        return
    if move == [MANUTENCAO]:
        return
    cartoes = cartoes_do_placar(raiz)
    if cartoes is None:
        erros.append(
            f"{nome}: 'move' cita cartão do placar, mas 'painel/cartoes/' não "
            "existe neste checkout — sem a lista, o nome não pode ser conferido, "
            "e nome não conferido é erro de digitação esperando para acontecer"
        )
        return
    for alvo in move:
        if alvo not in cartoes:
            erros.append(
                f"{nome}: 'move' cita {alvo!r}, que não é cartão de "
                f"'painel/cartoes/' — o número precisa existir antes de uma "
                "tarefa dizer que o move"
            )


def _conferir_medicao_fase4(nome: str, medicao: object, erros: list[str]) -> None:
    if medicao is None:
        return
    if not isinstance(medicao, dict):
        erros.append(f"{nome}: 'medicao_fase4' deveria ser objeto")
        return
    ausentes = sorted(CAMPOS_DA_MEDICAO_FASE4 - set(medicao))
    extras = sorted(set(medicao) - CAMPOS_DA_MEDICAO_FASE4 - {"par_id"})
    if ausentes:
        erros.append(f"{nome}: 'medicao_fase4' sem campos: {', '.join(ausentes)}")
    if extras:
        erros.append(f"{nome}: 'medicao_fase4' com campos desconhecidos: {', '.join(extras)}")
    for campo in CAMPOS_DA_MEDICAO_FASE4:
        if campo in medicao and (not isinstance(medicao[campo], str) or not medicao[campo].strip()):
            erros.append(f"{nome}: 'medicao_fase4.{campo}' precisa ser texto não vazio")
    if medicao.get("piloto") not in ("fase1", "fase2", "fase3"):
        erros.append(f"{nome}: 'medicao_fase4.piloto' precisa ser fase1, fase2 ou fase3")
    if medicao.get("condicao") not in ("antes", "depois"):
        erros.append(f"{nome}: 'medicao_fase4.condicao' precisa ser antes ou depois")
    revisao = medicao.get("revisao_instrumento")
    if not isinstance(revisao, str) or not re.fullmatch(r"[a-f0-9]{40}", revisao):
        erros.append(f"{nome}: 'medicao_fase4.revisao_instrumento' precisa ser SHA-1 hexadecimal")
    if "par_id" in medicao and medicao["par_id"] is not None and not isinstance(medicao["par_id"], str):
        erros.append(f"{nome}: 'medicao_fase4.par_id' precisa ser texto ou null")


def carregar_tarefas(raiz: Path, erros: list[str]) -> dict[str, dict]:
    """Todas as tarefas, validadas uma a uma. Erro entra em `erros`, não explode."""
    pasta = pasta_tarefas(raiz)
    tarefas: dict[str, dict] = {}
    numeros: dict[str, str] = {}
    if not pasta.is_dir():
        return tarefas
    for caminho in sorted(pasta.glob("*.json")):
        dados = _ler_json(caminho, erros)
        if dados is None:
            continue
        nome = caminho.name
        _conferir_campos(nome, dados, CAMPOS_DA_TAREFA, CAMPOS_OPCIONAIS_DA_TAREFA, erros)
        stem = caminho.stem
        if dados.get("arquivo") != stem:
            erros.append(f"{nome}: campo 'arquivo' ({dados.get('arquivo')!r}) ≠ nome do arquivo")
        numero = stem.split("-", 1)[0]
        if not numero.isdigit():
            erros.append(f"{nome}: o nome precisa começar com o número (NNN-slug.json)")
            continue
        esperado = f"TAR-{numero}"
        if dados.get("id") != esperado:
            erros.append(f"{nome}: 'id' ({dados.get('id')!r}) ≠ {esperado} (o número vem do nome)")
        if numero in numeros:
            erros.append(
                f"{nome}: número {numero} repetido (já usado por {numeros[numero]}) — "
                "o número vem do almoxarife, nunca de palpite"
            )
            continue
        numeros[numero] = nome
        toca = dados.get("toca")
        if isinstance(toca, list) and (not toca or not all(isinstance(t, str) and t.strip() for t in toca)):
            erros.append(f"{nome}: 'toca' precisa ser lista não vazia de textos")
        cria = dados.get("cria")
        if isinstance(cria, list) and not all(isinstance(c, str) and c.strip() for c in cria):
            erros.append(f"{nome}: 'cria' precisa ser lista de caminhos não vazios")
        move = dados.get("move")
        if isinstance(move, list):
            _conferir_move(nome, move, raiz, erros)
        _conferir_medicao_fase4(nome, dados.get("medicao_fase4"), erros)
        criada = dados.get("criada_em")
        if isinstance(criada, str) and not RE_DATA.match(criada):
            erros.append(f"{nome}: 'criada_em' precisa ser AAAA-MM-DD")
        tarefas[esperado] = dados
    # Dependências só se conferem com o mapa completo em mãos.
    for tid, dados in tarefas.items():
        for dep in dados.get("depende_de") or []:
            if dep == tid:
                erros.append(f"{tid}: depende de si mesma")
            elif dep not in tarefas:
                erros.append(f"{tid}: depende de {dep!r}, que não existe na fila")
    _conferir_ciclos(tarefas, erros)
    return tarefas


def _conferir_ciclos(tarefas: dict[str, dict], erros: list[str]) -> None:
    VISITANDO, PRONTO = 1, 2
    marca: dict[str, int] = {}

    def visitar(tid: str, trilha: list[str]) -> None:
        marca[tid] = VISITANDO
        for dep in tarefas.get(tid, {}).get("depende_de") or []:
            if dep not in tarefas:
                continue
            if marca.get(dep) == VISITANDO:
                ciclo = " → ".join(trilha + [tid, dep])
                erros.append(f"ciclo de dependências: {ciclo} — ninguém sairia da fila")
            elif dep not in marca:
                visitar(dep, trilha + [tid])
        marca[tid] = PRONTO

    for tid in tarefas:
        if tid not in marca:
            visitar(tid, [])


def carregar_eventos(raiz: Path, tarefas: dict[str, dict], erros: list[str]) -> list[dict]:
    """Todos os eventos, validados e em ordem cronológica (quando, arquivo)."""
    pasta = pasta_eventos(raiz)
    eventos: list[dict] = []
    if not pasta.is_dir():
        return eventos
    for caminho in sorted(pasta.glob("*.json")):
        dados = _ler_json(caminho, erros)
        if dados is None:
            continue
        nome = caminho.name
        _conferir_campos(nome, dados, CAMPOS_DO_EVENTO, CAMPOS_OPCIONAIS_DO_EVENTO, erros)
        if dados.get("arquivo") != caminho.stem:
            erros.append(f"{nome}: campo 'arquivo' ≠ nome do arquivo")
        tipo = dados.get("evento")
        if tipo not in EVENTOS_VALIDOS:
            erros.append(f"{nome}: evento {tipo!r} não existe (válidos: {', '.join(EVENTOS_VALIDOS)})")
            continue
        if tarefas and dados.get("tarefa") not in tarefas:
            erros.append(f"{nome}: fala da tarefa {dados.get('tarefa')!r}, que não existe")
        quando = dados.get("quando")
        try:
            dados["_quando"] = datetime.fromisoformat(str(quando))
        except (TypeError, ValueError):
            erros.append(f"{nome}: 'quando' precisa ser data-hora ISO (veio {quando!r})")
            continue
        if tipo == "submetida":
            erros.extend(f"{nome}: {erro}" for erro in problemas_da_submissao(dados))
        elif any(campo in dados for campo in ("pr", "revisao", "arvore")):
            erros.append(f"{nome}: pr, revisao e arvore pertencem ao evento submetida")
        if tipo == "concluida":
            if not str(dados.get("evidencia") or "").strip():
                erros.append(
                    f"{nome}: concluída SEM evidência não existe — a mesma lei do "
                    "verde do livro. Registre o que provou, ou não conclua."
                )
            if not RE_DATA.match(str(dados.get("verificado_em") or "")):
                erros.append(f"{nome}: concluída exige 'verificado_em' (AAAA-MM-DD)")
        if tipo in ("bloqueada", "cancelada", "reivindicacao_expirada") and not str(dados.get("detalhe") or "").strip():
            erros.append(f"{nome}: '{tipo}' sem 'detalhe' não conta a história — diga o motivo")
        espera = dados.get("espera")
        if espera is not None:
            if tipo != "bloqueada":
                erros.append(
                    f"{nome}: 'espera' só existe em evento 'bloqueada' — "
                    f"quem destrava só faz sentido para quem está travado (veio em '{tipo}')"
                )
            elif espera not in QUEM_DESTRAVA:
                erros.append(
                    f"{nome}: 'espera' é {espera!r}, e só existe "
                    f"{' ou '.join(repr(v) for v in QUEM_DESTRAVA)}"
                )
        if tipo == EXPLICADA:
            faltando = [c for c in CAMPOS_DA_EXPLICACAO if c not in dados]
            if faltando:
                erros.append(
                    f"{nome}: 'explicada' sem {', '.join(repr(c) for c in faltando)} "
                    "não explica nada — os quatro campos são o contrato"
                )
            else:
                for problema in problemas_da_explicacao(
                    dados["o_que_e"],
                    dados["o_que_muda"],
                    dados["exemplo"],
                    dados["importancia"],
                ):
                    erros.append(f"{nome}: {problema}")
        else:
            for campo in CAMPOS_DA_EXPLICACAO:
                if campo in dados:
                    erros.append(
                        f"{nome}: {campo!r} só existe em evento 'explicada' — a "
                        f"explicação diz o que a tarefa É, e veio em '{tipo}'"
                    )
        eventos.append(dados)
    eventos.sort(key=lambda e: (e["_quando"].isoformat(), e["arquivo"]))
    # Depois do fim, silêncio: evento após concluída/cancelada é história dupla.
    # A ÚNICA exceção é `explicada`, e ela é deliberada: a regra existe para que
    # ninguém reescreva o que ACONTECEU com a tarefa, e a explicação não conta
    # isso — ela diz o que a tarefa É. Tarefa concluída que ninguém entende
    # continua ilegível no histórico, e é justamente ali que o mantenedor procura
    # o que já foi feito.
    fim: dict[str, str] = {}
    for ev in eventos:
        tid = ev.get("tarefa")
        if ev["evento"] == EXPLICADA:
            continue
        if tid in fim:
            erros.append(
                f"{ev['arquivo']}: a tarefa {tid} já terminou ({fim[tid]}) — "
                "evento depois do fim reescreveria a história"
            )
        elif ev["evento"] in EVENTOS_TERMINAIS:
            fim[tid] = ev["evento"]
    return eventos


def problemas_da_submissao(dados: dict) -> list[str]:
    erros = []
    if not re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+/pull/[1-9]\d*", str(dados.get("pr") or "")):
        erros.append("pr exige a URL completa do pull request no GitHub")
    for campo in ("revisao", "arvore"):
        if not re.fullmatch(r"[0-9a-f]{40}", str(dados.get(campo) or "")):
            erros.append(f"{campo} exige o SHA completo do código validado")
    return erros


def ultima_submissao(eventos: list[dict], tid: str) -> dict | None:
    return next((e for e in reversed(_em_ordem(eventos))
                 if e.get("tarefa") == tid and e.get("evento") == "submetida"), None)


def calcular_estados(
    tarefas: dict[str, dict],
    eventos: list[dict],
    reservas_ativas: set[str] | None = None,
    prs_abertos: dict[str, str] | None = None,
) -> dict[str, dict]:
    """O quadro inteiro, calculado. Função pura: quem quiser outra vista, chama.

    `reservas_ativas` = ids com referência viva no almoxarife (só ao vivo);
    `prs_abertos` = id → "PR #N" para tarefas citadas em PR aberto (só ao vivo).
    """
    reservas_ativas = reservas_ativas or set()
    prs_abertos = prs_abertos or {}
    por_tarefa: dict[str, list[dict]] = {tid: [] for tid in tarefas}
    for ev in eventos:
        if ev.get("tarefa") in por_tarefa:
            por_tarefa[ev["tarefa"]].append(ev)

    estados: dict[str, dict] = {}

    def estado_de(tid: str) -> dict:
        if tid in estados:
            return estados[tid]
        cadeia = por_tarefa[tid]
        resultado = {"estado": NA_FILA, "motivo": "ninguém pegou ainda", "quem": None}
        terminal = next((e for e in cadeia if e["evento"] in EVENTOS_TERMINAIS), None)
        if terminal is not None:
            resultado = {
                "estado": CONCLUIDA if terminal["evento"] == "concluida" else CANCELADA,
                "motivo": terminal.get("evidencia") or terminal.get("detalhe") or "",
                "quem": terminal.get("quem"),
            }
            estados[tid] = resultado
            return resultado
        ultimo_ciclo = next(
            (e for e in reversed(cadeia) if e["evento"] in EVENTOS_DE_CICLO), None
        )
        submetida = ultima_submissao(cadeia, tid)
        if (ultimo_ciclo is not None and ultimo_ciclo["evento"] == "bloqueada"
                and (submetida is None or cadeia.index(ultimo_ciclo) > cadeia.index(submetida))):
            resultado = {
                "estado": BLOQUEADA,
                "motivo": ultimo_ciclo.get("detalhe") or "",
                "quem": ultimo_ciclo.get("quem"),
                # Quem bloqueou declarou quem destrava. Ausente só nos eventos
                # anteriores a 06/09/2026, e ausente NÃO vira `fila` por
                # conveniência: "ninguém declarou" e "a fila resolve" são
                # respostas diferentes, e fundi-las esconderia do dono uma
                # tarefa que talvez fosse dele. `cmd_validar` cobra o campo em
                # todo bloqueio vivo, então este `None` não sobrevive a um PR.
                "espera": ultimo_ciclo.get("espera"),
            }
            estados[tid] = resultado
            return resultado
        if submetida:
            resultado = {
                "estado": EM_EXECUCAO,
                "motivo": "Entrega submetida; falta comprovar o aceite da tarefa.",
                "quem": submetida["quem"],
                **{campo: submetida[campo] for campo in ("pr", "revisao", "arvore")},
            }
            estados[tid] = resultado
            return resultado
        if ultimo_ciclo is not None and ultimo_ciclo["evento"] == "reivindicacao_expirada":
            resultado = {
                "estado": NA_FILA,
                "motivo": ultimo_ciclo.get("detalhe") or "reivindicação expirada",
                "quem": ultimo_ciclo.get("quem"),
            }
            estados[tid] = resultado
            return resultado
        reivindicada = (
            ultimo_ciclo is not None and ultimo_ciclo["evento"] == "reivindicada"
        ) or tid in reservas_ativas
        # Dependência aberta bloqueia por conta, sem ninguém escrever nada.
        estados[tid] = resultado  # quebra ciclos que a validação deixou passar
        deps_abertas = [
            dep
            for dep in tarefas[tid].get("depende_de") or []
            if dep in tarefas and estado_de(dep)["estado"] != CONCLUIDA
        ]
        if deps_abertas and not reivindicada:
            resultado = {
                "estado": BLOQUEADA,
                "motivo": "esperando " + ", ".join(deps_abertas),
                "quem": None,
                # Ninguém escreveu, e ninguém precisa: esta trava se desfaz
                # sozinha quando a tarefa de cima terminar. É a própria fila
                # andando, e por isso nunca é assunto do mantenedor.
                "espera": ESPERA_A_FILA,
            }
        elif tid in prs_abertos:
            resultado = {
                "estado": EM_EXECUCAO,
                "motivo": prs_abertos[tid],
                "quem": (ultimo_ciclo or {}).get("quem"),
            }
        elif reivindicada:
            quem = (ultimo_ciclo or {}).get("quem") or "reserva ativa no almoxarife"
            resultado = {"estado": REIVINDICADA, "motivo": "", "quem": quem}
        estados[tid] = resultado
        return resultado

    for tid in tarefas:
        estado_de(tid)

    # A explicação para gente, do ÚLTIMO evento `explicada` — a última vence, e
    # é assim que se corrige um texto ruim sem editar arquivo nenhum. Sai daqui
    # e de nenhum outro lugar: `listar --json` só repassa, e é esse JSON que vira
    # o `estados.json` que a célula `admin` lê no build. Tarefa sem explicação
    # sai SEM os campos, nunca com texto de desculpa: quem apresenta decide o
    # que dizer no lugar, e um "sem descrição" escrito aqui seria uma segunda
    # definição de tela morando no cálculo.
    for tid, resultado in estados.items():
        ultima = next(
            (e for e in reversed(por_tarefa[tid]) if e["evento"] == EXPLICADA), None
        )
        if ultima is not None:
            resultado.update(
                {c: ultima[c] for c in CAMPOS_DA_EXPLICACAO if c in ultima}
            )
    return estados


# ---------------------------------------------------------------------------
# As leituras ao vivo — servidor e PRs. Só `listar --ao-vivo` e `pegar` usam.
# ---------------------------------------------------------------------------


def reservas_no_servidor(raiz: Path) -> set[str]:
    """Ids de tarefa com referência NÃO vencida em refs/reservas/tarefa-*."""
    ativos: set[str] = set()
    for ref in reservar.refs_existentes(raiz, reservar.NS_RESERVA):
        cauda = ref.rsplit("/", 1)[-1]
        if not cauda.startswith(PREFIXO_DA_RESERVA):
            continue
        leitura = reservar.executar(
            ["git", "ls-remote", "origin", ref],
            cwd=raiz,
            descricao="ler a validade da reserva da tarefa",
        ).stdout.strip()
        partes = leitura.split()
        if len(partes) != 2 or partes[1] != ref or not re.fullmatch(r"[0-9a-f]{40}", partes[0]):
            raise ErroDeInstrumentacao(
                "resposta da reserva inválida",
                f"Não consegui conferir {ref}. Sem saber se a reserva está viva, não libero a tarefa.",
            )
        sha = partes[0]
        reservar.executar(
            ["git", "fetch", "--no-tags", "origin", sha],
            cwd=raiz,
            descricao="ler o comprovante da reserva da tarefa",
        )
        corpo = reservar.executar(
            ["git", "show", "-s", "--format=%B", sha],
            cwd=raiz,
            descricao="conferir a validade da reserva da tarefa",
        ).stdout
        try:
            dados = json.loads(corpo)
            expira = datetime.fromisoformat(str(dados["expira_em"]))
            if dados.get("tipo") != "intencao" or dados.get("chave") != cauda:
                raise ValueError("identidade incompatível")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as erro:
            raise ErroDeInstrumentacao(
                "reserva de tarefa incompatível",
                f"O comprovante remoto {ref} não tem formato confiável. Não libero a tarefa.",
            ) from erro
        if expira.tzinfo is None:
            raise ErroDeInstrumentacao(
                "reserva de tarefa incompatível",
                f"O comprovante remoto {ref} não informa fuso horário na expiração.",
            )
        if expira > datetime.now(timezone.utc):
            ativos.add(cauda[len(PREFIXO_DA_RESERVA):])
    return ativos


def prs_citando_tarefas(raiz: Path) -> dict[str, str]:
    """id → 'PR #N' para todo PR ABERTO cujo título ou ramo cita TAR-NNN."""
    proc = subprocess.run(
        ["gh", "pr", "list", "--state", "open", "--json", "number,title,headRefName"],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        raise ErroDeInstrumentacao(
            "não consegui listar os PRs abertos",
            proc.stderr.strip()[:400] + "\nSem essa leitura, 'em execução' viraria chute.",
        )
    achados: dict[str, str] = {}
    for pr in json.loads(proc.stdout or "[]"):
        texto = f"{pr.get('title', '')} {pr.get('headRefName', '')}"
        for tid in tarefas_citadas(texto):
            achados.setdefault(tid, f"PR #{pr['number']}")
    return achados


def consultar_pr_submetido(raiz: Path, url: str) -> dict:
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", url, "--json", "url,state,headRefOid,mergeCommit"],
            cwd=str(raiz), capture_output=True, text=True, encoding="utf-8",
            timeout=120, stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0:
            raise ValueError("consulta recusada pelo GitHub")
        dados = json.loads(proc.stdout)
        if (not isinstance(dados, dict) or dados.get("url") != url
                or dados.get("state") not in ("OPEN", "MERGED", "CLOSED")):
            raise ValueError("identidade ou estado do PR incompatível")
        return dados
    except (OSError, subprocess.TimeoutExpired, ValueError) as erro:
        raise ErroDeInstrumentacao(
            "não consegui conferir o PR submetido",
            f"Confira gh pr view {url} e repita a operação. A tarefa não foi devolvida à fila.",
        ) from erro


def _git_predicado(raiz: Path, *argumentos: str, descricao: str) -> bool:
    try:
        proc = subprocess.run(
            ["git", *argumentos],
            cwd=str(raiz),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise ErroDeInstrumentacao(
            f"{descricao}: o git não respondeu",
            "A relação entre revisão, HEAD e integração não foi medida.",
        ) from erro
    if proc.returncode not in (0, 1):
        raise ErroDeInstrumentacao(
            f"{descricao}: resposta inválida do git",
            proc.stderr.strip() or "O git não explicou a falha.",
        )
    return proc.returncode == 0


def bancada_contem_main_publicada(raiz: Path) -> bool:
    _git_da_fila(
        raiz, "fetch", "origin", "main", para_que="atualizar a fila publicada"
    )
    return _git_predicado(
        raiz,
        "merge-base",
        "--is-ancestor",
        "origin/main",
        "HEAD",
        descricao="conferir se a bancada contém a fila publicada",
    )


def problemas_da_linhagem(
    submissao: dict,
    medicao: dict,
) -> list[str]:
    problemas = []
    if medicao.get("arvore_medida") != submissao.get("arvore"):
        problemas.append("a árvore da revisão difere da árvore submetida")
    if not medicao.get("revisao_ancestral"):
        problemas.append("a revisão submetida não é ancestral do HEAD final")
    if not medicao.get("head_ancestral"):
        problemas.append("o HEAD final não é ancestral do merge publicado")
    posteriores = medicao.get("caminhos_posteriores") or []
    codigo = [
        caminho
        for caminho in posteriores
        if not caminho.startswith(CAMINHOS_POSTERIORES_PERMITIDOS)
    ]
    if codigo:
        problemas.append("há código posterior à revisão: " + ", ".join(codigo))
    return problemas


def medir_linhagem(raiz: Path, submissao: dict, head: str, merge: str) -> None:
    profundidade = _git_da_fila(
        raiz,
        "rev-parse",
        "--is-shallow-repository",
        para_que="conferir a profundidade do histórico",
    ).strip()
    if profundidade != "false":
        raise ErroDeInstrumentacao(
            "histórico raso não prova a reconciliação",
            "Use um checkout com fetch-depth 0 e repita.",
        )
    revisao = submissao["revisao"]
    arvore_medida = _git_da_fila(
        raiz,
        "rev-parse",
        f"{revisao}^{{tree}}",
        para_que="medir a árvore da revisão submetida",
    ).strip()
    if not arvore_medida:
        raise ErroDeInstrumentacao("o git não devolveu a árvore da revisão")
    caminhos = _git_da_fila(
        raiz,
        "log",
        "--diff-merges=first-parent",
        "--format=",
        "--name-only",
        f"{revisao}..{head}",
        para_que="conferir mudanças posteriores à revisão",
    ).splitlines()
    caminhos = [caminho for caminho in caminhos if caminho]
    medicao = {
        "arvore_medida": arvore_medida,
        "revisao_ancestral": _git_predicado(
            raiz,
            "merge-base",
            "--is-ancestor",
            revisao,
            head,
            descricao="conferir revisão ancestral do HEAD",
        ),
        "head_ancestral": _git_predicado(
            raiz,
            "merge-base",
            "--is-ancestor",
            head,
            merge,
            descricao="conferir HEAD ancestral do merge",
        ),
        "caminhos_posteriores": caminhos,
    }
    problemas = problemas_da_linhagem(submissao, medicao)
    if problemas:
        raise RecusaDeReconciliacao("; ".join(problemas))


def provar_estado_terminal(estado: dict) -> None:
    if not isinstance(estado, dict) or not isinstance(estado.get("estado"), str):
        raise ErroDeInstrumentacao(
            "o leitor da entrega devolveu dados inválidos",
            "Não há estado confiável para reconciliar.",
        )
    if estado["estado"] == "ENCERRADO_SEM_INTEGRAR":
        raise RecusaDeReconciliacao("a entrega não foi integrada")
    if not estado.get("terminal") or estado["estado"] not in (
        "PUBLICADO",
        "SEM_PUBLICACAO",
    ):
        raise RecusaDeReconciliacao(
            f"a publicação ainda não terminou com sucesso ({estado['estado']})"
        )
    for campo in ("sha_atual", "sha_integrado"):
        if not re.fullmatch(r"[0-9a-f]{40}", str(estado.get(campo) or "")):
            raise ErroDeInstrumentacao(
                f"{campo} ausente no estado da entrega",
                "O GitHub não devolveu a identidade completa do código.",
            )


def provar_atestado(resultado) -> None:
    if not isinstance(resultado, revisor_de_pouso.Resultado):
        raise ErroDeInstrumentacao(
            "o revisor devolveu um resultado inválido",
            "A avaliação independente não pôde ser interpretada.",
        )
    if resultado.estado is not Estado.PASS:
        raise RecusaDeReconciliacao(
            "o atestado independente do HEAD final não foi aprovado: "
            + resultado.resumo
        )


def provar_conteudo_do_aceite(registro: dict, provas_da_publicacao: list[str]) -> None:
    if registro.get("gravidade") != "verde":
        raise RecusaDeReconciliacao("o registro de aceite não tem veredito verde")
    if registro.get("precisa_do_dono") is not False:
        raise RecusaDeReconciliacao("o registro ainda declara uma pendência do dono")
    verificado_em = str(registro.get("verificado_em") or "")
    try:
        if not RE_DATA.fullmatch(verificado_em):
            raise ValueError
        datetime.strptime(verificado_em, "%Y-%m-%d")
    except ValueError:
        raise RecusaDeReconciliacao(
            "o registro de aceite não informa quando foi verificado"
        )
    evidencia = str(registro.get("evidencia") or "")
    citadas = set()
    for texto in RE_URL.findall(evidencia):
        texto = texto.rstrip(".,;:)")
        try:
            urlsplit(texto)
        except ValueError:
            continue
        citadas.add(texto)
    if not provas_da_publicacao or not citadas.intersection(provas_da_publicacao):
        raise RecusaDeReconciliacao(
            "o registro de aceite não cita a prova da publicação correspondente"
        )


def urls_da_publicacao_comprovada(estado: dict, pr: str) -> list[str]:
    if estado["estado"] == "SEM_PUBLICACAO":
        return [pr]
    fonte = estado.get("publicacoes")
    if fonte is None:
        fonte = estado.get("runs", [])
    return sorted(
        {
            str(item["url"])
            for item in fonte
            if isinstance(item, dict) and item.get("url")
        }
    )


def _ler_registro(raiz: Path, caminho: str) -> dict:
    script = (
        "const fs=require('fs'),vm=require('vm');"
        "const s={window:{}};"
        "vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),s,{timeout:1000});"
        "const r=s.window.REGISTROS||[];"
        "if(r.length!==1)process.exit(3);"
        "process.stdout.write(JSON.stringify(r[0]));"
    )
    saida = executar(
        ["node", "-e", script, str(raiz / caminho)],
        cwd=raiz,
        descricao="ler o aceite na fonte oficial do livro",
        exigir_stdout=True,
    ).stdout
    try:
        registro = json.loads(saida)
    except (TypeError, json.JSONDecodeError) as erro:
        raise ErroDeInstrumentacao(
            "o registro de aceite não pôde ser lido",
            "O livro não devolveu um objeto JSON confiável.",
        ) from erro
    if not isinstance(registro, dict):
        raise ErroDeInstrumentacao("o registro de aceite não é um objeto")
    return registro


def carregar_aceite(
    raiz: Path,
    caminho: str,
    merge: str,
    provas_da_publicacao: list[str],
) -> dict:
    caminho = caminho.replace("\\", "/")
    if not RE_REGISTRO_DE_ACEITE.fullmatch(caminho):
        raise RecusaDeReconciliacao(
            "--aceite-registro exige painel/registros/AAAAMMDD-NNN-slug.js"
        )
    rastreado = _git_da_fila(
        raiz,
        "ls-tree",
        "-r",
        "--name-only",
        "origin/main",
        "--",
        caminho,
        para_que="localizar o aceite na linha publicada",
    ).splitlines()
    if rastreado != [caminho]:
        raise RecusaDeReconciliacao("o registro de aceite não existe em origin/main")
    if not _git_predicado(
        raiz,
        "diff",
        "--quiet",
        "origin/main",
        "--",
        caminho,
        descricao="comparar o aceite local com origin/main",
    ):
        raise RecusaDeReconciliacao(
            "o registro de aceite local difere da fonte já integrada em origin/main"
        )
    introducao = _git_da_fila(
        raiz,
        "log",
        "-1",
        "--diff-filter=A",
        "--format=%H",
        "origin/main",
        "--",
        caminho,
        para_que="localizar quando o aceite entrou no livro",
    ).strip()
    if not introducao:
        raise RecusaDeReconciliacao("não foi possível localizar a introdução do aceite")
    if introducao == merge or not _git_predicado(
        raiz,
        "merge-base",
        "--is-ancestor",
        merge,
        introducao,
        descricao="conferir aceite posterior à integração",
    ):
        raise RecusaDeReconciliacao(
            "o registro de aceite não foi introduzido após o merge"
        )
    registro = _ler_registro(raiz, caminho)
    if registro.get("arquivo") != Path(caminho).stem:
        raise RecusaDeReconciliacao(
            "a identidade interna do registro de aceite diverge do arquivo"
        )
    provar_conteudo_do_aceite(registro, provas_da_publicacao)
    return registro


def provar_reconciliacao(
    raiz: Path,
    submissao: dict,
    aceite_registro: str,
) -> tuple[str, str]:
    numero = int(submissao["pr"].rsplit("/", 1)[1])
    pr = estado_da_entrega.ler_pr(raiz, numero)
    if pr.get("url") != submissao["pr"]:
        raise RecusaDeReconciliacao(
            "a URL submetida não identifica o PR deste repositório"
        )
    estado = estado_da_entrega.consultar_entrega(raiz, numero)
    provar_estado_terminal(estado)
    head = estado["sha_atual"]
    merge = estado["sha_integrado"]
    if (
        pr.get("headRefOid") != head
        or (pr.get("mergeCommit") or {}).get("oid") != merge
    ):
        raise ErroDeInstrumentacao(
            "as duas leituras do PR discordam",
            "HEAD ou merge mudou durante a reconciliação. Repita a medição.",
        )
    medir_linhagem(raiz, submissao, head, merge)

    comentarios = estado_da_entrega._api(  # uma leitura GitHub, sem segundo protocolo
        raiz, f"issues/{numero}/comments", paginas=True
    )
    atestado = revisor_de_pouso.avaliar_atestado(
        head,
        comentarios,
        correcoes=estado_da_entrega.correcoes_declaradas(pr),
    )
    provar_atestado(atestado)

    provas = urls_da_publicacao_comprovada(estado, submissao["pr"])
    registro = carregar_aceite(raiz, aceite_registro, merge, provas)
    publicacao = ",".join(provas)
    evidencia = (
        f"entrega={submissao['pr']}; revisao={submissao['revisao']}; "
        f"arvore={submissao['arvore']}; head={head}; merge={merge}; "
        f"estado={estado['estado']}; publicacao={publicacao}; "
        f"atestado={atestado.resumo}; aceite={aceite_registro.replace('\\', '/')}"
    )
    return evidencia, registro["verificado_em"]


def _ultimos_ciclos(eventos: list[dict]) -> dict[str, dict]:
    ultimos: dict[str, dict] = {}
    for evento in _em_ordem(eventos):
        if evento.get("evento") in EVENTOS_DE_CICLO:
            ultimos[evento["tarefa"]] = evento
    return ultimos


def rotular_orfaos(
    raiz: Path,
    tarefas: dict[str, dict],
    eventos: list[dict],
    reservas: set[str],
    prs: dict[str, str],
    quem: str,
) -> list[Path]:
    """Registra reivindicações sem reserva viva nem PR aberto, sem apagar nada."""
    ultimos = _ultimos_ciclos(eventos)
    terminais = {
        evento["tarefa"]
        for evento in _em_ordem(eventos)
        if evento.get("evento") in EVENTOS_TERMINAIS
    }
    escritos: list[Path] = []
    for tid in sorted(tarefas):
        if tid in terminais:
            continue
        submetida = ultima_submissao(eventos, tid)
        if submetida:
            consultar_pr_submetido(raiz, submetida["pr"])
            continue
        ultimo = ultimos.get(tid)
        if not ultimo or ultimo["evento"] != "reivindicada":
            continue
        if tid in reservas or tid in prs:
            continue
        escritos.append(
            _escrever_evento(
                raiz,
                tid,
                "reivindicacao_expirada",
                quem,
                detalhe=(
                    "reivindicação órfã: a reserva venceu e não há PR aberto. "
                    "A tarefa voltou à fila; nenhum ramo ou PR foi apagado."
                ),
            )
        )
    return escritos


# ---------------------------------------------------------------------------
# Os gestos
# ---------------------------------------------------------------------------


def _slug(texto: str) -> str:
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    plano = re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-")
    return plano[:60] or "tarefa"


def _escrever_json(caminho: Path, dados: dict) -> None:
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def montar_evento(
    tid: str,
    evento: str,
    quem: str,
    detalhe: str | None = None,
    evidencia: str | None = None,
    verificado_em: str | None = None,
    espera: str | None = None,
    explicacao: dict | None = None,
    agora: datetime | None = None,
) -> dict:
    """O conteúdo de um evento, sem tocar no disco.

    Separado de `_escrever_evento` de propósito: a porta do pouso precisa
    MOSTRAR o evento que gravaria sem gravá-lo (a sombra, mais abaixo), e duas
    receitas para o mesmo arquivo divergiriam no primeiro dia em que alguém
    mexesse numa só.
    """
    agora = agora or datetime.now(timezone.utc)
    stem = f"{agora.strftime('%Y%m%d-%H%M%S')}-{tid}-{evento}"
    dados: dict = {
        "arquivo": stem,
        "tarefa": tid,
        "evento": evento,
        "quando": agora.isoformat(timespec="seconds"),
        "quem": quem,
    }
    if detalhe:
        dados["detalhe"] = detalhe
    if evidencia:
        dados["evidencia"] = evidencia
    if verificado_em:
        dados["verificado_em"] = verificado_em
    if espera:
        dados["espera"] = espera
    if explicacao:
        dados.update({c: explicacao[c] for c in CAMPOS_DA_EXPLICACAO})
    return dados


def _escrever_evento(
    raiz: Path,
    tid: str,
    evento: str,
    quem: str,
    detalhe: str | None = None,
    evidencia: str | None = None,
    verificado_em: str | None = None,
    espera: str | None = None,
    explicacao: dict | None = None,
    agora: datetime | None = None,
) -> Path:
    dados = montar_evento(
        tid, evento, quem, detalhe, evidencia, verificado_em, espera, explicacao, agora
    )
    pasta = pasta_eventos(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{dados['arquivo']}.json"
    _escrever_json(caminho, dados)
    return caminho


# ---------------------------------------------------------------------------
# O EVENTO "CONCLUÍDA" PELA PORTA DO POUSO — nasce EM SOMBRA (06/09/2026)
#
# O buraco é de DESENHO, e é o mesmo que `ci/divida_do_livro.py` descreve para
# o livro: o rito manda pedir pouso e ir embora, a pista mergeia depois, e não
# há mais ninguém ali para escrever o evento. Hoje quem escreve é o robô, à
# mão, antes de sair — e quando a sessão acaba antes do merge, o evento não
# nasce e a tarefa fica presa em "reivindicada" para sempre.
#
# Os seis campos do evento existem TODOS no instante do pouso: a tarefa (o PR
# a cita), quando (o merge), quem (a sessão que reivindicou, que a fila já
# sabe), evidência (a URL do PR e o commit de merge) e verificado_em. Nada
# aqui é adivinhação.
#
# POR QUE SOMBRA, e não gravar de uma vez: a lei do Sistema Imunológico manda
# regra nova nascer observando (`ci/muralha_das_armadilhas.py`, "A LEI DA
# AUTORIDADE PROPORCIONAL À CERTEZA"). Escrever no livro da fila é escrita
# permanente, e "corrigir é acrescentar": um evento errado gravado pela porta
# não tem desfazer, porque depois do terminal a fila não aceita mais nada. A
# sombra IMPRIME o que gravaria e mede, e a graduação vem depois.
#
# O QUE GRADUA (PR futuro, depois de uma semana de medição): que os disparos
# medidos mostrem "geraria" batendo com o que o robô escreveria à mão, sem um
# único caso de tarefa errada. Aí a porta passa a gravar o evento no RAMO e
# commitá-lo ANTES do merge — antes, e não depois, porque o evento precisa
# entrar na `main` pelo próprio PR, como o registro do livro faz desde
# 31/08/2026 (`armadilhas/248`).
# ---------------------------------------------------------------------------

SOMBRA_GERARIA = "geraria"
SOMBRA_JA_EXISTE = "ja_existe"
SOMBRA_SILENCIO = "silencio"

PASTA_DE_EVENTOS_NO_DIFF = "fila/eventos/"


def eventos_no_diff(remessas: list[dict]) -> list[dict]:
    """Os eventos da fila que viajam DENTRO de um PR, lidos do diff da API.

    `remessas` é o que `gh api .../pulls/N/files` devolve: uma lista de
    `{"filename": ..., "patch": ...}`. Vem de fora porque a pista nunca faz
    checkout do ramo do PR (`pouso.yml`): o evento que o robô escreveu à mão
    não está no disco de quem julga, só no diff. É o mesmo caminho que
    `ci/divida_do_livro.py` já usa para achar o registro embarcado.

    Só linhas ADICIONADAS contam, e só arquivo que se decodifica inteiro: um
    patch truncado ou um evento removido não vira fato.
    """
    achados: list[dict] = []
    for remessa in remessas or []:
        caminho = str(remessa.get("filename") or "").replace("\\", "/")
        if not (caminho.startswith(PASTA_DE_EVENTOS_NO_DIFF) and caminho.endswith(".json")):
            continue
        corpo = "\n".join(
            linha[1:]
            for linha in str(remessa.get("patch") or "").splitlines()
            if linha.startswith("+") and not linha.startswith("+++")
        )
        try:
            dados = json.loads(corpo)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(dados, dict) and dados.get("evento") in EVENTOS_VALIDOS:
            achados.append(dados)
    return achados


def _em_ordem(eventos: list[dict]) -> list[dict]:
    """Cronológica, como `carregar_eventos` entrega — `calcular_estados` conta
    com a ordem para saber qual foi o último gesto do ciclo."""

    def chave(ev: dict) -> tuple[str, str]:
        quando = ev.get("_quando")
        if quando is None:
            try:
                quando = datetime.fromisoformat(str(ev.get("quando")))
            except (TypeError, ValueError):
                return ("", str(ev.get("arquivo") or ""))
        return (quando.isoformat(), str(ev.get("arquivo") or ""))

    return sorted(eventos, key=chave)


def _silencio(tid: str, motivo: str) -> dict:
    return {"tarefa": tid, "desfecho": SOMBRA_SILENCIO, "motivo": motivo, "evento": None}


def evento_de_conclusao_em_sombra(
    raiz: Path,
    *,
    numero: int,
    titulo: str,
    corpo: str,
    ramo: str,
    url: str,
    sha_do_merge: str,
    arquivos_do_diff: list[dict],
    agora: datetime | None = None,
) -> list[dict]:
    """O que a porta do pouso GRAVARIA, sem gravar nada. Função pura de disco.

    Devolve uma decisão por tarefa citada no PR: `geraria` (com o evento
    pronto), `ja_existe` (o robô já escreveu o dele neste ramo) ou `silencio`
    (com o motivo, que é o que a telemetria mede). PR sem tarefa citada devolve
    lista vazia: silêncio total, sem nem medir.
    """
    ids: list[str] = []
    for tid in tarefas_citadas(f"{titulo}\n{corpo}\n{ramo}"):
        if tid not in ids:
            ids.append(tid)
    if not ids:
        return []

    erros: list[str] = []
    tarefas = carregar_tarefas(raiz, erros)
    eventos = carregar_eventos(raiz, tarefas, erros)
    if erros:
        # Não conseguir ler a fila nunca vira "então pode gravar" (INV-CI01).
        return [_silencio(tid, "a fila está inválida no disco de quem julga") for tid in ids]

    do_pr = eventos_no_diff(arquivos_do_diff)
    ja_a_bordo = {
        str(ev.get("tarefa")) for ev in do_pr if ev.get("evento") == "concluida"
    }
    estados = calcular_estados(tarefas, _em_ordem(eventos + do_pr))
    agora = agora or datetime.now(timezone.utc)

    saida: list[dict] = []
    for tid in ids:
        if tid not in tarefas:
            saida.append(_silencio(tid, f"{tid} é citada no PR mas não existe na fila"))
            continue
        if tid in ja_a_bordo:
            saida.append(
                {
                    "tarefa": tid,
                    "desfecho": SOMBRA_JA_EXISTE,
                    "motivo": "o evento de conclusão já viaja neste PR, escrito à mão",
                    "evento": None,
                }
            )
            continue
        estado = estados[tid]
        if estado["estado"] != REIVINDICADA:
            saida.append(
                _silencio(
                    tid,
                    f"{tid} está '{estado['estado']}', e só tarefa reivindicada "
                    "se conclui pela porta",
                )
            )
            continue
        quem = str(estado.get("quem") or "").strip()
        if not quem:
            saida.append(
                _silencio(tid, f"{tid} está reivindicada, mas a fila não sabe por quem")
            )
            continue
        saida.append(
            {
                "tarefa": tid,
                "desfecho": SOMBRA_GERARIA,
                "motivo": f"reivindicada por {quem}",
                "evento": montar_evento(
                    tid,
                    "concluida",
                    quem,
                    detalhe=f"PR #{numero}: {titulo} ({url})",
                    evidencia=f"{url} (merge {sha_do_merge[:12]})",
                    verificado_em=agora.strftime("%Y-%m-%d"),
                    agora=agora,
                ),
            }
        )
    return saida


def _carregar_ou_parar(raiz: Path) -> tuple[dict[str, dict], list[dict]]:
    erros: list[str] = []
    tarefas = carregar_tarefas(raiz, erros)
    eventos = carregar_eventos(raiz, tarefas, erros)
    if erros:
        raise ErroDeInstrumentacao(
            "a fila está inválida — conserte antes de mexer nela",
            "\n".join(f"  - {e}" for e in erros),
        )
    return tarefas, eventos


def normalizar_responsabilidade(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def cmd_criar(raiz: Path, args) -> int:
    recusa = _parar_se_for_o_espelho("criar", raiz)
    if recusa:
        print(recusa)
        return 1
    responsabilidade = normalizar_responsabilidade(getattr(args, "responsabilidade", ""))
    despacho = args.despacho
    if args.despacho_arquivo:
        despacho = Path(args.despacho_arquivo).read_text(encoding="utf-8").strip()
    if not (despacho or "").strip():
        print("RECUSADO: tarefa sem despacho pronto não entra na fila —")
        print("é o prompt de colar que os três consultores pediram. Use --despacho.")
        return 1
    tarefas, _ = _carregar_ou_parar(raiz)
    for dep in args.depende_de:
        if dep not in tarefas:
            print(f"RECUSADO: --depende-de {dep} não existe na fila.")
            return 1
    # Antes de gastar número do almoxarife: o elo com o placar tem de fechar.
    recusa_do_move: list[str] = []
    _conferir_move("--move", args.move, raiz, recusa_do_move)
    if recusa_do_move:
        for linha in recusa_do_move:
            print(f"RECUSADO: {linha.removeprefix('--move: ')}")
        cartoes = cartoes_do_placar(raiz)
        # A lista só ajuda quem errou um NOME; em erro de forma ela é ruído.
        if cartoes and any("não é cartão" in linha for linha in recusa_do_move):
            print(f"Cartões que existem: {', '.join(sorted(cartoes))}")
        return 1
    # E a explicação para gente, também ANTES do almoxarife: nasceu obrigatória
    # pela mesma lição que o `--move` e o `--espera` já deram nesta casa — campo
    # que nasce opcional no balcão nasce vazio, e ninguém volta para preencher.
    # Quem cria a tarefa é quem sabe, naquele instante, o que ela é.
    problemas = problemas_da_explicacao(
        args.o_que_e, args.o_que_muda, args.exemplo, args.importancia
    )
    if problemas:
        for problema in problemas:
            print(f"RECUSADO: {problema}")
        print()
        print("A tarefa vive no painel do dono, e ele é leigo em código: sem estes")
        print("quatro campos ela chega lá como um título que ninguém entende.")
        return 1
    if not responsabilidade:
        print("RECUSADO: toda tarefa nova precisa de --responsabilidade com uma unidade cadastrada.")
        return 1
    cadastro = raiz / "painel" / "responsabilidades.json"
    if not cadastro.exists():
        print("RECUSADO: painel/responsabilidades.json não existe; cadastre a unidade antes de criar a tarefa.")
        return 1
    try:
        problemas_da_responsabilidade = responsabilidades.validar_entrega(raiz, responsabilidade)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as erro:
        print(f"RECUSADO: não foi possível ler o cadastro de responsabilidades ({erro}). Corrija painel/responsabilidades.json e repita.")
        return 1
    if problemas_da_responsabilidade:
        print(f"RECUSADO: responsabilidade {responsabilidade} não é válida.")
        for problema in problemas_da_responsabilidade:
            print(f"- {problema}")
        return 1
    numero = reservar.alocar_numero(raiz, "tarefa")
    tid = f"TAR-{numero}"
    stem = f"{numero}-{_slug(args.titulo)}"
    pasta = pasta_tarefas(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    dados = {
        "arquivo": stem,
        "id": tid,
        "titulo": args.titulo,
        "toca": args.toca,
        "depende_de": args.depende_de,
        "cria": args.cria,
        "move": args.move,
        "evidencia_exigida": args.evidencia_exigida,
        "despacho": despacho,
        "origem": args.origem,
        "criada_em": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "responsabilidade_obrigatoria": True,
    }
    if responsabilidade:
        dados["responsabilidade"] = responsabilidade
    caminho = pasta / f"{stem}.json"
    _escrever_json(caminho, dados)
    # Dois arquivos, um gesto: a tarefa (para o robô) e a explicação dela (para
    # ele). Separados porque a tarefa é imutável e a explicação se corrige.
    do_evento = _escrever_evento(
        raiz,
        tid,
        EXPLICADA,
        args.origem,
        explicacao={
            "o_que_e": args.o_que_e,
            "o_que_muda": args.o_que_muda,
            "exemplo": args.exemplo,
            "importancia": args.importancia,
        },
    )
    print(f"{tid} criada: {caminho.relative_to(raiz)}")
    print(f"   explicação: {do_evento.relative_to(raiz)} (commite os DOIS no seu PR)")
    return 0


def cmd_explicar(raiz: Path, args) -> int:
    """Escreve o evento `explicada` — a tarefa dita em português, para ele.

    Medido em 06/09/2026: ele abriu `/admin/caixa/robos/`, viu 22 tarefas
    paradas e não entendeu nenhuma. Nenhum dos 214 arquivos de tarefa da fila
    tinha um campo dirigido a quem paga a conta.

    É o único verbo que PODE REPETIR, e a última explicação vence: o arquivo da
    tarefa não se edita (`armadilhas/356`), então corrigir um texto ruim é
    acrescentar outro. E é o único que funciona em tarefa `concluída` ou
    `cancelada`: a explicação diz o que a tarefa É, não o que aconteceu com ela.

    Recusa no espelho, como todo gesto que escreve: o evento tem de nascer na
    bancada para embarcar no PR (`armadilhas/192`).
    """
    recusa = _parar_se_for_o_espelho("explicar", raiz)
    if recusa:
        print(recusa)
        return 1
    tarefas, _ = _carregar_ou_parar(raiz)
    tid = args.tarefa
    if tid not in tarefas:
        print(f"RECUSADO: {tid} não existe na fila.")
        return 1
    problemas = problemas_da_explicacao(
        args.o_que_e, args.o_que_muda, args.exemplo, args.importancia
    )
    if problemas:
        for problema in problemas:
            print(f"RECUSADO: {problema}")
        return 1
    caminho = _escrever_evento(
        raiz,
        tid,
        EXPLICADA,
        args.quem,
        explicacao={
            "o_que_e": args.o_que_e,
            "o_que_muda": args.o_que_muda,
            "exemplo": args.exemplo,
            "importancia": args.importancia,
        },
    )
    print(f"📖 {tid} explicada. Evento: {caminho.relative_to(raiz)} (commite-o no seu PR)")
    print(f"   importância {args.importancia}: {args.o_que_e}")
    return 0


def cmd_listar(raiz: Path, args) -> int:
    tarefas, eventos = _carregar_ou_parar(raiz)
    reservas: set[str] = set()
    prs: dict[str, str] = {}
    if args.ao_vivo:
        reservas = reservas_no_servidor(raiz)
        prs = prs_citando_tarefas(raiz)
    estados = calcular_estados(tarefas, eventos, reservas, prs)
    if args.json:
        visao = {
            tid: {**estados[tid], "titulo": tarefas[tid]["titulo"], "toca": tarefas[tid]["toca"]}
            for tid in sorted(tarefas)
        }
        print(json.dumps(visao, ensure_ascii=False, indent=2))
        return 0
    if not tarefas:
        print("a fila está vazia.")
        return 0
    modo = "ao vivo (arquivos + reservas + PRs)" if args.ao_vivo else "só arquivos (use --ao-vivo para reservas e PRs)"
    print(f"A FILA DE TRABALHO — {len(tarefas)} tarefa(s) · {modo}\n")
    for tid in sorted(tarefas):
        t, e = tarefas[tid], estados[tid]
        extra = f" · {e['quem']}" if e.get("quem") else ""
        motivo = f" — {e['motivo']}" if e.get("motivo") else ""
        print(f"  {tid}  [{e['estado']}{extra}]{motivo}")
        print(f"         {t['titulo']}  (toca: {', '.join(t['toca'])})")
    return 0


def cmd_zelar(raiz: Path, args) -> int:
    recusa = _parar_se_for_o_espelho("zelar", raiz)
    if recusa:
        print(recusa)
        return 1
    tarefas, eventos = _carregar_ou_parar(raiz)
    reservas = reservas_no_servidor(raiz)
    prs = prs_citando_tarefas(raiz)
    escritos = rotular_orfaos(raiz, tarefas, eventos, reservas, prs, args.quem)
    if not escritos:
        print("✅ Zelador: nenhuma reivindicação órfã encontrada.")
        return 0
    print(f"🏷️  Zelador: {len(escritos)} reivindicação(ões) órfã(s) rotulada(s).")
    for caminho in escritos:
        print(f"   {caminho.relative_to(raiz)}")
    print("Nenhum ramo, PR ou reserva foi apagado. Commite os eventos no PR desta bancada.")
    return 0


def cmd_pegar(raiz: Path, args) -> int:
    # Antes de tudo — antes até de ler a fila e de tocar no servidor: se a
    # pasta é o espelho, o comprovante nasceria órfão (armadilhas/192).
    recusa = _parar_se_for_o_espelho("pegar", raiz)
    if recusa:
        print(recusa)
        return 1
    tarefas, eventos = _carregar_ou_parar(raiz)
    tid = args.tarefa
    if tid not in tarefas:
        print(f"RECUSADO: {tid} não existe na fila.")
        return 1
    reservas = reservas_no_servidor(raiz)
    prs = prs_citando_tarefas(raiz)
    escritos = rotular_orfaos(raiz, tarefas, eventos, reservas, prs, args.quem)
    if escritos:
        eventos = _carregar_ou_parar(raiz)[1]
        print(f"🏷️  Zelador: {len(escritos)} reivindicação(ões) órfã(s) rotulada(s) antes da aquisição.")
        for caminho in escritos:
            print(f"   {caminho.relative_to(raiz)}")
    estado = calcular_estados(tarefas, eventos, reservas, prs)[tid]
    if estado["estado"] == REIVINDICADA and tid in reservas:
        cadeia = [ev for ev in eventos if ev.get("tarefa") == tid and ev.get("evento") in EVENTOS_DE_CICLO]
        ultimo = cadeia[-1] if cadeia else None
        coerente = ultimo is None or (ultimo["evento"] == "reivindicada" and ultimo.get("quem") == args.quem)
        if coerente and reservar.confirmar_intencao(raiz, f"{PREFIXO_DA_RESERVA}{tid}"):
            if ultimo is None:
                _escrever_evento(raiz, tid, "reivindicada", args.quem)
            print(f"PASS {tid}: reserva própria conferida no servidor; reivindicação retomada.")
            print(tarefas[tid]["despacho"])
            return 0
    if estado["estado"] != NA_FILA:
        print(f"RECUSADO: {tid} está '{estado['estado']}'" + (f" ({estado['motivo']})" if estado["motivo"] else "") + ".")
        print("Só tarefa NA FILA se pega. Veja o quadro: python ci/fila.py listar --ao-vivo")
        return 1
    ganhou, recado = reservar.reservar_intencao(
        raiz, f"{PREFIXO_DA_RESERVA}{tid}", objetivo=tarefas[tid]["titulo"]
    )
    if not ganhou:
        print(f"RECUSADO PELO SERVIDOR: {recado}")
        return 1
    caminho = _escrever_evento(raiz, tid, "reivindicada", args.quem)
    print(f"✅ {tid} é sua — {recado}")
    print(f"   evento: {caminho.relative_to(raiz)} (commite-o no seu PR)")
    print(f"   evidência exigida para concluir: {tarefas[tid]['evidencia_exigida']}\n")
    print("── DESPACHO ────────────────────────────────────────────────")
    print(tarefas[tid]["despacho"])
    print("────────────────────────────────────────────────────────────")
    return 0


def cmd_soltar(raiz: Path, args) -> int:
    tarefas, eventos = _carregar_ou_parar(raiz)
    tid = args.tarefa
    if tid not in tarefas:
        print(f"RECUSADO: {tid} não existe na fila.")
        return 1
    _soltar_reserva_se_houver(raiz, tid)
    if ultima_submissao(eventos, tid):
        print(f"{tid}: reserva solta; entrega continua aguardando comprovação.")
        return 0
    caminho = _escrever_evento(raiz, tid, "devolvida", args.quem, detalhe=args.motivo)
    print(f"{tid} devolvida à fila. Evento: {caminho.relative_to(raiz)}")
    return 0


def cmd_bloquear(raiz: Path, args) -> int:
    """Escreve o evento `bloqueada` — o estado que existia sem ninguém para criá-lo.

    O `bloqueada` é estado calculado desde que a fila nasceu, e `validar` já
    exigia `detalhe` nele. Só faltava o verbo: quem precisasse bloquear escrevia
    o JSON do evento à mão, fora do balcão, sem passar por nenhuma das recusas
    daqui. Em 04/09/2026 duas sessões do mesmo lote fizeram exatamente isso, uma
    delas chamando `_escrever_evento` por dentro do módulo.

    Escrever evento à mão é a porta de entrada da `armadilhas/192`: o arquivo
    nasce onde ninguém commita, o PR viaja sem ele, e `validar` responde
    "✅ Fila válida" porque o que não está lá não pode reprovar.

    Recusa no espelho, como `concluir`: o evento tem de nascer na bancada, para
    embarcar no PR. Diferente do `soltar`, que continua livre porque devolver à
    fila uma tarefa presa é gesto de emergência.

    Desde 06/09/2026 exige `--espera`, e a obrigatoriedade é a mesma lição que o
    `--move` já deu nesta casa: campo que nasce opcional no balcão nasce vazio.
    Quem bloqueia sabe, naquele instante, se um robô destrava aquilo sozinho —
    ninguém depois vai saber melhor, e ninguém depois vai voltar para preencher.
    """
    recusa = _parar_se_for_o_espelho("bloquear", raiz)
    if recusa:
        print(recusa)
        return 1
    tarefas, eventos = _carregar_ou_parar(raiz)
    tid = args.tarefa
    if tid not in tarefas:
        print(f"RECUSADO: {tid} não existe na fila.")
        return 1
    estado = calcular_estados(tarefas, eventos)[tid]
    if estado["estado"] in (CONCLUIDA, CANCELADA):
        print(f"RECUSADO: {tid} já terminou ({estado['estado']}).")
        print("Depois do fim, silêncio: evento após o fim reprova na muralha.")
        return 1
    if not (args.motivo or "").strip():
        print("RECUSADO: bloquear sem motivo não existe.")
        print("O motivo é o que a caixa do painel e o próximo robô vão LER para")
        print("saber o que destrava — e `validar` reprova `bloqueada` sem detalhe.")
        return 1
    _soltar_reserva_se_houver(raiz, tid)
    caminho = _escrever_evento(
        raiz, tid, "bloqueada", args.quem, detalhe=args.motivo, espera=args.espera
    )
    print(f"⛔ {tid} bloqueada. Evento: {caminho.relative_to(raiz)} (commite-o no seu PR)")
    if args.espera == ESPERA_O_MANTENEDOR:
        print("Ela vai aparecer em 'Esperando uma decisão sua' no /admin/caixa/robos/,")
        print("e o `motivo` é o texto que ele vai ler ali — escreva para leigo.")
    print("Para destravar: um evento `devolvida` (python ci/fila.py soltar ...).")
    return 0


def cmd_cancelar(raiz: Path, args) -> int:
    """Escreve o evento `cancelada` — o segundo estado que não tinha verbo.

    `cancelada` é terminal desde que a fila nasceu, `validar` já exigia
    `detalhe` nele, e o painel já tinha o grupo "Não vão mais ser feitas" para
    mostrá-lo. Faltava a mesma peça que faltou ao `bloquear` até 04/09/2026: a
    porta. Quem precisasse cancelar escrevia o JSON à mão — a porta de entrada
    da `armadilhas/192`, com o arquivo nascendo onde ninguém commita.

    Medido em 06/09/2026, ao limpar a fila: oito tarefas (TAR-057 a TAR-065)
    estavam paradas em `bloqueada` com o motivo dizendo "TRANCADA ... substituta
    já criada". Elas nunca mais seriam feitas, e por falta deste verbo moravam
    no bloco de urgência do painel do dono, ao lado das que esperavam decisão
    dele. Estado sem verbo não é estado: é um lugar que ninguém alcança.

    Não pede `--espera`, e isso é a diferença que importa: cancelada não espera
    ninguém. É por isso que ela cura o que `bloqueada` não deveria carregar.
    """
    recusa = _parar_se_for_o_espelho("cancelar", raiz)
    if recusa:
        print(recusa)
        return 1
    tarefas, eventos = _carregar_ou_parar(raiz)
    tid = args.tarefa
    if tid not in tarefas:
        print(f"RECUSADO: {tid} não existe na fila.")
        return 1
    estado = calcular_estados(tarefas, eventos)[tid]
    if estado["estado"] in (CONCLUIDA, CANCELADA):
        print(f"RECUSADO: {tid} já terminou ({estado['estado']}).")
        print("Depois do fim, silêncio: evento após o fim reprova na muralha.")
        return 1
    if not (args.motivo or "").strip():
        print("RECUSADO: cancelar sem motivo não existe.")
        print("O motivo é o que fica no lugar da tarefa para sempre — diga por que")
        print("ela não vai mais ser feita, e para onde foi o trabalho, se foi.")
        return 1
    # Quem depende dela trava para SEMPRE: `calcular_estados` só destrava
    # dependência CONCLUÍDA. Dizer isso antes é o que separa uma decisão de uma
    # surpresa — e foi exatamente assim que a TAR-060 caiu, por depender de uma
    # trancada. Avisa e segue: cancelar mesmo assim é legítimo quando a
    # substituta já existe, e o balcão não sabe se existe.
    presas = sorted(
        outra
        for outra, dados in tarefas.items()
        if tid in (dados.get("depende_de") or [])
        and calcular_estados(tarefas, eventos)[outra]["estado"]
        not in (CONCLUIDA, CANCELADA)
    )
    if presas:
        print(f"⚠️  Estas dependem de {tid} e vão ficar presas para sempre:")
        print(f"   {', '.join(presas)}")
        print("   Dependência só se destrava CONCLUÍDA. Cancele-as ou dê substituta.")
    _soltar_reserva_se_houver(raiz, tid)
    caminho = _escrever_evento(raiz, tid, "cancelada", args.quem, detalhe=args.motivo)
    print(f"🗑️  {tid} cancelada. Evento: {caminho.relative_to(raiz)} (commite-o no seu PR)")
    print("Não há volta: depois do terminal, a fila não aceita mais nenhum evento.")
    return 0


def cmd_submeter(raiz: Path, args) -> int:
    recusa = _parar_se_for_o_espelho("submeter", raiz)
    if recusa:
        print(recusa)
        return 1
    tarefas, eventos = _carregar_ou_parar(raiz)
    tid = args.tarefa
    if tid not in tarefas:
        print(f"RECUSADO: {tid} não existe. Confira python ci/fila.py listar.")
        return 1
    if calcular_estados(tarefas, eventos)[tid]["estado"] in (CONCLUIDA, CANCELADA):
        print(f"RECUSADO: {tid} já terminou. Confira sua cadeia antes de submeter.")
        return 1
    vinculo = {campo: getattr(args, campo) for campo in ("pr", "revisao", "arvore")}
    erros = problemas_da_submissao(vinculo)
    if erros:
        print("RECUSADO: " + "; ".join(erros) + ". Retome com o PR e a revisão validados.")
        return 1
    anterior = ultima_submissao(eventos, tid)
    if anterior and anterior.get("pr") != args.pr:
        print(f"RECUSADO: {tid} já tem outra entrega submetida. Confira {anterior['pr']} antes de trocar o vínculo.")
        return 1
    if not anterior or any(anterior.get(campo) != valor for campo, valor in vinculo.items()):
        dados = montar_evento(tid, "submetida", args.quem)
        dados.update(vinculo)
        pasta_eventos(raiz).mkdir(parents=True, exist_ok=True)
        caminho = pasta_eventos(raiz) / f"{dados['arquivo']}.json"
        if caminho.exists():
            raise ErroDeInstrumentacao("evento de submissão já existe", "Repita após conferir o evento; não sobrescreva a história.")
        _escrever_json(caminho, dados)
    _soltar_reserva_se_houver(raiz, tid)
    print(f"{tid}: entrega submetida em {args.pr}; aguardando comprovação do aceite.")
    return 0


def _concluir_com_prova(
    raiz: Path,
    tid: str,
    quem: str,
    evidencia: str,
    verificado_em: str,
) -> int:
    """Único ponto terminal para `concluir` e `reconciliar`.

    Guardas sobre a responsabilidade da entrega pertencem aqui, antes da
    soltura da reserva e da escrita do evento, para valer nos dois caminhos.
    """
    tarefas, _ = _carregar_ou_parar(raiz)
    tarefa = tarefas.get(tid)
    if tarefa is None and (raiz / "fila" / "tarefas").exists():
        print(f"RECUSADO: {tid} não existe na fila.")
        return 1
    responsabilidade = normalizar_responsabilidade(tarefa.get("responsabilidade")) if tarefa else ""
    if tarefa and tarefa_exige_responsabilidade(tarefa) and not responsabilidade:
        print("RECUSADO: tarefa nova sem responsabilidade declarada.")
        print("Cadastre uma unidade de responsabilidade antes de concluir.")
        return 1
    cadastro = raiz / "painel" / "responsabilidades.json"
    if tarefa and tarefa_exige_responsabilidade(tarefa) and not cadastro.exists():
        print("RECUSADO: cadastro de responsabilidades não existe.")
        print("Crie painel/responsabilidades.json antes de concluir a entrega.")
        return 1
    if responsabilidade and cadastro.exists():
        try:
            problemas = responsabilidades.validar_entrega(raiz, responsabilidade)
        except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError, KeyError, TypeError) as erro:
            print(f"RECUSADO: não foi possível ler o cadastro de responsabilidades ({erro}). Corrija painel/responsabilidades.json e repita.")
            return 1
        if problemas:
            print("RECUSADO: a entrega não pode ser concluída sem responsabilidade comprovada.")
            for problema in problemas:
                print(f"   - {problema}")
            return 1
    caminho = _escrever_evento(
        raiz,
        tid,
        "concluida",
        quem,
        evidencia=evidencia,
        verificado_em=verificado_em,
    )
    try:
        _soltar_reserva_se_houver(raiz, tid)
    except ErroDeInstrumentacao as erro:
        raise ErroDeInstrumentacao(
            "a conclusão foi registrada, mas a reserva não foi liberada",
            f"Evento: {caminho.relative_to(raiz)}\n"
            f"Rode python ci/fila.py soltar {tid} --quem {quem} e confira a reserva.\n"
            f"Causa original: {erro.resumo}",
        ) from erro
    print(
        f"✅ {tid} concluída. Evento: {caminho.relative_to(raiz)} (commite-o no seu PR)"
    )
    return 0


def cmd_concluir(raiz: Path, args) -> int:
    recusa = _parar_se_for_o_espelho("concluir", raiz)
    if recusa:
        print(recusa)
        return 1
    tarefas, eventos = _carregar_ou_parar(raiz)
    tid = args.tarefa
    if tid not in tarefas:
        print(f"RECUSADO: {tid} não existe na fila.")
        return 1
    estado = calcular_estados(tarefas, eventos)[tid]
    if estado["estado"] in (CONCLUIDA, CANCELADA):
        print(f"RECUSADO: {tid} já terminou ({estado['estado']}).")
        return 1
    if ultima_submissao(eventos, tid):
        print(
            f"RECUSADO: {tid} aguarda comprovação do aceite, além da abertura ou integração do PR."
        )
        print(
            "Use a reconciliação da entrega com a prova exigida; não encerre por texto livre."
        )
        print(f"O que esta tarefa exige: {tarefas[tid]['evidencia_exigida']}")
        return 1
    if not (args.evidencia or "").strip():
        print(
            "RECUSADO: concluir sem evidência não existe — a mesma lei do verde do livro."
        )
        print(f"O que esta tarefa exige: {tarefas[tid]['evidencia_exigida']}")
        return 1
    return _concluir_com_prova(
        raiz,
        tid,
        args.quem,
        args.evidencia,
        args.verificado_em or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )


def tarefa_exige_responsabilidade(tarefa: dict) -> bool:
    """Somente tarefas criadas pela guarda exigem responsabilidade."""
    return tarefa.get("responsabilidade_obrigatoria") is True

def cmd_reconciliar(raiz: Path, args) -> int:
    recusa = _parar_se_for_o_espelho("reconciliar", raiz)
    if recusa:
        print(recusa)
        return 1
    if not bancada_contem_main_publicada(raiz):
        print(
            "RECUSADO: origin/main contém eventos que esta bancada ainda não incorporou."
        )
        print(
            "Faça merge de origin/main nesta bancada e repita reconciliar; "
            "nenhuma reserva ou evento foi alterado."
        )
        return 1
    tarefas, eventos = _carregar_ou_parar(raiz)
    tid = args.tarefa
    if tid not in tarefas:
        print(f"RECUSADO: {tid} não existe na fila.")
        return 1
    estado = calcular_estados(tarefas, eventos)[tid]
    if estado["estado"] in (CONCLUIDA, CANCELADA):
        print(
            f"RECUSADO: {tid} já terminou ({estado['estado']}); nenhum evento foi repetido."
        )
        return 1
    submissao = ultima_submissao(eventos, tid)
    if not submissao:
        print(f"RECUSADO: {tid} não tem entrega submetida para reconciliar.")
        print(
            "Use concluir no fluxo legado, ou submeter com PR, revisão e árvore validados."
        )
        return 1
    try:
        evidencia, verificado_em = provar_reconciliacao(
            raiz, submissao, args.aceite_registro
        )
    except RecusaDeReconciliacao as erro:
        print(f"RECUSADO: {erro}.")
        print(f"O que esta tarefa exige: {tarefas[tid]['evidencia_exigida']}")
        return 1
    return _concluir_com_prova(
        raiz,
        tid,
        args.quem,
        evidencia,
        verificado_em,
    )

def _soltar_reserva_se_houver(raiz: Path, tid: str) -> None:
    """Solta a referência no servidor; se ela não existir, não é erro."""
    try:
        reservar.soltar(raiz, f"{PREFIXO_DA_RESERVA}{tid}")
    except ErroDeInstrumentacao as erro:
        texto = f"{erro.resumo}\n{erro.detalhe or ''}"
        if "remote ref does not exist" in texto or "unable to delete" in texto:
            return
        raise


def cmd_validar(raiz: Path) -> int:
    if not (raiz / "fila").is_dir():
        print("❌ FILA: a pasta fila/ não existe.")
        print("   A fila de trabalho faz parte do repositório desde 29/08/2026 —")
        print("   apagá-la (ou movê-la) não pode passar verde.")
        return 1
    erros: list[str] = []
    tarefas = carregar_tarefas(raiz, erros)
    eventos = carregar_eventos(raiz, tarefas, erros)
    if erros:
        print(f"❌ FILA INVÁLIDA — {len(erros)} problema(s):")
        for erro in erros:
            print(f"   - {erro}")
        return 1
    estados = calcular_estados(tarefas, eventos)
    # Bloqueio VIVO sem `espera` reprova; bloqueio já superado, não. A régua é o
    # estado de HOJE, e não uma data de corte no código: os 22 eventos
    # `bloqueada` de tarefas que já seguiram adiante são história encerrada, e
    # cobrar deles exigiria reescrever evento — que esta fila não faz. O que
    # importa é que nenhuma tarefa PARADA fique sem dizer quem a destrava, e
    # essa conta se refaz inteira a cada PR.
    sem_dono = sorted(
        tid
        for tid, e in estados.items()
        if e["estado"] == BLOQUEADA and not e.get("espera")
    )
    for tid in sem_dono:
        erros.append(
            f"{tid}: parada sem dizer quem destrava. Acrescente um bloqueio novo "
            f"com --espera ({' ou '.join(QUEM_DESTRAVA)}), ou conclua/cancele a tarefa"
        )
    if erros:
        print(f"❌ FILA INVÁLIDA — {len(erros)} problema(s):")
        for erro in erros:
            print(f"   - {erro}")
        return 1
    contagem: dict[str, int] = {}
    for e in estados.values():
        contagem[e["estado"]] = contagem.get(e["estado"], 0) + 1
    resumo = " · ".join(f"{k}: {v}" for k, v in sorted(contagem.items())) or "vazia"
    print(f"✅ Fila válida — {len(tarefas)} tarefa(s), {len(eventos)} evento(s) ({resumo}).")
    # E, em SOMBRA, o que o ✅ sozinho já escondeu uma vez: comprovante que
    # existe no disco e o Git não conhece (armadilhas/192). Avisa, não reprova.
    dizer_os_comprovantes_soltos(raiz)
    return 0


# ---------------------------------------------------------------------------
# A IMUTABILIDADE DO ARQUIVO DE TAREFA — o guarda que faltava (05/09/2026)
#
# A lei está no cabeçalho deste arquivo desde 29/08/2026 ("o arquivo da tarefa
# nunca muda depois de criado" · "nada se edita, corrigir é acrescentar") e até
# 05/09/2026 NINGUÉM a fazia valer: `validar` confere cada arquivo EM SI (molde,
# campo obrigatório, dependência que existe, ausência de ciclo) e nunca o compara
# com a versão anterior. Medido e catalogado em `armadilhas/356`. Este guarda
# entrou com mandato escrito do mantenedor, porque `ci/` é caminho CODEOWNERS.
#
# A ASSIMETRIA é o miolo do guarda, e fica justificada aqui, não só no despacho:
#
#   tarefa NOVA .............. passa livre. Criar não é editar.
#   tarefa APAGADA ........... REPROVA. Apagar e recriar é editar por outra
#                              porta, e um guarda que ignorasse isso seria
#                              contornado no primeiro dia.
#   tarefa QUE JÁ EXISTE ..... só pode mudar `depende_de`.
#
# Por que só `depende_de`: `titulo`, `evidencia_exigida`, `despacho`, `toca`,
# `move`, `cria`, `origem` e `criada_em` dizem O QUE a tarefa é e por que ela
# existe. Não têm por que mudar depois de criados, porque trabalho diferente é
# tarefa NOVA, e mexer num deles reescreve a tarefa debaixo de quem já a pegou,
# ou apaga a prova que o `concluir` vai cobrar. O `depende_de` é o único campo
# que descreve a RELAÇÃO com as outras tarefas: ele erra sozinho (uma escada
# nasce encadeada em linha reta e sai com correntes falsas) e é o único cuja
# correção NÃO tem caminho append-only, porque nenhum dos cinco eventos de
# `EVENTOS_VALIDOS` muda uma corrente, e cancelar-e-recriar trava a vizinha para
# sempre (`calcular_estados` só destrava a dependência CONCLUÍDA e `cmd_pegar`
# só aceita tarefa NA FILA). Liberar só ele é o mínimo que devolve o conserto
# sem abrir a porta para reescrever a história de uma tarefa.
#
# Por que fail-closed no primeiro dia, e não em sombra: o precedente legítimo foi
# medido antes de escrever uma linha. O único commit que já corrigiu uma corrente
# na história da fila (8dcba645, PR #1139) mudou EXATAMENTE dois `depende_de` e
# nada mais, e passa por aqui. O que este guarda reprova é o que ninguém nunca
# teve motivo legítimo de fazer.
# ---------------------------------------------------------------------------

CAMPO_QUE_PODE_MUDAR = "depende_de"
BASE_PADRAO = "origin/main"


def _git_da_fila(raiz: Path, *args: str, para_que: str) -> str:
    """Um `git` que, quando não responde, vira ERROR e não silêncio."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(raiz), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ErroDeInstrumentacao(
            f"o git não respondeu ao {para_que}",
            f"Comando: git {' '.join(args)}\n{exc}\n\n"
            "A imutabilidade da fila NÃO foi medida. Isto não é um OK.",
        ) from exc
    if proc.returncode != 0:
        raise ErroDeInstrumentacao(
            f"o git recusou o {para_que} (exit {proc.returncode})",
            f"Comando: git {' '.join(args)}\n{(proc.stderr or '').strip()}\n\n"
            "A base existe nesta pasta? O checkout do CI tem fetch-depth: 0?\n"
            "A imutabilidade da fila NÃO foi medida. Isto não é um OK.",
        )
    return proc.stdout


def mudancas_em_tarefas(raiz: Path, base: str) -> list[tuple[str, str]]:
    """(status, caminho) de cada arquivo de `fila/tarefas/` que o ramo mexeu.

    `--no-renames` de propósito: renomear desdobra em remoção mais adição, para
    nenhum dos dois lados escapar da inspeção. `-z` de propósito: os nomes de
    tarefa têm acento, e fora do modo NUL o git citaria o caminho.
    """
    saida = _git_da_fila(
        raiz, "diff", "--raw", "--no-renames", "-z", f"{base}...HEAD",
        "--", "fila/tarefas",
        para_que="diff de fila/tarefas contra a base",
    )
    pedacos = [p for p in saida.split("\0") if p]
    mudancas: list[tuple[str, str]] = []
    while pedacos:
        meta = pedacos.pop(0)
        if not meta.startswith(":") or not pedacos:
            raise ErroDeInstrumentacao(
                "o diff cru da fila veio numa forma que não sei ler",
                f"Pedaço inesperado: {meta!r}\n\n"
                "A imutabilidade da fila NÃO foi medida. Isto não é um OK.",
            )
        mudancas.append((meta.rsplit(" ", 1)[-1], pedacos.pop(0)))
    return mudancas


def _tarefa_na_revisao(raiz: Path, revisao: str, caminho: str) -> dict:
    bruto = _git_da_fila(
        raiz, "show", f"{revisao}:{caminho}",
        para_que=f"leitura de {caminho} em {revisao}",
    )
    try:
        return json.loads(bruto)
    except json.JSONDecodeError as exc:
        raise ErroDeInstrumentacao(
            f"{caminho} não é JSON válido em {revisao}",
            f"{exc}\n\nSem os dois lados não dá para comparar campo a campo. "
            "A imutabilidade da fila NÃO foi medida.",
        ) from exc


def conferir_imutabilidade(raiz: Path, base: str) -> list[str]:
    """As violações da lei "nada se edita", uma frase por violação."""
    problemas: list[str] = []
    for status, caminho in mudancas_em_tarefas(raiz, base):
        if status.startswith("A"):
            continue  # criar não é editar
        if status.startswith("D"):
            problemas.append(
                f"{caminho} foi APAGADO — apagar e recriar é editar por outra porta"
            )
            continue
        if not status.startswith("M"):
            problemas.append(
                f"{caminho} entrou com status '{status}' (troca de tipo ou de modo) — "
                "arquivo de tarefa é dado, e só nasce ou fica como está"
            )
            continue
        antes = _tarefa_na_revisao(raiz, base, caminho)
        depois = _tarefa_na_revisao(raiz, "HEAD", caminho)
        for campo in sorted(set(antes) | set(depois)):
            if campo == CAMPO_QUE_PODE_MUDAR:
                continue
            if antes.get(campo) != depois.get(campo):
                problemas.append(f"{caminho} mudou o campo '{campo}'")
    return problemas


def cmd_imutabilidade(raiz: Path, base: str) -> int:
    if not (raiz / ".git").exists():
        raise ErroDeInstrumentacao(
            "esta pasta não é um checkout git",
            "Sem repositório não há versão anterior com que comparar.\n"
            "A imutabilidade da fila NÃO foi medida. Isto não é um OK.",
        )
    problemas = conferir_imutabilidade(raiz, base)
    if problemas:
        print(f"❌ FILA EDITADA — {len(problemas)} violação(ões) da lei 'nada se edita':")
        for problema in problemas:
            print(f"   - {problema}")
        print()
        print("   O arquivo de uma tarefa nunca muda depois de criado (RITOS.md §5).")
        print(f"   A ÚNICA exceção é o campo '{CAMPO_QUE_PODE_MUDAR}', porque nenhum evento")
        print("   conserta uma corrente errada, e cancelar-e-recriar trava a vizinha")
        print("   para sempre (armadilhas/356).")
        print()
        print("   Trabalho diferente do que a tarefa descreve? Crie uma tarefa NOVA:")
        print("     python ci/fila.py criar --titulo ... --toca <celula> --move <cartao>")
        print("   Mudou de estado (pegou, devolveu, travou, concluiu)? Isso é EVENTO,")
        print("   nunca campo: pegar, soltar, bloquear, concluir.")
        return 1
    print(
        f"✅ Fila imutável — nenhuma tarefa que já existia mudou fora de "
        f"'{CAMPO_QUE_PODE_MUDAR}' (base {base})."
    )
    return 0


def _argumentos_da_explicacao(p: argparse.ArgumentParser) -> None:
    """Os quatro campos, com o mesmo nome e a mesma ajuda em `criar` e em
    `explicar` — dois textos de ajuda para o mesmo campo já divergiriam aqui."""
    p.add_argument(
        "--o-que-e",
        required=True,
        help="o que existe hoje, em português de leigo, sem sigla e sem jargão",
    )
    p.add_argument(
        "--o-que-muda",
        required=True,
        help="o que essa tarefa muda na vida de quem usa o site, ou o que custa não fazer",
    )
    p.add_argument(
        "--exemplo",
        required=True,
        help="um caso concreto ou uma comparação do dia a dia, para a coisa ficar visível",
    )
    p.add_argument(
        "--importancia",
        required=True,
        type=int,
        metavar="0-100",
        help=(
            f"o quanto isto pesa hoje, de {IMPORTANCIA_MINIMA} a {IMPORTANCIA_MAXIMA} — "
            "é o que ordena a tela dele"
        ),
    )


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A fila de trabalho: tarefa registrada, estado calculado, trava no servidor."
    )
    sub = parser.add_subparsers(dest="acao", required=True)

    p = sub.add_parser("criar", help="registra uma tarefa nova (número vem do almoxarife)")
    p.add_argument("--titulo", required=True, help="uma linha, para leigo, sem sigla")
    p.add_argument("--toca", required=True, nargs="+", help="o que ela mexe (ex.: admin painel)")
    p.add_argument("--depende-de", nargs="*", default=[], metavar="TAR-NNN")
    p.add_argument(
        "--cria",
        nargs="*",
        default=[],
        metavar="CAMINHO",
        help="pastas que esta tarefa traz à existência (só a gênese precisa)",
    )
    p.add_argument(
        "--move",
        required=True,
        nargs="+",
        metavar="CARTAO",
        help=(
            "que número do placar esta tarefa move (nome de painel/cartoes/), "
            f"ou '{MANUTENCAO}' se ela mantém a fábrica de pé sem mover número"
        ),
    )
    p.add_argument("--evidencia-exigida", required=True, help="que prova fecha esta tarefa")
    p.add_argument("--responsabilidade", required=True, help="id da unidade de responsabilidade que acompanha o desfecho")
    p.add_argument("--despacho", default="", help="o prompt pronto para colar")
    p.add_argument("--despacho-arquivo", default="", help="ou um arquivo com o despacho")
    p.add_argument("--origem", default="despacho do mantenedor", help="de onde a tarefa veio")
    _argumentos_da_explicacao(p)

    p = sub.add_parser(
        "explicar",
        help="diz em português o que a tarefa é — pode repetir, e a última vence",
    )
    p.add_argument("tarefa", metavar="TAR-NNN")
    p.add_argument("--quem", required=True)
    _argumentos_da_explicacao(p)

    p = sub.add_parser("listar", help="o quadro, com estados calculados")
    p.add_argument("--ao-vivo", action="store_true", help="soma reservas do servidor e PRs abertos")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("pegar", help="trava a tarefa no servidor e escreve o evento")
    p.add_argument("tarefa", metavar="TAR-NNN")
    p.add_argument("--quem", required=True, help="quem está pegando (ex.: sessao-fila-2908)")

    p = sub.add_parser("zelar", help="rotula reivindicações órfãs sem apagar ramos ou PRs")
    p.add_argument("--quem", required=True, help="quem registrou a varredura")

    p = sub.add_parser("soltar", help="devolve a tarefa à fila")
    p.add_argument("tarefa", metavar="TAR-NNN")
    p.add_argument("--quem", required=True)
    p.add_argument("--motivo", default="", help="por que está devolvendo")

    p = sub.add_parser("bloquear", help="trava a tarefa — exige motivo e quem destrava")
    p.add_argument("tarefa", metavar="TAR-NNN")
    p.add_argument("--quem", required=True)
    p.add_argument("--motivo", required=True, help="o que trava, e o que destrava")
    p.add_argument(
        "--espera",
        required=True,
        choices=QUEM_DESTRAVA,
        help=(
            f"quem destrava: '{ESPERA_O_MANTENEDOR}' (autorização, decisão ou prova "
            f"que só ele pode dar) ou '{ESPERA_A_FILA}' (um robô resolve quando a vez "
            "dela chegar). O que for 'mantenedor' aparece em bloco próprio no painel"
        ),
    )

    p = sub.add_parser("cancelar", help="tira a tarefa da fila para sempre — exige motivo")
    p.add_argument("tarefa", metavar="TAR-NNN")
    p.add_argument("--quem", required=True)
    p.add_argument("--motivo", required=True, help="por que ela não vai mais ser feita")

    p = sub.add_parser("submeter", help="vincula a entrega validada sem concluir a tarefa")
    p.add_argument("tarefa", metavar="TAR-NNN")
    p.add_argument("--quem", required=True)
    p.add_argument("--pr", required=True, help="URL completa do pull request")
    p.add_argument("--revisao", required=True, help="SHA completo do código validado")
    p.add_argument("--arvore", required=True, help="SHA completo da árvore validada")

    p = sub.add_parser("concluir", help="fecha a tarefa — exige evidência")
    p.add_argument("tarefa", metavar="TAR-NNN")
    p.add_argument("--quem", required=True)
    p.add_argument("--evidencia", required=True, help="a prova (URL de PR, saída de teste…)")
    p.add_argument("--verificado-em", default="", help="quando a prova foi conferida (AAAA-MM-DD)")

    p = sub.add_parser(
        "reconciliar",
        help="fecha entrega submetida após conferir integração, publicação e aceite",
    )
    p.add_argument("tarefa", metavar="TAR-NNN")
    p.add_argument("--quem", required=True)
    p.add_argument(
        "--aceite-registro",
        required=True,
        help="painel/registros/AAAAMMDD-NNN-slug.js já integrado após a entrega",
    )

    sub.add_parser("validar", help="fail-closed; é o que a muralha roda")

    p = sub.add_parser(
        "imutabilidade",
        help="o diff de fila/tarefas contra a base; é o que a muralha roda",
    )
    p.add_argument(
        "--base",
        default=os.environ.get("BASE_REF") or BASE_PADRAO,
        help="a revisão com que comparar (padrão: BASE_REF, ou origin/main)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    args = construir_parser().parse_args(argv)
    try:
        raiz = raiz_do_repo()
        if args.acao == "criar":
            return cmd_criar(raiz, args)
        if args.acao == "listar":
            return cmd_listar(raiz, args)
        if args.acao == "zelar":
            return cmd_zelar(raiz, args)
        if args.acao == "pegar":
            return cmd_pegar(raiz, args)
        if args.acao == "soltar":
            return cmd_soltar(raiz, args)
        if args.acao == "bloquear":
            return cmd_bloquear(raiz, args)
        if args.acao == "cancelar":
            return cmd_cancelar(raiz, args)
        if args.acao == "submeter":
            return cmd_submeter(raiz, args)
        if args.acao == "concluir":
            return cmd_concluir(raiz, args)
        if args.acao == "reconciliar":
            return cmd_reconciliar(raiz, args)
        if args.acao == "explicar":
            return cmd_explicar(raiz, args)
        if args.acao == "imutabilidade":
            return cmd_imutabilidade(raiz, args.base)
        return cmd_validar(raiz)
    except ErroDeInstrumentacao as erro:
        print(f"\nPAROU POR SEGURANÇA: {erro.resumo}\n")
        if erro.detalhe:
            print(erro.detalhe)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
