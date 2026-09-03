# 300 — O rito de pouso em três passos deixou o mantenedor esperando o robô, que esperava por ele

**Sintoma.** O mantenedor abre a conversa horas depois e escreve: *"eu fiquei
esperando por horas aqui só pra descobrir que você é que estava esperando por
mim, lamentável o dia todo esperando por isso"*. Nos fatos, os PRs do dia
tinham pousado em minutos e os deploys estavam verdes. O que ele viu foi outra
coisa: uma sessão que terminou dizendo "quando o PR pousar, o placar estará no
ar", e nenhuma frase dizendo **"nada mais depende de ninguém, isto acontece
sozinho em uns 8 minutos"**. Para quem não lê código, "o robô parou de falar" e
"o robô está esperando alguma coisa de mim" são a mesma cena.

**Causa.** Duas, e a segunda é a que dá a lição.

1. O rito de pouso tinha três passos separados (esperar os checks, `--conferir`,
   `--pousar`), e os dois últimos dependiam de o robô VOLTAR para executá-los.
   Qualquer sessão que termine entre um passo e outro deixa um PR verde e
   parado, sem que ninguém o perceba: a pista só atende quem tem a etiqueta.
   Nesta sessão os passos foram cumpridos, mas o desenho permitia o buraco, e
   ele já tinha sido pisado antes por outras sessões.
2. O relatório final obedeceu à lei "peça pouso e vá embora" e NÃO disse, com
   todas as letras, que nada dependia de ninguém nem quanto tempo a fila leva.
   É a mesma família da `armadilhas/161` (espera sem voz é indistinguível de
   trabalho) vista do outro lado: **silêncio sem explicação é indistinguível de
   espera**, e o mantenedor esperou.

**Solução.**

1. **O caminho inteiro num comando** (desde 03/09/2026):
   `python ci/esperar.py --checks <N> --teto 20 --e-pousar`, pela ferramenta
   `Monitor`. A própria espera, ao ver os checks verdes, chama o MESMO portão
   (`ci/mergear.py <N> --pousar`) e pede o pouso. Vermelho, estouro ou medição
   impossível nunca viram pedido, e o portão continua recusando por conta
   própria (base velha, dívida do livro, registro ausente). `CLAUDE.md` e
   `RITOS.md` §2 peça 5 ensinam este caminho como o normal.
2. **O relatório final diz o que acontece sozinho e quanto demora.** "Os PRs
   estão na fila da pista; ela mergeia sem ninguém, em 8 minutos de mediana; o
   deploy leva mais 3; você não precisa fazer nada." Uma frase, sempre. Está
   escrito no `CLAUDE.md`, passo 3 do rito.
3. **Quando algo de fato depende dele, é caixa estruturada, não frase solta**
   (regra que já existia, `~/.claude/CLAUDE.md`). Aqui a caixa foi aberta, mas
   depois dela veio o fechamento sem a frase do item 2.

**Quem faz valer:** `ci/tests/test_espera.py` (os cinco testes de `--e-pousar`,
inclusive vermelho que nunca chama o portão e portão que recusa). A frase do
relatório final não tem mecanismo; é lei em prosa, e está no `CLAUDE.md`.
