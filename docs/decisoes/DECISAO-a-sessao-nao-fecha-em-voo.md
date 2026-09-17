# DECISÃO: a sessão não fecha com entrega em voo

**Pedida pelo mantenedor em 17/09/2026**, depois de uma sessão do Codex que
encerrou com o PR aberto, os checks rodando e o ambiente local quebrado. As
palavras do próprio Codex, que ele trouxe:

> "Eu encerrei com trabalho ainda em andamento e transformei problemas meus de
> execução em pendências suas. Isso falha no objetivo de trabalhar de verdade."

E a ordem dele, na mesma mensagem: "A parte mais importante é transformar 1, 2
e 7 em verificações no hook/CI. Texto sozinho não bastou."

## A lei, em uma frase

**PR aberto é estado intermediário, nunca entrega final: enquanto houver ação
técnica segura disponível, o relatório é atualização e o Stop recusa o fecho.**

## As sete regras pedidas, e onde cada uma mora agora

| # | Regra | Onde | Mecanismo |
|---|---|---|---|
| 1 | Relatório com pendências é atualização, não fecho | CLAUDE.md, Lei 11 | portão do voo no Stop |
| 2 | CI em andamento é acompanhada até resultado terminal | CLAUDE.md, RITOS §2.8 | portão do voo; `ci/esperar.py` |
| 3 | Falha local de banco, processo ou ambiente é do executor | CLAUDE.md, Lei 11 | julgamento |
| 4 | Rascunho, check pendente ou commit não enviado é objetivo incompleto | CLAUDE.md, Lei 11 | portão do voo (rascunho e check) |
| 5 | Bloqueio não é veredito com ação segura disponível | CLAUDE.md, Lei 11 | julgamento |
| 6 | Bancada isolada antes de tocar código | CLAUDE.md, RITOS §1 | `ci/sessao.py` |
| 7 | O Stop recusa o fecho sem prova terminal | CLAUDE.md, Lei 11 | `ci/prestacao_de_contas.py` |

## O mecanismo, em uma frase cada

- O Stop já cobrava o RELATÓRIO. Agora, com o relatório escrito, ele mede o PR
  que ESTA sessão abriu: `gh pr view <N> --json state,isDraft,statusCheckRollup`.
- Só `MERGED` e `CLOSED` liberam o fecho. Rascunho, check vermelho, check sem
  resultado e PR verde ainda aberto são entrega em voo.
- A recusa entrega o comando: `ci/esperar.py --checks`, `--entrega`,
  `gh pr ready`, `ci/rerun_de_deploy.py --ultimo`.
- Uma recusa por situação (`1692:pendente`). Situação nova é fato novo e cobra
  de novo; a mesma situação duas vezes vira aviso, nunca laço.
- `gh` mudo é ERROR, não aprovação: o portão grita "isto NÃO é está tudo certo"
  e libera o turno (INV-CI01).

## Por que isto não é a espera em laço que a tríade proibiu

`DECISAO-triade-de-ias.md`, regra 2, proíbe esperar em laço, e ela continua
valendo. O portão não espera: mede uma vez, no fim do turno, e devolve um
comando que tem teto e morre sozinho. Estourado o teto, o fecho honesto é NÃO
PRONTO com a dívida no livro, e o portão aceita. A diferença entre as duas
coisas é quem segura a sessão: antes era o robô, olhando; agora é o teto.

## O que ficou de fora, de propósito

Commit não enviado e ambiente local quebrado NÃO entraram no mecanismo. Os dois
já caem no portão do relatório (trabalho de bancada nenhum passa calado), e
medi-los aqui cobraria a mesma dívida duas vezes, recusando a cada turno quem
editou, mediu e escreveu um NÃO PRONTO honesto. Continuam lei de texto, com o
executor respondendo pela remediação (Lei 11).

Também ficou de fora a tentativa que já falhou uma vez, documentada em
`ci/prestacao_de_contas.py`: adiar a cobrança até "não haver mais nada em voo"
lendo as notificações de tarefa de fundo do harness. Aquele sinal some sem
avisar, e sinal que some não vira guarda. O Git e o `gh` não somem.

## O que esta decisão não muda

- A integração continua automática (`DECISAO-merge-sem-rito-de-pouso.md`): o
  portão do voo não pede atestado, etiqueta nem gesto da maestro.
- O cancelamento escrito do mantenedor encerra a entrega na hora.
- A ficha do executor, o `AGENTS.md` e o `RUNBOOK-LOTES.md` continuam com o
  texto morto do rito de pouso. O mantenedor deu esse mandato ao Codex em
  17/09/2026, e é ele quem os corrige; esta decisão não toca nesses arquivos.

## Quem faz valer

`ci/prestacao_de_contas.py` (o portão do voo no Stop, ligado nos dois ganchos),
`ci/esperar.py` (o teto), `ci/rerun_de_deploy.py` (o deploy que não chegou) e
`ci/tests/test_prestacao_de_contas.py` (8 testes novos, 11 guardas provadas por
mutação).
