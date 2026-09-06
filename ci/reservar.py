"""O ALMOXARIFE — o servidor DÁ o número; o robô para de adivinhar.

    python ci/reservar.py numero registro      # aloca e imprime: 040
    python ci/reservar.py numero armadilha     # aloca e imprime: 154
    python ci/reservar.py numero tarefa        # aloca e imprime: 003 (fila/)
    python ci/reservar.py intencao <chave> --objetivo "..."
    python ci/reservar.py listar
    python ci/reservar.py soltar <chave>

Onda 2 do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`. Ataca a **Classe 3
(corrida por número livre)** por classe, e barateia a **Classe 5 (trabalho
duplicado invisível)**.

**O problema, medido:** "crie o arquivo com o próximo número livre" resolve o
conflito de texto e cria outro — duas sessões que listam a pasta no mesmo minuto
veem o MESMO livre, e o Git junta os dois sem ter nada para detectar (nomes
diferentes). Em 26/08/2026 foram QUATRO colisões num dia entre três sessões
(`armadilhas/085`); em 28/08/2026, cinco numa única sessão. Cada superfície nova
vinha reinventando o próprio validador — cura de caso, nunca de classe.

**A cura: alocação atômica, arbitrada pelo servidor.** Criar uma referência que
ainda não existe é uma operação de comparar-e-trocar no GitHub — a mesma coisa
que impede dois `git push` simultâneos de corromperem um ramo. Quem chega
primeiro cria; o segundo recebe recusa DO SERVIDOR, na hora, e tenta o próximo.
Sem votação, sem processo rodando, sem plano pago.

---

## A ARMADILHA QUE ESTE ARQUIVO EXISTE PARA NÃO CAIR

Medido contra o repositório real em 28/08/2026, antes de uma linha ser escrita:

    git commit-tree <mesma árvore> -p <mesmo pai> -m "<mesma mensagem>"

produz o MESMO SHA em duas sessões. E empurrar um commit que já é o valor da
referência devolve **exit 0, "Everything up-to-date"** — o `--force-with-lease`
**nem chega a ser conferido**, porque o Git vê que não há o que fazer.

Ou seja: duas sessões que montassem um commit idêntico (mesma árvore, mesmo pai,
mesma mensagem, mesmo segundo) **ganhariam as duas** a mesma reserva, cada uma
lendo um exit 0. Seria uma trava que parece funcionar e não funciona — a pior
categoria de falha deste projeto.

**Por isso toda tentativa carrega um `nonce` único.** Com ele os SHAs nunca
coincidem, o Git sempre tem o que fazer, e a trava sempre é conferida. Provado
nas duas direções: com nonce, a segunda tentativa é `! [rejected] (stale info)`,
exit 1; sem nonce, `Everything up-to-date`, exit 0.

Guarda extra, para o caso de alguém tirar o nonce um dia: `Everything
up-to-date` é tratado como ERROR, nunca como vitória.

---

Exit codes: 0 alocado/reservado · 1 recusado (já é de outro) · 2 ERROR.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

CI = Path(__file__).resolve().parent
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import telemetria  # noqa: E402  (irmão de pasta; o insert acima é o que o permite)
from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    executar,
    raiz_do_repo,
)

# Onde cada coisa mora no servidor. Namespaces separados de propósito: número é
# permanente (nunca se solta), intenção é temporária (vence e pode ser roubada).
NS_NUMERO = "refs/numeros"
NS_RESERVA = "refs/reservas"

HORAS_DE_RESERVA = 3
TENTATIVAS = 25

# As marcas que o Git usa para dizer "essa referência já é de outro". Distinguir
# isto de "não consegui falar com o servidor" é obrigatório: tratar rede caída
# como "ocupado" faria o laço consumir números que ninguém pegou.
MARCAS_DE_RECUSA = ("[rejected]", "stale info", "already exists", "fetch first")

# O RECIBO DA ALOCAÇÃO — a prova local de que este número veio daqui.
#
# A reserva de verdade mora no servidor, e conferir lá custa uma ida à rede. O
# gancho da lição do caminho (`ci/licao_do_caminho.py`) precisa saber, no
# instante em que um registro vai ser gravado, se aquele número foi pedido ou
# escolhido — e um gancho que bate na rede a cada Write é um gancho que alguém
# desliga. Por isso toda alocação deixa um recibo no caderninho da telemetria:
# ele já mora dentro do `.git` comum (não vai ao GitHub, é visível a todos os
# worktrees da casa) e já é a memória local desta casa. Guardar isto num arquivo
# próprio seria uma segunda verdade sobre o mesmo fato.
#
# A BANCADA é a identidade prática de quem alocou. O almoxarife roda como
# subprocesso e não recebe o `session_id` do harness (só os ganchos recebem),
# então "esta sessão" se prova pelo checkout de onde o número foi pedido — e
# esta casa dá uma bancada por despacho (RITOS §1, muralha da pasta).
EVENTO_DO_RECIBO = "numero_reservado"


def bancada(raiz: Path) -> str:
    """O checkout, num formato que os dois lados comparam sem discordar."""
    return os.path.normcase(str(Path(raiz).resolve()))


def _git(raiz: Path, args: list[str]) -> subprocess.CompletedProcess:
    """Roda git SEM pipe e devolve o resultado cru — o exit é do git, não de um `tail`.

    A regra da casa, paga com falso-verde real: veredito nunca sai do exit de um
    comando com `| tail`/`| head` pendurado (§5.10). Aqui não há cano nenhum.
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(raiz),
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as erro:
        raise ErroDeInstrumentacao(
            "git não encontrado no PATH",
            "Sem git não há como reservar nada — e não reservar não é reservar.",
        ) from erro
    except subprocess.TimeoutExpired as erro:
        raise ErroDeInstrumentacao(
            "o git travou ao falar com o servidor",
            f"comando: git {' '.join(args)}",
        ) from erro


def criar_ref_atomica(raiz: Path, ref: str, corpo: dict) -> bool:
    """Tenta criar `ref` no servidor. True = ganhou, False = já era de outro.

    Levanta `ErroDeInstrumentacao` quando não deu para saber — que é diferente
    de perder, e precisa ser diferente no código também.
    """
    corpo = dict(corpo)
    # O nonce é o que torna o commit único e faz o lease ser conferido de
    # verdade. Ver a seção "A ARMADILHA" no topo: sem ele, dois vencedores.
    corpo["nonce"] = uuid.uuid4().hex
    mensagem = json.dumps(corpo, ensure_ascii=False, sort_keys=True)

    arvore = executar(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=raiz,
        descricao="obter a árvore atual para o commit da reserva",
        exigir_stdout=True,
    ).stdout.strip()
    pai = executar(
        ["git", "rev-parse", "HEAD"],
        cwd=raiz,
        descricao="obter o commit atual para o commit da reserva",
        exigir_stdout=True,
    ).stdout.strip()
    commit = executar(
        ["git", "commit-tree", arvore, "-p", pai, "-m", mensagem],
        cwd=raiz,
        descricao="montar o commit da reserva",
        exigir_stdout=True,
    ).stdout.strip()

    resultado = _git(
        raiz,
        ["push", f"--force-with-lease={ref}:", "origin", f"{commit}:{ref}"],
    )
    saida = f"{resultado.stdout}\n{resultado.stderr}"

    if resultado.returncode == 0:
        if "Everything up-to-date" in saida:
            # Impossível com nonce. Se acontecer, alguém tirou o nonce — e o
            # lease não foi conferido. Vitória não conferida não é vitória.
            raise ErroDeInstrumentacao(
                "o servidor disse 'Everything up-to-date' numa reserva NOVA",
                "Isso só acontece quando o commit já é o valor da referência, e\n"
                "nesse caminho o --force-with-lease NÃO é conferido: dois robôs\n"
                "sairiam daqui achando que ganharam. Quase certamente o `nonce`\n"
                "foi removido de `criar_ref_atomica`. Não trate como sucesso.",
            )
        return True

    if any(marca in saida for marca in MARCAS_DE_RECUSA):
        return False

    raise ErroDeInstrumentacao(
        f"não consegui saber se a reserva {ref} foi criada",
        f"exit {resultado.returncode}\n{saida.strip()[:600]}\n\n"
        "Isto NÃO é 'então está ocupado': é não saber. Tratar rede caída como\n"
        "'ocupado' queimaria números que ninguém pegou.",
    )


def refs_existentes(raiz: Path, prefixo: str) -> list[str]:
    """As referências que já existem sob `prefixo`, lidas do SERVIDOR.

    `ls-remote` e não `for-each-ref`: o que importa é o que o servidor tem, não
    o que este clone baixou por último. Ler local aqui seria a Classe 8 outra
    vez, dentro da cura da Classe 3.
    """
    saida = executar(
        ["git", "ls-remote", "origin", f"{prefixo}/*"],
        cwd=raiz,
        descricao=f"listar as reservas em {prefixo}",
    ).stdout
    return [
        linha.split("\t", 1)[1].strip() for linha in saida.splitlines() if "\t" in linha
    ]


def numeros_em_uso(raiz: Path, superficie: str, chave_do_dia: str) -> set[int]:
    """Números já gastos: os dos ARQUIVOS e os das RESERVAS ainda não commitadas.

    Contar só os arquivos devolveria um número que outra sessão já reservou mas
    ainda não commitou — que é exatamente a janela que abriu as colisões.
    """
    usados: set[int] = set()

    if superficie == "registro":
        pasta, padrao, corte = (
            (raiz / "painel" / "registros"),
            f"{chave_do_dia}-*.js",
            len(chave_do_dia) + 1,
        )
    elif superficie == "tarefa":
        # A fila de trabalho (fila/tarefas/NNN-slug.json). A pasta pode ainda
        # não existir no dia em que a fila nasce — aí os números em uso são só
        # os das reservas no servidor, e isso é correto, não é falha.
        pasta, padrao, corte = (raiz / "fila" / "tarefas"), "*.json", 0
        if not pasta.is_dir():
            prefixo = f"{NS_NUMERO}/{superficie}"
            for ref in refs_existentes(raiz, prefixo):
                cauda = ref.rsplit("/", 1)[-1]
                if cauda.isdigit():
                    usados.add(int(cauda))
            return usados
    else:
        pasta, padrao, corte = (raiz / "armadilhas"), "*.md", 0
    if not pasta.is_dir():
        raise ErroDeInstrumentacao(
            f"não encontrei {pasta}",
            "Sem a pasta não dá para saber quais números já existem.",
        )
    for arquivo in pasta.glob(padrao):
        if arquivo.name == "INDICE.md":
            continue
        numero = arquivo.name[corte:].split("-")[0]
        if numero.isdigit():
            usados.add(int(numero))

    prefixo = (
        f"{NS_NUMERO}/{superficie}/{chave_do_dia}"
        if superficie == "registro"
        else f"{NS_NUMERO}/{superficie}"
    )
    for ref in refs_existentes(raiz, prefixo):
        cauda = ref.rsplit("/", 1)[-1]
        if cauda.isdigit():
            usados.add(int(cauda))
    return usados


def alocar_numero(raiz: Path, superficie: str, agora: datetime | None = None) -> str:
    """Ganha um número no servidor e devolve ele. Nunca devolve um palpite."""
    if superficie not in ("registro", "armadilha", "tarefa"):
        raise ErroDeInstrumentacao(
            f"superfície desconhecida: {superficie!r}",
            "Use 'registro', 'armadilha' ou 'tarefa'. Chutar a política de\n"
            "numeração daria uma dica errada com cara de certa (ver ci/boletim.py).",
        )
    agora = agora or datetime.now(timezone.utc)
    chave_do_dia = agora.strftime("%Y%m%d")
    usados = numeros_em_uso(raiz, superficie, chave_do_dia)

    if superficie in ("armadilha", "tarefa"):
        # Números vagos no meio estão APOSENTADOS e ainda são citados
        # (`armadilhas/085`): nunca se reusa, sempre acima de todos. A tarefa
        # segue a mesma política: TAR-007 concluída continua citada em eventos
        # e registros para sempre — reusar o número contaria outra história.
        candidato = (max(usados) + 1) if usados else 1
        passo = lambda n: n + 1  # noqa: E731
    else:
        candidato = 1
        while candidato in usados:
            candidato += 1
        passo = lambda n: n + 1  # noqa: E731

    base = f"{NS_NUMERO}/{superficie}"
    if superficie == "registro":
        base = f"{base}/{chave_do_dia}"

    for _ in range(TENTATIVAS):
        numero = str(candidato).zfill(3)
        if criar_ref_atomica(
            raiz,
            f"{base}/{numero}",
            {
                "tipo": "numero",
                "superficie": superficie,
                "numero": numero,
                "criado_em": agora.isoformat(),
            },
        ):
            # Fail-open de propósito: `registrar` engole a própria falha, e um
            # recibo perdido só faz o gancho falar em sombra sem motivo. Perder
            # o NÚMERO por causa do caderninho é que seria inaceitável.
            telemetria.registrar(
                EVENTO_DO_RECIBO,
                {
                    "superficie": superficie,
                    "numero": numero,
                    "dia": chave_do_dia,
                    "bancada": bancada(raiz),
                },
                cwd=str(raiz),
            )
            return numero
        # Perdeu a corrida: outra sessão levou. Segue para o próximo.
        candidato = passo(candidato)
        while candidato in usados:
            candidato = passo(candidato)

    raise ErroDeInstrumentacao(
        f"{TENTATIVAS} tentativas seguidas de alocar número foram recusadas",
        "Ou há um lote enorme rodando agora, ou alguma reserva antiga ficou\n"
        "presa. Rode `python ci/reservar.py listar` para ver o que existe.",
    )


def reservar_intencao(
    raiz: Path,
    chave: str,
    objetivo: str,
    horas: int = HORAS_DE_RESERVA,
    agora: datetime | None = None,
) -> tuple[bool, str]:
    """Anuncia "estou fazendo isto" para as outras sessões. (ganhou?, recado)

    Não é trava de área — é anúncio de INTENÇÃO, que é o que ataca a Classe 5
    (duas sessões construindo a mesma coisa sem saber). O prazo mora dentro da
    reserva de propósito: sessão de IA morre no meio, e trava que sobrevive ao
    processo que a criou exige um vigia — que este projeto não pode ter.
    """
    agora = agora or datetime.now(timezone.utc)
    ref = f"{NS_RESERVA}/{chave}"
    ganhou = criar_ref_atomica(
        raiz,
        ref,
        {
            "tipo": "intencao",
            "chave": chave,
            "objetivo": objetivo,
            "criado_em": agora.isoformat(),
            "expira_em": (agora + timedelta(hours=horas)).isoformat(),
        },
    )
    if ganhou:
        return True, f"reserva '{chave}' é sua até {horas}h a partir de agora."
    return False, (
        f"'{chave}' JÁ ESTÁ RESERVADA por outra sessão.\n"
        "Isto não é erro: é o mecanismo funcionando. Fale com quem despachou, ou\n"
        "escolha outra frente. Para ver quem tem o quê: python ci/reservar.py listar"
    )


def listar(raiz: Path) -> list[str]:
    return sorted(refs_existentes(raiz, NS_RESERVA) + refs_existentes(raiz, NS_NUMERO))


def soltar(raiz: Path, chave: str) -> None:
    resultado = _git(raiz, ["push", "origin", f":{NS_RESERVA}/{chave}"])
    if resultado.returncode != 0:
        raise ErroDeInstrumentacao(
            f"não consegui soltar a reserva '{chave}'",
            f"{resultado.stdout}\n{resultado.stderr}".strip()[:600],
        )


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="O almoxarife: o servidor dá o número, o robô não adivinha."
    )
    sub = parser.add_subparsers(dest="acao", required=True)

    p_num = sub.add_parser("numero", help="aloca o próximo número de uma superfície")
    p_num.add_argument("superficie", choices=["registro", "armadilha", "tarefa"])

    p_int = sub.add_parser("intencao", help="anuncia que você vai fazer algo")
    p_int.add_argument("chave", help="slug curto e estável, ex.: onda2-reservar")
    p_int.add_argument("--objetivo", default="", help="uma frase")
    p_int.add_argument("--horas", type=int, default=HORAS_DE_RESERVA)

    sub.add_parser("listar", help="o que está reservado agora, no servidor")

    p_sol = sub.add_parser("soltar", help="libera uma reserva de intenção")
    p_sol.add_argument("chave")
    return parser


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    args = construir_parser().parse_args(argv)
    try:
        raiz = raiz_do_repo()
        if args.acao == "numero":
            print(alocar_numero(raiz, args.superficie))
            return 0
        if args.acao == "intencao":
            ganhou, recado = reservar_intencao(
                raiz, args.chave, args.objetivo, args.horas
            )
            print(recado)
            return 0 if ganhou else 1
        if args.acao == "listar":
            refs = listar(raiz)
            print("\n".join(refs) if refs else "nada reservado agora.")
            return 0
        soltar(raiz, args.chave)
        print(f"reserva '{args.chave}' solta.")
        return 0
    except ErroDeInstrumentacao as erro:
        print(f"\nPAROU POR SEGURANÇA: {erro.resumo}\n")
        if erro.detalhe:
            print(erro.detalhe)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
