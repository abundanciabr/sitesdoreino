---
schema_version: 2
armadilha: 431
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
gatilho:
  - services/sugestoes/apps/core/templates/sugestoes/base_caixa.html
  - services/sugestoes/config/settings.py
  - services/sugestoes/apps/core/avisos.py
guarda:
  tipo: CI
  dono: services/sugestoes/tests/test_avisos_script_name.py
sinal:
  - "o ícone sumiu, mas `avisos.sino` ainda é context processor"
licao: Ao remover uma navegação duplicada, retire também o processamento e o cliente exclusivos dela; manter o contador invisível preserva custo de rede e código sem consumidor.
---

# O sino sumiu da tela, mas o contador invisível continuou sendo carregado

**Sintoma.** O item do sino foi removido visualmente da sidebar, mas o
context processor ainda entregava `avisos_nao_lidos` em todas as páginas e o
cliente ainda consultava o endpoint de resumo da central.

**Causa.** A mudança foi tratada como remoção de HTML, sem seguir a dependência
até o settings, o cliente, o cache e os testes que existiam apenas para decorar
essa navegação.

**Solução.** Remover o item da moldura, o símbolo SVG, o context processor, o
cache do resumo, o método de cliente exclusivo e os guardas que mediam somente
o sino. A página central continua usando a listagem completa de avisos, que é
um fluxo diferente e permanece protegido pela suíte.
