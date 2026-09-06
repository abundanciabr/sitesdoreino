---
schema_version: 2
armadilha: 367
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - .claude/agents/
licao: Ficha de sub-agente SEM `model:` no frontmatter herda o modelo da maestro, que é o mais caro. Escolha o modelo na ficha (rito fixo) ou no disparo (tarefa a tarefa); herdar não é decisão, é omissão que aparece só na conta.
guarda:
  tipo: teste
  detector: ci/tests/test_fichas_de_robo.py
  motivo: o teste segura só a ficha do escrivão (que preenche molde). O modelo que a maestro pede a cada despacho não tem mecanismo nenhum, porque nada no CI vê qual modelo uma sessão pediu
sinal:
  - 47% da semana
  - cota semanal
  - herdado=Opus
---

# Sub-agente sem `model` herda o modelo mais caro, e a conta só aparece no fim da semana

**Data:** 06/09/2026 · **Onde:** `.claude/agents/`, medido nos transcripts de 05 e 06/09 · **Custo medido:** o mantenedor consumiu 47% da cota semanal em 36 horas e achou que tinha pedido "umas 10 tarefas simples".

## Sintoma

O painel de uso do plano marca 47% da semana consumidos num domingo de manhã, com a semana tendo reiniciado no sábado. O mantenedor não reconhece o próprio consumo: na cabeça dele foram poucas tarefas, e simples.

## O que estava acontecendo

Duas coisas ao mesmo tempo, e nenhuma era desperdício óbvio.

A primeira é que o trabalho era real: 165 falas dele viraram **124 PRs mergeados** em 36 horas, pela lei "Todo pedido do mantenedor é um lote". O consumo comprou produto.

A segunda é o preço unitário, e aí estava o buraco. A medição dos transcripts (`~/.claude/projects/**/*.jsonl`, campo `message.usage`):

- **19.708 chamadas ao modelo**, com contexto **mediano de 198k** e médio de 249k.
- **97,7% de toda a entrada é releitura de contexto.** Rodar `ls` numa sessão de 250k custa 250k.
- **3.401 chamadas com contexto acima de 400k queimaram 38% da semana.** A maior sessão começou em 78k e terminou em 967k fazendo o mesmo tipo de trabalho: doze vezes mais cara no fim, pela mesma entrega.
- **53 dos 81 sub-agentes rodaram no modelo mais caro sem ninguém ter escolhido**, porque `Agent` sem o parâmetro `model` e ficha sem `model:` no frontmatter **herdam o modelo da maestro**.

A herança é o que engana: ela não aparece em lugar nenhum. Não há log, não há aviso, e o resultado do sub-agente é bom, então nada chama atenção. A conta chega uma vez por semana, agregada, sem dizer de onde veio.

## Como se cura

**Escolha o modelo, sempre.** Ficha cujo rito é fixo declara no frontmatter (`model: sonnet` no `escrivao`, que só preenche molde). Tarefa que varia, a maestro escolhe no disparo: `model: "sonnet"` para rotina (registro, armadilha, texto de tela, teste, rota, semente) e o de cima para arquitetura, contrato e código novo de produto.

**Na dúvida, o modelo de cima.** Um PR de conserto custa cerca de 40 milhões de tokens, que é a economia de cinco despachos baratos. Economizar no lugar errado sai mais caro que não economizar.

**E vigie o tamanho da conversa, não só o modelo.** Passando de ~300k de contexto, cada comando custa o triplo pela mesma entrega. Sessão longa é a maior das três sangrias, e é a que ninguém enxerga porque cresce devagar.

## Como medir de novo

```bash
python - <<'EOF'
import json, glob, os, collections
faixas = collections.Counter()
for a in glob.glob(os.path.expanduser("~/.claude/projects/**/*.jsonl"), recursive=True):
    for linha in open(a, encoding="utf-8", errors="replace"):
        if '"usage"' not in linha:
            continue
        try:
            u = (json.loads(linha).get("message") or {}).get("usage") or {}
        except Exception:
            continue
        ctx = sum(u.get(k, 0) or 0 for k in
                  ("cache_read_input_tokens", "cache_creation_input_tokens", "input_tokens"))
        faixas[min(int(ctx / 100000) * 100, 500)] += ctx + (u.get("output_tokens", 0) or 0)
for k in sorted(faixas):
    print(f"contexto {k:3}k+ : {faixas[k]/1_000_000:8.0f}M tokens")
EOF
```

Se a linha `400k+` somada à `500k+` passar de um terço do total, a sangria é conversa longa, não modelo.

## Lei

`CLAUDE.md`, seção "O que uma chamada custa (desde 06/09/2026)". A decisão foi do mantenedor, em pergunta estruturada, em 06/09/2026.

**Isto não é corte de escopo.** Os 124 PRs eram trabalho legítimo, e a lei "feito completo" continua inteira. O que muda é o preço de cada chamada, nunca a ambição.
