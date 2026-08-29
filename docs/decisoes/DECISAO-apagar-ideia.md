# DECISÃO — apagar uma ideia de verdade, sem volta nenhuma

> **Pedida pelo mantenedor em 29/08/2026**, no mesmo dia de
> `DECISAO-arquivar-ideia.md`, depois de testar o botão "Arquivar" recém-
> lançado: *"além do que já fizemos também quero o botão de excluir/apagar
> definitivamente uma ideia e que ela desapareça completamente do sistema,
> desapareça até mesmo para quem a criou"*.
>
> Duas perguntas estruturadas, com o preço de cada caminho na mesa antes da
> escolha:
>
> 1. **Trava contra clique errado, já que não tem como desfazer:** pedir para
>    digitar uma palavra antes de liberar, ou só uma segunda pergunta
>    ("tem certeza?"). Ele escolheu **a segunda pergunta** — mais rápido, um
>    passo a mais e chega.
> 2. **Como apagar por dentro, dado que ideias que já andaram de fase têm uma
>    proteção do sistema contra apagar histórico:** a linha inteira sumindo
>    do banco (só funcionaria em ideias que nunca mudaram de fase), ou "lousa
>    apagada" — conteúdo destruído para sempre, mas a linha fica, para não
>    desmontar essa proteção. Ele escolheu **lousa apagada**.
>
> **Status:** isto é lei.

## 1. O que muda, em uma frase

Um botão "Apagar definitivamente" na tela da ideia, ao lado de "Arquivar",
com uma confirmação ("tem certeza? não tem volta") antes de agir. Depois de
apagada: título, texto da solução, votos e comentários — de QUALQUER pessoa
que interagiu, não só do autor — desaparecem para sempre, e ninguém alcança
esse conteúdo de novo em lugar nenhum, nem pelo link direto.

## 2. Por que a linha continua existindo no banco

`HistoricoStatus`, `ChangeSpecAprovado` e `Aviso` apontam para `Sugestao`
com `on_delete=PROTECT`, e os dois primeiros são append-only em três degraus
(save() recusa, o queryset recusa, e o Postgres tem um trigger recusando —
EVO-11/EVO-40). Isto é DELIBERADO: garante que ninguém — nem um bug, nem um
`manage.py shell` às 23h — reescreve o passado de quem moderou uma ideia.

Apagar a `Sugestao` de verdade (a linha sumindo da tabela) exigiria apagar
primeiro essas três tabelas — ou seja, desmontar a mesma proteção que este
projeto construiu com cuidado extra (três degraus, não um) para garantir que
nunca acontecesse.

**A saída, e por que ela cumpre a promessa por fora sem tocar a proteção por
dentro:** a linha da `Sugestao` fica, mas o conteúdo que uma pessoa consegue
LER é destruído — título, problema e solução viram texto vazio; os votos e
os comentários são apagados de verdade (essas duas tabelas não têm a mesma
proteção, porque não são histórico de decisão da equipe). `HistoricoStatus`
e `Aviso` continuam existindo, mas eles nunca guardaram o título ou o texto
da ideia — só o status e a nota da equipe — então nada do que a pessoa
escreveu sobrevive em lugar nenhum que alguém possa ler.

## 3. Apagada é sempre arquivada, e o inverso não é verdade

Uma ideia apagada recebe o MESMO carimbo de arquivamento
(`arquivada_em`/`arquivada_por`) — não porque sejam a mesma coisa, mas
porque toda superfície que já sabe esconder uma ideia arquivada (o quadro do
aluno, a busca de duplicatas, os números do topo, a listagem padrão da
gestão) automaticamente também esconde a apagada, sem precisar aprender um
segundo carimbo.

O que `apagada` acrescenta, e que `arquivada` sozinha não tem: **não existe
"Restaurar".** Desarquivar uma ideia apagada é recusado com uma frase que
explica por quê — não há mais nada para trazer de volta.

## 4. O que NÃO mudou

- **Quem pode apagar é quem já modera** (`ADMIN_EMAILS`, o mesmo crachá de
  arquivar, mover fase e avaliar) — não é um poder novo, é o mesmo de sempre.
- **Nenhum motivo é pedido.** Ao contrário de arquivar (que tem um campo
  opcional "por quê"), apagar não pergunta nada além da confirmação — decisão
  do mantenedor, pela fricção mínima que ele escolheu na pergunta 1.

## 5. Contrato

Rito de Mudança de Contrato (`RITOS.md` §3) — aditivo: nova rota
`POST /gestao/ideias/{id}/apagar`, atrás do mesmo Bearer das demais rotas de
gestão, e o campo opcional `apagada` em `IdeiaEmGestao`/`IdeiaComHistorico`.
Nada removido, nada renomeado.

---

*Relacionado: `DECISAO-arquivar-ideia.md` (o mesmo tema, versão reversível) ·
`DECISAO-a-ficha-nao-se-apaga.md` (a mesma pergunta para o cadastro do
aluno, resposta oposta — lá o mantenedor decidiu que NUNCA existe apagar;
aqui ele decidiu que existe, mas por dentro do banco o dado de outras
pessoas — o histórico de quem moderou — continua protegido do mesmo jeito).*
