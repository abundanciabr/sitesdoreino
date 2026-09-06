---
schema_version: 2
armadilha: 368
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/prestacao_de_contas.py
licao: "`stop_hook_active` verdadeiro diz só que já houve uma recusa neste fim de turno, não que ela foi ignorada. Toda decisão da segunda passada relê o transcript com a mesma régua da primeira; gritar pelo campo sozinho avisou errado em 32 de 50 vezes."
guarda:
  tipo: teste
  detector: ci/tests/test_prestacao_de_contas.py
sinal:
  - cobrado e terminou assim mesmo
---

# A segunda passada do gancho Stop gritava sem reler o transcript

**Data:** 06/09/2026 · **Onde:** `ci/prestacao_de_contas.py`, `modo_contas` · **Custo medido:** 32 avisos falsos em 50, na tela do mantenedor, em dois dias.

## Sintoma

O portão da prestação de contas recusa o fim do turno (exit 2), o robô obedece e escreve o relatório com os seis blocos e o veredito, e mesmo assim aparece na tela do mantenedor:

```
⚠️  PRESTAÇÃO DE CONTAS: o robô foi cobrado e terminou assim mesmo.
   O que você tem na tela pode não ser o relatório da tarefa.
```

No transcript, toda segunda execução do gancho Stop sai como `hook_non_blocking_error` com exit 1 e essa mensagem, tenha o relatório saído ou não.

## O que estava acontecendo

Quando um gancho Stop recusa, o harness deixa o robô continuar e chama o Stop de novo no fim, agora com `stop_hook_active: true`. O campo significa uma coisa só: "esta é a segunda passada, porque houve uma recusa". Ele não diz nada sobre o que o robô fez depois dela.

O gancho tratava o campo como prova de desobediência. Na primeira linha de `modo_contas`, se o campo era verdadeiro, devolvia exit 1 com o aviso, sem abrir o transcript. A intenção era certa (recusar de novo prenderia a sessão em laço), mas a leitura do campo estava errada.

Medição nos transcripts de `~/.claude/projects` (05 e 06/09/2026, o gancho nasceu em 05/09):

| | |
|---|---|
| recusas do Stop (exit 2) | 50 |
| segundas passadas com o aviso (exit 1) | 50 |
| dessas, com o relatório válido na tela | 32 |
| dessas, sem relatório | 18 |

Dois em cada três avisos eram falsos. Um aviso que sai também no caminho certo é um aviso que o mantenedor aprende a ignorar, e aí os 18 verdadeiros ficam mudos por dentro de um sinal que não significa mais nada. É a mesma doença do falso-verde, com a cor trocada.

## Como se cura

A segunda passada mede o transcript com a MESMA régua da primeira, a função `decidir()`. Relatório presente e válido: exit 0 em silêncio. Ainda faltando: exit 1 com o aviso. Nunca exit 2 na segunda passada, porque isso prenderia a sessão em laço. O campo `stop_hook_active` passa a decidir só entre recusar e gritar, e só QUANDO o relatório falta.

A regra geral, para qualquer gancho: **um campo que diz "X já aconteceu" não diz "X foi atendido".** Estado do harness é histórico; o resultado só está no transcript, e é lá que se mede.

## Como medir de novo

```bash
python - <<'EOF'
import json, glob, os, re, collections
V = re.compile(r"veredito[\s:*—–\-]*\b(n[ãa]o\s+pronto|pronto)\b", re.I)
c = collections.Counter()
for a in glob.glob(os.path.expanduser("~/.claude/projects/**/*.jsonl"), recursive=True):
    es = []
    for l in open(a, encoding="utf-8", errors="replace"):
        try: es.append(json.loads(l))
        except Exception: es.append(None)
    for i, e in enumerate(es):
        if not isinstance(e, dict) or e.get("type") != "system": continue
        if "cobrado e terminou assim mesmo" not in json.dumps(e.get("hookErrors") or "", ensure_ascii=False): continue
        t = next(("\n".join(b.get("text", "") for b in (x["message"]["content"]) if isinstance(b, dict) and b.get("type") == "text")
                  for x in reversed(es[:i]) if isinstance(x, dict) and x.get("type") == "assistant"
                  and isinstance((x.get("message") or {}).get("content"), list)), "")
        c["com relatório" if V.search(t) else "sem relatório"] += 1
print(dict(c))
EOF
```

Se "com relatório" for maior que zero depois desta correção, a régua da segunda passada divergiu da primeira: as duas têm de ser a mesma função.

## Guarda

`ci/tests/test_prestacao_de_contas.py`: `test_segunda_passada_com_o_relatorio_passa_calada` (nasceu vermelho contra o gancho anterior) e `test_segunda_passada_sem_o_relatorio_grita_sem_prender` (o par, que continua gritando com exit 1 e nunca 2).
