"""MÉTRICAS DA FÁBRICA — "está apodrecendo?" vira número.

Onda 6 do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md` (P13 e B14). O
diagnóstico da consultoria foi direto: *"vocês estão voando sem instrumento"*.
O projeto media a saúde de cada MUDANÇA (testes, muralhas, portões) e não media
a saúde da FÁBRICA — se ela está ficando mais lenta, mais retrabalhosa, mais
dependente do dono. Sem número, "está apodrecendo?" só tem resposta por
impressão, e impressão de quem está dentro é a pior fonte que existe.

AS QUATRO MEDIDAS, e por que estas
-----------------------------------
1. **Tempo de pouso** (mediana): do PR aberto ao merge. É o relógio do ciclo
   inteiro. Se subir, alguma coisa na esteira está engasgando.
2. **Retrabalho**: quantos pushes um PR precisou depois do primeiro. Foi a dor
   medida em 28/08 — oito voltas num PR de quatro arquivos (`armadilhas/156`).
   É o número que a pista de pouso existe para derrubar.
3. **Devoluções da pista**: PRs que pediram pouso e voltaram reprovados. Taxa
   alta = a catraca está pegando trabalho quebrado cedo (bom) ou a esteira está
   implicando com trabalho são (ruim) — o número sozinho não decide, mas sem
   ele ninguém nem pergunta.
4. **Pedidos ao dono** (B14): quantos registros do livro esperam resposta dele.
   **O mantenedor é o único recurso do projeto que não escala**, e esta é a
   única medida aqui que fala de uma pessoa, não de máquina.

O QUE ELE NÃO FAZ, de propósito
-------------------------------
**Não reprova nada.** Métrica que reprova vira meta, e meta vira gente
otimizando o número em vez do trabalho. Ele mede e mostra; a decisão continua
humana.

**Não guarda estado.** Cada execução mede o presente, direto do GitHub e do
livro. Um arquivo de histórico aqui seria uma segunda fonte de verdade sobre
fatos que o GitHub já guarda — e a lei anti-duplicação do `CLAUDE.md` existe
porque essa segunda fonte SEMPRE diverge (`PLANO-10X`, o painel que mentia).

Uso:

    python ci/metricas_da_fabrica.py            # últimos 7 dias
    python ci/metricas_da_fabrica.py --dias 30

Exit codes: 0 medi e mostrei · 2 ERROR (não consegui medir; nunca "está tudo
bem"). Não existe exit 1: este arquivo não julga.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    executar,
    raiz_do_repo,
)

DIAS_PADRAO = 7
ETIQUETA_DE_POUSO = "pousar"

# Teto da AMOSTRA usada para medir tempos — nunca a contagem de entregas. O
# campo `commits` é caro no GraphQL do GitHub, e acima disto a consulta inteira
# é recusada. Quem conta entregas é o Git (ver `coletar`).
TETO_DA_AMOSTRA = 40


# Claude Code persiste Message.usage por bloco da mesma mensagem. Os snapshots
# são cumulativos: https://platform.claude.com/docs/en/build-with-claude/streaming
# input_tokens exclui os dois caches; cache_creation e iterations são detalhes,
# não parcelas adicionais. A consolidação não audita cobrança nem assinatura.
CAMPOS_USO = {
    "entrada_nova": "input_tokens", "leitura_cache": "cache_read_input_tokens",
    "escrita_cache": "cache_creation_input_tokens", "saida": "output_tokens",
}


def consolidar_uso(arquivos: list[Path]) -> dict:
    """Reconstrói uso Claude Code por origem/sessão/mensagem/modelo, sem texto.

    Caminho não participa da identidade: uma exportação sobreposta é a mesma
    origem. Formatos incrementais, SSE cru e outras origens não são somados.
    As somas são apenas da parcela conhecida; cobertura é por campo/mensagem.
    """
    mensagens = {}
    ferramentas = set()
    cobertura = dict(arquivos=0, arquivos_ilegiveis=0, linhas_invalidas=0,
                    registros=0, snapshots_consolidados=0, sem_identidade=0,
                    incompativeis=0, campos_invalidos=0, ferramentas_sem_id=0)
    for arquivo in sorted({Path(p).resolve() for p in arquivos}):
        cobertura["arquivos"] += 1
        try:
            with arquivo.open(encoding="utf-8-sig") as entrada:
                for linha in entrada:
                    if not linha.strip():
                        continue
                    try:
                        evento = json.loads(linha)
                    except ValueError:
                        cobertura["linhas_invalidas"] += 1
                        continue
                    if not isinstance(evento, dict):
                        cobertura["linhas_invalidas"] += 1
                        continue
                    mensagem = evento.get("message")
                    if not isinstance(mensagem, dict) or mensagem.get("role") != "assistant":
                        if "usage" in evento or evento.get("type") in ("message_start", "message_delta", "event_msg"):
                            cobertura["incompativeis"] += 1
                        continue
                    cobertura["registros"] += 1
                    if evento.get("type") != "assistant" or evento.get("usage_mode", "cumulative") != "cumulative":
                        cobertura["incompativeis"] += 1
                        continue
                    chave = ("claude-code", evento.get("sessionId"), mensagem.get("id"), mensagem.get("model"))
                    if not all(isinstance(v, str) and v for v in chave):
                        cobertura["sem_identidade"] += 1
                        continue
                    if chave in mensagens:
                        cobertura["snapshots_consolidados"] += 1
                    uso = mensagens.setdefault(chave, {c: None for c in CAMPOS_USO})
                    bruto = mensagem.get("usage")
                    if not isinstance(bruto, dict):
                        cobertura["campos_invalidos"] += 1
                        bruto = {}
                    for campo, origem in CAMPOS_USO.items():
                        valor = bruto.get(origem)
                        if valor is None:
                            continue
                        if type(valor) is not int or valor < 0:
                            cobertura["campos_invalidos"] += 1
                            continue
                        uso[campo] = max(uso[campo], valor) if uso[campo] is not None else valor
                    conteudo = mensagem.get("content")
                    if isinstance(conteudo, list):
                        for bloco in conteudo:
                            if not isinstance(bloco, dict) or bloco.get("type") != "tool_use":
                                continue
                            if not isinstance(bloco.get("id"), str) or not bloco["id"]:
                                cobertura["ferramentas_sem_id"] += 1
                                continue
                            ferramentas.add((chave[0], chave[1], bloco["id"]))
        except (OSError, UnicodeError):
            cobertura["arquivos_ilegiveis"] += 1
    tokens = {}
    cobertura["campos"] = {}
    for campo in CAMPOS_USO:
        valores = [m[campo] for m in mensagens.values() if m[campo] is not None]
        tokens[campo] = sum(valores) if valores else None
        cobertura["campos"][campo] = dict(conhecidas=len(valores), mensagens=len(mensagens))
    cobertura["incompleta"] = not mensagens or any(
        cobertura[c] for c in ("arquivos_ilegiveis", "linhas_invalidas", "sem_identidade",
                              "incompativeis", "campos_invalidos", "ferramentas_sem_id")
    ) or any(c["conhecidas"] < len(mensagens) for c in cobertura["campos"].values())
    return dict(metodo="reconstrução de snapshots cumulativos; não audita cobrança",
                mensagens=len(mensagens), chamadas_modelo=None,
                ferramentas=len(ferramentas), tokens=tokens, cobertura=cobertura)


def consolidar_percurso(eventos: list[dict]) -> dict:
    """Observações distintas por tentativa e revisão, sem inferir aprovação."""
    from telemetria import FASES, identidade_fase

    unicos = {}
    invalidos = 0
    antigos = 0
    campos = ("quando", "tarefa", "tentativa", "branch", "commit", "pr", "fase",
              "resultado", "contexto_bytes")
    for evento in eventos:
        if not isinstance(evento, dict) or evento.get("evento") != "fase_operacional":
            antigos += 1
            continue
        identidade = identidade_fase(evento)
        if identidade is None or identidade != evento.get("id"):
            invalidos += 1
            continue
        try:
            quando = _quando(evento["quando"])
            if quando.tzinfo is None:
                raise ValueError("timestamp sem fuso")
        except (ValueError, TypeError, KeyError):
            invalidos += 1
            continue
        linha = {c: evento.get(c) for c in campos}
        linha["quando"] = quando.astimezone(timezone.utc).isoformat()
        anterior = unicos.get(evento["id"])
        if anterior is None or linha["quando"] < anterior["quando"]:
            unicos[evento["id"]] = linha
    linhas = sorted(unicos.values(), key=lambda e: (e["quando"], e["tarefa"], e["tentativa"], e["fase"], e["resultado"]))
    return dict(tarefas=len({e["tarefa"] for e in linhas}),
                tentativas=len({(e["tarefa"], e["tentativa"]) for e in linhas}),
                eventos=linhas,
                publicacoes_verificadas=sum(e["fase"] == "publicacao" and e["resultado"] == "verificado" for e in linhas),
                cobertura=dict(eventos_invalidos=invalidos, eventos_sem_correlacao=antigos,
                               fases_ausentes=[f for f in FASES if not any(e["fase"] == f for e in linhas)]))


def _gh_json(args: list[str], raiz: Path, descricao: str):
    """Consulta o GitHub e devolve JSON — ou levanta. Nunca devolve [] por erro.

    A distinção que este projeto já pagou caro para aprender: "a lista veio
    vazia" e "não consegui perguntar" são fatos diferentes.
    """
    saida = executar(
        ["gh", *args], cwd=raiz, descricao=descricao, exigir_stdout=True
    ).stdout
    try:
        return json.loads(saida)
    except json.JSONDecodeError as erro:
        raise ErroDeInstrumentacao(
            f"{descricao}: o GitHub respondeu algo que não é JSON",
            f"Primeiros 300 caracteres:\n{saida[:300]}\n\n{erro}",
        ) from erro


def _quando(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def coletar(raiz: Path, dias: int, agora: datetime | None = None) -> dict:
    """Mede tudo. Qualquer falha interrompe — não existe medida parcial."""
    agora = agora or datetime.now(timezone.utc)
    corte = agora - timedelta(days=dias)

    # A CONTAGEM VEM DO GIT — exata, local, sem teto. A lição é de hoje de
    # manhã (registro 20260828-077): o boletim anunciava "40" num dia de 98
    # porque somava o tamanho da própria lista limitada. Aqui o mesmo erro
    # apareceu na primeira execução — a consulta com `commits` estoura o
    # orçamento do GraphQL acima de ~40 PRs — e a resposta certa não é baixar o
    # teto e chamar de total: é contar noutro lugar.
    contagem = executar(
        [
            "git",
            "rev-list",
            "--count",
            "--first-parent",
            f"--since={dias} days ago",
            "origin/main",
        ],
        cwd=raiz,
        descricao="contar as entregas que pousaram na janela",
        exigir_stdout=True,
    ).stdout.strip()
    if not contagem.isdigit():
        raise ErroDeInstrumentacao(
            "não consegui contar as entregas da janela",
            f"`git rev-list --count --first-parent` devolveu: {contagem!r}",
        )
    pousos = int(contagem)

    # A AMOSTRA, para os tempos. `commits` é o campo caro: com 100 PRs o GitHub
    # recusa a consulta inteira ("exceeds the maximum limit of 500,000 nodes").
    # Ela é amostra POR CONSTRUÇÃO, e o texto diz isso — nunca vira o total.
    mergeados = _gh_json(
        [
            "pr",
            "list",
            "--state",
            "merged",
            "--limit",
            str(TETO_DA_AMOSTRA),
            "--json",
            "number,title,createdAt,mergedAt,commits",
        ],
        raiz,
        "amostrar os PRs mergeados",
    )
    janela = [
        pr
        for pr in mergeados
        if pr.get("mergedAt") and _quando(pr["mergedAt"]) >= corte
    ]

    minutos = [
        (_quando(pr["mergedAt"]) - _quando(pr["createdAt"])).total_seconds() / 60
        for pr in janela
    ]
    # O retrabalho aparece como COMMITS além do primeiro: cada volta de "a base
    # envelheceu, atualiza e empurra de novo" deixa um commit a mais. É uma
    # aproximação, e está dita como tal — o número exato de pushes exigiria a
    # API de eventos, que é paginada e cara.
    commits = [len(pr.get("commits") or []) for pr in janela]

    devolvidos = _gh_json(
        [
            "pr",
            "list",
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "number,labels",
        ],
        raiz,
        "listar os PRs abertos",
    )
    na_fila = [
        pr
        for pr in devolvidos
        if any(r.get("name") == ETIQUETA_DE_POUSO for r in pr.get("labels") or [])
    ]

    return {
        "dias": dias,
        "pousos": pousos,
        "amostra": len(janela),
        "minutos": minutos,
        "commits": commits,
        "na_fila": len(na_fila),
        "abertos": len(devolvidos),
        "pedidos_ao_dono": pedidos_ao_dono(raiz),
        "leis_sem_mecanismo": leis_sem_mecanismo(raiz),
    }


# O leitor do livro, em JavaScript, porque a REGRA é de lá.
#
# Ele carrega cada registro do jeito que o painel carrega (é código JS, e só um
# motor JS o lê sem inventar), e depois pergunta o tamanho da fila a
# `painel/logica.js::caixaDeEntrada` — a MESMA função que desenha a caixa
# "Precisa de você" na tela do mantenedor.
_CONTAR_PEDIDOS = """
var fs = require('fs'), path = require('path'), vm = require('vm');
var raiz = process.cwd();   // executar() roda com cwd = raiz do repo
var LOGICA = require(path.join(raiz, 'painel', 'logica.js'));
var dir = path.join(raiz, 'painel', 'registros');
var regs = [];
fs.readdirSync(dir).filter(function (n) { return n.slice(-3) === '.js'; })
  .sort().forEach(function (n) {
    var caixa = { window: {} };
    vm.runInNewContext(fs.readFileSync(path.join(dir, n), 'utf8'), caixa,
                       { timeout: 5000 });
    (caixa.window.REGISTROS || []).forEach(function (r) { regs.push(r); });
  });
if (!regs.length) { throw new Error('nenhum registro carregado'); }
process.stdout.write(String(LOGICA.caixaDeEntrada(regs, new Date()).length));
"""


def pedidos_ao_dono(raiz: Path) -> int:
    """Pedidos do livro esperando resposta — a fila de UMA pessoa (B14).

    A regra é a do painel, e é a do painel LITERALMENTE: esta função chama
    `painel/logica.js::caixaDeEntrada`, a mesma que desenha a caixa "Precisa de
    você". Duas medidas da mesma coisa não podem discordar quando só existe uma.

    POR QUE ISTO MUDOU (auditoria das Ondas 3 a 6, 29/08/2026)
    ----------------------------------------------------------
    Até aqui esta função não LIA o livro: ela procurava o texto
    `precisa_do_dono: true` DENTRO do arquivo. Um registro gravado com as chaves
    entre aspas — `"precisa_do_dono": true`, forma que o livro aceita sem
    reclamar — não casava com nenhuma das variações procuradas, e o pedido
    simplesmente não era contado. Medido: o Python dizia 6 e o painel dizia 7.

    O guarda `test_a_fila_do_dono_bate_com_a_do_painel` pegou, e é por isso que
    ele existe. Mas comparar duas implementações só descobre a divergência
    DEPOIS que ela aparece; ter uma implementação só a torna impossível — que é
    o que a lei anti-duplicação do `CLAUDE.md` pede desde sempre.

    Sem Node isto é ERROR, nunca um número: um contador que chuta a fila do
    mantenedor é pior que um contador que se cala.
    """
    pasta = raiz / "painel" / "registros"
    if not pasta.is_dir():
        raise ErroDeInstrumentacao(
            "painel/registros/ não existe",
            "Sem o livro não dá para medir a fila do mantenedor.",
        )
    if not (raiz / "painel" / "logica.js").is_file():
        raise ErroDeInstrumentacao(
            "painel/logica.js não existe",
            "A regra da caixa 'Precisa de você' mora lá. Sem ela, contar aqui "
            "seria inventar uma segunda regra — exatamente o que causou a "
            "divergência de 29/08/2026.",
        )
    saida = executar(
        ["node", "-e", _CONTAR_PEDIDOS],
        cwd=raiz,
        descricao="contar a fila do mantenedor pela regra do painel",
        exigir_stdout=True,
    ).stdout.strip()
    if not saida.isdigit():
        raise ErroDeInstrumentacao(
            "o contador da fila não devolveu um número",
            f"Recebido:\n  {saida!r}\n\nSem número não há medida, e 'não sei' "
            "nunca vira zero.",
        )
    return int(saida)


def leis_sem_mecanismo(raiz: Path) -> int:
    """Quantas regras ninguém faz valer — o censo da Onda 6, reusado."""
    caminho = raiz / "ci" / "leis-sem-mecanismo.txt"
    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError as exc:
        raise ErroDeInstrumentacao(
            "ci/leis-sem-mecanismo.txt ilegível", str(exc)
        ) from exc
    return len(
        [
            linha
            for linha in texto.splitlines()
            if linha.strip() and not linha.strip().startswith("#")
        ]
    )


def montar(dados: dict) -> str:
    """Rende o boletim de saúde. Sem dados, não inventa linha."""
    faltando = [c for c in ("pousos", "minutos", "commits") if c not in dados]
    if faltando:
        raise ErroDeInstrumentacao(
            "medida incompleta — não vou imprimir meia-verdade",
            "Campos ausentes: " + ", ".join(faltando),
        )

    linhas = [
        "",
        "=" * 72,
        f"SAÚDE DA FÁBRICA — últimos {dados['dias']} dia(s)",
        "=" * 72,
        "",
    ]

    if not dados["amostra"]:
        linhas += [
            "Nenhuma entrega pousou na janela. Isto não é 'tudo bem' nem 'tudo",
            "mal' — é ausência de dado. Amplie a janela (--dias) ou volte depois.",
            "",
        ]
    else:
        mediana = statistics.median(dados["minutos"])
        pior = max(dados["minutos"])
        media_commits = statistics.mean(dados["commits"])
        retrabalho = [c for c in dados["commits"] if c > 2]
        linhas += [
            f"POUSOS                {dados['pousos']} entrega(s) — contadas no Git",
            f"TEMPO DE POUSO        mediana {mediana:.0f} min · pior {pior:.0f} min",
            f"                      (do PR aberto ao merge; amostra de "
            f"{dados['amostra']} PR(s))",
            f"RETRABALHO            média de {media_commits:.1f} commit(s) por PR;"
            f" {len(retrabalho)} PR(s) com mais de 2",
            "                      (cada volta de 'a base envelheceu' deixa um commit)",
            "",
        ]

    linhas += [
        f"NA FILA DA PISTA      {dados['na_fila']} de {dados['abertos']} PR(s) abertos",
        f"PEDIDOS AO DONO       {dados['pedidos_ao_dono']} esperando resposta dele",
        "                      (é o único recurso do projeto que não escala)",
        f"LEIS SEM MECANISMO    {dados['leis_sem_mecanismo']} regra(s) que ninguém faz valer",
        "",
        "Este arquivo MEDE e não julga: nenhum destes números reprova nada.",
        "Métrica que reprova vira meta, e meta vira gente otimizando o número.",
        "=" * 72,
        "",
    ]
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="Métricas da fábrica (Onda 6)")
    parser.add_argument("--dias", type=int, default=DIAS_PADRAO)
    parser.add_argument("--local", action="store_true", help="percurso observado no Git comum, sem consultar GitHub")
    parser.add_argument("--transcricoes", nargs="+", type=Path,
                        help="JSONL Claude Code locais; consolida somente metadados de uso")
    args = parser.parse_args(argv)
    if args.dias < 1:
        print("ERROR: --dias precisa ser >= 1.")
        return 2
    try:
        raiz = raiz_do_repo()
        if args.local or args.transcricoes:
            from telemetria import dir_git_comum, ler_tudo
            git = dir_git_comum(raiz)
            leitura = {}
            eventos = ler_tudo(git, cobertura=leitura) if git else []
            dados = {"percurso": consolidar_percurso(eventos)}
            dados["percurso"]["cobertura"]["git_disponivel"] = git is not None
            dados["percurso"]["cobertura"]["leitura"] = leitura
            if args.transcricoes:
                dados["uso"] = consolidar_uso(args.transcricoes)
            print(json.dumps(dados, ensure_ascii=False, indent=2))
        else:
            print(montar(coletar(raiz, args.dias)))
    except ErroDeInstrumentacao as erro:
        print("\nPAROU POR SEGURANÇA — as métricas NÃO foram impressas.\n")
        print(f"  {erro.resumo}")
        if erro.detalhe:
            print(f"\n{erro.detalhe}")
        print(
            "\nIsto não é 'a fábrica está bem': é não saber. Meia-medida sobre "
            "saúde\nengana mais que medida nenhuma.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
