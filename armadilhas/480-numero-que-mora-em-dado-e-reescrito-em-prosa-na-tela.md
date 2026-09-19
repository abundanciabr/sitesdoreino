---
schema_version: 2
armadilha: 480
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: medio
gatilho:
  - painel/cartoes/
  - services/admin/apps/core/templates/admin/
guarda:
  tipo: teste
  dono: services/admin/tests/test_ciclo.py
  detector: test_a_prosa_da_tela_conta_as_mesmas_semanas_em_zero_que_o_cartao
licao: Frase em português que repete um número vindo de arquivo de dados é cópia, e cópia não muda quando o dado muda. Ao mexer na régua de uma meta, ou a frase sai da tela, ou nasce um teste que lê o dado, conta, e cobra a frase correspondente. Checklist completo em CAMINHO-DOURADO.md R13.
---

# Número que mora num dado e é reescrito em prosa na tela envelhece calado

Um número de regra (uma meta, um prazo, uma contagem de faixas) mora num arquivo
de dados e é lido pela tela. Ao lado da tabela que mostra esse dado, alguém
escreve a mesma informação em português, para explicar: "as três primeiras
semanas pedem zero venda de propósito". A partir daí existem DUAS verdades sobre
o mesmo número, e só uma delas muda quando o dado muda.

Editar o dado não toca na frase. Nenhum portão vê: lint não lê português, o
validador do arquivo confere a forma dos campos, e o teste da tela confere que
ela abre. A tela continua verde, coerente e errada, com ar de certeza, porque a
tabela ao lado mostra o número novo e a frase acima explica o antigo.

Aconteceu duas vezes em duas semanas no mesmo arquivo. Em 04/09/2026 a curva de
`painel/cartoes/compras-no-ciclo.json` passou de três para cinco faixas em zero;
`services/admin/apps/core/templates/admin/ciclo.html` continuou dizendo "as três
primeiras semanas" por treze dias, até 17/09/2026. No mesmo dia, o deslocamento
do calendário encurtou a recuperação para dois dias e a tela ainda a chamava de
"semana de recuperação".

O conserto não é reler o texto com atenção: é um guarda que lê o DADO, conta, e
exige a frase correspondente no template, com o número por extenso. A frase fica
inteira numa linha do template (armadilhas/394) e o teste falha no dia em que o
dado andar sem ela.
