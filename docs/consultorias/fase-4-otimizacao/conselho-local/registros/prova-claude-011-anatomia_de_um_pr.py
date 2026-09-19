"""Anatomia das chamadas de um PR: o que um despacho (e uma conversa de topo)
faz nas ~100-150 chamadas de cada PR. Somente leitura dos transcripts."""
import glob
import json
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict

RAIZ = os.path.expanduser("~/.claude/projects")
DIAS = float(sys.argv[1]) if len(sys.argv) > 1 else 7
LIMITE = time.time() - DIAS * 86400
pastas = [p for p in glob.glob(os.path.join(RAIZ, "*")) if "sitesdoreino" in p or "-wt-" in p]

CLASSES = [
    ("teste", re.compile(r"pytest|make (ci|celula|muralhas|testador|freeze)|ci/ci\.py|resumo_de_teste|provar_guardas")),
    ("git", re.compile(r"(^|[;&|\s])git\s")),
    ("gh", re.compile(r"(^|[;&|\s])gh\s")),
    ("make_pr", re.compile(r"make pr\b|ci/pr\.py")),
    ("sessao", re.compile(r"make sessao|ci/sessao\.py")),
    ("fila_reg", re.compile(r"ci/fila\.py|ci/reservar\.py|ci/divida_do_livro|painel/")),
    ("espera", re.compile(r"esperar\.py|Start-Sleep|sleep \d|mergear\.py")),
    ("consulta", re.compile(r"consultar_armadilhas|economia_da_fabrica|travessao\.py|indice_de_armadilhas")),
    ("leitura_shell", re.compile(r"(^|[;&|\s])(cat|sed -n|head|tail|grep|rg|ls|find|wc|type)\b")),
    ("python", re.compile(r"python")),
]

def classe(cmd):
    for nome, rx in CLASSES:
        if rx.search(cmd):
            return nome
    return "outro_shell"

def anatomia(path):
    ferramentas = Counter()
    classes = Counter()
    saida_por_ferramenta = Counter()
    chamadas = 0
    antes_pr = None
    reprovacoes = 0
    ids_para_nome = {}
    ultimo_texto = ""
    with open(path, encoding="utf-8", errors="replace") as f:
        for linha in f:
            try:
                d = json.loads(linha)
            except Exception:
                continue
            m = d.get("message") or {}
            if d.get("type") == "assistant":
                if m.get("usage"):
                    chamadas += 1
                for b in m.get("content") or []:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text":
                        ultimo_texto = b.get("text", "")[-400:]
                    if b.get("type") != "tool_use":
                        continue
                    nome = b.get("name", "?")
                    ferramentas[nome] += 1
                    ids_para_nome[b.get("id")] = nome
                    if nome in ("Bash", "PowerShell"):
                        cmd = str((b.get("input") or {}).get("command", ""))
                        c = classe(cmd)
                        classes[c] += 1
                        if antes_pr is None and (c == "make_pr" or "gh pr create" in cmd):
                            antes_pr = chamadas
            elif d.get("type") == "user":
                for b in m.get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        conteudo = b.get("content")
                        texto = conteudo if isinstance(conteudo, str) else json.dumps(conteudo, ensure_ascii=False)
                        nome = ids_para_nome.get(b.get("tool_use_id"), "?")
                        saida_por_ferramenta[nome] += len(texto)
                        if re.search(r"\bFAIL\b|REPROV|recus|exit code [1-9]|Error|Traceback", texto):
                            reprovacoes += 1
    return dict(chamadas=chamadas, ferramentas=ferramentas, classes=classes,
                saida=saida_por_ferramenta, antes_pr=antes_pr, reprovacoes=reprovacoes,
                teto=("max turns" in ultimo_texto.lower() or "maxTurns" in ultimo_texto or chamadas >= 148))

despachos = []
for pasta in pastas:
    for path in glob.glob(os.path.join(pasta, "**", "subagents", "**", "agent-*.jsonl"), recursive=True):
        if os.path.getmtime(path) < LIMITE:
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            cabeca = f.read(4000).lower()
        if "despacho" in cabeca and ("brief" in cabeca or "rito" in cabeca or "tar-" in cabeca):
            despachos.append(anatomia(path))

n = len(despachos)
print(f"DESPACHOS analisados: {n}")
tot_ferr = Counter()
tot_cls = Counter()
tot_saida = Counter()
for a in despachos:
    tot_ferr.update(a["ferramentas"]); tot_cls.update(a["classes"]); tot_saida.update(a["saida"])
soma = sum(tot_ferr.values())
print(f"\nchamadas de ferramenta por despacho (mediana): {statistics.median([sum(a['ferramentas'].values()) for a in despachos]):.0f}")
print("\nFERRAMENTA          chamadas   % do total   bytes de saida (% )")
tot_bytes = sum(tot_saida.values()) or 1
for nome, c in tot_ferr.most_common():
    print(f"{nome:18} {c:9} {100*c/soma:9.1f}%   {tot_saida[nome]/1e6:8.1f}MB ({100*tot_saida[nome]/tot_bytes:4.1f}%)")
print("\nCLASSE DO COMANDO DE SHELL   chamadas   por despacho (media)")
for nome, c in tot_cls.most_common():
    print(f"{nome:26} {c:9} {c/n:8.1f}")
com_pr = [a for a in despachos if a["antes_pr"] is not None]
print(f"\ndespachos que chegaram ao make pr / gh pr create: {len(com_pr)} de {n}")
if com_pr:
    print(f"  chamadas ATE o primeiro pedido de PR: mediana {statistics.median([a['antes_pr'] for a in com_pr]):.0f}")
    print(f"  chamadas DEPOIS do primeiro pedido de PR: mediana {statistics.median([a['chamadas']-a['antes_pr'] for a in com_pr]):.0f}, media {statistics.mean([a['chamadas']-a['antes_pr'] for a in com_pr]):.0f}")
print(f"\ndespachos que bateram no teto de turnos (>=148 chamadas ou texto de max turns): {sum(1 for a in despachos if a['teto'])} de {n}")
print(f"resultados de ferramenta com cara de reprovacao/erro por despacho: mediana {statistics.median([a['reprovacoes'] for a in despachos]):.0f}, media {statistics.mean([a['reprovacoes'] for a in despachos]):.1f}")
