# Consultoria aberta fora do livro é invisível — e ninguém cobra o veredito

**Sintoma:** uma rodada de consultoria externa foi aberta, as respostas
chegaram no mesmo dia (três pareceres completos, um até com desenho de tela)…
e ficou tudo parado. Nenhuma sessão seguinte leu, nenhum veredito saiu, o
painel nunca mostrou nada pendente. A rodada só voltou à vida porque o
MANTENEDOR lembrou dela, um dia depois — que é exatamente o tipo de memória
que o sistema existe para substituir.

Aconteceu de verdade em 28→29/08/2026: a rodada "Central de Orquestração de
Trabalho" (hoje em `docs/consultorias/central-de-orquestracao/`) viveu esse
dia inteiro como quatro arquivos órfãos numa pasta local não versionada
(`docs/paineis/Central de Orquestração de Trabalho/`), sem commit e sem
registro.

**Causa:** o rito de consultoria tem um último passo — pedir o veredito — que
por natureza acontece numa SESSÃO FUTURA, e o estado "rodada aberta, veredito
faltando" não morava em lugar nenhum que uma sessão futura lê. A caixa
"precisa de você" do painel é CALCULADA do livro (`painel/registros/`): pedido
que nunca virou registro não existe para ela — ela não esquece, mas também não
inventa. E pasta local fora do Git nem sequer aparece para as outras sessões
(que leem do `origin/main`, `armadilhas/148`). É a mesma doença do H18 — lista
de pendências fora do lugar calculado — vestida de consultoria.

A classe, além do caso: **qualquer trabalho em várias etapas cujo próximo
passo pertence a uma sessão futura precisa deixar o estado no livro, senão o
passo morre.** Vale para consultoria, para "constrói X quando Y existir", para
qualquer combinado com gatilho.

**Solução:** abrir rodada de consultoria é UM gesto com três partes, na mesma
sessão em que a rodada nasce:

1. A pasta versionada em `docs/consultorias/<tema>/` (molde do
   `docs/consultorias/forum-da-escola/`) — prompt e respostas entram por
   commit, nunca ficam só no disco.
2. Um registro no livro (`painel/registros/`, tipo `pendencia` ou `nota` com
   `precisa_do_dono` quando a resposta é dele) dizendo que a rodada está
   aberta e o que falta para fechá-la.
3. O veredito, quando sair, é registro NOVO com `responde_a` apontando o da
   abertura — e aí a caixa calculada fecha o ciclo sozinha.

Se você encontrar uma rodada órfã (respostas sem veredito, fora do livro), o
conserto é o mesmo gesto, atrasado: versionar a pasta, escrever o veredito e
registrar — foi o que o PR desta armadilha fez.

**Origem:** rodada "Central de Orquestração de Trabalho", 28→29/08/2026, e o
plano mestre aprovado pelo mantenedor em 29/08/2026 que a retomou (fase 1).
