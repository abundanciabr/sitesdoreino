#!/usr/bin/env python3
"""ECONOMIA DA FÁBRICA — modelo caro só trabalha onde compra decisão difícil.

Este comando mecaniza três escolhas que antes moravam em disciplina de sessão:

1. classificar a tarefa antes de despachar;
2. recomendar modelo, esforço e teto de contexto para aquele tipo de trabalho;
3. compilar um brief curto, com só as armadilhas citadas, para o sub-agente.

Ele não corta escopo e não substitui portão. A economia vem de tirar contexto
repetido e impedir herança silenciosa de modelo caro em trabalho mecânico.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import ErroDeInstrumentacao, configurar_saida, raiz_do_repo  # noqa: E402

MODELO_ROTINA = "sonnet"
MODELO_TOPO = "modelo-de-cima"


@dataclass(frozen=True)
class Perfil:
    tipo: str
    modelo: str
    esforco: str
    teto_contexto: int
    motivo: str


PERFIS: dict[str, Perfil] = {
    "arquitetura": Perfil(
        "arquitetura",
        MODELO_TOPO,
        "high",
        180_000,
        "muda contrato, fronteira ou desenho de produto; erro aqui custa retrabalho amplo",
    ),
    "produto": Perfil(
        "produto",
        MODELO_TOPO,
        "high",
        180_000,
        "cria ou muda comportamento de produto; precisa de julgamento semantico",
    ),
    "contrato": Perfil(
        "contrato",
        MODELO_TOPO,
        "high",
        160_000,
        "muda promessa entre celulas; a economia errada aqui quebra consumidores",
    ),
    "revisao": Perfil(
        "revisao",
        MODELO_ROTINA,
        "medium",
        90_000,
        "le diff contra checklist fechado; modelo barato acha escopo, recibo e prova faltando",
    ),
    "escrita": Perfil(
        "escrita",
        MODELO_ROTINA,
        "medium",
        70_000,
        "preenche moldes de registro, fila e armadilha; criatividade aqui e risco",
    ),
    "diagnostico": Perfil(
        "diagnostico",
        MODELO_ROTINA,
        "medium",
        100_000,
        "mede estado e classifica FAIL ou ERROR antes de qualquer conserto",
    ),
    "teste": Perfil(
        "teste",
        MODELO_ROTINA,
        "medium",
        100_000,
        "guarda focado nasce de comportamento ja definido; contrato aberto sobe para produto",
    ),
    "texto": Perfil(
        "texto",
        MODELO_ROTINA,
        "medium",
        70_000,
        "reescreve superficie publicada sem decidir arquitetura",
    ),
    "espera": Perfil(
        "espera",
        MODELO_ROTINA,
        "low",
        40_000,
        "acompanha estado externo e so acorda quando ha mudanca acionavel",
    ),
}

PALAVRAS_POR_TIPO = {
    "contrato": ("contrato", "openapi", "freeze", "api publica", "api pública"),
    "arquitetura": ("arquitetura", "fronteira", "codeowners", "infra", "pipeline"),
    "produto": ("produto", "comportamento", "checkout", "pagamento", "compra"),
    "revisao": ("revisar", "review", "revisor", "diff", "pr "),
    "escrita": ("registro", "armadilha", "fila", "livro", "escrivao", "escrivão"),
    "diagnostico": ("diagnostico", "diagnóstico", "medir", "investigar", "verificar"),
    "teste": ("teste", "pytest", "guarda", "mutacao", "mutação"),
    "texto": ("texto", "template", "portugues", "português", "copy"),
    "espera": ("esperar", "monitor", "deploy", "checks", "pouso"),
}


def perfil_por_tipo(tipo: str) -> Perfil:
    try:
        return PERFIS[tipo]
    except KeyError as exc:
        raise ErroDeInstrumentacao(
            "tipo de tarefa desconhecido",
            f"Tipo recebido: {tipo!r}\nTipos válidos: {', '.join(PERFIS)}",
        ) from exc


def classificar(texto: str) -> Perfil:
    baixo = " " + texto.lower() + " "
    for tipo, palavras in PALAVRAS_POR_TIPO.items():
        if any(palavra in baixo for palavra in palavras):
            return PERFIS[tipo]
    return PERFIS["produto"]


def _frontmatter(caminho: Path) -> dict[str, str]:
    texto = caminho.read_text(encoding="utf-8")
    if not texto.startswith("---\n"):
        raise ErroDeInstrumentacao(
            "ficha sem frontmatter",
            f"{caminho}: a ficha precisa começar com frontmatter YAML.",
        )
    fim = texto.find("\n---", 4)
    if fim == -1:
        raise ErroDeInstrumentacao(
            "frontmatter da ficha não fecha",
            f"{caminho}: faltou a linha final `---`.",
        )
    campos: dict[str, str] = {}
    for linha in texto[4:fim].splitlines():
        if not linha.strip() or ":" not in linha:
            continue
        chave, _, valor = linha.partition(":")
        campos[chave.strip()] = valor.strip()
    return campos


def auditar_fichas(raiz: Path) -> list[str]:
    pasta = raiz / ".claude" / "agents"
    if not pasta.is_dir():
        raise ErroDeInstrumentacao(
            "pasta de fichas não existe",
            f"Esperado: {pasta}\nSem fichas não há herança de modelo a auditar.",
        )
    falhas: list[str] = []
    for caminho in sorted(pasta.glob("*.md")):
        texto = caminho.read_text(encoding="utf-8")
        campos = _frontmatter(caminho)
        modelo = campos.get("model", "").strip()
        nome = campos.get("name") or caminho.stem
        relativo = caminho.relative_to(raiz).as_posix()
        if nome in {"revisor", "escrivao"} and not modelo:
            falhas.append(f"{relativo}: {nome} precisa declarar model")
        if nome in {"revisor", "escrivao"} and "opus" in modelo.lower():
            falhas.append(
                f"{relativo}: {nome} não usa modelo de topo para rito fechado"
            )
        if nome == "despacho" and not modelo and "modelo_recomendado" not in texto:
            falhas.append(
                f"{relativo}: despacho sem model só é aceito se o brief declarar modelo_recomendado"
            )
    return falhas


def _titulo_da_armadilha(caminho: Path) -> str:
    texto = caminho.read_text(encoding="utf-8")
    for linha in texto.splitlines():
        if linha.startswith("# "):
            return linha[2:].strip()
    return caminho.stem


def _resolver_armadilhas(raiz: Path, numeros: list[str]) -> list[str]:
    linhas: list[str] = []
    pasta = raiz / "armadilhas"
    for numero in numeros:
        if not re.fullmatch(r"\d{3}", numero):
            raise ErroDeInstrumentacao(
                "número de armadilha inválido",
                f"Recebido: {numero!r}. Use três dígitos, como 367.",
            )
        encontrados = sorted(pasta.glob(f"{numero}-*.md"))
        if not encontrados:
            raise ErroDeInstrumentacao(
                "armadilha citada não existe",
                f"Não encontrei arquivo para armadilhas/{numero}-*.md.",
            )
        caminho = encontrados[0]
        linhas.append(f"- armadilhas/{caminho.name}: {_titulo_da_armadilha(caminho)}")
    return linhas


def compilar_brief(
    raiz: Path,
    *,
    objetivo: str,
    tipo: str,
    celula: str,
    alvos: list[str],
    armadilhas: list[str],
) -> str:
    perfil = perfil_por_tipo(tipo)
    if not objetivo.strip():
        raise ErroDeInstrumentacao("objetivo vazio", "Brief sem objetivo vira adivinhação.")
    if not alvos:
        raise ErroDeInstrumentacao(
            "brief sem arquivos-alvo",
            "Declare ao menos um alvo. Sem cerca, o despacho vira exploração aberta.",
        )
    linhas_armadilhas = _resolver_armadilhas(raiz, armadilhas) if armadilhas else ["- nenhuma citada"]
    linhas = [
        "# Brief compilado",
        "",
        f"objetivo: {objetivo.strip()}",
        f"tipo: {perfil.tipo}",
        f"modelo_recomendado: {perfil.modelo}",
        f"esforco_recomendado: {perfil.esforco}",
        f"teto_de_contexto: {perfil.teto_contexto}",
        f"motivo_do_modelo: {perfil.motivo}",
        f"celula: {celula or 'ci'}",
        "",
        "## Arquivos-alvo",
        *[f"- {alvo}" for alvo in alvos],
        "",
        "## Armadilhas injetadas",
        *linhas_armadilhas,
        "",
        "## Prova exigida",
        "- Rode a suíte ou o teste focal que prova a mudança.",
        "- Se escrever guarda novo, faça a mutação e confirme vermelho.",
        "- FAIL corrige código; ERROR corrige instrumento ou ambiente.",
        "",
        "## Limite",
        "- Não leia documentação ampla sem gatilho do erro, caminho ou contrato.",
        "- Ao passar do teto de contexto, devolva handoff curto e pare a expansão.",
    ]
    return "\n".join(linhas) + "\n"


def cmd_rotear(args: argparse.Namespace) -> int:
    perfil = perfil_por_tipo(args.tipo) if args.tipo else classificar(args.texto or "")
    print(
        json.dumps(
            {
                "tipo": perfil.tipo,
                "modelo": perfil.modelo,
                "esforco": perfil.esforco,
                "teto_contexto": perfil.teto_contexto,
                "motivo": perfil.motivo,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    raiz = raiz_do_repo()
    texto = compilar_brief(
        raiz,
        objetivo=args.objetivo,
        tipo=args.tipo,
        celula=args.celula,
        alvos=args.alvo,
        armadilhas=args.armadilha,
    )
    if len(texto) > 8_000:
        raise ErroDeInstrumentacao(
            "brief compilado ficou grande demais",
            f"Tamanho: {len(texto)} caracteres. Corte alvo ou armadilha antes de despachar.",
        )
    if args.saida:
        Path(args.saida).write_text(texto, encoding="utf-8")
        print(f"gravei {args.saida} ({len(texto)} caracteres)")
    else:
        print(texto, end="")
    return 0


def cmd_auditar_fichas(args: argparse.Namespace) -> int:
    raiz = raiz_do_repo()
    falhas = auditar_fichas(raiz)
    if falhas:
        print("FAIL economia-fichas: herança cara ou brief sem modelo")
        for falha in falhas:
            print(f"  - {falha}")
        return 1
    print("PASS economia-fichas: fichas mecânicas declaram modelo e despacho exige brief roteado.")
    return 0


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    roteador = sub.add_parser("rotear")
    roteador.add_argument("--tipo", choices=sorted(PERFIS))
    roteador.add_argument("--texto", default="")
    roteador.set_defaults(func=cmd_rotear)

    brief = sub.add_parser("brief")
    brief.add_argument("--tipo", required=True, choices=sorted(PERFIS))
    brief.add_argument("--objetivo", required=True)
    brief.add_argument("--celula", default="ci")
    brief.add_argument("--alvo", action="append", default=[])
    brief.add_argument("--armadilha", action="append", default=[])
    brief.add_argument("--saida")
    brief.set_defaults(func=cmd_brief)

    fichas = sub.add_parser("auditar-fichas")
    fichas.set_defaults(func=cmd_auditar_fichas)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ErroDeInstrumentacao as erro:
        print(f"ERROR economia-da-fabrica: {erro.resumo}")
        if erro.detalhe:
            print(erro.detalhe)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
