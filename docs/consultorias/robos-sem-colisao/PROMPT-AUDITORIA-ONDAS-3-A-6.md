# PROMPT DE AUDITORIA — as Ondas 3 a 6 (29/08/2026)

> **Como usar:** abra uma sessão NOVA do Claude Code neste repositório e cole o
> bloco inteiro abaixo, do `---` ao `---`. A sessão que fez o trabalho não pode
> ser a que audita — é o ponto inteiro.
>
> Existe também a auditoria EXTERNA prevista na Parte 5 do plano mestre (cada
> consultor volta e confere o próprio parecer). Esta aqui é a interna, e é mais
> barata: ela roda contra o GitHub e o código, sem ninguém de fora.

---

Você é uma sessão de AUDITORIA. Você não construiu nada disto e não deve
confiar em nenhuma afirmação sem medir. Seu trabalho não é melhorar o código:
é dizer **o que é verdade**.

## O que foi feito (a afirmação a auditar)

Em 28–29/08/2026, uma sessão executou as Ondas 3, 4, 5 e 6 do
`docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`, em 18 PRs (#434 a #451). O
resumo do que ela AFIRMA ter entregue:

| # | Afirmação |
|---|---|
| 434 | o boletim contava o teto da amostra como se fosse o total; agora conta pelo Git |
| 435 | `painel.html` e `livro-*.js` saíram do Git; quem os materializa é a integração |
| 436 | o arquivo de mês passou a ter um registro por linha |
| 438 | entrega que falha reverte sozinha para a última imagem publicada |
| 439 | as células sobem em ordem de dependência (provedor antes de consumidor) |
| 440 | a reversão distingue "não há imagem anterior" de "não consegui medir" |
| 441 | o agente não mergeia mais: pede pouso, e a pista mergeia |
| 442 | nasceu `celulas.yml` com um varredor que o impede de mentir |
| 443 | o `ci-celula` virou matriz: roda a suíte de CADA célula tocada |
| 445 | contrato cresce por adição; remover exige a etiqueta `contrato-remocao` |
| 446 | **a cerca "1 PR = 1 célula" caiu** |
| 447 | toda lei declara quem a faz valer; 21 leis, 18 com mecanismo, 3 em dívida |
| 448 | nenhum teste some em silêncio (apagado, reduzido ou desligado) |
| 449 | a `main` vermelha abre sozinha o PR de reversão |
| 450 | existem métricas da fábrica, e elas não reprovam nada |
| 451 | a pista deixou de terminar vermelha (dependia de permissão que não tem) |

## As regras da sua auditoria

1. **Não pergunte ao projeto se algo foi feito. Meça.** Documento é afirmação,
   não prova. `gh`, `git`, os arquivos e os testes são prova.
2. **Sabote antes de acreditar.** Para cada guarda novo, quebre de propósito o
   que ele promete guardar e confirme que ele fica VERMELHO. Guarda que nunca
   foi visto reprovando é guarda que ninguém sabe se reprova. **Desfaça a
   sabotagem depois** (`git checkout -- <arquivo>`), e nunca commite sabotagem.
3. **Distinga os três estados** (`RETROSPECTIVA-FASE-D.md` §1): PASS, FAIL e
   ERROR. Um portão que fica verde por não conseguir medir é o defeito central
   desta casa — procure especificamente por isso.
4. **Procure o que a sessão NÃO viu.** Ela conferia o resultado ("o PR entrou?")
   e deixou passar um workflow que terminava vermelho toda vez. Pergunte de cada
   peça: *o instrumento está verde, ou só o resultado?*
5. **Leia primeiro:** `armadilhas/INDICE.md` (só as entradas que casarem com o
   que for tocar), `docs/decisoes/RETROSPECTIVA-FASE-D.md` (os 8 padrões) e o
   `CLAUDE.md`.

## As sete perguntas que interessam

Responda cada uma com **CONFIRMADO**, **NÃO CONFIRMADO** ou **NÃO CONSEGUI
MEDIR**, sempre com o comando e a saída crua.

1. **A cerca caiu de verdade, e o que a substituiu funciona?** Abra um PR de
   teste que toque DUAS células ao mesmo tempo e veja se o `ci-celula` roda as
   duas suítes. Se rodar só uma, a cerca caiu sem substituto — o pior desfecho
   possível. (Feche o PR de teste ao terminar; não mergeie.)

2. **O painel sobrevive à materialização?** `painel.html` não está no Git. Prove
   que ele chega à imagem da célula `admin` mesmo assim, e que um registro novo
   aparece no painel online. Se não chegar, o painel do mantenedor congelou em
   silêncio — exatamente a doença que ele existe para curar.

3. **A reversão automática reverte para o lugar certo?** Leia `ci/reversao.py` e
   procure o caso em que ela escolheria uma imagem ERRADA. Ela nunca rodou de
   verdade num deploy quebrado — só em teste. O que acontece se o registry
   responder devagar em vez de responder errado?

4. **A pista pode entrar em laço ou perder um PR?** Ela agora atende até 5 PRs
   por passagem. Procure o caminho em que um PR fica na fila para sempre, e o
   caminho em que a mesma passagem mergeia algo que não devia.

5. **O censo de leis mede ou decora?** As 18 declarações `**Quem faz valer:**`
   apontam para portões que realmente impõem aquela lei — ou para arquivos que
   só existem? Escolha 5 ao acaso e confira o que o portão citado de fato faz.

6. **A catraca de testes é contornável?** Ache um jeito de reduzir a proteção
   real dos testes sem que ela reprove. (Ela mesma admite dois: `assert True` e
   mover teste entre arquivos. Procure um terceiro.)

7. **O que ficou pela metade?** Compare a Parte 4 do plano mestre (as 56
   recomendações com veredito) com o que existe hoje. Liste o que foi ACEITO e
   não foi feito — sem inventar prioridade, só a lista.

## O que entregar

- Um relatório por pergunta, com comando e saída crua.
- **Um registro no livro** (`painel/registros/`, molde em `painel/LEIA-ME.md`)
  com o veredito consolidado, em português para leigo. Se a auditoria achar
  defeito, ele vira registro do tipo `incidente`.
- Se achar defeito com correção clara e pequena, **abra o PR** (peça pouso com
  `python ci/mergear.py <N> --pousar`; o merge não é mais do agente).
- Se achar defeito grande, **não conserte**: descreva, e deixe a decisão para o
  mantenedor numa pergunta estruturada.

**A resposta mais valiosa que você pode dar é "esta afirmação não se sustenta".**
Uma auditoria que só confirma não pagou o próprio custo.

---
