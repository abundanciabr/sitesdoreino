# DECISÃO: o fim da tríade, cooperação sem papel fixo

**Decidida pelo mantenedor em 18/09/2026.** O pedido dele, com as palavras dele:

> "a tríade, ou seja, onde cada IA fazia uma coisa acabou, mas o ranking não tem
> nada a ver com isso, o ranking é outra coisa que foi criada depois da tríade
> para as ias cooperarem entre si, o rádio pode ser removido sim, mas o ranking
> não pode ser removido, e a tríade acabou mas as ias cooperam para criar um
> sistema mais fácil de operar, cada ia contríbui para a melhora do mesmo"

Revoga a [`DECISAO-triade-de-ias.md`](DECISAO-triade-de-ias.md) de 12/09/2026.

## A lei, em uma frase

**Nenhuma IA tem papel fixo. Qualquer uma faz qualquer parte do rito, e o que
separa uma sessão da outra é a tarefa que ela pegou, nunca a marca dela.**

## Por que

A própria decisão da tríade dizia, na seção "Quem faz valer", a frase que agora
a derruba:

> "A divisão de papéis em si é julgamento: nenhum portão sabe qual IA está
> digitando. O que ele sabe conferir é o rastro."

Isso continua verdade, e é o ponto inteiro. O que protege esta casa nunca foi
saber quem digita: é a bancada por worktree (`RITOS.md` §1), a tarefa na fila,
o PR com recibo, o livro de ocorrências e a integração por check verde. Nenhum
desses mecanismos pergunta a marca de ninguém, e nenhum deles muda hoje.

O papel fixo, esse, cobrava sem pagar. Uma sessão que enxergava o bug tinha de
devolver o bug porque "construir é do executor". Uma auditoria esperava a IA com
o crachá de auditor. Um achado virava três artefatos (proposta, voto,
verificação) antes de virar uma linha de código. A casa ganhou vocabulário e
perdeu tempo.

O que o mantenedor quer no lugar é mais simples e já estava acontecendo: as IAs
cooperam para deixar o sistema mais fácil de operar, e cada uma contribui para
a melhora do mesmo sistema. Quem pega, faz. Quem vê, conserta. Quem entrega,
responde pela entrega até o estado terminal (`CONSTITUICAO.md`, Lei 11).

## O que sai e o que fica

| Sai | Fica |
|---|---|
| Maestro, Executor e Sentinela como papéis atribuídos por marca | As fichas `despacho`, `revisor` e `escrivao`, que são funções de uma sessão, não crachás de uma IA |
| "Claude rege, Codex constrói, Antigravity audita" | `.claude/agents/` e `.codex/agents/`: as três IAs continuam trabalhando aqui |
| "Codex nunca pergunta ao mantenedor", "Antigravity nunca edita" | "Subagente não pergunta ao mantenedor nem cria subagente", que já era lei geral e cobre o caso |
| O correio da sentinela e o rádio entre as IAs | A fila e o livro, que já carregam o que está por fazer e o que aconteceu |
| A coluna de papel no ranking das IAs | O ranking inteiro, contagem, custo e retrabalho |

## O rádio sai

O rádio (`MensagemDoRadio`, `ci/radio.py`, a tela em `/admin/radio/`) nasceu para
três IAs de papéis distintos trocarem recado sem o mantenedor levar e trazer
texto. Sem papel fixo, ele duplica o que a fila e o PR já fazem, e duplicação de
fato é exatamente o que a lei da casa proíbe: fato nenhum mora em dois lugares.

A remoção apaga a tabela e as mensagens já gravadas. O mantenedor autorizou a
remoção nas palavras citadas acima.

## O ranking fica

O ranking das IAs (`/admin/ranking-ias/`, `ci/ranking_das_ias.py`,
`painel/ranking-ias.json`) nasceu em 17/09/2026, depois da tríade e por outro
motivo: medir quanto cada IA publicou em `main` e o que custou, para que o plano
de uso de cada uma seja decidido por número. Isso é cooperação medida, não papel
atribuído, e sobrevive intacto.

O que ele perde é a coluna `papel`, que hoje imprime "Maestro", "Executor" e
"Sentinela" embaixo de cada nome. Uma tela que continuasse anunciando crachá
extinto ensinaria a lei errada a quem a lesse.

## O que esta decisão não muda

- O rito do PR: bancada por `ci/sessao.py`, `make pr` com recibo e eventos a
  bordo, integração automática pelos dois checks obrigatórios, com mandato
  CODEOWNERS e contrato congelado preservados.
- A lei do lote: pedido colado numa sessão continua sendo lote regido por
  aquela sessão, qualquer que seja a IA, com as fichas de `.claude/agents/` ou
  `.codex/agents/`.
- O canal entre sessões por `gh pr comment`, só em PR aberto. Tarefa nova
  continua exigindo `python ci/fila.py criar`, decisão e mandato.
- Trabalho novo descoberto no caminho vira tarefa na fila (`RITOS.md` §5) e
  volta a quem rege o lote.

## O histórico não se apaga

A `DECISAO-triade-de-ias.md` continua no repositório, marcada como revogada. Mais
de quarenta registros, eventos e tarefas em `fila/` e `painel/` citam maestro,
executor e sentinela porque foi assim que aconteceu. Apagar o arquivo apagaria o
porquê e deixaria esses rastros apontando para o vazio.

## Quem faz valer

`ci/padrao_de_trabalho.py` (teto e integridade do `CLAUDE.md`),
`ci/leis_sem_mecanismo.py` (toda lei declara quem a faz valer) e
`ci/tests/test_fichas_de_robo.py` (as fichas continuam válidas sem os papéis).
A ausência de papel fixo não precisa de portão: ela é a remoção de um texto que
portão nenhum media.

## A memória

- 12/09/2026: o mantenedor pede a tríade, e ela entra na lei com três papéis
  fixos.
- 17/09/2026: nasce o ranking das IAs, por outro pedido e outro motivo.
- 18/09/2026: o mantenedor encerra a tríade. Os papéis saem da lei, o rádio sai
  do produto, o ranking fica.
