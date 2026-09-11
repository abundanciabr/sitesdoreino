---
schema_version: 2
armadilha: 450
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/prestacao_de_contas.py
  detector: prestacao_de_contas
sinal: 'o robô informa PRONTO ou NÃO PRONTO, mas o mantenedor precisa inventar a mensagem para continuar'
gatilho:
  - ci/prestacao_de_contas.py
licao: 'Quando ainda houver dependência humana, o relatório precisa mostrar o marcador visual AÇÃO NECESSÁRIA DO MANTENEDOR, a ação em Faça agora e o próximo efeito em Quando você fizer isso. Sem isso, a etapa parece encerrada e o gargalo volta para o mantenedor.'
---

# 450: Pausa sem ação humana explícita

**Data:** 09/09/2026. **Onde:** prestação de contas ao fim de uma etapa.

## Sintoma e causa

O relatório dizia que o PR estava pronto, embora ainda dependesse de uma ação
do mantenedor. A frase genérica não dizia qual mensagem enviar nem o que
aconteceria depois, então a tela treinava o usuário a escrever “Continue”.

## Regra

Pendência humana aparece com um marcador visual, uma ação concreta e o efeito
seguinte. Quando nada depende do mantenedor, o relatório diz isso diretamente.
