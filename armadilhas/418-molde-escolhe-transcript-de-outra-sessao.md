---
schema_version: 2
armadilha: 418
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/prestacao_de_contas.py
  - ci/tests/test_prestacao_de_contas.py
guarda:
  tipo: CI
  dono: ci/tests/test_prestacao_de_contas.py
  detector: 'test_molde_com_fatos_sem_identidade_recusa_escolher_transcript: sem identidade o molde termina em recusa'
sinal: 'o comando manual do molde escolhe o jsonl mais recente da máquina e mistura checklist, comandos ou PR de outra sessão'
licao: 'O molde só pode ler o transcript informado explicitamente; sem identidade ele recusa, nunca escolhe o arquivo mais recente da máquina.'
---

# 418: O molde presta contas com fatos de outra sessão

**Sintoma.** `--molde-com-fatos` preenchia o checklist, os comandos e o PR usando o transcript mais recente encontrado no computador.

**Causa.** Bancadas diferentes podem compartilhar a pasta de transcripts, e o caminho da bancada não identifica com segurança a sessão que chamou o comando.

**Lição.** A identidade precisa vir em `--transcript`. Sem ela, o comando recusa e ensina como informar o caminho. O teste encena sessões A e B e confirma que o molde de A não traz o fato de B.

**Evidência.** A mutação que trocou a recusa por saída bem-sucedida fez o teste de identidade reprovar; restaurada, a suíte passou com 61 testes.
