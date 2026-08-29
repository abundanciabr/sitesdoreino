# DECISÃO — arquivar uma ideia, nunca apagá-la de vez

> **Pedida pelo mantenedor em 29/08/2026**: faltava, na tela
> `/admin/caixa/ideia/<id>/`, uma forma de tirar uma ideia de vista. Perguntado
> por pergunta estruturada — apagar de vez (irreversível, perde votos e
> comentários) ou arquivar (reversível, some da vitrine, nada se perde) — ele
> escolheu **arquivar**.
>
> **Status:** isto é lei. Segue a mesma linha de
> `docs/decisoes/DECISAO-a-ficha-nao-se-apaga.md` (29/08/2026, um dia antes
> desta): dado que uma pessoa criou não desaparece do banco por um clique da
> equipe — ele só deixa de aparecer.

## 1. O que muda, em uma frase

Uma ideia arquivada some do quadro do aluno, da busca de duplicatas e de
qualquer página que ele alcance — mas **o registro, os votos, os comentários e
o histórico continuam intactos no banco**, e a equipe pode desarquivá-la a
qualquer momento pela mesma tela, exatamente como estava.

## 2. Por que não é status

`Sugestao.status` é o trilho que a equipe decide sobre o MÉRITO da ideia (em
análise → planejado → em desenvolvimento → implementado, ou não planejado).
Arquivar é outra pergunta: a equipe tirando algo de vista por um motivo
operacional — spam, duplicata, pedido enviado por engano — que não é uma
opinião sobre se a ideia é boa. Uma ideia pode estar arquivada em qualquer fase
do trilho, e desarquivar a devolve exatamente onde estava, com o status
intacto. Por isso são dois campos novos (`arquivada_em`, `arquivada_por`) e
não um sétimo valor de `Status`.

## 3. Onde mora o corte de visibilidade

`SugestaoQuerySet.visiveis()` (`apps/sugestoes/models.py`) é o único lugar que
decide "isto aparece para o aluno?" — toda superfície que o aluno alcança
(quadro, sugestão individual, votar, desvotar, comentar, busca de duplicatas,
os números do topo, a faixa de roadmap, "meu impacto") passa por ele. A
gestão (`api_gestao.py`) usa o manager padrão, sem o filtro: quem arquivou
precisa achar a ideia de novo para desarquivar, e o Admin decide por si mesmo,
via `incluir_arquivadas`, quando quer ver as arquivadas na listagem.

## 4. O contrato

Rito de Mudança de Contrato (`RITOS.md` §3) — este PR contém **somente**
`contracts/sugestoes.openapi.yaml`, com a label `contrato`. Mudança
inteiramente aditiva, nada removido nem renomeado:

- `GET /gestao/ideias` ganha o parâmetro opcional `incluir_arquivadas`
  (default `false` — as arquivadas ficam de fora por padrão, do mesmo jeito
  que já ficavam antes deste contrato existir);
- `IdeiaEmGestao`/`IdeiaComHistorico` ganham três campos opcionais:
  `arquivada`, `arquivada_em`, `motivo_do_arquivamento`;
- duas rotas novas, `POST /gestao/ideias/{id}/arquivar` e
  `POST /gestao/ideias/{id}/desarquivar`, atrás do MESMO Bearer das demais
  rotas de gestão — nenhuma trava nova, nenhuma afrouxada.

**Quem consome:** a célula `sugestoes` implementa as duas rotas novas e o
filtro de visibilidade (PR seguinte, código); a célula `admin` acrescenta o
botão "Arquivar"/"Restaurar" na tela da ideia (PR seguinte a esse). Nenhum
consumidor existente quebra: os três campos novos são opcionais, e o parâmetro
novo tem default que preserva o comportamento de hoje.

## 5. O que NÃO mudou

- **Quem pode arquivar é quem já modera** (`ADMIN_EMAILS`, o mesmo crachá de
  mover fase e avaliar) — arquivar não é "assinar obra": não é um segundo
  portão, é a mesma trava de moderação de sempre.
- **Nada que já existe muda de significado.** Toda ideia de hoje nasce com
  `arquivada_em` nulo — "nunca arquivada" — e continua se comportando
  exatamente como antes desta lei.

---

*Relacionado: `DECISAO-a-ficha-nao-se-apaga.md` (a mesma escolha, para o
cadastro do aluno) · `DECISAO-a-gestao-da-caixa-mora-no-admin.md` (onde a
gestão das ideias mora) · `RITOS.md` §3.*
