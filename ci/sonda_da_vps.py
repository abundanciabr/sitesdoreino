#!/usr/bin/env python3
"""A SONDA DA VPS — a medição que faltava DENTRO do deploy (armadilhas/127).

A `armadilhas/127` é a campeã de reincidência deste catálogo: 6 quedas em 3
dias. O deploy morre em `dial tcp ***:22: i/o timeout`, a VPS está viva, o site
responde 200 o tempo inteiro — é um soluço de rede entre o runner do GitHub e a
VPS. A entrada manda fazer três coisas, nesta ordem: **medir a porta 22**,
**repetir com pausa**, **parar na terceira**.

O QUE JÁ EXISTIA, E O QUE FALTAVA (TAR-013, 30/08/2026)
------------------------------------------------------
Duas das três já estavam no `deploy-celula.yml` desde 26/08/2026: três
tentativas, com 45 s e 60 s de pausa, e só a última decide o veredito. A
terceira — **medir** — não existia em lugar nenhum do deploy. Ela morava em dois
lugares fora dele: no texto da armadilha (um comando para o agente colar) e em
`ci/rerun_de_deploy.py`, que é a vacina do PC, rodada DEPOIS do fato, por um
robô que já percebeu o vermelho.

Sem a medição, o retry do deploy repete às cegas: ele trata TODO timeout de SSH
como o soluço da 127, inclusive quando é a `armadilhas/017` — a falha
PERMANENTE de configuração, em que nenhuma tentativa vai passar nunca. Gasta 105
segundos de pausa e três conexões para chegar a "a suspeita é a 017", que é um
palpite. Este módulo troca o palpite por uma medição, feita no lugar certo: **do
runner**, que é exatamente a ponta da conexão que engasga.

AS DUAS CARAS DESTE ARQUIVO
---------------------------
    python ci/sonda_da_vps.py --sondar-porta   # mede e decide (VPS_HOST no env)
    python ci/sonda_da_vps.py --resumir        # narra o que o deploy fez

A primeira roda no `deploy-celula.yml` entre as tentativas. A segunda roda no
fim do job e escreve, no resumo do run, o que aconteceu — em português de
resultado, não de processo. É o "registrando o que fez" da vacina: até aqui, um
deploy que se salvou na 2ª tentativa era indistinguível, para quem olha de fora,
de um deploy que passou de primeira, e o padrão da VPS recusando continuava
invisível.

POR QUE O `veredito` SAI POR `$GITHUB_OUTPUT`, E NÃO PELO EXIT CODE
-------------------------------------------------------------------
O workflow precisa distinguir TRÊS respostas — porta viva, porta morta, não
consegui medir — e o `outcome` de um passo do GitHub só tem duas
(`success`/`failure`). Ler a decisão do `outcome` juntaria "a porta está morta"
com "não consegui medir", que é precisamente a confusão que o [INV-CI01] existe
para proibir: **não medir nunca vira veredito**. Por isso o passo é
`continue-on-error: true` (o exit code não derruba o job) e o workflow lê
`steps.<id>.outputs.veredito`, nunca `steps.<id>.outcome`.

O exit code continua valendo para quem roda isto na mão, com a semântica da casa:

    0  PASS   a porta 22 respondeu — é o soluço da 127, repetir é o certo
    1  FAIL   a porta 22 NÃO respondeu — é a 017, e repetir é teatro
    2  ERROR  não consegui medir — e "não medi" nunca vira "pode repetir"

O QUE ESTA SONDA NUNCA FAZ
--------------------------
**Ela nunca reprova um deploy que ainda poderia dar certo.** A única direção em
que ela encurta o laço é a provada: quando as DUAS medições (depois da 1ª e
depois da 2ª tentativa) disserem que a porta está morta, o workflow pula a 3ª —
duas medições independentes concordando é evidência; uma é ruído. Porta viva ou
"não medi" mantêm o retry inteiro, exatamente como antes desta entrega. Uma
sonda que pudesse derrubar entrega boa seria uma arma, não uma vacina.

O host vem por `env`, nunca por argumento: `VPS_HOST` é segredo do repositório,
e argumento aparece na tabela de processos e em qualquer eco de comando. Nada
aqui imprime o host — nem no acerto, nem no erro.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _nucleo import configurar_saida  # noqa: E402

# O IP da VPS (`reference_vps_acesso_estado`): serve de padrão para quem roda
# isto na mão, do PC. No runner o valor vem do segredo `VPS_HOST`.
VPS_PADRAO = "217.196.62.220"
BANNER_SSH = "SSH-2.0"
SONDA_DO_SITE = "https://meshcraft.top/healthz"
ESPERA_DO_SOCKET_S = 10

BLIP = "blip"
PERMANENTE = "permanente"
NAO_MEDI = "nao_medi"

# A sentinela que `infra/deploy-celula-na-vps.sh` imprime na última linha e que
# o passo "A entrega rodou mesmo?" EXIGE ver — a cura do verde que não subiu
# nada (28/08/2026). O narrador procura a mesma marca, e não uma variação dela:
# `ci/tests/test_sonda_da_vps.py` reprova se as três cópias divergirem, porque
# duas grafias diferentes fariam o resumo do run contar uma história e o portão
# do workflow contar outra sobre a mesma entrega.
MARCA_DE_CONCLUSAO = "ENTREGA-CONCLUIDA:"


@dataclass
class Medicao:
    """O mundo, medido. Separado da decisão para que a tabela inteira seja
    testável sem rede, sem VPS e sem runner — as três coisas que não se
    produzem sob encomenda."""

    porta22: bool | None = None  # None = NÃO MEDI, sempre
    site_http: int | None = None
    host_declarado: bool = True


@dataclass
class Veredito:
    veredito: str  # BLIP | PERMANENTE | NAO_MEDI
    codigo: int  # 0 PASS · 1 FAIL · 2 ERROR
    motivo: str
    recado: str = ""


def decidir_pela_sonda(medicao: Medicao) -> Veredito:
    """A tabela de decisão da sonda — pura, completa e sem rede.

    Ela responde uma pergunta só, e é a pergunta que a `armadilhas/127` manda
    fazer antes de repetir: *o problema é a rede engasgando (a 127) ou a porta
    fechada (a 017)?* Confundir as duas custa nos dois sentidos — repetir uma
    falha permanente é teatro, e desistir de um soluço é deixar o merge fora do
    ar por nada.
    """
    if not medicao.host_declarado:
        return Veredito(
            NAO_MEDI, 2,
            "não recebi o endereço da VPS (`VPS_HOST` vazio) — sem alvo não há "
            "o que sondar, e 'não medi' nunca vira 'a porta está morta'.",
            "O retry segue inteiro, como se esta sonda não existisse.",
        )
    if medicao.porta22 is None:
        return Veredito(
            NAO_MEDI, 2,
            "não consegui medir a porta 22 da VPS — a sonda em si falhou "
            "(nome que não resolve, socket recusado pelo próprio runner). "
            "Sem a medição não dá para separar a armadilhas/127 da 017, e a "
            "ausência de evidência não é evidência de nada [INV-CI01].",
            "O retry segue inteiro: uma sonda que não mediu não tira tentativa "
            "de ninguém.",
        )
    if medicao.porta22:
        return Veredito(
            BLIP, 0,
            "a porta 22 da VPS RESPONDEU o banner de SSH agora, deste runner. "
            "A VPS está viva e alcançável: o que falhou foi a rede no momento "
            "da tentativa — é o soluço intermitente da armadilhas/127, não a "
            "017. Repetir é exatamente o certo.",
            _recado_do_site(medicao.site_http),
        )
    return Veredito(
        PERMANENTE, 1,
        "a porta 22 da VPS NÃO respondeu deste runner. Isso não é o soluço da "
        "armadilhas/127 — é a assinatura da 017: falha PERMANENTE de alcance "
        "(o que o VPS_HOST resolve? há CDN na frente? o firewall passou a "
        "recusar a faixa dos runners?). Nenhuma tentativa nova vai passar, e o "
        "conserto é de configuração — território do mantenedor (Lei 5).",
        _recado_do_site(medicao.site_http),
    )


def _recado_do_site(codigo: int | None) -> str:
    """A frase que o mantenedor precisa ouvir, e que é fácil esquecer.

    Deploy vermelho por SSH significa que a imagem NOVA não subiu — a ANTIGA
    continua servindo. Ninguém fica fora do ar, mas o merge não está em
    produção até o verde. Anunciar a entrega como "no ar" nesse estado já
    aconteceu nesta casa mais de uma vez (armadilhas/127).
    """
    if codigo == 200:
        return (
            "O site continua no ar servindo a versão ANTERIOR — ninguém ficou "
            "fora do ar. Mas o que foi mergeado NÃO está em produção enquanto "
            "este deploy não ficar verde."
        )
    if codigo is None:
        return (
            "Não consegui medir o site pela internet pública daqui — o que não "
            "significa que ele esteja fora do ar; significa que não medi."
        )
    return (
        f"ATENÇÃO: a sonda pública do site respondeu {codigo}, não 200. Isso é "
        "outra coisa, além do deploy — confira o ar."
    )


# ------------------------------------------------------------------ o mundo --


def porta_22_responde(host: str, porta: int = 22) -> bool | None:
    """A porta 22 da VPS devolve o banner de SSH? `None` = não consegui medir.

    A distinção entre `False` e `None` é o coração do arquivo. `False` é "abri
    o socket e a VPS não falou comigo" — prova. `None` é "a sonda nem chegou a
    perguntar" (nome que não resolve, permissão de socket negada) — e isso
    jamais pode ser lido como porta morta, senão a sonda passa a derrubar
    deploys por defeito próprio.

    `porta` existe para que o guarda possa apontar a sonda para um servidor de
    mentira e provar as duas respostas em milissegundos, sem rede e sem VPS. Em
    produção ela nunca é passada: a única porta que interessa é a 22.
    """
    try:
        with socket.create_connection((host, porta), timeout=ESPERA_DO_SOCKET_S) as con:
            con.settimeout(ESPERA_DO_SOCKET_S)
            return BANNER_SSH in con.recv(64).decode("utf-8", "replace")
    except (socket.timeout, TimeoutError, ConnectionError):
        return False  # cheguei a perguntar e não fui atendido: isso é medição
    except socket.gaierror:
        return False  # o nome não resolve: é a 017 clássica, e é resposta
    except OSError:
        return None  # a sonda falhou antes de perguntar: NÃO MEDI


def http_do_site(url: str = SONDA_DO_SITE) -> int | None:
    """O site responde pela internet pública? `None` = não consegui medir.

    A prova de que algo funciona em produção se mede do lado do usuário
    (RETROSPECTIVA-FASE-D §3), não perguntando ao container.
    """
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=15) as resposta:
            return int(resposta.status)
    except urllib.error.HTTPError as erro:
        return int(erro.code)
    except Exception:
        return None


def _escrever_saida_do_passo(veredito: str) -> None:
    """`veredito=...` em `$GITHUB_OUTPUT` — o canal que o workflow lê.

    Falha de escrita aqui NÃO derruba nada: fora do Actions a variável não
    existe, e este script precisa continuar rodando na mão.
    """
    caminho = os.environ.get("GITHUB_OUTPUT")
    if not caminho:
        return
    try:
        with open(caminho, "a", encoding="utf-8") as arquivo:
            arquivo.write(f"veredito={veredito}\n")
    except OSError as erro:
        print(f"(não consegui escrever em GITHUB_OUTPUT: {erro})", file=sys.stderr)


def _escrever_no_resumo(texto: str) -> None:
    """O resumo do run — a página que se abre sem cavar log."""
    caminho = os.environ.get("GITHUB_STEP_SUMMARY")
    if not caminho:
        return
    try:
        with open(caminho, "a", encoding="utf-8") as arquivo:
            arquivo.write(texto.rstrip() + "\n\n")
    except OSError as erro:
        print(f"(não consegui escrever no resumo do run: {erro})", file=sys.stderr)


# ----------------------------------------------------------------- a narrativa --

# Como cada tentativa aparece no resumo. `skipped` é o caso normal e feliz: a
# 2ª e a 3ª nem existem quando a 1ª atende.
_FALA_DA_TENTATIVA = {
    "success": "a VPS **atendeu**",
    "failure": "a VPS **recusou a conexão**",
    "skipped": "não foi preciso",
    "": "não foi preciso",
}

_FALA_DO_VEREDITO = {
    BLIP: (
        "a porta 22 **respondeu** deste runner — a VPS está viva, foi soluço de "
        "rede (armadilhas/127)"
    ),
    PERMANENTE: (
        "a porta 22 **não respondeu** deste runner — isto não é soluço; é falha "
        "de alcance (armadilhas/017)"
    ),
    NAO_MEDI: "**não consegui medir** a porta 22 — e não medir não é veredito",
    "": "",
}

# A medição de PARTIDA fala outra língua, de propósito. Ela acontece antes de
# qualquer tentativa, então não há falha para diagnosticar: ela é a linha de
# base ("a porta estava alcançável às HH:MM?"), e chamá-la de soluço citaria uma
# armadilha em deploys perfeitamente normais — alarme que grita no caso certo é
# alarme que se aprende a ignorar.
_FALA_DA_PARTIDA = {
    BLIP: "a porta 22 da VPS estava alcançável deste runner",
    PERMANENTE: (
        "a porta 22 da VPS **já não respondia** deste runner antes mesmo da "
        "primeira tentativa"
    ),
    NAO_MEDI: "**não consegui medir** a porta 22 antes de começar",
    "": "",
}


@dataclass
class Entrega:
    """O que o job fez, do jeito que o YAML sabe contar."""

    celula: str = ""
    tentativas: tuple[str, ...] = ()
    sondas: tuple[str, ...] = ()  # a de antes de tudo vem primeiro
    marca_de_conclusao: bool = False
    site_http: int | None = None


def narrar(entrega: Entrega) -> str:
    """O registro do que o deploy fez, em português de resultado.

    Por que isto existe: até esta entrega, um deploy que se salvou na 2ª
    tentativa era, para quem olha de fora, idêntico a um que passou de primeira
    — o padrão da VPS recusando ficava invisível justamente nos dias em que ela
    mais recusou. O log preservava as tentativas; ninguém lê log. O resumo do
    run é a primeira coisa que aparece ao abrir a execução.
    """
    linhas = [f"## Deploy da célula `{entrega.celula or '?'}` — o que aconteceu"]

    antes = entrega.sondas[0] if entrega.sondas else ""
    if antes:
        linhas.append(f"- **Antes de começar:** {_FALA_DA_PARTIDA.get(antes, antes)}.")

    depois = list(entrega.sondas[1:])
    for indice, resultado in enumerate(entrega.tentativas, start=1):
        fala = _FALA_DA_TENTATIVA.get(resultado, f"terminou `{resultado}`")
        linhas.append(f"- **{indice}ª tentativa de ativar na VPS:** {fala}.")
        if indice <= len(depois) and depois[indice - 1]:
            veredito = depois[indice - 1]
            linhas.append(
                f"  - Medição logo depois: {_FALA_DO_VEREDITO.get(veredito, veredito)}."
            )

    linhas.append(
        "- **A entrega rodou mesmo na VPS?** "
        + (
            "Sim — a marca de conclusão do script apareceu."
            if entrega.marca_de_conclusao
            else "**Não** — nenhuma tentativa produziu a marca de conclusão."
        )
    )
    if entrega.site_http is not None:
        linhas.append(
            f"- **O site, medido daqui pela internet pública:** {entrega.site_http}."
        )
    else:
        linhas.append("- **O site:** não consegui medir daqui (não é 'está fora').")

    linhas.append("")
    linhas.append(_desfecho(entrega))
    return "\n".join(linhas)


def _desfecho(entrega: Entrega) -> str:
    vitoriosa = next(
        (i for i, r in enumerate(entrega.tentativas, start=1) if r == "success"), 0
    )
    if entrega.marca_de_conclusao and vitoriosa == 1:
        return (
            "**Resultado: a versão nova ESTÁ em produção**, e a VPS atendeu de "
            "primeira — nada de anormal neste deploy."
        )
    if entrega.marca_de_conclusao and vitoriosa:
        return (
            f"**Resultado: a versão nova ESTÁ em produção** — mas foram precisas "
            f"{vitoriosa} tentativas. A VPS recusou a conexão antes de aceitar: é "
            "a armadilhas/127 mordendo de novo, e o deploy sobreviveu sozinho, "
            "sem ninguém pedir rerun. Registre a ocorrência em `painel/registros/`."
        )
    if PERMANENTE in entrega.sondas[1:]:
        return (
            "**Resultado: a versão nova NÃO subiu, e não é soluço de rede.** A "
            "porta 22 não respondeu deste runner — é a armadilhas/017, falha de "
            "alcance. O site continua servindo a versão anterior; repetir o run "
            "não vai adiantar enquanto a porta não voltar. Isto passa pelo "
            "mantenedor (Lei 5)."
        )
    return (
        "**Resultado: a versão nova NÃO subiu.** O site continua servindo a "
        "versão anterior — ninguém ficou fora do ar —, mas o que foi mergeado "
        "não está em produção. Diagnóstico e repetição: "
        "`python ci/rerun_de_deploy.py --run <id>`."
    )


def _tupla_do_env(*nomes: str) -> tuple[str, ...]:
    return tuple((os.environ.get(nome) or "").strip() for nome in nomes)


# --------------------------------------------------------------------- main --


def _sondar(args: argparse.Namespace) -> int:
    host = (os.environ.get("VPS_HOST") or "").strip()
    medicao = Medicao(host_declarado=bool(host))
    if host:
        medicao.porta22 = porta_22_responde(host)
        medicao.site_http = http_do_site(args.site)
    decisao = decidir_pela_sonda(medicao)

    _escrever_saida_do_passo(decisao.veredito)
    marca = {BLIP: "🌐", PERMANENTE: "🧱", NAO_MEDI: "❓"}[decisao.veredito]
    corpo = f"{marca} **A porta 22 da VPS, medida do runner:** {decisao.motivo}"
    if decisao.recado:
        corpo += f"\n\n{decisao.recado}"
    print(corpo.replace("**", ""))
    _escrever_no_resumo(corpo)
    estado = {0: "PASS", 1: "FAIL", 2: "ERROR"}[decisao.codigo]
    print(f"RESULTADO  {estado}")
    return decisao.codigo


def _resumir(args: argparse.Namespace) -> int:
    # A marca é procurada nas MESMAS saídas capturadas que o passo "A entrega
    # rodou mesmo?" examina — e não num sinalizador que aquele passo teria
    # passado adiante. Motivo: quando a 3ª tentativa falha, aquele passo NEM
    # RODA (o job já morreu), e um sinalizador vindo dele estaria vazio
    # justamente no caso em que a narrativa mais importa.
    saidas = "\n".join(_tupla_do_env("SAIDA_1", "SAIDA_2", "SAIDA_3"))
    entrega = Entrega(
        celula=(os.environ.get("CELULA") or "").strip(),
        tentativas=_tupla_do_env("R1", "R2", "R3"),
        sondas=_tupla_do_env("V0", "V1", "V2"),
        marca_de_conclusao=MARCA_DE_CONCLUSAO in saidas,
        site_http=http_do_site(args.site),
    )
    texto = narrar(entrega)
    print(texto)
    _escrever_no_resumo(texto)
    return 0  # o narrador conta o que houve; quem reprova são os passos acima


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="A sonda da VPS dentro do deploy (armadilhas/127): mede a "
                    "porta 22 do runner e narra o que o deploy fez."
    )
    acao = parser.add_mutually_exclusive_group(required=True)
    acao.add_argument("--sondar-porta", action="store_true",
                      help="mede a porta 22 (host em VPS_HOST) e decide")
    acao.add_argument("--resumir", action="store_true",
                      help="narra o que o deploy fez, para o resumo do run")
    parser.add_argument("--site", default=SONDA_DO_SITE)
    args = parser.parse_args(argv)
    if args.sondar_porta:
        return _sondar(args)
    return _resumir(args)


if __name__ == "__main__":
    sys.exit(main())
