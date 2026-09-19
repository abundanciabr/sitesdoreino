---
schema_version: 2
armadilha: 446
estado: guardada
degrau: 6
confianca: alta
custo_por_queda: alto
gatilho:
  - .codex/hooks.json
  - .codex/agents/*.toml
  - ci/patch_codex.py
  - ci/hook_codex.py
guarda:
  tipo: teste
  detector: ci/tests/test_codex_nativo.py
sinal:
  - "apply_patch permitido onde Write é recusado"
  - "hook depende de CLAUDE_PROJECT_DIR no Codex"
licao: Aliases Edit e Write só selecionam o hook; o Codex envia apply_patch em tool_name e o patch em tool_input.command. Meça o evento inteiro, incluindo destinos de move, e prove o launcher real sem Python no PATH.
---

# Hook copiado de outro agente pode ficar configurado e não proteger a escrita

A cópia local de hooks chamava Python por um PATH que o aplicativo não tinha
e procurava CLAUDE_PROJECT_DIR. Mesmo iniciada, a guarda devolvia permissão ao
receber apply_patch. Dezesseis testes novos reproduziram a lacuna.

O launcher CMD valida Python 3.11+, preserva stdin e exit 2, e roda a partir de
subpastas. Não altera ExecutionPolicy. O parser mede todas as operações e rejeita
patch malformado ou caminho com travessia. A régua de texto reconstrói o destino
antes da escrita, inclusive quando um arquivo privado é movido para templates.

O transcript do Codex também tem outro formato: response_item e
event_msg.item_completed. O Stop normaliza esses eventos antes de aplicar a
prestação de contas existente. O aviso de preço da conversa continua exclusivo
do Claude e essa ausência é declarada na abertura, sem falsa medição.

Fonte do contrato: https://learn.chatgpt.com/docs/hooks, conferida em 09/09/2026.
