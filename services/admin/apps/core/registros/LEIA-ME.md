# registros/ - o que as telas do placar leem do livro

Esta pasta guarda os registros que o placar lê: só os tipos `medicao` e
`compromisso`. Cada registro é um arquivo novo nesta pasta.
Registro existente não se edita: a atualização é outro registro, que aponta
para o anterior em `responde_a`.

A célula `admin` lê só o CABEÇALHO de cada arquivo (`direcao.ler_registros`),
campo por campo, por linha. Por isso:

- cada campo fica numa linha própria, no formato `nome: valor,`;
- o valor é `null`, `true`, `false`, um número inteiro ou um texto entre aspas
  duplas, na mesma linha, sem aspas duplas dentro do texto;
- nome do arquivo: `AAAAMMDD-NNN-slug.js`, e o campo `arquivo` é o mesmo nome
  sem o `.js`. O `NNN` não pode repetir no mesmo dia.

## Os campos que as telas leem

| campo | o que é |
| --- | --- |
| `arquivo` | o nome do arquivo sem `.js` |
| `tipo` | `medicao` ou `compromisso` |
| `quando` | o dia em que o FATO aconteceu, `AAAA-MM-DD` |
| `titulo` | uma linha, para leigo, sem sigla |
| `responde_a` | o `arquivo` de outro registro que este fecha, ou `null` |
| `vence_em_dias` | prazo em dias; obrigatório em `compromisso`, número maior que zero |
| `precisa_do_dono` | `true` ou `false` |
| `foto` | só em `medicao`: os números medidos, `nome=valor; nome=valor` |
| `problema`, `hipotese`, `metrica`, `guarda` | só no experimento (abaixo) |
| `veredito` | só no resultado de um experimento (abaixo) |
| `portao` | o portão da escola que o registro prova (abaixo) |
| `evidencia`, `verificado_em` | a prova, e o dia em que foi conferida |

## Molde de uma `medicao`

O arquivo inteiro, exatamente neste formato:

```js
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260926-001-contagem-da-rede",
  tipo: "medicao",
  quando: "2026-09-26",
  titulo: "Contagem da rede de talentos",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/999",
  verificado_em: "2026-09-26",
  precisa_do_dono: false,
  responde_a: null,
  foto: "estudios-parceiros=3; encaixes-com-estudio=1",
  vence_em_dias: null
});})();
```

`foto` usa o nome de cada cartão de `apps/core/cartoes/` e o número medido.
Sem `foto` a medição vale como texto, mas o bloco "o que mudou" da capa não
consegue compará-la com o placar.

### Experimento e resultado

Um experimento é uma `medicao` que declara a aposta ANTES de saber o resultado:
`problema` (o que dói), `hipotese`, `metrica` (qual número ela quer mover),
`guarda` (o que a faz parar antes da hora) e `vence_em_dias`. Os cinco campos
vêm juntos.

O resultado é um registro NOVO, também `medicao`, com `responde_a` apontando
para o experimento e `veredito` com uma destas três palavras: `venceu`,
`perdeu`, `nao-deu-para-saber`.

### Portão da escola

`portao` diz qual dos oito portões o registro prova: `demanda`, `conversao`,
`economia`, `entrega`, `resultado`, `retencao`, `repeticao` ou `escala`.
Declarar não é provar: sem `evidencia` E `verificado_em` o portão não conta. Na
dúvida, `portao: null`.

## Molde de um `compromisso`

O que alguém promete fazer nesta semana. Quem o cumpre escreve outro registro
com `responde_a` apontando para ele. O veredito (cumprido, não cumprido, em
aberto) é calculado disso, nunca marcado à mão.

```js
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260928-003-fechar-a-lista-de-estudios",
  tipo: "compromisso",
  quando: "2026-09-28",
  titulo: "Fechar a lista de estúdios parceiros até sexta",
  evidencia: null,
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  vence_em_dias: 7
});})();
```

## Criar o arquivo

Crie o arquivo novo nesta pasta (`services/admin/apps/core/registros/`) e abra
um PR. Confira antes com `pytest tests/test_direcao.py` dentro de
`services/admin`: o teste lê a pasta inteira e reprova se algum registro ficar sem
`tipo`.
