---
schema_version: 2
armadilha: 555
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  dono: ci/tests/test_economia_da_fabrica.py
sinal:
  - "Agent type not found"
  - "mapping values are not allowed here"
gatilho:
  - .claude/agents/
  - ci/economia_da_fabrica.py
licao: "Ficha em .claude/agents com ': ' ou ' #' na description sem aspas não abre como YAML, e o Claude Code a descarta sem aviso: o Agent responde 'Agent type not found'. Ponha o valor entre aspas. auditar-fichas lê o frontmatter como o harness lê e reprova o caso."
---

# 555: Ficha com dois-pontos na `description` some do Agent

**Data:** 27/09/2026 · **Onde:** `.claude/agents/` · **Custo por queda:** a
ficha inteira fica inútil sem aviso; `conferente`, `adversario` e `provador`
ficaram nove dias fora do Agent (18/09 a 27/09/2026).

## Sintoma

A ficha existe na pasta, a muralha dos sub-agentes aprova a chamada, e o Agent
responde "Agent type not found". A lista de tipos da sessão simplesmente não
tem a ficha.

## Causa

A `description` sem aspas tinha `: ` no meio ("ainda são: lei contra código").
Em YAML isso é erro ("mapping values are not allowed here"), e o Claude Code
descarta a ficha inteira em silêncio. A muralha e a auditoria liam o
frontmatter com `linha.partition(":")`, que aceita o que o YAML recusa, e o
diagnóstico corrente era "o PR da ficha ainda não pousou" ou "espelho velho".

## Solução

Valor com `: ` ou ` #` vai entre aspas (simples, se o texto já tiver aspas
duplas). `python ci/economia_da_fabrica.py auditar-fichas` agora lê com
`yaml.safe_load` e aponta a ficha e a linha; o teste
`test_auditoria_passa_nas_fichas_reais_do_repositorio` roda essa auditoria
contra a pasta real na CI.

## Evidência

Sem as aspas, a lista de tipos do Agent numa sessão do app de 27/09/2026 tinha
só despacho, escrivao, maquinista, procurador e revisor. Com as aspas, a
mensagem `init` de uma sessão sem tela aberta na bancada lista as oito fichas.
