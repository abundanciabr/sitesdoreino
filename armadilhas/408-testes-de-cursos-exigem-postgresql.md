---
schema_version: 2
armadilha: 408
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
gatilho:
  - services/cursos/*
  - services/cursos/tests/*
guarda:
  tipo: nenhum
  motivo: a suíte depende de PostgreSQL e a bancada foi aberta sem container
sinal: 'a suíte de cursos falha na preparação com ADD CONSTRAINT no SQLite'
licao: 'Os testes de cursos precisam rodar com PostgreSQL. SQLite falha antes dos casos porque a migração usa ALTER TABLE ADD CONSTRAINT, então a falha de preparação não é falha do código testado.'
---

# 408: A suíte de cursos exige PostgreSQL

**Sintoma.** A suíte de `services/cursos` falha no início com `near "CONSTRAINT": syntax error` quando `DATABASE_URL` aponta para SQLite.

**Causa.** A célula usa uma migração PostgreSQL para adicionar a chave estrangeira composta `aula_e_bloco_do_mesmo_curso`. SQLite não aceita esse `ALTER TABLE`.

**Lição.** Quando a sessão for aberta com `--sem-container`, use o PostgreSQL local da sessão ou registre `NÃO RODEI`. Não interprete os erros de preparação SQLite como falhas dos testes de Boss.

**Evidência.** SQLite: 163 erros na preparação. PostgreSQL local da sessão: 163 testes passaram em 44,57 segundos.
