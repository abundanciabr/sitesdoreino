# 363 — A lei afirmava que a compra já informava o curso, e o evento não carrega o campo

**Sintoma:** uma lei recém-aprovada declara que metade de um invariante "já está
resolvida porque a porta X exige o campo", e o guarda que você constrói fica
verde sem cobrir o caminho que realmente cria a maioria das linhas. Ninguém vê
nada vermelho, e a lei parece cumprida.

**Onde já aconteceu:** 06/09/2026, TAR-220. A
`DECISAO-cursos-matriculas-e-alunos.md` §3 e §4 dizem, por escrito, que "quem
entra pela compra já informa o curso: `POST /matriculas` exige `product_id` no
corpo, e o checkout o manda", e concluem que o buraco é um só (a sala de espera).
O despacho repetiu a mesma frase. Medido no `origin/main`:

- `POST /matriculas` é o **reprocesso manual**, e a lei o tomou pela porta da
  compra;
- a porta da compra de verdade é o **evento**, e
  `contracts/eventos/pagamento.aprovado.v1.json` **não tem `product_id`**;
- `services/alunos/apps/matriculas/handlers.py` grava `product_id=""`, e a
  própria `LICOES.md` da célula já dizia isso desde a primeira fase.

Ou seja: o caminho que cria toda matrícula paga do site continua produzindo
exatamente a linha que o invariante proíbe, e nenhum teste da célula reprova por
isso, porque o guarda novo mora na outra porta.

**Causa:** uma lei é escrita a partir de uma leitura do sistema, e a leitura pode
errar de porta. Nome parecido basta: `POST /matriculas` e "a matrícula que a
compra cria" soam como a mesma coisa e não são. Quem executa a lei chega com ela
já aprovada, com a medição dentro dela apresentada como fato, e é natural
construir em cima em vez de conferir embaixo.

**Solução:**

1. **A medição que a lei carrega se refaz, não se herda.** Toda vez que um
   despacho diz "isto já existe, é só ligar", abra os dois arquivos e confira: o
   que a porta exige, e quem de fato chama aquela porta em produção. Custou dez
   minutos aqui; custaria um invariante mentindo por semanas.
2. **A divergência não vira silêncio nem vira conserto por conta própria.** O
   evento é de outra célula e mudá-lo é Rito de Contrato: o caminho é escrever o
   furo, com todas as letras, nos três lugares onde alguém vai passar (o
   invariante em `INVARIANTES.md`, a docstring da função que o guarda, e o
   cabeçalho do arquivo de teste), e devolver a divergência a quem tem
   autoridade sobre a lei.
3. **Invariante com metade coberta é declarado como metade.** A seção "o que
   este invariante NÃO alcança" é obrigatória quando a cobertura é parcial. Um
   invariante que se apresenta inteiro e cobre metade é pior do que nenhum: ele
   compra a confiança que o outro não tinha.

**Irmã de:** `armadilhas/195` (guarda que não morde quando sabotado) e do padrão
"garantia sem mecanismo" da `RETROSPECTIVA-FASE-D`. A diferença é a origem: aqui
o mecanismo existe e funciona, e o que está errado é a fronteira que a lei
imaginou para ele.
