schema_version: 2
armadilha: 427
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_por_a_chave_da_ia_do_admin.py
  detector: test_conferencia_pages_compara_com_a_copia_anterior_e_morde_a_sabotagem
sinal: 'a conferência diz OK mesmo depois de a releitura da variável antiga ser quebrada'
gatilho:
  - infra/provisionar-admin.sh
  - ci/tests/test_por_a_chave_da_ia_do_admin.py
licao: 'Uma conferência feita depois de reescrever o arquivo não pode comparar o valor vivo com a variável que acabou de alimentá-lo. Ela precisa comparar com a cópia de segurança feita antes da escrita; sem cópia na primeira execução, não há valor anterior a preservar.'
---

# 427: Conferência compara o arquivo com o valor novo

**Data:** 09/09/2026. **Onde:** conferência do token `TOKENS_ACEITOS_PAGES`
no provisionamento da área administrativa.

## Sintoma e causa

O roteiro reescrevia `env/admin.env`, mas a conferência comparava o valor vivo
com `$T_PAGES`, a mesma variável usada para escrever a linha. Se a releitura do
arquivo antigo fosse quebrada, o roteiro geraria um token novo e compararia o
arquivo novo com esse token novo. A saída seria verde enquanto o token em uso
na outra célula continuaria antigo.

## Solução

A conferência lê `TOKENS_ACEITOS_PAGES` de `env/admin.env.bak-<epoch>`, criada
antes da reescrita, e compara o arquivo vivo com esse valor. A primeira
execução, sem cópia anterior, é aceita porque não existe valor para preservar.

## Evidência

O teste guarda executa o bloco real em shell. Com cópia antiga e valor vivo
novo, a lógica antiga sai verde e a lógica corrigida sai com `FALTANDO`. Com os
valores iguais, a lógica corrigida sai verde.
