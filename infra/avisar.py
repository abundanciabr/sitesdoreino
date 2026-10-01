#!/usr/bin/env python3
"""Avisa o mantenedor por e-mail, a partir da VPS, sem GitHub.

O CANAL JÁ EXISTENTE
--------------------
A plataforma já tem conta de e-mail provisionada: o SMTP da célula `mensageria`
(Brevo, escolha do mantenedor em 02/09/2026, `infra/provisionar-email.sh`). As
credenciais moram na VPS, em `env/mensageria.env`: SMTP_HOST, SMTP_PORT,
SMTP_USER, SMTP_PASSWORD e SMTP_FROM. O endereço do mantenedor é o da
administração, ADMIN_EMAILS de `env/admin.env` (com IDENTIDADE_STAFF_EMAILS como
reserva). Os outros canais não servem para texto livre: o aviso no celular
(`notificacoes`) carrega dado, nunca frase, e só o teste manda carta pela porta;
o WhatsApp (`mensageria`) ainda é stub e WHATSAPP_GATEWAY_URL está vazio.

NENHUM VALOR SECRETO SAI DAQUI: nem na tela, nem em mensagem de erro, nem no
e-mail. As mensagens de falha dizem o NOME da chave que falta, nunca o valor.

USO (na VPS, com PLATAFORMA_DIR=/opt/plataforma, que é o padrão)
    python3 infra/avisar.py "texto do aviso"
    echo "texto" | python3 infra/avisar.py -
    python3 infra/avisar.py --verificar          (entra no SMTP e sai: não manda nada)
    python3 infra/avisar.py "texto" --chave cadeado-vermelho --a-cada-horas 72

`--chave` com `--a-cada-horas` evita repetir o mesmo alarme: enquanto a última
carta daquela chave tiver menos horas que o prazo, o aviso é silenciado (o que a
issue já aberta fazia no GitHub). A hora só é gravada depois que a carta SAIU.

Como função: `avisar(texto, assunto=None, chave=None, a_cada_horas=None)`
devolve "enviado" ou "silenciado" e levanta `AvisoFalhou` se não saiu.
Só biblioteca padrão.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import smtplib
import socket
import ssl
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from typing import Callable, Mapping

PREFIXO_DO_ASSUNTO = "[sitesdoreino] "
LIMITE_DO_TEXTO = 20000
LIMITE_DE_DESTINATARIOS = 5
PRAZO_DO_SMTP_SEGUNDOS = 20
CHAVES_SMTP = ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM")
ENDERECO = re.compile(r"[^@\s,;<>\"']+@[^@\s,;<>\"']+\.[^@\s,;<>\"']+")


class AvisoFalhou(Exception):
    """O aviso NÃO saiu. A mensagem nunca carrega valor de segredo."""


@dataclass(frozen=True)
class Configuracao:
    host: str
    porta: int
    usuario: str
    senha: str
    remetente: str
    destinatarios: tuple[str, ...]

    def segredos(self) -> tuple[str, ...]:
        return tuple(v for v in (self.senha, self.usuario) if v)


def raiz_da_plataforma(ambiente: Mapping[str, str] | None = None) -> Path:
    ambiente = os.environ if ambiente is None else ambiente
    return Path(ambiente.get("PLATAFORMA_DIR") or "/opt/plataforma")


def ler_env(caminho: Path) -> dict[str, str]:
    """Lê um env no formato do Docker Compose. A última linha de uma chave vale."""
    valores: dict[str, str] = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if linha.startswith("export "):
            linha = linha[len("export "):].lstrip()
        chave, igual, valor = linha.partition("=")
        chave = chave.strip()
        if not igual or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", chave):
            continue
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] in "\"'" and valor[-1] == valor[0]:
            valor = valor[1:-1]
        else:
            valor = re.split(r"\s+#", valor, maxsplit=1)[0].rstrip()
        valores[chave] = valor
    return valores


def _ler(raiz: Path, nome: str, opcional: bool = False) -> dict[str, str]:
    try:
        return ler_env(raiz / "env" / nome)
    except FileNotFoundError:
        if opcional:
            return {}
        raise AvisoFalhou(f"não achei {raiz / 'env' / nome}; esta cópia roda na VPS, em PLATAFORMA_DIR?") from None
    except OSError as erro:
        raise AvisoFalhou(
            f"não consegui ler {raiz / 'env' / nome} ({erro.__class__.__name__}); "
            "esta cópia está rodando na VPS, como o usuário deploy?"
        ) from None


def enderecos(texto: str) -> tuple[str, ...]:
    vistos: list[str] = []
    for parte in re.split(r"[,;\s]+", texto or ""):
        if ENDERECO.fullmatch(parte) and parte.lower() not in vistos:
            vistos.append(parte.lower())
    return tuple(vistos[:LIMITE_DE_DESTINATARIOS])


def configuracao(
    raiz: Path | None = None, ambiente: Mapping[str, str] | None = None
) -> Configuracao:
    ambiente = os.environ if ambiente is None else ambiente
    raiz = raiz or raiz_da_plataforma(ambiente)
    smtp = _ler(raiz, "mensageria.env")
    faltam = [chave for chave in CHAVES_SMTP if not smtp.get(chave)]
    if faltam:
        raise AvisoFalhou(
            "env/mensageria.env sem " + ", ".join(faltam) + ": o e-mail da plataforma "
            "não está provisionado (infra/provisionar-email.sh é passo do mantenedor)."
        )
    try:
        porta = int(smtp.get("SMTP_PORT") or "587")
    except ValueError:
        raise AvisoFalhou("SMTP_PORT em env/mensageria.env não é um número.") from None
    para = enderecos(ambiente.get("AVISAR_PARA", ""))
    if not para:
        administracao = _ler(raiz, "admin.env", opcional=True)
        para = enderecos(administracao.get("ADMIN_EMAILS", ""))
        if not para:
            para = enderecos(_ler(raiz, "identidade.env", opcional=True).get("IDENTIDADE_STAFF_EMAILS", ""))
    if not para:
        raise AvisoFalhou(
            "nenhum destinatário: ADMIN_EMAILS (env/admin.env) e "
            "IDENTIDADE_STAFF_EMAILS (env/identidade.env) vazios ou sem endereço válido."
        )
    return Configuracao(
        host=smtp["SMTP_HOST"],
        porta=porta,
        usuario=smtp["SMTP_USER"],
        senha=smtp["SMTP_PASSWORD"],
        remetente=smtp["SMTP_FROM"],
        destinatarios=para,
    )


def _sem_segredo(texto: str, cfg: Configuracao) -> str:
    for segredo in cfg.segredos():
        texto = texto.replace(segredo, "***")
    return texto


def _assunto(assunto: str | None, texto: str) -> str:
    base = assunto or next((l for l in texto.splitlines() if l.strip()), "aviso")
    base = re.sub(r"[\x00-\x1f\x7f]+", " ", base).strip()[:150] or "aviso"
    return PREFIXO_DO_ASSUNTO + base


def montar(cfg: Configuracao, texto: str, assunto: str | None, agora: datetime) -> EmailMessage:
    if len(texto) > LIMITE_DO_TEXTO:
        texto = texto[:LIMITE_DO_TEXTO] + "\n[... cortado em %d caracteres]" % LIMITE_DO_TEXTO
    mensagem = EmailMessage()
    mensagem["From"] = cfg.remetente
    mensagem["To"] = ", ".join(cfg.destinatarios)
    mensagem["Subject"] = _assunto(assunto, texto)
    mensagem["Date"] = format_datetime(agora)
    mensagem.set_content(
        texto.rstrip()
        + "\n\n--\nenviado de %s em %s por infra/avisar.py"
        % (socket.gethostname(), agora.strftime("%Y-%m-%dT%H:%M:%SZ"))
    )
    return mensagem


def conectar_smtp(cfg: Configuracao):
    """Cliente SMTP já autenticado. Porta 465 é SSL direto; as outras, STARTTLS."""
    contexto = ssl.create_default_context()
    if cfg.porta == 465:
        cliente = smtplib.SMTP_SSL(cfg.host, cfg.porta, timeout=PRAZO_DO_SMTP_SEGUNDOS, context=contexto)
    else:
        cliente = smtplib.SMTP(cfg.host, cfg.porta, timeout=PRAZO_DO_SMTP_SEGUNDOS)
    try:
        if cfg.porta != 465:
            cliente.ehlo()
            cliente.starttls(context=contexto)
            cliente.ehlo()
        cliente.login(cfg.usuario, cfg.senha)
    except BaseException:
        cliente.close()
        raise
    return cliente


def _mascarar(endereco: str) -> str:
    usuario, _, dominio = endereco.partition("@")
    return usuario[:1] + "***@" + dominio


def _estado(raiz: Path, ambiente: Mapping[str, str]) -> Path:
    return Path(ambiente.get("AVISAR_ESTADO") or raiz / ".avisos-enviados.json")


def _ler_estado(caminho: Path) -> dict[str, str]:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar_estado(caminho: Path, dados: dict[str, str]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    descritor, provisorio = tempfile.mkstemp(dir=caminho.parent, prefix=caminho.name + ".")
    try:
        with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, sort_keys=True)
        os.replace(provisorio, caminho)
    except BaseException:
        try:
            os.unlink(provisorio)
        except OSError:
            pass
        raise


def _silenciado(estado: dict[str, str], chave: str, horas: float, agora: datetime) -> bool:
    try:
        ultimo = datetime.fromisoformat(estado[chave])
    except (KeyError, ValueError, TypeError):
        return False
    return (agora - ultimo).total_seconds() < horas * 3600


def avisar(
    texto: str,
    assunto: str | None = None,
    *,
    chave: str | None = None,
    a_cada_horas: float | None = None,
    raiz: Path | None = None,
    ambiente: Mapping[str, str] | None = None,
    conectar: Callable = conectar_smtp,
    agora: datetime | None = None,
) -> str:
    """Manda o aviso. Devolve "enviado" ou "silenciado"; levanta AvisoFalhou se falhar."""
    if not texto or not texto.strip():
        raise AvisoFalhou("texto do aviso vazio.")
    ambiente = os.environ if ambiente is None else ambiente
    raiz = raiz or raiz_da_plataforma(ambiente)
    agora = agora or datetime.now(timezone.utc)
    estado_caminho = _estado(raiz, ambiente)
    if chave and a_cada_horas:
        if _silenciado(_ler_estado(estado_caminho), chave, a_cada_horas, agora):
            return "silenciado"
    cfg = configuracao(raiz, ambiente)
    mensagem = montar(cfg, texto, assunto, agora)
    try:
        with conectar(cfg) as cliente:
            recusados = cliente.send_message(mensagem)
    except (OSError, smtplib.SMTPException) as erro:
        raise AvisoFalhou(
            "o provedor de e-mail não aceitou o aviso: %s: %s"
            % (erro.__class__.__name__, _sem_segredo(str(erro), cfg))
        ) from None
    if recusados:
        raise AvisoFalhou("o provedor recusou %d destinatário(s)." % len(recusados))
    if chave and a_cada_horas:
        try:
            dados = _ler_estado(estado_caminho)
            dados[chave] = agora.isoformat()
            _gravar_estado(estado_caminho, dados)
        except OSError:
            pass  # o aviso saiu; só a memória do silêncio falhou
    return "enviado"


def verificar(
    raiz: Path | None = None,
    ambiente: Mapping[str, str] | None = None,
    conectar: Callable = conectar_smtp,
) -> str:
    """Entra no SMTP com as credenciais da VPS e sai. Não manda carta nenhuma."""
    cfg = configuracao(raiz, ambiente)
    try:
        with conectar(cfg) as cliente:
            cliente.noop()
    except (OSError, smtplib.SMTPException) as erro:
        raise AvisoFalhou(
            "o provedor de e-mail recusou a entrada: %s: %s"
            % (erro.__class__.__name__, _sem_segredo(str(erro), cfg))
        ) from None
    return "canal ok: %s:%d, login aceito, %d destinatário(s) (%s); nada foi enviado" % (
        cfg.host,
        cfg.porta,
        len(cfg.destinatarios),
        ", ".join(_mascarar(e) for e in cfg.destinatarios),
    )


def main(argv: list[str] | None = None, **injecao) -> int:
    parser = argparse.ArgumentParser(
        prog="avisar.py",
        description="Avisa o mantenedor por e-mail, a partir da VPS (SMTP de env/mensageria.env).",
        allow_abbrev=False,
    )
    parser.add_argument("texto", nargs="?", help='o aviso; "-" lê da entrada padrão')
    parser.add_argument("--assunto", help="assunto (padrão: a primeira linha do texto)")
    parser.add_argument("--chave", help="nome do alarme, para não repetir")
    parser.add_argument("--a-cada-horas", type=float, help="silêncio mínimo entre dois avisos da mesma chave")
    parser.add_argument("--verificar", action="store_true", help="só entra no SMTP; não manda nada")
    args = parser.parse_args(argv)
    try:
        if args.verificar:
            print("avisar: " + verificar(**injecao))
            return 0
        if args.texto is None:
            parser.error('faltou o texto do aviso (ou "-" para ler da entrada padrão)')
        texto = sys.stdin.read() if args.texto == "-" else args.texto
        resultado = avisar(
            texto, args.assunto, chave=args.chave, a_cada_horas=args.a_cada_horas, **injecao
        )
    except AvisoFalhou as erro:
        print(f"avisar: FALHOU: {erro}", file=sys.stderr)
        return 1
    print(f"avisar: {resultado}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except AttributeError:
        pass
    raise SystemExit(main())
