"""De onde vem o contexto de um despacho: base (sistema+brief), saidas de
ferramenta, e o que o proprio robo escreve. E quais leituras pesam mais
(bytes lidos x chamadas que ainda faltavam, porque cada chamada rele tudo)."""
import glob
import json
import os
import re
import statistics
import sys
import time
from collections import Counter

RAIZ = os.path.expanduser("~/.claude/projects")
DIAS = float(sys.argv[1]) if len(sys.argv) > 1 else 7
LIMITE = time.time() - DIAS * 86400
pastas = [p for p in glob.glob(os.path.join(RAIZ, "*")) if "sitesdoreino" in p or "-wt-" in p]

def alvo_do_comando(cmd):
    m = re.search(r"(?:cat|sed -n '[^']*'|sed -n \S+|head(?: -\S+)?|tail(?: -\S+)?)\s+\"?([\w./\\:-]+\.\w+)", cmd)
    return m.group(1) if m else None

base, fim, saidas, escritos, chamadas_l = [], [], [], [], []
peso = Counter()
freq = Counter()
for pasta in pastas:
    for path in glob.glob(os.path.join(pasta, "**", "subagents", "**", "agent-*.jsonl"), recursive=True):
        if os.path.getmtime(path) < LIMITE:
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            cabeca = f.read(4000).lower()
        if not ("despacho" in cabeca and ("brief" in cabeca or "rito" in cabeca or "tar-" in cabeca)):
            continue
        ctxs, ids, leituras = [], {}, []
        bytes_saida = bytes_escritos = 0
        with open(path, encoding="utf-8", errors="replace") as f:
            for linha in f:
                try:
                    d = json.loads(linha)
                except Exception:
                    continue
                m = d.get("message") or {}
                if d.get("type") == "assistant":
                    u = m.get("usage")
                    if u:
                        ctxs.append(u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0))
                    for b in m.get("content") or []:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "text":
                            bytes_escritos += len(b.get("text", ""))
                        elif b.get("type") == "tool_use":
                            inp = b.get("input") or {}
                            bytes_escritos += len(json.dumps(inp, ensure_ascii=False))
                            ids[b.get("id")] = b.get("name")
                            alvo = None
                            if b.get("name") == "Read":
                                alvo = inp.get("file_path")
                            elif b.get("name") in ("Bash", "PowerShell"):
                                alvo = alvo_do_comando(str(inp.get("command", "")))
                            if alvo:
                                alvo = re.sub(r"^.*?(sitesdoreino|wt-[\w-]+)[\\/]", "", alvo).replace("\\", "/")
                                leituras.append((len(ctxs), alvo, b.get("id")))
                elif d.get("type") == "user":
                    for b in m.get("content") or []:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            c = b.get("content")
                            t = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
                            bytes_saida += len(t)
                            for (n, alvo, tid) in leituras:
                                if tid == b.get("tool_use_id"):
                                    freq[alvo] += 1
                                    peso[alvo] += len(t) // 4 * max(0, 150 - n)
        if len(ctxs) < 5:
            continue
        base.append(ctxs[0]); fim.append(max(ctxs)); saidas.append(bytes_saida // 4); escritos.append(bytes_escritos // 4); chamadas_l.append(len(ctxs))

n = len(base)
print(f"despachos: {n}")
print(f"contexto na 1a chamada (sistema + ficha + brief): mediana {statistics.median(base):.0f} tokens")
print(f"contexto maximo: mediana {statistics.median(fim):.0f} tokens")
print(f"crescimento (max - base): mediana {statistics.median([f-b for f,b in zip(fim,base)]):.0f} tokens")
print(f"  saidas de ferramenta (bytes/4): mediana {statistics.median(saidas):.0f} tokens")
print(f"  o que o robo escreveu (texto + Edit/Write/comandos, bytes/4): mediana {statistics.median(escritos):.0f} tokens")
print(f"chamadas: mediana {statistics.median(chamadas_l):.0f}")
print("\nARQUIVOS MAIS PESADOS NA RELEITURA (tokens lidos x chamadas que ainda faltavam ate 150), top 25:")
tot = sum(peso.values()) or 1
for alvo, p in peso.most_common(25):
    print(f"  {p/1e6:6.1f}M  ({100*p/tot:4.1f}%)  lido {freq[alvo]:3}x  {alvo}")
print(f"\nsoma do peso de releitura de tudo que foi lido: {tot/1e6:.0f}M tokens em {n} despachos = {tot/1e6/n:.1f}M por despacho")
