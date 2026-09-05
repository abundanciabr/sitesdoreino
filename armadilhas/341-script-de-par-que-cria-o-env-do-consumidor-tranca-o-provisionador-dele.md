---
schema_version: 2
armadilha: 341
estado: guardada
degrau: 5
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_provisionar_pares_da_sala_de_aula.py
sinal:
  - "tem variável que eu NÃO sei gerar"
  - "PAROU POR SEGURANÇA: não achei /opt/plataforma/env/cursos.env"
---

# Script de par que CRIA o env do consumidor antes do provisionador dele tranca o provisionador para sempre

**Sintoma.** O mantenedor roda a linha de um script de par (o que liga
`TOKENS_ACEITOS_*` de um lado e `*_API_TOKEN` do outro) ANTES da linha que
provisiona a célula consumidora. O script de par, prestativo, cria
`env/<celula>.env` com as chaves dele. Dias depois, a linha do provisionador
da célula (`infra/provisionar-<celula>.sh`) para na hora:

```
PAROU POR SEGURANÇA: o env/cursos.env desta máquina tem variável que eu
NÃO sei gerar, e eu reescrevo o arquivo inteiro. Rodar assim apagaria:
   - CATALOGO_API_URL
   - TOKEN_CATALOGO
   - TOKENS_ACEITOS_ADMIN
```

E não há ordem que conserte: o provisionador recusa enquanto o arquivo
existir com chave estranha, e apagar o arquivo à mão é exatamente o gesto que
os roteiros existem para o mantenedor nunca fazer.

**Causa.** Duas famílias de roteiro escrevem no mesmo env com contratos
opostos. O **provisionador da célula** reescreve o env INTEIRO por heredoc e
tem a trava de deriva (`CHAVES_QUE_EU_GERO`, `armadilhas/111`): chave que ele
não conhece é motivo de parar. O **script de par** acrescenta chave por chave
(`garantir`) e não conhece o heredoc do outro. Se o script de par cria o
arquivo, ele nasce só com chaves que o provisionador não sabe gerar, e a trava
dispara para sempre. A trava está certa; o erro é o script de par ter criado
um arquivo que não é dele.

**Solução.** Script de par **exige** que o env do consumidor exista e PARA
se não existir, e a recusa traz a linha do provisionador para colar antes
(é o `test_sem_o_env_da_sala_de_aula_a_recusa_ensina_a_linha_do_banco`). O
`for arquivo in …; [ -f "$arquivo" ] || parar` dos irmãos já fazia isso por
acaso, sem dizer o porquê nem a linha certa; quando o env é de uma célula
NOVA, cuja linha do banco o mantenedor ainda não rodou, a mensagem genérica
("alguma das células não está provisionada") o deixaria sem saber qual linha
colar. A ordem fica gravada no próprio roteiro: banco primeiro, pares depois.
E o cabeçalho do script de par avisa o outro lado da moeda: re-rodar o
provisionador DEPOIS dele para na trava, de propósito, e o conserto é rodar o
par de novo logo em seguida (é idempotente).

**Origem.** Degrau 1.8b da célula `cursos` (TAR-162, 05/09/2026), ao desenhar
`infra/provisionar-pares-da-sala-de-aula.sh` sobre um `env/cursos.env` que
ainda não existe na VPS.
