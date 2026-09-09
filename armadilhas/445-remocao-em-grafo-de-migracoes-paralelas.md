---
schema_version: 2
armadilha: 445
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
gatilho: "Criar uma migração nova em services/encomendas/apps/encomendas/migrations quando houver mais de uma folha no grafo."
licao: "Antes de nomear a migração, confira todas as dependências finais. Neste serviço, a remoção de pista precisa ser 0007 e depender de 0006, o último ramo comum."
guarda:
  tipo: nenhum
  motivo: "O grafo de migrações e o teste makemigrations --check detectam o conflito antes da publicação."
sinal: null
---

# Remoção em grafo de migrações paralelas

O app de encomendas tem folhas de migração paralelas, então uma migração nova
não pode reutilizar o próximo número de um ramo antigo. A remoção de `pista`
entrou em `0007`, dependente de `0006`, que é o último ramo comum. Aplicar,
reverter e reaplicar em PostgreSQL 17 confirmou o caminho inteiro.
