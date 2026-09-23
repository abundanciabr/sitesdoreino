#!/usr/bin/env python3
"""Escada do cartão Appmax: um passo legal, até a auditoria.

Relatório de status não encerra esta obra. A fila recusa pegar fora de ordem.
O gancho de parada do Cursor, quando a bancada está armada, devolve o mesmo
passo como próxima mensagem. A obrigação do robô termina na TAR-564. Compra
real e estorno (TAR-565 e TAR-566) não entram no laço: exigem a palavra do
mantenedor.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import fila

# Ordem única. Paralelismo foi o buraco por onde a tela nasceu antes do motor.
PASSOS: tuple[tuple[str, str, str, bool], ...] = (
    ("TAR-614", "pagamentos", "estorno-e-contestacao-appmax", False),
    ("TAR-556", "pagamentos", "cliente-http-appmax", False),
    ("TAR-557", "pagamentos", "cobranca-appmax", False),
    ("TAR-593", "contracts", "parcelas-do-cartao", True),
    ("TAR-558", "pagamentos", "inbox-appmax", False),
    ("TAR-559", "pagamentos", "reconciliacao-appmax", False),
    ("TAR-615", "checkout", "tela-do-cartao-appmax", False),
    ("TAR-560", "infra", "worker-appmax-dormente", True),
    ("TAR-561", "pagamentos", "sandbox-appmax", False),
    ("TAR-562", "e2e", "compra-na-tela-appmax", True),
    ("TAR-563", "e2e", "cross-smoke-appmax", True),
    ("TAR-564", "painel", "auditoria-do-cartao-appmax", True),
)
AUDITORIA = "TAR-564"
# O que a fila precisa recusar mesmo se o gancho não estiver armado.
CORRENTES: dict[str, tuple[str, ...]] = {
    "TAR-615": ("TAR-552", "TAR-557", "TAR-593", "TAR-559"),
    "TAR-558": ("TAR-557", "TAR-593"),
    "TAR-556": ("TAR-614",),
    "TAR-560": ("TAR-615",),
    "TAR-562": ("TAR-615",),
}
LIMITE_SEM_AVANCO = 6
FUSO = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class Decisao:
    tipo: str
    tar: str
    estado: str
    texto: str


def _passo(tar: str) -> tuple[str, str, str, bool]:
    for passo in PASSOS:
        if passo[0] == tar:
            return passo
    raise KeyError(tar)


def _comando(tar: str) -> str:
    _, celula, slug, sem_container = _passo(tar)
    extra = " --sem-container" if sem_container else ""
    return (
        f"python ci/sessao.py --celula {celula} --tarefa {slug} "
        f"--tar {tar}{extra}"
    )


def _texto(tipo: str, tar: str, estado: str, motivo: str) -> str:
    if tipo == "fim":
        return (
            "FIM DE FABRICA. A TAR-564 está concluída e os passos anteriores "
            "também. TAR-565 e TAR-566 ficam paradas até o mantenedor autorizar "
            "valor, cobrança e estorno. Não declare produção pronta."
        )
    if tipo == "bloqueio":
        return (
            f"BLOQUEIO. {tar} está {estado}. {motivo} "
            "Isto não é pronto. Não invente credencial, cartão de teste nem "
            "autorização de dinheiro."
        )
    if tipo == "aguardar":
        return (
            f"AGUARDAR. {tar} já tem entrega submetida. "
            "Não abra a próxima. Não reescreva o relatório como se a escada "
            "tivesse acabado."
        )
    return (
        "OBRIGACAO DA ESCADA DO CARTAO. Esta parada não encerra a obra.\n"
        f"O único passo legal agora é {tar} ({estado}).\n"
        f"{_comando(tar)}\n"
        "Execute o brief inteiro até o PR, ou grave bloqueio com espera "
        "mantenedor se a peça for credencial, cartão oficial ou dinheiro real.\n"
        "Proibido: pegar outra TAR, relatório de status no lugar do PR, "
        "declarar pronto antes da TAR-564."
    )


def decidir(estados: dict[str, dict]) -> Decisao:
    """O primeiro passo da escada que ainda não está concluído."""
    for tar, *_resto in PASSOS:
        info = estados.get(tar) or {}
        estado = info.get("estado") or fila.NA_FILA
        if estado == fila.CONCLUIDA:
            continue
        motivo = str(info.get("motivo") or "")
        if estado == fila.CANCELADA or (
            estado == fila.BLOQUEADA and info.get("espera") == fila.ESPERA_O_MANTENEDOR
        ):
            return Decisao("bloqueio", tar, estado, _texto("bloqueio", tar, estado, motivo))
        if estado == fila.EM_EXECUCAO:
            return Decisao("aguardar", tar, estado, _texto("aguardar", tar, estado, motivo))
        # guarda: o primeiro incompleto é o único passo; sem isto a escada vira fim
        return Decisao("pegar", tar, estado, _texto("pegar", tar, estado, motivo))
    return Decisao("fim", AUDITORIA, fila.CONCLUIDA, _texto("fim", AUDITORIA, fila.CONCLUIDA, ""))


def correntes_falsas(tarefas: dict[str, dict]) -> list[str]:
    erros = []
    for tar, exigidas in CORRENTES.items():
        atuais = tuple(tarefas.get(tar, {}).get("depende_de") or [])
        faltando = [dep for dep in exigidas if dep not in atuais]
        if faltando:
            erros.append(f"{tar} sem depende_de {', '.join(faltando)}")
    return erros


def carregar(raiz: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    erros: list[str] = []
    tarefas = fila.carregar_tarefas(raiz, erros)
    if erros:
        raise RuntimeError("; ".join(erros))
    eventos = fila.carregar_eventos(raiz, tarefas, erros)
    if erros:
        raise RuntimeError("; ".join(erros))
    return tarefas, fila.calcular_estados(tarefas, eventos)


def _arquivo_de_arme() -> Path:
    bruto = os.environ.get("ESCADA_ARQUIVO_DE_ARME", "").strip()
    if bruto:
        return Path(bruto)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "sitesdoreino" / "escada-do-cartao.json"


def ler_arme() -> dict:
    caminho = _arquivo_de_arme()
    if not caminho.is_file():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


def gravar_arme(dados: dict) -> None:
    caminho = _arquivo_de_arme()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


def armada(raiz: Path) -> bool:
    dados = ler_arme()
    registrada = str(dados.get("raiz") or "")
    if not registrada:
        return False
    return Path(registrada).resolve() == raiz.resolve()


def _impressao(raiz: Path, decisao: Decisao) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(raiz), "status", "--porcelain=v1", "-uno"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15, stdin=subprocess.DEVNULL,
        )
        cabeca = subprocess.run(
            ["git", "-C", str(raiz), "rev-parse", "HEAD"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15, stdin=subprocess.DEVNULL,
        )
        miolo = f"{cabeca.stdout}\n{proc.stdout}\n{decisao.tipo}\n{decisao.tar}"
    except (OSError, subprocess.SubprocessError):
        miolo = f"sem-git\n{decisao.tipo}\n{decisao.tar}"
    return hashlib.sha256(miolo.encode("utf-8")).hexdigest()


def hora_de_nao_abrir_caixa(agora: datetime | None = None) -> bool:
    momento = agora or datetime.now(FUSO)
    return (momento.hour, momento.minute) >= (21, 30)


def resposta_do_gancho(
    *,
    status: str,
    armada_aqui: bool,
    decisao: Decisao,
    repeticoes: int,
    hora_de_nova_caixa: bool,
) -> dict:
    if status != "completed" or not armada_aqui:
        return {}
    if decisao.tipo in {"fim", "bloqueio", "aguardar"}:
        return {}
    if hora_de_nova_caixa and decisao.estado == fila.NA_FILA:
        return {}
    if repeticoes >= LIMITE_SEM_AVANCO:
        return {}
    return {"followup_message": decisao.texto}


def gancho(entrada: dict, raiz: Path) -> dict:
    if not isinstance(entrada, dict):
        return {}
    if not armada(raiz):
        return resposta_do_gancho(
            status=str(entrada.get("status") or ""),
            armada_aqui=False,
            decisao=Decisao("fim", AUDITORIA, "", ""),
            repeticoes=0,
            hora_de_nova_caixa=False,
        )
    _tarefas, estados = carregar(raiz)
    decisao = decidir(estados)
    dados = ler_arme()
    impressao = _impressao(raiz, decisao)
    repeticoes = int(dados.get("repeticoes") or 0)
    if dados.get("impressao") == impressao:
        repeticoes += 1
    else:
        repeticoes = 1
    dados["impressao"] = impressao
    dados["repeticoes"] = repeticoes
    gravar_arme(dados)
    return resposta_do_gancho(
        status=str(entrada.get("status") or ""),
        armada_aqui=True,
        decisao=decisao,
        repeticoes=repeticoes,
        hora_de_nova_caixa=hora_de_nao_abrir_caixa(),
    )


def _raiz_do_argv(argv: list[str]) -> Path:
    if "--raiz" in argv:
        return Path(argv[argv.index("--raiz") + 1]).resolve()
    return Path.cwd().resolve()


def main(argv: list[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    gancho_pedido = "--gancho-parar" in argumentos
    try:
        return _executar(argumentos, gancho_pedido)
    except Exception as erro:  # noqa: BLE001 — gancho que quebra não pode prender a parada
        if gancho_pedido:
            print("{}")
            print(f"escada: gancho não medido ({erro}). A parada não foi forçada.", file=sys.stderr)
            return 0
        print(f"escada: {erro}", file=sys.stderr)
        return 1


def _executar(argumentos: list[str], gancho_pedido: bool) -> int:
    if gancho_pedido:
        bruto = sys.stdin.read()
        entrada = json.loads(bruto) if bruto.strip() else {}
        print(json.dumps(gancho(entrada, _raiz_do_argv(argumentos)), ensure_ascii=False))
        return 0
    raiz = _raiz_do_argv(argumentos)
    if "armar" in argumentos:
        gravar_arme({"raiz": str(raiz), "repeticoes": 0})
        print(f"ARMADA {raiz}")
        return 0
    if "desarmar" in argumentos:
        caminho = _arquivo_de_arme()
        caminho.unlink(missing_ok=True)
        print("DESARMADA")
        return 0
    tarefas, estados = carregar(raiz)
    falsas = correntes_falsas(tarefas)
    if falsas:
        print("CORRENTE FALSA")
        for erro in falsas:
            print(erro)
        return 2
    decisao = decidir(estados)
    print(decisao.texto)
    if "fechar" in argumentos:
        if decisao.tipo == "fim":
            return 0
        if decisao.tipo == "bloqueio":
            return 3
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
