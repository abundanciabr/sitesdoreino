---
schema_version: 2
armadilha: 404
estado: observada
confianca: alta
degrau: 2
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: "A tela e o inventário dependem do estado do site e da fonte de conteúdo do mantenedor; não há mecanismo local que possa criar os títulos ausentes com segurança."
sinal:
  - "Não existe nenhum curso primeiros-dolares nesta escola"
  - "96 conteúdos"
  - "lista soma 91"
gatilho:
  - services/admin/apps/core/estrutura.py
  - painel/registros/
licao: A importação só pode começar depois de o curso existir no site e a lista canônica fechar a contagem. Referências históricas e uma lista incompleta não autorizam criar curso, inventar títulos ou importar uma estrutura parcial.
---

# O curso e o inventário precisam fechar antes da prévia

Na Fase 2, confirme o curso no Admin e use o Prever com a lista canônica antes de importar. Se o curso não aparece na lista da escola, a prévia informa que nada foi gravado. Se o resumo diz 96 conteúdos e a lista soma 91, faltam cinco títulos de fonte confiável. Sem esses títulos, pare e peça a lista corrigida.
