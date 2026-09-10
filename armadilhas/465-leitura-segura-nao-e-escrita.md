---
schema_version: 2
armadilha: 465
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
gatilho:
  - services/admin/apps/core/templates/admin/caixa_robos.html
  - services/admin/tests/test_robos_no_admin.py
licao: uma guarda que proíbe toda tag form bloqueia também uma consulta GET sem efeitos; ela deve proibir escrita e exigir que a leitura segura declare o seu limite.
guarda:
  tipo: teste
  dono: services/admin/tests/test_robos_no_admin.py
sinal:
  - assert "<form" not in corpo
---

# Guarda de leitura segura precisa medir escrita, não a tag

**Sintoma.** A central de robôs recebeu uma prévia que só organiza um pedido e
responde no próprio navegador. Ela não cria TAR, reserva, PR nem executa robô,
mas a suíte recusou a tela porque uma proteção antiga interpretava qualquer
`<form>` como escrita.

**Causa.** A proteção media uma marcação HTML, não o efeito que precisava
impedir. Um formulário GET foi colocado no mesmo grupo de um POST que cria ou
altera dados, apesar de a diferença ser justamente a fronteira de segurança da
tela.

**Solução.** Ao liberar uma leitura interativa, o teste exige explicitamente o
formulário GET, proíbe formulário POST e procura a frase que declara os efeitos
ausentes. Assim a página pode orientar sem ganhar capacidade de alterar o
sistema.

**Prova observada.** A CI do PR #1539 recusou a prévia pela asserção genérica;
a guarda específica passou junto com a suíte administrativa completa.
