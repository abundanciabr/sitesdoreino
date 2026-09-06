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

O SEGUNDO OLHO: O NÚMERO DO REGISTRO (06/09/2026, em SOMBRA)
------------------------------------------------------------
Ensinar não bastou. Depois de este gancho e o guarda de commit pousarem, o dia
06/09/2026 ainda teve QUATRO colisões de número no livro (031, 032, 052 e 055):
o robô lê a lição, concorda com ela, e mesmo assim escolhe o número olhando a
pasta — porque olhar a pasta funciona nas nove vezes em que ninguém mais está
escrevendo. Cada colisão reprova os três checks do PR e custa uma rodada
inteira de diagnóstico.

Então a lição ganhou um olho que CONFERE em vez de só avisar: quando o arquivo
gravado é `painel/registros/AAAAMMDD-NNN-*.js`, ele pergunta ao caderninho se
aquele `NNN` tem recibo de alocação desta bancada (o recibo que
`ci/reservar.py` passou a deixar em toda alocação). Sem recibo, o número foi
escolhido, não pedido.

Ele nasce em SOMBRA, pela lei da autoridade proporcional à certeza do Sistema
Imunológico: NÃO recusa nada, imprime o que TERIA recusado e grava o disparo na
mesma telemetria da muralha em sombra (`ci/termometro.py` conta e diz quando
promover). O motivo de não bloquear já no primeiro dia é medido, não tímido: um
falso positivo aqui travaria a escrituração obrigatória de toda sessão, e o
recibo depende de um caderninho que pode não existir (bancada recém-nascida,
almoxarife rodado de outra pasta, número legitimamente herdado de um rebase).
Sombra mede antes de tijolar.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import telemetria  # noqa: E402  (irmão de pasta; o insert acima é o que o permite)
from muralha_pasta_compartilhada import raiz_do_checkout  # noqa: E402

NOME_DO_ARQUIVO = "GATILHOS.json"
EVENTO = "licao_entregue"
TETO_DE_LICOES = 4  # o mesmo caminho pode ter várias; a tela tem limite

# O olho do número do registro. O recibo é escrito por `ci/reservar.py`; o
# disparo em sombra usa o evento e os campos da `ci/muralha_das_armadilhas.py`,
# que é o que faz o `ci/termometro.py` contar os dois na mesma tabela.
PASTA_DOS_REGISTROS = "painel/registros"
NOME_DE_REGISTRO = re.compile(r"^(?P<dia>\d{8})-(?P<numero>\d{3})-.+\.js$")
EVENTO_DO_RECIBO = "numero_reservado"
EVENTO_DA_SOMBRA = "regra_disparou"
ARMADILHA_DO_NUMERO = "179"


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


def ja_dito(caderninho: list[dict], evento: str, sessao: str, caminho: str) -> bool:
    """Esta sessão já ouviu isto sobre este caminho?

    O caderninho da telemetria é a memória: ele já existe, já é por sessão, e já
    é comum ao clone e a todos os worktrees. Guardar isto num arquivo próprio
    seria uma segunda verdade sobre o mesmo fato.
    """
    return any(
        linha.get("evento") == evento
        and linha.get("sessao") == sessao
        and linha.get("caminho") == caminho
        for linha in caderninho
    )


def registro_sem_reserva(
    caderninho: list[dict], raiz: Path, relativo: str
) -> str | None:
    """`AAAAMMDD-NNN` do registro sendo gravado sem recibo do almoxarife.

    `None` quer dizer "nada a dizer", e engloba os três casos em que calar é o
    certo: não é um registro do livro; o número tem recibo desta bancada; ou o
    caderninho não tem recibo NENHUM.

    O terceiro é o fail-open, e o limite dele está dito na cara: numa casa
    recém-clonada (ou enquanto uma bancada antiga ainda roda o almoxarife sem
    recibo) este olho não sabe nada sobre alocação, e acusar sem saber seria
    chute com cara de medição. Basta UM recibo na casa para ele voltar a julgar,
    e o caderninho mora no `.git` comum: ele acumula e nunca é limpo.
    """
    pasta, _, arquivo = relativo.rpartition("/")
    if pasta != PASTA_DOS_REGISTROS:
        return None
    nome = NOME_DE_REGISTRO.match(arquivo)
    if nome is None:
        return None  # não é um registro do livro (o molde, um rascunho, o LEIA-ME)
    aqui = os.path.normcase(str(raiz))
    algum_recibo = False
    for linha in caderninho:
        if linha.get("evento") != EVENTO_DO_RECIBO:
            continue
        algum_recibo = True
        if (
            linha.get("superficie") == "registro"
            and linha.get("dia") == nome["dia"]
            and linha.get("numero") == nome["numero"]
            and linha.get("bancada") == aqui
        ):
            return None
    if not algum_recibo:
        return None
    return f"{nome['dia']}-{nome['numero']}"


def montar_sombra(chave: str) -> str:
    return (
        f"👁️ SOMBRA (armadilhas/{ARMADILHA_DO_NUMERO}): o registro {chave} não tem "
        "reserva desta sessão no almoxarife.\n"
        "   Esta regra ainda NÃO impede nada. Se impedisse, este Write seria "
        "recusado agora.\n"
        "   O número se PEDE: `python ci/reservar.py numero registro` devolve o "
        "próximo livre, alocado no servidor.\n"
        "   Se o número já veio de lá (ou de um rebase), siga: isto é uma "
        "medição, não um veredito."
    )


def falar_em_sombra(
    caderninho: list[dict], raiz: Path, relativo: str, sessao: str, ferramenta: str
) -> None:
    """Diz o que TERIA sido recusado, e mede. Nunca muda o exit de ninguém."""
    chave = registro_sem_reserva(caderninho, raiz, relativo)
    if chave is None:
        return
    if ja_dito(caderninho, EVENTO_DA_SOMBRA, sessao, relativo):
        return  # o mesmo arquivo reescrito é o mesmo fato: medir duas vezes é ruído
    telemetria.registrar(
        EVENTO_DA_SOMBRA,
        {
            "armadilha": ARMADILHA_DO_NUMERO,
            "detector": "registro_sem_reserva",
            "modo": "sombra",
            "ferramenta": ferramenta,
            "caminho": relativo,
        },
        cwd=str(raiz),
        sessao=sessao,
    )
    print(montar_sombra(chave), file=sys.stderr)


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
    sessao = str(entrada.get("session_id") or "")[:64]
    raiz_git = telemetria.dir_git_comum(alvo.parent)
    caderninho = telemetria.ler_tudo(raiz_git) if raiz_git is not None else []

    # A sombra fala primeiro e falha sozinha: ela é um segundo olho pendurado
    # aqui, e um defeito dela não pode engolir a lição que já funcionava.
    try:
        ferramenta = str(entrada.get("tool_name") or "")
        falar_em_sombra(caderninho, raiz, relativo, sessao, ferramenta)
    except Exception:
        pass  # fail-open: medir é conselho, e conselho nunca trava a casa

    padrao, licoes = licoes_do_caminho(raiz, relativo)
    if not licoes:
        return 0

    if ja_dito(caderninho, EVENTO, sessao, padrao):
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
