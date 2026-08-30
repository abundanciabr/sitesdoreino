---
schema_version: 2
armadilha: 236
estado: guardada
degrau: 1
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: "nenhum portao consegue adivinhar que uma entrega fecha um pedido especifico; so quem escreve sabe. Degrau 1: leitura."
sinal: null
---

# Entrega não fecha pedido: quem fecha é o `responde_a` — o trabalho foi feito e a caixa "Precisa de você" continuou cobrando

**Sintoma:** a caixa "Precisa de você" do painel mostra um pedido em aberto que
**já foi atendido**, às vezes horas antes, com a entrega registrada no livro,
verde e com prova de fora. O mantenedor abre o painel e é cobrado por algo que
ele já decidiu.

**Caso medido — 30/08/2026:** o registro `20260830-060` pedia que o dono lesse
as dez dúvidas de partida do fórum antes de publicar (`precisa_do_dono: true`).
Ele leu e mandou publicar no mesmo dia; a entrega virou o registro
`20260830-063`, verde, com prova pública (`/forum/t/1` = 200, autoria "a escola",
"resposta aceita"). Mesmo assim, ao republicar o painel horas depois, a caixa
ainda mostrava **1 pedido aberto** — exatamente aquele.

**Por que isso confunde:** tudo estava certo. O pedido estava certo, a entrega
estava certa, a prova estava certa, o gerador aprovou os dois. Nada reprova, nada
avisa. E como a caixa é CALCULADA (o argumento de venda dela é justamente
"uma lista calculada não consegue esquecer um pedido"), a tendência de quem lê é
acreditar na tela e ir refazer o trabalho — ou, pior, incomodar o mantenedor
pedindo de novo uma decisão que ele já tomou. Foi o que quase aconteceu: uma
sessão chegou a abrir a pergunta estruturada para ele antes de conferir o fato
no ar.

A regra é literal e está em `painel/LEIA-ME.md`: *pendência = registro
`precisa_do_dono: true` sem nenhum outro registro com `responde_a` apontando
para ele*. **Entregar não fecha nada.** O que fecha é o ponteiro. Um registro de
entrega com `responde_a: null` — o padrão do molde, e por isso o caminho fácil —
deixa o pedido na tela para sempre.

**Solução:** um registro NOVO (nunca editar o antigo — `tipo: "resposta"` serve
bem) com `responde_a` igual ao campo `arquivo` do pedido, sem `.js`:

```js
  responde_a: "20260830-060-o-forum-ja-sabe-falar-em-nome-da-escola",
```

**Como conferir antes de dar a tarefa por terminada** (do `origin/main`, não do
clone principal — `armadilhas/148`):

```bash
git fetch origin -q
D=$(mktemp -d); git archive origin/main painel/registros | tar -x -C "$D"
node -e '
const fs=require("fs"),p=require("path");global.window={};
const d=process.argv[1]+"/painel/registros";
for(const f of fs.readdirSync(d).sort()) eval(fs.readFileSync(p.join(d,f),"utf8"));
const R=window.REGISTROS, resp=new Set(R.map(r=>r.responde_a).filter(Boolean));
R.filter(r=>r.precisa_do_dono&&!resp.has(r.arquivo))
 .forEach(a=>console.log("ABERTO:",a.arquivo,"|",a.titulo));
' "$D"
```

Se aparecer um pedido que você sabe que já foi atendido, **não refaça o trabalho
e não pergunte ao mantenedor**: confira o fato no ar e escreva o registro-resposta.

**A regra de bolso, para o gesto de todo dia:** ao registrar uma entrega,
pergunte *"isto atende algo que estava na caixa dele?"*. Se sim, o registro tem
de dizer isso — senão a caixa que promete nunca esquecer passa a cobrar por
trabalho já feito, que é a mesma doença de credibilidade que um alarme tocando
sem motivo (`armadilhas/127` e o sino que aprendeu a duvidar).

**Sem mecanismo, de propósito:** nenhum portão consegue adivinhar que uma entrega
qualquer fecha um pedido específico — só quem escreve sabe. O que dá para
mecanizar um dia é o AVISO: um pedido aberto há mais de N dias cuja frente já
teve entrega verde merece aparecer destacado no painel, para o humano decidir. Até
lá, isto é degrau 1: leitura.

**Origem:** republicação do painel a pedido do mantenedor, 30/08/2026 — registros
`20260830-095` (a republicação) e `20260830-098` (o ponteiro que faltava).
