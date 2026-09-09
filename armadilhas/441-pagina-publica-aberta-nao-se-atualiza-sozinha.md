---
schema_version: 2
armadilha: 441
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: "A página pública é renderizada no carregamento e precisa ser recarregada para medir o estado novo."
sinal: null
---

# A página pública aberta não se atualiza sozinha

O salvamento da matrícula acontece no servidor na hora, mas uma aba pública já
aberta continua mostrando o HTML que recebeu antes. Para conferir liberação ou
bloqueio, é preciso recarregar a página pública; sem isso, a tela antiga parece
provar que o acesso não mudou.
