---
schema_version: 2
armadilha: 295
estado: guardada
degrau: 3
confianca: media
custo_por_queda: medio
guarda:
  tipo: CI
  dono: ci/tests/test_enviar_a_imagem.py
sinal:
  - `unknown blob`
  - `blob upload unknown`
---

# Deploy vermelho com `unknown blob` e a imagem já construída: é o transporte, não o código

**Sintoma:** o `deploy-celula` fecha `failure`, mas o log mostra o build inteiro
tendo dado certo — a imagem foi escrita, nomeada com o SHA e com `:main`, e
várias camadas subiram (`Pushed`, `Layer already exists`). O erro é uma linha
solta no fim, sem traceback e sem contexto:

```
3cf536b3e643: Pushed
unknown blob
##[error]Process completed with exit code 1.
```

**A pegadinha que faz perder tempo:** logo acima disso, no mesmo log, há um
traceback gritando `ImproperlyConfigured: variável obrigatória ausente:
DJANGO_SECRET_KEY`. Ele é **inofensivo e esperado** — vem de um passo do build
que roda sem env e é tolerado (o passo fecha `DONE`). Quem lê o log de baixo
para cima acha o traceback primeiro, "conserta" uma configuração que não estava
quebrada, e o `unknown blob` volta no deploy seguinte. **O veredito está na
ÚLTIMA linha, não na mais assustadora.**

**Causa:** o upload de uma camada para o `ghcr.io` morre no meio e o registro
perde o rastro do blob que ele mesmo estava recebendo. É engasgo de rede entre
o runner e o registro — a mesma família da `armadilhas/127`, com outro ator.
Nada no código muda o desfecho: em 02/09/2026 (PR #897) a repetição passou em
2min38s sem uma vírgula alterada.

**Solução:** desde 02/09/2026 o envio repete sozinho, até três vezes, em
`ci/enviar_a_imagem.py` — decisão do mantenedor, que escolheu isso sabendo do
risco de retry automático esconder falha real. Se você caiu aqui vendo o deploy
verde na 2ª tentativa, é a vacina funcionando, e o log preserva a 1ª de
propósito.

**As duas regras que impedem a vacina de virar arma** (as duas vêm da
`armadilhas/209`, que é o dia em que uma vacina de retry desistiu de uma
entrega viva):

1. **Resposta definitiva ≠ silêncio.** `denied`, `unauthorized`,
   `manifest unknown` são o registro RESPONDENDO — isso é diagnóstico, e para na
   primeira tentativa. `unknown blob`, 5xx, `EOF`, timeout são silêncio, e
   repetem.
2. **O que a lista não reconhece REPETE, e nunca é declarado permanente.**
   Desistir do que não se reconhece é transformar ignorância em veredito, que é
   literalmente a 209. Repetir sem reconhecer custa um minuto e termina no mesmo
   vermelho; desistir sem reconhecer perde uma entrega. O log avisa, com todas
   as letras, quando está repetindo às cegas — leia por `assinatura NÃO
   reconhecida` e acrescente a linha nova à lista do módulo.

**O que continua NÃO se repetindo, e é a metade que mais importa:** o
`docker build`. Ele ficou num passo separado de propósito. Build que falha é
defeito do código, e repetir build quebrado é a definição de esconder o
vermelho.

**Contexto:** primeira ocorrência conhecida no projeto — procurei em
`armadilhas/` e no livro antes de escrever, e não havia precedente. Por isso a
`confianca` é `media`: uma ocorrência não distingue "o ghcr tossiu" de "há algo
errado no nosso envio". Se cair de novo com assinatura diferente, é aqui que a
linha nova entra.
