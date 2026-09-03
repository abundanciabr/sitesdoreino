# painel/cartoes/ — o cartão de cada número do painel de gestão

> Nascida em 03/09/2026, degrau 0 do `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`
> (§2). A lei desta pasta: **número sem cartão não aparece em tela nenhuma.**

## O que é um cartão

Um arquivo `<nome>.json` por métrica, versionado no Git, por PR. Ele responde,
em português e para leigo, o que aquele número É, de onde vem, quem tem o
direito de declará-lo, e qual outra métrica o segura. É a tradução do "registro
de métricas" que as arquiteturas de receita pedem (v2 §65, v3 §93), no molde
da casa: arquivo por entrada, nunca uma lista mantida à mão.

| Campo | O que é |
|---|---|
| `nome` | igual ao nome do arquivo, sem `.json` (a tela confere) |
| `tipo` | `resultado` (retrovisor) · `direcao` (volante, move-se esta semana) · `par` (segura outra métrica) · `confianca` (quanto se pode acreditar) |
| `andar` | 0 a 4, o andar do painel onde o número mora (plano, §3) |
| `pergunta` | a pergunta que o número responde, sem sigla |
| `definicao` | o que conta e o que não conta |
| `formula` | como se calcula |
| `fonte` | de onde o número sai; `null` se a fonte ainda não existe, e aí `sem_fonte_porque` é obrigatório |
| `autoridade` | quem tem o DIREITO de declarar este número (a célula dona, ou `mantenedor` para medição digitada) |
| `dono` | quem responde por ele |
| `frequencia` | tempo real, diária, por ciclo |
| `par` | o nome do cartão que segura este; só `confianca` dispensa |
| `alvo`, `ate`, `partida`, `partida_em` | a meta, os quatro juntos ou nenhum: Y, a data, o X do dia em que a meta foi fixada, e esse dia |
| `limiar_ambar`, `limiar_vermelho` | quando a cor muda (ou `null` até a primeira medição) |
| `versao`, `desde` | a versão da régua e desde quando vale; mudar `formula` sem subir `versao` reprova |
| `componentes` | só em número composto; composto nunca desce ao andar 0 |

## As regras, e quem as faz valer

- **Cartão ausente ou inválido ⇒ a tela abre, diz o que faltou, e não mostra o
  número.** Fail-closed, como o painel do dono com registro inválido.
- **Toda métrica que pode ser forçada tem par.** Conversão sobe, reembolso
  tem que ficar parado; alunos sobem, alunos ativos têm que subir junto.
- **Composto nunca no andar 0.** Uma nota de 0 a 100 esconde qual componente
  se mexeu.
- **A régua mora aqui; o fato mora no livro.** Alvo e data são parâmetros
  (por PR). A decisão do mantenedor de fixá-los é um registro em
  `painel/registros/`, tipo `decisao`, citando o PR.

Quem faz valer: `services/admin/apps/core/placar.py::validar` e
`services/admin/tests/test_placar.py` (inclusive o caso que DEVE reprovar).
Esta pasta viaja inteira para a imagem da `admin` junto com o resto de
`painel/`.
