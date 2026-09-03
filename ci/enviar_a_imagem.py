#!/usr/bin/env python3
"""O ENVIO DA IMAGEM, com repetição — a vacina do engasgo do registro.

Nasce em 02/09/2026, no deploy do PR #897. A imagem foi construída inteira e
nomeada, e o `docker push` morreu no meio do upload com uma linha só:

    unknown blob

Repetido com `gh run rerun --failed`, sem trocar uma vírgula de código, passou
em 2min38s. Foi a primeira vez que esse engasgo apareceu no projeto — não há
precedente em `armadilhas/` nem no livro. O mantenedor escolheu, sabendo do
risco, que o robô passasse a repetir sozinho (registro `20260903-002`).

POR QUE ISTO É UM MÓDULO, E NÃO TRÊS LINHAS DE BASH NO WORKFLOW
---------------------------------------------------------------
Porque repetição automática é a ferramenta que mais facilmente vira arma nesta
casa, e a `armadilhas/209` é o registro do dia em que ela virou: uma vacina de
retry declarou "falha PERMANENTE" sobre uma VPS viva, e o deploy DESISTIU de
uma entrega que teria subido na tentativa seguinte. O falso-vermelho
categórico. Lógica que decide isso precisa de teste, e bash no meio de um YAML
não tem como ser testado.

A RÉGUA, HERDADA INTEIRA DA 209: resposta definitiva ≠ silêncio
----------------------------------------------------------------
A 209 caiu porque juntou duas coisas num `except` só: "a conexão foi RECUSADA"
(o pacote chegou a algum lugar e voltou um "não" — isso é um FATO) e "o tempo
ESTOUROU" (silêncio, que é a assinatura literal do soluço). Aqui a mesma
fronteira organiza tudo:

  · O registro RESPONDEU "não" (`denied`, `unauthorized`, `manifest unknown`) —
    isso é diagnóstico, e repetir é gastar tentativa numa falha que nenhuma
    repetição conserta. **Para na primeira**, com a mensagem do registro à
    vista.
  · O registro ficou em SILÊNCIO ou tossiu (`unknown blob`, 5xx, `EOF`,
    `i/o timeout`, conexão resetada) — isso é dúvida, não diagnóstico.
    **Repete**, até três vezes.
  · A mensagem não casa com NADA que este arquivo conhece — também **repete**,
    e o log diz, com todas as letras, que a assinatura não foi reconhecida.

Essa última linha é a 209 sendo obedecida ao pé da letra. O caminho tentador
seria "não conheço ⇒ é permanente, desiste", e ele é exatamente o erro que ela
guarda: transformar ignorância em veredito. Repetir sem reconhecer custa cerca
de um minuto e termina vermelho do mesmo jeito; DESISTIR sem reconhecer perde
uma entrega que ia subir. Os dois erros não têm o mesmo preço, e a escolha
segue o mais barato.

REPETIR AQUI É SEGURO, e a razão é a mesma do retry da VPS logo abaixo dele no
workflow: `docker push` das MESMAS tags é idempotente. Camada que já subiu
volta como `Layer already exists`. No dia em que deixar de ser, este arquivo
vira uma arma e precisa sair.

O QUE ELE NÃO FAZ, DE PROPÓSITO
--------------------------------
Não constrói a imagem. O `docker build` continua no workflow, sozinho, porque
build que falha é defeito do código e **não deve ser repetido nunca** — repetir
um build quebrado é a definição de esconder o vermelho. Este módulo só toca o
transporte da imagem pronta, que é a única parte cujo erro é de rede.

E não engole o vermelho: esgotadas as tentativas, o exit é 1 e o log mostra
CADA tentativa. As tentativas ficam dentro do MESMO run de propósito — quando o
rerun manual passa, o GitHub sobrescreve a conclusão anterior e o histórico
apaga a evidência do próprio padrão (medido em 28/08/2026, e é por isso que o
retry da VPS também mora dentro do run).

    python3 ci/enviar_a_imagem.py ghcr.io/x/y:sha ghcr.io/x/y:main
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

#: Quantas vezes tentar CADA tag. Três é o mesmo teto do retry da VPS, e pelo
#: mesmo motivo: é onde a chance de um soluço acabar já foi colhida e o que
#: sobra é tempo gasto para chegar ao mesmo vermelho.
TENTATIVAS = 3

#: A pausa entre tentativas, em segundos. Cresce, porque engasgo de registro
#: costuma ser de alguns segundos e a segunda pausa é a que vale.
PAUSAS = (10, 30)

#: O registro RESPONDEU "não". Isto é diagnóstico, não dúvida: nenhuma
#: repetição conserta credencial errada, permissão faltando ou tag inexistente.
#: Parar na primeira aqui não é desistir cedo — é não fingir que uma resposta
#: clara é um soluço. (A 209 caiu pelo erro simétrico: tratar silêncio como
#: resposta clara.)
RESPOSTAS_DEFINITIVAS = (
    "denied",
    "unauthorized",
    "authentication required",
    "manifest unknown",
    "name unknown",
    "no space left on device",
    "invalid reference format",
)

#: Silêncio, ou o registro tossindo. `unknown blob` é o caso que originou este
#: arquivo: o upload de uma camada morre no meio e o registro perde o rastro
#: dela. Os 5xx e os timeouts são a mesma família — a resposta que não é uma
#: resposta.
ENGASGOS_CONHECIDOS = (
    "unknown blob",
    "blob upload unknown",
    "blob upload invalid",
    "i/o timeout",
    "tls handshake timeout",
    "connection reset by peer",
    "connection refused",
    "unexpected eof",
    "eof",
    "500 internal server error",
    "502 bad gateway",
    "503 service unavailable",
    "504 gateway",
    "received unexpected http status: 5",
    "temporarily unavailable",
    "too many requests",
)

# Os três veredictos sobre uma saída de erro. Nomeados porque o teste os
# compara — e porque um booleano juntaria "sei que repetir não adianta" com
# "não sei o que é isto", que é a fusão exata que a 209 proíbe.
DEFINITIVO = "definitivo"
ENGASGO = "engasgo"
DESCONHECIDO = "desconhecido"


def classificar(saida: str) -> str:
    """O que o registro disse: uma resposta, um engasgo, ou algo novo.

    A ORDEM importa e é a metade da regra. Uma saída de `docker push` costuma
    trazer várias linhas, e um `denied` no meio de ruído de rede continua sendo
    um `denied`: se as duas famílias casarem, a resposta definitiva vence. O
    contrário faria uma credencial errada ser repetida três vezes e sair com
    cara de problema de rede — trocando um diagnóstico certo por um palpite.
    """
    baixa = (saida or "").lower()
    if any(marca in baixa for marca in RESPOSTAS_DEFINITIVAS):
        return DEFINITIVO
    if any(marca in baixa for marca in ENGASGOS_CONHECIDOS):
        return ENGASGO
    return DESCONHECIDO


def _empurrar(tag: str) -> tuple[int, str]:
    """Uma tentativa. Devolve (código, saída juntada) — nunca levanta.

    `stderr` entra em `stdout` de propósito: o `docker push` escreve o motivo
    da falha nos dois, e classificar por metade da evidência é como se erra
    aqui.
    """
    processo = subprocess.run(
        ["docker", "push", tag],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return processo.returncode, processo.stdout or ""


def enviar(tag: str, *, empurrar=_empurrar, dormir=time.sleep) -> bool:
    """Manda a tag, repetindo o que vale a pena repetir. `True` = subiu.

    `empurrar` e `dormir` entram por parâmetro para o teste poder medir a
    decisão sem docker e sem esperar 40 segundos de pausa. Não é enfeite de
    testabilidade: esta função decide se uma entrega vai ao ar, e a única
    forma de provar que ela para na hora certa é conseguir mentir para ela.
    """
    for tentativa in range(1, TENTATIVAS + 1):
        print(f"→ enviando {tag} (tentativa {tentativa} de {TENTATIVAS})", flush=True)
        codigo, saida = empurrar(tag)
        if codigo == 0:
            if tentativa > 1:
                print(
                    f"✅ {tag} subiu na tentativa {tentativa}. As anteriores "
                    f"falharam por engasgo do registro, e ficam no log acima — "
                    f"o run fecha verde SEM apagar que isto aconteceu.",
                    flush=True,
                )
            return True

        print(saida.rstrip(), flush=True)
        veredito = classificar(saida)

        if veredito == DEFINITIVO:
            print(
                f"🧱 PAROU POR SEGURANÇA: o registro RESPONDEU um 'não' sobre "
                f"{tag}, e isso não é engasgo de rede — é diagnóstico. "
                f"Repetir gastaria tentativa numa falha que nenhuma repetição "
                f"conserta. A mensagem do registro está logo acima.",
                flush=True,
            )
            return False

        if tentativa == TENTATIVAS:
            print(
                f"🧱 {tag} falhou nas {TENTATIVAS} tentativas. O deploy fica "
                f"VERMELHO, que é o certo: a imagem nova não está no registro, "
                f"e o site segue servindo a anterior.",
                flush=True,
            )
            return False

        if veredito == DESCONHECIDO:
            # A 209 em uma frase: não saber NUNCA vira veredito. Repetimos, e
            # dizemos que estamos repetindo às cegas — para que a próxima
            # pessoa que ler este log possa acrescentar a assinatura à lista
            # em vez de descobrir tudo de novo.
            print(
                "⚠ assinatura NÃO reconhecida por ci/enviar_a_imagem.py. Vou "
                "repetir mesmo assim, porque desistir do que eu não reconheço "
                "seria transformar ignorância em veredito (armadilhas/209). Se "
                "esta falha se repetir, acrescente a linha dela a "
                "ENGASGOS_CONHECIDOS ou a RESPOSTAS_DEFINITIVAS.",
                flush=True,
            )

        pausa = PAUSAS[min(tentativa - 1, len(PAUSAS) - 1)]
        print(f"… esperando {pausa}s antes da próxima tentativa", flush=True)
        dormir(pausa)

    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Envia tags de imagem ao registro, repetindo engasgo de rede."
    )
    parser.add_argument("tags", nargs="+", help="as tags completas a enviar")
    args = parser.parse_args(argv)

    for tag in args.tags:
        if not enviar(tag):
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
