---
schema_version: 2
armadilha: 426
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
gatilho:
  - services/sugestoes/apps/core/templates/sugestoes/base_caixa.html
  - services/sugestoes/tests/test_avisos_script_name.py
guarda:
  tipo: CI
  dono: services/sugestoes/tests/test_avisos_script_name.py
sinal:
  - "o sino lateral ainda leva para /forms/sugestoes/avisos"
licao: Quando uma tela de uma célula passa a compartilhar uma central pública com o restante do site, o link visível do sino deve apontar diretamente para a raiz pública da central; a rota antiga pode continuar existindo para compatibilidade, mas não deve permanecer como destino da navegação nova.
---

# O sino da célula continua apontando para a tela legada depois que a central nasceu

**Sintoma.** A central de notificações já existe na página inicial, mas o sino
da moldura da Caixa de Sugestões ainda usa a reversão local de `avisos` e leva
o aluno para a tela antiga sob `/forms/sugestoes/avisos`. A pessoa encontra a
mesma informação em dois lugares, contrariando a decisão de centralização.

**Causa.** O link foi tratado como uma rota interna da célula, embora o destino
seja uma página pública compartilhada entre células. A rota legada continua
útil para favoritos e links salvos, mas isso não justifica mantê-la como o
destino do sino que aparece na navegação corrente.

**Solução.** O template da moldura aponta explicitamente para `/notificacoes`,
e o teste de contrato da moldura fixa esse destino. A rota antiga permanece
publicada para compatibilidade; somente o caminho visível da navegação muda.
