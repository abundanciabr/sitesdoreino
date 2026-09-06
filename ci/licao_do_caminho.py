#!/usr/bin/env python3
"""A LIÇÃO DO CAMINHO — o que já custou caro aqui chega ANTES de você escrever.

Por que ela existe (06/09/2026, pedido do mantenedor). O catálogo de
`armadilhas/` tem 339 entradas e duas formas de alcançar quem trabalha, ambas
TARDIAS por construção:

  o índice ...... depende de o agente lembrar de dar Ctrl+F, e adivinhar a
                  palavra certa antes de errar;
  o sino ........ casa a MENSAGEM DE ERRO na saída do comando, e mensagem de
                  erro só existe depois da queda.

Medido no dia em que este arquivo nasceu: 140 das 339 entradas tinham
assinatura de erro e NENHUMA tinha como dizer "isto vai te morder quando você
for mexer em tal lugar". Na mesma sessão, a armadilhas/179 (o número do
registro se PEDE ao almoxarife, nunca se escolhe) mordeu um agente que a tinha
no disco desde 29/08: ninguém procura por "número repetido" enquanto escreve um
registro. Procura-se depois, quando o CI já reprovou, e o preço foi uma rodada
inteira de checks mais uma devolução da pista.

O que muda aqui: a lição passa a ser indexada pela INTENÇÃO. Cada entrada pode
declarar `gatilho` (os caminhos que se toca antes de cair nela) e `licao` (a
frase que salva a rodada), o gerador do índice compila os dois em
`armadilhas/GATILHOS.json`, e este gancho os entrega no momento em que o agente
vai gravar naquele caminho.

COMO ELE FALA — e por que RECUSAR é o canal, não um bilhete
------------------------------------------------------------
Recusa (exit 2) porque é o único canal comprovado desta casa para o PreToolUse:
o stderr da recusa chega ao agente como texto que ele lê e obedece na hora
(provado pela muralha da pasta, pela do travessão e pela das armadilhas). O
`additionalContext` do PostToolUse existe e funciona (é como o sino fala), mas
ele só fala DEPOIS da gravação — e para a classe de armadilha que este gancho
cobre, o dano mora no próprio ato de gravar: um registro criado com o número
errado já nasce colidindo com o de outra sessão.

E ele recusa UMA VEZ POR CAMINHO, POR SESSÃO. A segunda tentativa de gravar
passa direto, mesmo que nada tenha mudado — porque o objetivo é ENSINAR, não
impedir. A conta é honesta: custa uma repetição da chamada de escrita, e
devolve a rodada de CI que a lição evita. Um aviso que se repetisse a cada
gravação viraria ruído, e ruído é o que faz alguém desligar o mecanismo (a
lição da TAR-043, medida nesta casa).

FAIL-OPEN, ao contrário das muralhas — a lei da autoridade proporcional à
certeza, que esta casa já escreveu para o sino:

    muralha IMPEDE   ⇒ na dúvida, impede (erro interno vira recusa)
    lição   ENSINA   ⇒ na dúvida, CALA   (erro interno vira silêncio)

Aqui não há dano a impedir: o agente pode estar fazendo tudo certo. Travar uma
sessão por causa de um conselho seria pior que conselho nenhum. Por isso
`GATILHOS.json` ausente, JSON corrompido, caminho ilegível e qualquer exceção
interna viram exit 0 e silêncio.

O QUE ELE NÃO VÊ, dito na cara: escrita por shell (heredoc, `echo >`) não passa
por Write/Edit e não é vista aqui; e a lição só existe para a armadilha que
declarou `gatilho`. Entrada sem gatilho continua dependendo do índice e do sino,
como sempre — este gancho não substitui nenhum dos dois, ele chega antes.
"""

from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import telemetria  # noqa: E402  (irmão de pasta; o insert acima é o que o permite)
from muralha_pasta_compartilhada import raiz_do_checkout  # noqa: E402

NOME_DO_ARQUIVO = "GATILHOS.json"
EVENTO = "licao_entregue"
TETO_DE_LICOES = 4  # o mesmo caminho pode ter várias; a tela tem limite


def _utf8_na_saida() -> None:
    # armadilhas/003: acento/emoji em console cp1252 estoura UnicodeEncodeError
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def caminho_do_alvo(entrada: dict) -> Path | None:
    """O arquivo que a ferramenta vai gravar, absoluto. `None` se não há um."""
    if entrada.get("tool_name") not in ("Write", "Edit"):
        return None
    bruto = (entrada.get("tool_input") or {}).get("file_path") or ""
    if not bruto:
        return None
    alvo = Path(bruto)
    if not alvo.is_absolute():
        alvo = Path(entrada.get("cwd") or ".") / alvo
    try:
        return alvo.resolve()
    except OSError:
        return None


def licoes_do_caminho(raiz: Path, relativo: str) -> tuple[str, list[dict]]:
    """As lições declaradas para este caminho, e o padrão que as trouxe.

    O agrupamento é pelo PADRÃO, não pela armadilha: `painel/registros/*` tem
    mais de uma lição, e quem está escrevendo um registro merece receber todas
    de uma vez, não uma interrupção para cada.
    """
    arquivo = raiz / "armadilhas" / NOME_DO_ARQUIVO
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    por_padrao: dict[str, list[dict]] = {}
    for item in dados.get("gatilhos") or []:
        padrao = str(item.get("caminho") or "")
        if padrao and fnmatch.fnmatch(relativo, padrao):
            por_padrao.setdefault(padrao, []).append(item)
    if not por_padrao:
        return "", []
    # Mais específico primeiro: o padrão mais longo é o que fala do gesto exato.
    padrao = max(por_padrao, key=len)
    return padrao, por_padrao[padrao]


def ja_ensinado(raiz_git: Path | None, sessao: str, padrao: str) -> bool:
    """Esta sessão já recebeu a lição deste caminho?

    O caderninho da telemetria é a memória: ele já existe, já é por sessão, e já
    é comum ao clone e a todos os worktrees. Guardar isto num arquivo próprio
    seria uma segunda verdade sobre o mesmo fato.
    """
    if raiz_git is None:
        return False
    for linha in telemetria.ler_tudo(raiz_git):
        if (
            linha.get("evento") == EVENTO
            and linha.get("sessao") == sessao
            and linha.get("caminho") == padrao
        ):
            return True
    return False


def montar_recusa(padrao: str, licoes: list[dict]) -> str:
    linhas = [
        "📖 LIÇÃO DO CAMINHO — leia antes de gravar (uma vez por sessão).",
        "",
        f"Você está prestes a escrever em `{padrao}`, e isto já custou caro aqui:",
        "",
    ]
    for item in licoes[:TETO_DE_LICOES]:
        linhas.append(f"  • {item.get('licao', '').strip()}")
        linhas.append(f"    ({item.get('arquivo')})")
    if len(licoes) > TETO_DE_LICOES:
        linhas.append(f"  … e mais {len(licoes) - TETO_DE_LICOES} no índice.")
    linhas += [
        "",
        "Não há nada errado com a sua escrita: este aviso é sobre o CAMINHO, e",
        "chega agora porque depois de tudo pronto ele custaria uma rodada de CI.",
        "Confira a lição acima, ajuste se precisar, e GRAVE DE NOVO — este",
        "caminho não vai mais interromper você nesta sessão.",
    ]
    return "\n".join(linhas)


def decidir(entrada: dict) -> int:
    alvo = caminho_do_alvo(entrada)
    if alvo is None:
        return 0
    checkout = raiz_do_checkout(alvo)
    if checkout is None:
        return 0
    raiz = checkout[0]
    relativo = alvo.relative_to(raiz).as_posix()

    padrao, licoes = licoes_do_caminho(raiz, relativo)
    if not licoes:
        return 0

    sessao = str(entrada.get("session_id") or "")[:64]
    raiz_git = telemetria.dir_git_comum(alvo.parent)
    if ja_ensinado(raiz_git, sessao, padrao):
        return 0

    # Registrar ANTES de recusar: se a escrita for repetida, o segundo passe
    # precisa encontrar a marca. Sem caderninho não há como não repetir, e um
    # aviso que repete a cada gravação é ruído — então aí ele cala.
    if telemetria.registrar(
        EVENTO,
        {"caminho": padrao, "armadilhas": [i.get("armadilha") for i in licoes]},
        cwd=str(alvo.parent),
        sessao=sessao,
    ) is None:
        return 0

    print(montar_recusa(padrao, licoes), file=sys.stderr)
    return 2


def main() -> int:
    _utf8_na_saida()
    try:
        return decidir(json.load(sys.stdin))
    except Exception:
        return 0  # fail-open: ensinar é conselho, e conselho nunca trava a casa


if __name__ == "__main__":
    raise SystemExit(main())
