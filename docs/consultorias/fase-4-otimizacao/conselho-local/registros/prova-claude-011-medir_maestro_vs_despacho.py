"""Mede, nos transcripts locais do Claude Code (todas as pastas de projeto do
sitesdoreino e das bancadas wt-*), o custo de uma conversa de topo (maestro)
contra o custo de um sub-agente (despacho/revisor/escrivao/outro).
Somente leitura. Saida em texto."""
import glob
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict

RAIZ = os.path.expanduser("~/.claude/projects")
DIAS = float(sys.argv[1]) if len(sys.argv) > 1 else 7
LIMITE = time.time() - DIAS * 86400

pastas = [p for p in glob.glob(os.path.join(RAIZ, "*"))
          if "sitesdoreino" in p or "-wt-" in p]

def ler(path):
    """Devolve (chamadas_dedup, max_ctx, total_tokens, modelos, prs_criados,
    disparos_agent, sistema_prefixo)."""
    usos = {}
    modelos = Counter()
    prs = 0
    disparos = []
    primeiro_texto = ""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for linha in f:
                try:
                    d = json.loads(linha)
                except Exception:
                    continue
                m = d.get("message") or {}
                if d.get("type") == "user" and not primeiro_texto:
                    c = m.get("content")
                    if isinstance(c, str):
                        primeiro_texto = c[:300]
                    elif isinstance(c, list):
                        for b in c:
                            if isinstance(b, dict) and b.get("type") == "text":
                                primeiro_texto = b.get("text", "")[:300]
                                break
                if d.get("type") != "assistant":
                    continue
                u = m.get("usage")
                mid = m.get("id") or d.get("uuid")
                if u:
                    usos[mid] = u
                    modelos[m.get("model", "?")] += 1
                for b in m.get("content") or []:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    nome = b.get("name", "")
                    inp = b.get("input") or {}
                    if nome in ("Bash", "PowerShell"):
                        cmd = str(inp.get("command", ""))
                        if "gh pr create" in cmd or "make pr " in cmd or "ci/pr.py" in cmd:
                            prs += 1
                    if nome in ("Agent", "Task"):
                        disparos.append((inp.get("subagent_type", "?"), inp.get("model")))
    except OSError:
        return None
    if not usos:
        return None
    ctx = [(u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
            + u.get("cache_creation_input_tokens", 0)) for u in usos.values()]
    total = sum(c + u.get("output_tokens", 0) for c, u in zip(ctx, usos.values()))
    return dict(chamadas=len(usos), max_ctx=max(ctx), media_ctx=int(statistics.mean(ctx)),
                total=total, modelos=modelos, prs=prs, disparos=disparos,
                texto=primeiro_texto)

topo, subs = [], []
for pasta in pastas:
    for path in glob.glob(os.path.join(pasta, "*.jsonl")):
        if os.path.getmtime(path) < LIMITE:
            continue
        r = ler(path)
        if r:
            r["arquivo"] = os.path.basename(path)[:8]
            r["pasta"] = os.path.basename(pasta)[-30:]
            topo.append(r)
    for path in glob.glob(os.path.join(pasta, "**", "subagents", "**", "agent-*.jsonl"), recursive=True):
        if os.path.getmtime(path) < LIMITE:
            continue
        r = ler(path)
        if r:
            r["arquivo"] = os.path.basename(path)[:14]
            r["pasta"] = os.path.basename(pasta)[-30:]
            t = r["texto"].lower()
            r["papel"] = ("despacho" if "despacho" in t and ("brief" in t or "rito" in t or "tar-" in t)
                          else "revisor" if "revis" in t else "escrivao" if "escriv" in t else "outro")
            subs.append(r)

def modelo_pred(c):
    return c.most_common(1)[0][0] if c else "?"

print(f"JANELA: ultimos {DIAS:g} dias | pastas de projeto olhadas: {len(pastas)}")
print(f"\n== CONVERSAS DE TOPO (n={len(topo)}) ==")
print(f"{'sessao':8} {'pasta':30} {'chamadas':>8} {'max_ctx':>8} {'media':>7} {'tokens(M)':>10} {'PRs':>4} {'Agent':>5} modelo")
for r in sorted(topo, key=lambda x: -x["total"]):
    print(f"{r['arquivo']:8} {r['pasta']:30} {r['chamadas']:8} {r['max_ctx']:8} {r['media_ctx']:7} {r['total']/1e6:10.1f} {r['prs']:4} {len(r['disparos']):5} {modelo_pred(r['modelos'])}")

com_pr = [r for r in topo if r["prs"] > 0]
sem_despacho = [r for r in com_pr if not any(d[0] == "despacho" for d in r["disparos"])]
print(f"\nconversas de topo que abriram PR: {len(com_pr)}; dessas, SEM nenhum despacho disparado: {len(sem_despacho)}")
if com_pr:
    tot_prs = sum(r["prs"] for r in com_pr)
    tot_tok = sum(r["total"] for r in com_pr)
    print(f"PRs abertos por conversas de topo: {tot_prs}; tokens dessas conversas: {tot_tok/1e6:.0f}M; tokens por PR (bruto): {tot_tok/tot_prs/1e6:.1f}M")
    print(f"mediana de chamadas por conversa com PR: {statistics.median([r['chamadas'] for r in com_pr])}")
    print(f"mediana do contexto maximo: {statistics.median([r['max_ctx'] for r in com_pr])}")

print(f"\n== SUB-AGENTES (n={len(subs)}) ==")
por_papel = defaultdict(list)
for r in subs:
    por_papel[r["papel"]].append(r)
for papel, lista in por_papel.items():
    ch = [r["chamadas"] for r in lista]
    mx = [r["max_ctx"] for r in lista]
    tk = [r["total"] for r in lista]
    print(f"{papel:9} n={len(lista):3} chamadas mediana={statistics.median(ch):.0f} max={max(ch)} | "
          f"ctx max mediana={statistics.median(mx):.0f} | tokens mediana={statistics.median(tk)/1e6:.1f}M media={statistics.mean(tk)/1e6:.1f}M max={max(tk)/1e6:.1f}M | "
          f"PRs={sum(r['prs'] for r in lista)} | modelos={Counter(modelo_pred(r['modelos']) for r in lista).most_common(3)}")
desp = por_papel.get("despacho", [])
desp_pr = [r for r in desp if r["prs"] > 0]
if desp_pr:
    print(f"\ndespachos que abriram PR: {len(desp_pr)}; tokens por despacho-com-PR: mediana {statistics.median([r['total'] for r in desp_pr])/1e6:.1f}M, media {statistics.mean([r['total'] for r in desp_pr])/1e6:.1f}M")
    for r in sorted(desp_pr, key=lambda x: -x["total"])[:12]:
        print(f"  {r['arquivo']:14} {r['pasta']:30} chamadas={r['chamadas']:4} max_ctx={r['max_ctx']:7} tokens={r['total']/1e6:6.1f}M PRs={r['prs']} {modelo_pred(r['modelos'])}")
