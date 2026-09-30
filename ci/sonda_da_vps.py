#!/usr/bin/env python3
"""Mede o alcance SSH da VPS e resume evidências da aplicação.

VPS_HOST vem pelo ambiente e não é impresso. A sonda distingue respostas
negativas, ausência de resposta e falha do instrumento. Ela não aprova imagens.
Uso: python ci/sonda_da_vps.py --sondar-porta ou --resumir"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _nucleo import configurar_saida  # noqa: E402

VPS_PADRAO = "217.196.62.220"
BANNER_SSH = "SSH-2.0"
SONDA_DO_SITE = "https://meshcraft.top/healthz"
ESPERA_DO_SOCKET_S = 10

SONDAGENS_POR_MEDICAO = 3
PAUSA_ENTRE_SONDAGENS_S = 2
MEDICOES_MINIMAS_PARA_PERMANENTE = 2

BLIP = "blip"
PERMANENTE = "permanente"
NAO_MEDI = "nao_medi"

ATENDEU = "atendeu"                      # falou o banner de SSH: a porta está viva
NAO_E_SSH = "nao_e_ssh"                  # a conexão abriu, mas quem está lá não é SSH
RECUSOU = "recusou"                      # levou um "não" da rede: resposta negativa
NOME_NAO_RESOLVE = "nome_nao_resolve"    # o DNS respondeu "não existe": resposta negativa
SEM_RESPOSTA = "sem_resposta"            # estourou o tempo: SILÊNCIO, não resposta
NAO_PERGUNTEI = "nao_perguntei"          # a sonda falhou antes de perguntar

RESPOSTAS_NEGATIVAS = frozenset({NAO_E_SSH, RECUSOU, NOME_NAO_RESOLVE})

MARCA_DE_CONCLUSAO = "ENTREGA-CONCLUIDA:"


@dataclass
class Medicao:
    """O mundo, medido. Separado da decisão para que a tabela inteira seja
    testável sem rede, sem VPS e sem runner — as três coisas que não se
    produzem sob encomenda."""

    porta22: bool | None = None  # None = NÃO MEDI, sempre
    site_http: int | None = None
    host_declarado: bool = True
    apos_recusa: bool = True
    sinais: tuple[str, ...] = ()


def resumo_dos_sinais(sinais: tuple[str, ...] | list[str]) -> bool | None:
    """Resume sinais como alcance confirmado, recusa corroborada ou medição inconclusiva."""
    sinais = tuple(sinais)
    if not sinais:
        return None
    if ATENDEU in sinais:
        return True
    negativas = sum(1 for sinal in sinais if sinal in RESPOSTAS_NEGATIVAS)
    if negativas == len(sinais) and negativas >= MEDICOES_MINIMAS_PARA_PERMANENTE:
        return False
    return None


@dataclass
class Veredito:
    veredito: str  # BLIP | PERMANENTE | NAO_MEDI
    codigo: int  # 0 PASS · 1 FAIL · 2 ERROR
    motivo: str
    recado: str = ""
    medicoes: int = 0


def decidir_pela_sonda(medicao: Medicao) -> Veredito:
    """Classifica o alcance usando sondagens e a resposta pública do mesmo runner."""
    sinais = tuple(medicao.sinais)
    quantas = len(sinais)
    viva = medicao.porta22 is True or ATENDEU in sinais
    negativas = sum(1 for sinal in sinais if sinal in RESPOSTAS_NEGATIVAS)
    silencios = sum(1 for sinal in sinais if sinal == SEM_RESPOSTA)

    if not medicao.host_declarado:
        return Veredito(
            NAO_MEDI, 2,
            "não recebi o endereço da VPS (`VPS_HOST` vazio) — sem alvo não há "
            "o que sondar, e 'não medi' nunca vira 'a porta está morta'.",
            "O retry segue inteiro, como se esta sonda não existisse.",
            medicoes=quantas,
        )
    if viva and not medicao.apos_recusa:
        return Veredito(
            BLIP, 0,
            "a porta 22 da VPS RESPONDEU o banner de SSH deste runner, antes de "
            "qualquer tentativa. É a linha de base do deploy: no minuto em que "
            "ele começou, a VPS estava alcançável daqui.",
            medicoes=quantas,
        )
    if viva:
        return Veredito(
            BLIP, 0,
            "a porta 22 da VPS RESPONDEU o banner de SSH agora, deste runner. "
            "O alcance SSH foi confirmado agora. A falha anterior pode ter sido "
            "intermitente. Repetir é exatamente o certo.",
            _recado_do_site(medicao.site_http),
            medicoes=quantas,
        )

    if quantas < MEDICOES_MINIMAS_PARA_PERMANENTE:
        return Veredito(
            NAO_MEDI, 2,
            _porque_nao_bastou(quantas)
            + " Sem corroboração não dá para distinguir falha intermitente de "
            "falha persistente de alcance.",
            "O retry segue inteiro: uma sonda que não mediu — ou que mediu uma "
            "vez só — não tira tentativa de ninguém.",
            medicoes=quantas,
        )
    if negativas + silencios < quantas:
        return Veredito(
            NAO_MEDI, 2,
            f"{_quantas(quantas)} pela porta 22, e "
            f"{quantas - negativas - silencios} delas nem chegaram a perguntar "
            "(a sonda falhou antes da conexão: socket bloqueado pelo próprio "
            "runner). Defeito do instrumento não determina o estado da VPS.",
            "O retry segue inteiro.",
            medicoes=quantas,
        )
    if negativas == quantas:
        return _permanente(
            medicao, quantas,
            f"a porta 22 da VPS RESPONDEU 'não' nas {_quantas(quantas)} feitas "
            f"deste runner ({_detalhe(sinais)}). Não é silêncio de rede: em "
            "todas elas alguém do outro lado respondeu, e não era SSH.",
        )
    if medicao.site_http is not None:
        return _permanente(
            medicao, quantas,
            f"a porta 22 da VPS ficou MUDA nas {_quantas(quantas)} feitas deste "
            f"runner ({_detalhe(sinais)}) — mas o site público respondeu "
            f"{medicao.site_http} DAQUI, na mesma janela. A saída do runner "
            "está funcionando; o buraco é a porta 22, e só ela.",
        )
    return Veredito(
        NAO_MEDI, 2,
        f"a porta 22 da VPS ficou MUDA nas {_quantas(quantas)} feitas deste "
        f"runner ({_detalhe(sinais)}) — e daqui eu também NÃO alcancei o site "
        "público. Não foi possível corroborar o estado da porta. Estouro de "
        "tempo (`i/o timeout`) também pode ocorrer por falha de rede do runner.",
        "O retry segue inteiro — e é isso que fail-closed significa aqui: "
        "repetir à toa custa 45 s, desistir à toa custa a entrega.",
        medicoes=quantas,
    )


def _permanente(medicao: Medicao, quantas: int, medido: str) -> Veredito:
    """Descreve uma falha corroborada de alcance e a quantidade de sondagens."""
    if not medicao.apos_recusa:
        return Veredito(
            PERMANENTE, 1,
            f"{medido} Isto é a linha de base — foi medido ANTES da primeira "
            "tentativa. Foi observada uma falha de alcance. Esta medição sozinha "
            "NÃO interrompe a aplicação.",
            _recado_do_site(medicao.site_http),
            medicoes=quantas,
        )
    return Veredito(
        PERMANENTE, 1,
        f"{medido} Falha persistente de alcance deste runner. Confira DNS, "
        "proxy e firewall antes de repetir a conexão.",
        _recado_do_site(medicao.site_http),
        medicoes=quantas,
    )


def _quantas(quantas: int) -> str:
    return "1 sondagem" if quantas == 1 else f"{quantas} sondagens seguidas"


def _porque_nao_bastou(quantas: int) -> str:
    if quantas == 0:
        return (
            "não consegui medir a porta 22 da VPS — não sobrou nenhuma sondagem "
            "utilizável, e a sonda não sabe em quantas medições se apoiaria."
        )
    return (
        "a porta 22 da VPS não atendeu, mas isto foi UMA sondagem só — e uma "
        "sondagem sozinha nunca manda o deploy desistir. Um engasgo momentâneo "
        f"do próprio runner produz exatamente esta leitura (mínimo exigido: "
        f"{MEDICOES_MINIMAS_PARA_PERMANENTE})."
    )


_NOME_DO_SINAL = {
    ATENDEU: "atendeu falando SSH",
    NAO_E_SSH: "atendeu sem falar SSH",
    RECUSOU: "recusou a conexão",
    NOME_NAO_RESOLVE: "o nome não resolve",
    SEM_RESPOSTA: "estourou o tempo",
    NAO_PERGUNTEI: "nem cheguei a perguntar",
}


def _detalhe(sinais: tuple[str, ...]) -> str:
    """O que cada sondagem viu, contado — para que a mensagem seja falsificável
    em vez de categórica."""
    vistos: dict[str, int] = {}
    for sinal in sinais:
        vistos[sinal] = vistos.get(sinal, 0) + 1
    return "; ".join(
        f"{_NOME_DO_SINAL.get(sinal, sinal)} em {contagem}"
        for sinal, contagem in vistos.items()
    ) or "sem detalhe"


def _recado_do_site(codigo: int | None) -> str:
    """Conta somente o alcance público medido, sem presumir a imagem ativa."""
    if codigo == 200:
        return (
            "O endereço público respondeu 200. Essa medição não identifica a "
            "imagem em uso nem substitui a prova do produto."
        )
    if codigo is None:
        return "Não consegui medir o endereço público deste runner."
    return f"O endereço público respondeu {codigo}; confira a disponibilidade."


def sondar_uma_vez(host: str, porta: int = 22) -> str:
    """Mede o banner SSH sem confundir recusa de conexão com estouro de tempo."""
    try:
        conexao = socket.create_connection((host, porta), timeout=ESPERA_DO_SOCKET_S)
    except (socket.timeout, TimeoutError):
        return SEM_RESPOSTA  # ninguém disse nada: SILÊNCIO, e silêncio não decide
    except socket.gaierror:
        return NOME_NAO_RESOLVE  # o DNS respondeu, e a resposta foi "não existe"
    except ConnectionError:
        return RECUSOU  # levei um "não" da rede: isso é resposta
    except OSError:
        return NAO_PERGUNTEI  # a sonda falhou antes de perguntar: NÃO MEDI
    with conexao:
        conexao.settimeout(ESPERA_DO_SOCKET_S)
        try:
            banner = conexao.recv(64).decode("utf-8", "replace")
        except OSError:
            return NAO_E_SSH
    return ATENDEU if BANNER_SSH in banner else NAO_E_SSH


def medir_a_porta(
    host: str,
    porta: int = 22,
    sondagens: int = 0,
) -> tuple[str, ...]:
    """Repete a medição até o limite, parando quando recebe um banner SSH."""
    sondagens = sondagens or SONDAGENS_POR_MEDICAO
    sinais: list[str] = []
    for numero in range(1, max(1, sondagens) + 1):
        sinal = sondar_uma_vez(host, porta)
        sinais.append(sinal)
        if sinal == ATENDEU:
            break
        if numero < sondagens and PAUSA_ENTRE_SONDAGENS_S:
            time.sleep(PAUSA_ENTRE_SONDAGENS_S)
    return tuple(sinais)


def porta_22_responde(host: str, porta: int = 22) -> bool | None:
    """True confirma SSH, False confirma recusas repetidas e None indica incerteza."""
    return resumo_dos_sinais(medir_a_porta(host, porta))


def http_do_site(url: str = SONDA_DO_SITE) -> int | None:
    """Retorna o status HTTP público ou None quando não consegue medir."""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=15) as resposta:
            return int(resposta.status)
    except urllib.error.HTTPError as erro:
        return int(erro.code)
    except Exception:
        return None


def _escrever_saida_do_passo(veredito: str, medicoes: int) -> None:
    """Escreve veredito e quantidade de sondagens em GITHUB_OUTPUT."""
    caminho = os.environ.get("GITHUB_OUTPUT")
    if not caminho:
        return
    try:
        with open(caminho, "a", encoding="utf-8") as arquivo:
            arquivo.write(f"veredito={veredito}\n")
            arquivo.write(f"sondagens={medicoes}\n")
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


_FALA_DA_TENTATIVA = {
    "success": "a VPS **atendeu**",
    "failure": "a tentativa **falhou**",
    "skipped": "não foi preciso",
    "": "não foi preciso",
}

_FALA_DO_VEREDITO = {
    BLIP: (
        "a porta 22 **respondeu** deste runner — a VPS está viva, foi soluço de "
        "rede intermitente"
    ),
    PERMANENTE: (
        "a porta 22 **não respondeu** deste runner — isto não é soluço; é falha "
        "de alcance"
    ),
    NAO_MEDI: "**não consegui medir** a porta 22 — e não medir não é veredito",
    "": "",
}

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
    """Resume tentativas, conclusão técnica e alcance público sem aprovar imagens."""
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
    if entrega.marca_de_conclusao and vitoriosa:
        tentativas = (
            "de primeira" if vitoriosa == 1 else f"após {vitoriosa} tentativas"
        )
        return (
            f"**Resultado: o script de aplicação concluiu {tentativas}.** "
            "A aprovação da imagem depende da prova registrada pelo script de "
            "publicação; a sonda de rede não registra aprovação. "
            + _recado_do_site(entrega.site_http)
        )
    depois = [sonda for sonda in entrega.sondas[1:] if sonda]
    if len(depois) >= MEDICOES_MINIMAS_PARA_PERMANENTE and all(
        sonda == PERMANENTE for sonda in depois
    ):
        return (
            "**Resultado: aplicação sem conclusão confirmada.** A porta 22 "
            f"não estava alcançável deste runner nas {len(depois)} medições "
            "posteriores às tentativas. Confira "
            "rede, credenciais e estado da célula antes de uma nova tentativa. "
            + _recado_do_site(entrega.site_http)
        )
    return (
        "**Resultado: aplicação sem conclusão confirmada.** Confira os logs "
        "da aplicação e da recuperação e o estado da célula. "
        + _recado_do_site(entrega.site_http)
    )


def _tupla_do_env(*nomes: str) -> tuple[str, ...]:
    return tuple((os.environ.get(nome) or "").strip() for nome in nomes)


def _sondar(args: argparse.Namespace) -> int:
    host = (os.environ.get("VPS_HOST") or "").strip()
    medicao = Medicao(
        host_declarado=bool(host),
        apos_recusa=(os.environ.get("MOMENTO") or "").strip() != "partida",
    )
    if host:
        medicao.sinais = medir_a_porta(host)
        medicao.porta22 = resumo_dos_sinais(medicao.sinais)
        medicao.site_http = http_do_site(args.site)
    decisao = decidir_pela_sonda(medicao)

    _escrever_saida_do_passo(decisao.veredito, decisao.medicoes)
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
        description="A sonda da VPS: mede a "
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
