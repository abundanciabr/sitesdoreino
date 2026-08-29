# DECISÃO — "Não planejado" some do quadro, mas o link direto continua abrindo

> **Pedida pelo mantenedor em 29/08/2026**, na mesma sessão da
> `DECISAO-arquivar-ideia.md`. Perguntado se o sumiço deveria ser total (nem
> por link direto, como uma ideia arquivada) ou só das listas, ele escolheu:
> *"o autor pode ver a ideia, mas ela não aparece no quadro e nem na faixa
> 'fora do trilho'"*.
>
> **Status:** isto é lei, e **reverte** um design do EVO-31
> (`tests/test_faixa_de_roadmap.py`): até aqui, uma ideia "Não planejado"
> ficava DE PROPÓSITO na faixa "Fora do trilho", porque a equipe é OBRIGADA a
> escrever a justificativa (EVO-13) e "quem sugeriu vai ler" era lido como "vai
> ler NA PÁGINA". A reversão está registrada aqui, por extenso, para ninguém no
> futuro achar que foi descuido.

## 1. O que muda, em uma frase

Uma ideia "Não planejado" some da grade principal do quadro (as três abas —
Em alta, Mais votadas, Novas) e da faixa "Fora do trilho" — mas **o link direto
continua abrindo**, com a justificativa escrita ali. `mesclado` **não muda**:
continua aparecendo em "Fora do trilho", exatamente como antes — o pedido foi
só sobre `nao_planejado`.

## 2. Por que o link direto continua vivo

A garantia do EVO-13 — *"quem sugeriu vai ler a justificativa"* — não depende
mais da página desde o EVO-42 (o sininho, `Aviso`/`avisos.py`): todo mundo que
interagiu com a ideia já recebe a nota escrita no instante em que o status
muda, por notificação in-app, antes de qualquer coisa que este PR toca. A
página deixar de LISTAR a ideia não desfaz essa entrega — ela só deixa de ser
o único lugar onde a explicação mora. É por isso que sumir da lista é seguro
sem sumir do link: a garantia velha continua de pé, só que por outro canal.

## 3. A aritmética que quase quebrou em silêncio

`tests/test_faixa_de_roadmap.py` tinha um guarda plantado no EVO-31 —
*"a soma das quatro zonas do trilho mais as saídas tem que dar o total de
sugestões do quadro"* — para impedir alguém de esconder um status sem
atualizar o total, o que faria a página "mentir" sobre quantas ideias existem.

Esconder `nao_planejado` da lista sem mexer em mais nada quebraria esse guarda
de propósito — e o guarda estava certo em reclamar. A correção não foi apagar
o teste: foi mudar o que "o total" significa. `numeros_do_quadro()["sugestoes"]`
(o número que o aluno lê no topo da página) passou a excluir `nao_planejado`,
do mesmo jeito que já excluía arquivadas (`DECISAO-arquivar-ideia.md` §3). A
aritmética volta a bater — só que agora ela é honesta sobre "o que a página
mostra", não sobre "o que existe no banco". `Sugestao.objects.count()`
continua contando as ideias recusadas; `numeros_do_quadro()` não.

## 4. Onde mora o filtro, e onde NÃO mora

Só a página do aluno (`ver_quadro`, `fora_do_trilho`, `numeros_do_quadro`)
aplica este filtro. **Não mudou:**

- a fila da equipe (`moderacao.ver_fila`, legado) continua vendo tudo,
  inclusive quando filtra explicitamente por `status=nao_planejado`;
- a gestão do Admin (`api_gestao._ideias_do_quadro`) continua vendo tudo —
  é o painel de trabalho da equipe, não a vitrine do aluno;
- "Meu impacto" (`meu_impacto`) continua listando as próprias ideias
  recusadas de quem está olhando — não foi pedido, e é informação sobre a
  PRÓPRIA participação, não a vitrine pública;
- a busca de possíveis duplicatas (`possiveis_duplicatas`) não foi tocada —
  não foi pedido, e escondê-la também exigiria decidir se uma ideia recusada
  continua contando como "isto já foi sugerido".

## 5. Contrato

Nenhum. Esta mudança é inteiramente dentro da célula `sugestoes` — não toca
`/gestao/*` (a superfície que o Admin consome), então `contracts/sugestoes.
openapi.yaml` não muda.

---

*Relacionado: `DECISAO-arquivar-ideia.md` (a decisão irmã, mesmo dia — mesma
pergunta, "isto sai de vista, mas de que jeito?", para o caso de arquivar em
vez de recusar).*
