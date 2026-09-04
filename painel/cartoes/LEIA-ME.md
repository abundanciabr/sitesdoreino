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
| `acao` | **obrigatório em número de resultado no andar 0** (desde 03/09/2026 à noite): o que fazer quando ele está abaixo do esperado. Regra dos documentos do Scale OS traduzida: "se este número mudar, alguém faz algo diferente? se não, sai da primeira tela" |
| `direcao` | `subir` (mais é melhor) · `descer` (menos é melhor) · `faixa`; opcional, é o que diz se uma seta para cima é boa ou má notícia |
| `unidade` | pessoas, reais, dias, por cento; opcional |
| `alvo_do_mes` | só na barra do mês (`compras-no-mes`): a meta que o mantenedor fixa para o mês corrente; `null` = a tela deriva a fatia da linha reta do ciclo que cai no mês |

**Os cartões do andar 0 hoje (reformulação de 03/09/2026, registro `20260903-036`):**
`compras-no-ciclo` (a Meta 1: de 0 até o alvo do cartão, somadas, de 03/09 a
15/12/2026, repartidas pela curva de `semanas`), `compras-no-mes` (a barra do mês, zera no dia 1) e o par
`alunos-ativos-30d` (ainda sem fonte). `alunos-na-plataforma` desceu ao andar
1: continua lido, é o mesmo número do mapa da jornada. A data que conta nos
dois de compras é `virou_aluno_em` (a liberação pela fila ou a confirmação do
pagamento; Rito de Contrato do PR #933), nunca a que a pessoa digitou.

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
