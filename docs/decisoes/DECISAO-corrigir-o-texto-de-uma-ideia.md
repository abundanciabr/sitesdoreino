# DECISÃO — corrigir o texto de uma ideia, sem que o aluno veja marca

> **Pedida pelo mantenedor em 31/08/2026**, com o caso na mão: um aluno criou
> uma sugestão chamada *"turorial de cabelo avançado masculino"* e repetiu o
> mesmo erro numa segunda. Ele procurou no site onde editar o nome das
> sugestões e não achou — porque não existia. Pedido dele, textual: *"você pode
> colocar isso (a parte de editar as sugestões) para aparecer para os admins lá
> mesmo na Caixa de Sugestões?"*
>
> **Status:** isto é lei. As duas perguntas abaixo foram decididas por ele, por
> pergunta estruturada, antes de qualquer linha de código.

## 1. O que muda, em uma frase

A tela `/admin/caixa/ideia/<id>/` ganha um formulário que corrige **o nome e o
texto** de uma ideia; o aluno passa a ver o texto novo **sem nenhuma marca de
que alguém mexeu**, e o que estava escrito antes fica guardado inteiro do lado
da equipe.

## 2. As duas decisões do mantenedor

**Primeira: dá para corrigir o nome E o texto** (`titulo`, `problema` e
`solucao_proposta`), não só o nome. O motivo é o próprio caso que originou o
pedido: quem digita "turorial" no título costuma repetir o erro no corpo, e uma
ferramenta que conserta só a primeira linha deixaria o mesmo erro vivo três
linhas abaixo, sem caminho nenhum para chegar até ele.

**Segunda: a correção é CALADA.** Nenhuma marca na página que o aluno lê —
nem "editado", nem "corrigido pela escola", nem data. Foi uma escolha entre
três (sempre marcar · marcar só no texto · nunca marcar), e ele escolheu a
terceira.

## 3. Calada não é sem rastro — e é isto que sustenta a decisão

O que a segunda decisão custaria, se fosse tomada sozinha: a escola poderia
reescrever a fala de um aluno sem que sobrasse prova do que ele tinha dito. O
dia em que alguém reclamar do texto trocado é exatamente o dia em que ninguém
consegue responder.

Por isso a correção nasce com uma tabela própria, `CorrecaoDeTexto`, que guarda
**uma linha por campo alterado**: o texto anterior, o texto novo, quem corrigiu
e quando. Ela é **append-only nos três degraus** da Lei 1 — `save()`,
`AppendOnlyQuerySet` e um trigger `BEFORE UPDATE OR DELETE` no Postgres —, como
o `HistoricoStatus` e o `ChangeSpecAprovado` já eram. Aqui o terceiro degrau
pesa mais do que nos outros dois: esta tabela é a **única cópia** do que o aluno
escreveu, e um `UPDATE` cru que passasse por baixo do Python destruiria a prova
justamente do que a decisão promete preservar.

O rastro volta no `correcoes` da ideia individual, que só o Admin alcança. O
aluno não o vê em lugar nenhum — é o que "calada" quer dizer.

## 4. Por que não é o mesmo que o fórum faz

O fórum da escola já corrige texto de aluno, e faz diferente: o título de uma
conversa muda calado, mas a **mensagem** ganha a marca "editada". Não é
contradição, e a diferença explica as duas escolhas.

Numa conversa de fórum, as pessoas **respondem** a uma mensagem: quem respondeu
confiando no que estava escrito precisa ver que o texto mudou, ou a resposta
dele passa a parecer fora de contexto. Na Caixa, ninguém responde a uma ideia —
as pessoas **votam** nela, e o voto continua valendo para a mesma ideia depois
de um "turorial" virar "tutorial". A marca só serviria para transformar um
conserto de digitação em um aviso público.

**Onde o limite está, e ele importa:** a régua acima vale para CONSERTO. Uma
correção que mude o SENTIDO da ideia é outra coisa, e a resposta certa para ela
não é marcar o texto: é não fazer. Quem lê o rastro consegue ver a diferença,
porque o texto anterior está lá inteiro.

## 5. As travas, e a razão de cada uma

- **Ideia apagada não se corrige.** A `DECISAO-apagar-ideia.md` promete que o
  conteúdo não existe mais em lugar nenhum; escrever um título novo nela seria
  trazê-lo de volta por uma porta lateral. Recusa 422.
- **As mesmas réguas de quando o aluno escreveu**: nome obrigatório e de até
  140 caracteres, problema obrigatório. Uma régua mais frouxa aqui deixaria a
  equipe gravar, por uma porta de máquina, uma ideia que o próprio aluno não
  conseguiria ter criado.
- **"Nada mudou" é recusa, não um sucesso mudo.** Salvar o formulário sem ter
  tocado em nada responderia "pronto, corrigido" tendo gravado zero linhas —
  falso-verde de produto, a mesma doença que a nota da avaliação já curou nesta
  casa quando parou de arredondar em silêncio.
- **Quem corrige é quem já modera** (`ADMIN_EMAILS`, o mesmo crachá de mover
  fase, avaliar e arquivar). Corrigir não é assinar obra: não é um segundo
  portão, é a trava de moderação de sempre.
- **Corrigir não avisa ninguém.** Nenhuma carta sai para a plateia e nenhuma
  linha nasce no histórico de fases: a ideia não andou, ela só está escrita
  certo. Se saísse aviso, "calada" seria mentira já no primeiro uso.

## 6. O contrato

Rito de Mudança de Contrato (`RITOS.md` §3) — este PR contém **somente**
`contracts/sugestoes.openapi.yaml` e esta lei, com a label `contrato`. Mudança
inteiramente aditiva, nada removido nem renomeado:

- uma rota nova, `POST /gestao/ideias/{id}/texto` (`fixIdeaText`), atrás do
  MESMO Bearer das demais rotas de gestão — nenhuma trava nova, nenhuma
  afrouxada;
- dois schemas novos: `TextoCorrigido` (o que a tela manda: os três campos
  inteiros, sempre) e `LinhaDaCorrecao` (uma linha do rastro);
- `IdeiaComHistorico` ganha o campo opcional `correcoes`, com o mesmo desenho
  do `changespecs`: ausente é lista vazia, e por isso nenhum consumidor de hoje
  quebra.

**Por que o corpo carrega os três campos, e não só o que mudou:** mandar só os
alterados obrigaria a distinguir "não mandei este campo" de "mandei este campo
vazio", que num JSON são a mesma ausência. Apagar a solução proposta é uma
correção legítima, e ela não pode depender dessa sutileza. O efeito colateral é
bom: reenviar o mesmo corpo duas vezes não cria uma segunda correção, porque a
segunda não muda nada e a Caixa a recusa dizendo isso.

**Quem consome:** a célula `sugestoes` implementa a rota, a tabela e as travas
(PR seguinte); a célula `admin` acrescenta o formulário e o rastro na tela da
ideia (PR seguinte a esse).

## 7. O que NÃO muda

- **Nada do que já existe muda de significado.** Toda ideia de hoje tem zero
  correções, e continua se comportando exatamente como antes desta lei.
- **O e-mail do aluno continua sem sair da Caixa**: o rastro carrega o nome
  exibido de quem corrigiu, nunca um endereço (`DECISAO-EVO-01` §3).
- **O histórico de fases continua intocado.** Corrigir texto e mover de fase são
  gestos diferentes, com tabelas diferentes, e nenhum dos dois escreve no
  registro do outro.

---

*Relacionado: `DECISAO-a-gestao-da-caixa-mora-no-admin.md` (onde a gestão das
ideias mora) · `DECISAO-arquivar-ideia.md` e `DECISAO-apagar-ideia.md` (os
outros dois gestos da mesma tela) · `RITOS.md` §3.*
