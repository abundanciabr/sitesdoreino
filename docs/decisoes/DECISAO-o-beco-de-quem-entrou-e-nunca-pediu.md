# DECISÃO — o beco de quem entrou e nunca pediu

**Data:** 29/08/2026 · **Quem decidiu:** o mantenedor · **Estado:** valendo

## O que aconteceu

O mantenedor entrou no meshcraft.top com a conta dele — a mesma que ele tinha
acabado de remover da escola — e viu isto, e nada mais:

> Meshcraft
> Em breve teremos muitas novidades.

Nenhum caminho. Nenhum botão. A home tinha exatamente uma coisa a oferecer a
ele, e ela era o silêncio.

O formulário de pedir entrada existia o tempo todo, inteiro e funcionando, na
Caixa de Sugestões. Só que **ninguém chega a um endereço que a tela não
mostra** — e quem entra pelo Google não tem por que saber que "Caixa de
Sugestões" é onde se pede para estudar aqui.

## O que esta decisão reverte

A `DECISAO-categorias-de-usuario.md` (28/08/2026) §5. Naquele dia o mantenedor
escolheu, **entre três opções e nominalmente**, que quem nunca pediu nada não
veria nada sobre a escola na home. A escolha tinha um motivo bom: até então o
caminho da Caixa aparecia para todo mundo que entrava, e quem não era aluno
clicava para receber um *"não encontramos matrícula para esse e-mail"*.

**Ele revogou essa escolha em 29/08/2026, depois de cair no próprio beco.** A
decisão de ontem curava um defeito real e criava outro: trocou uma porta que
batia na cara por uma parede sem porta nenhuma.

O que muda, em uma frase: **quem é `cadastrado` passa a ver um convite para
pedir entrada.** O convite não promete matrícula — diz que a equipe decide
quem entra, que é a verdade sobre a fila de liberação.

## O que NÃO mudou, e é o que impede o erro simétrico

O convite aparece **só para quem a célula `alunos` CONFIRMOU ser
`cadastrado`** — nunca para quem ela não conseguiu responder sobre.

Isso importa porque `categoria` faz *fail-open* para `cadastrado` quando a
`alunos` está fora do ar, e a direção desse fail-open continua certa (o pior
caso aceitável é alguém não ver o próprio atalho por alguns segundos). Mas
com o convite no ar, o mesmo fail-open passaria a **convidar um aluno a pedir
a entrada que ele já tem** — o defeito de 28/08 de cabeça para baixo: uma tela
afirmando o que a outra célula desmente.

Por isso o template pergunta duas coisas, e não uma:

```
{% elif request.ator.categoria == "cadastrado" and request.ator.categoria_conferida %}
```

`categoria_conferida` é a property nova de `AtorDaRequisicao`: responde se a
`alunos` respondeu, e não custa uma segunda ida à rede.

**Não saber não é motivo para oferecer nada a ninguém.** A regra de 28/08 não
morreu; ela encolheu para o caso em que ainda é verdadeira.

## O que também não mudou

- **`{% elif %}` explícito, nunca `{% else %}`.** Categoria nova que a `alunos`
  invente amanhã cai fora de todos os ramos e não mostra nada. Um `else` a
  adotaria em silêncio, e a tela passaria a convidar gente que ninguém decidiu
  convidar.
- **O destino é a Caixa, e não um caminho novo.** É onde o formulário da fila
  já mora, e é para lá que o ex-aluno já vai desde a
  `DECISAO-a-ficha-nao-se-apaga.md` §3. Duas portas para o mesmo pedido
  discordariam na primeira mudança de regra.
- **O rótulo do convite é diferente do de quem volta.** *Pedir entrada* e
  *Pedir para voltar* são frases distintas de propósito: dizer "voltar" a quem
  nunca esteve aqui é a tela afirmando uma passagem que não existiu.
- **Esconder ou mostrar continua não autorizando nada.** A Caixa confere
  matrícula na entrada dela, como sempre.

## Guardas

`services/funil/tests/test_categorias_na_home.py`:

- `test_o_cadastrado_ve_o_convite_para_pedir_entrada` — o beco, travado. Ele
  **substituiu** `test_o_cadastrado_nao_ve_o_caminho_da_caixa`, que media o
  contrário; a substituição de um teste-guarda é a forma de uma reversão de lei
  aparecer no código, e por isso esta decisão existe escrita.
- `test_nao_saber_nao_convida_ninguem` — o erro simétrico, travado.
- `test_o_convite_nao_e_o_rotulo_de_quem_volta` — as duas frases não colapsam.
- `test_o_visitante_continua_vendo_so_o_convite_de_entrar` — o convite não
  vaza para quem não entrou.

## O que isto NÃO resolve

Este é o primeiro dos cinco consertos que o mantenedor aprovou em 29/08/2026,
depois do mapa da jornada do aluno. Continuam em aberto, e cada um tem o seu
PR: a tela viva da jornada no painel · busca e filtro na lista de alunos ·
cadastrar alguém à mão · avisar pelo sino quando a situação muda.
