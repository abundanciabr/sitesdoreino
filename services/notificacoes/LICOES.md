# LIÇÕES — célula `notificacoes`

O que já custou tempo *dentro desta célula*. O que vale para qualquer célula
mora em `armadilhas/` (leia o `INDICE.md` e abra só a entrada que casa com a
sua tarefa).

## Esta célula é BURRA de propósito — não conserte isso

Ela não faz leque, não pergunta nada a ninguém e não decide quem deve ser
avisado. Uma carta que chega no fio já vem endereçada a UMA pessoa, e vira UMA
linha. Se você se pegar escrevendo aqui um laço sobre votantes, uma chamada HTTP
para a Caixa, ou uma regra do tipo "quem comentou também recebe" — pare: isso é
da célula que PUBLICA, e foi decidido assim pelo mantenedor no Rito de Contrato
de 26/08/2026 (`docs/decisoes/DECISAO-fase-2-do-sininho.md` §1).

O ganho não é elegância: é que o custo por carta não muda quando dez células
estiverem publicando.

## A célula nasceu sem tela e sem contrato — e isso é lei, não pendência

`freeze: not-applicable` no `ci/manifesto-de-contratos.json`, e `config/urls.py`
com uma rota só. Quem for consumir esta célula passa pela **Fase 4** do
`docs/notificacoes/PLANO-MESTRE.md`, que é Rito de Contrato (RITOS §3, com o
mantenedor presente). Publicar uma rota antes disso é fabricar a fronteira
dentro de um despacho — e o guarda `tests/test_healthz.py` reprova.

## O contador é uma CÓPIA, e cópia diverge

`ContadorDeNaoLidos` existe porque o sino aparece em toda página e `COUNT(*)`
numa tabela que só cresce fica lento exatamente quando o produto der certo
(`DECISAO-notificacoes` §5.2). O preço é um modo de falha que a versão lenta não
tinha: o número na tela deixar de bater com a caixa.

Duas regras que não são estilo:

1. **A linha e o contador nascem na mesma transação.** Um contador somado "logo
   depois" diverge no primeiro erro de rede e nunca mais volta sozinho.
2. **`F("nao_lidos") + 1`, nunca ler-somar-gravar.** Duas cartas chegando ao
   mesmo tempo para a mesma pessoa leriam o mesmo valor e gravariam o mesmo
   `+1`; uma das somas se perderia, sem erro nenhum.

Guarda das duas: `tests/test_inv_contador_bate_com_a_tabela.py`.

## O `ator_id` vem do ENVELOPE, não do `data`

É a única adaptação desta célula à receita R4 v1, e está declarada no ponto de
chamada de `consume_eventos.py` em vez de escondida. O Rito de Contrato pôs o
`ator_id` no nível de cima do envelope de propósito: assim qualquer célula lê
"quem fez isto" sem conhecer o formato do assunto. Um handler que só recebesse
`data` obrigaria o `ator_id` a descer para dentro de cada assunto — o desenho
que o rito recusou.

Use `.get("ator_id")`, nunca `[...]`: o contrato declara o campo **nulável**
(fato de máquina não tem gente), e estourar ali trocaria "não havia ator" por "a
célula caiu".

## Arquivar é mover de tabela, e nunca toca no contador

`NotificacaoArquivada` é tabela separada, não uma coluna `arquivada`: uma coluna
deixaria as linhas velhas engordando o índice que a página do sino percorre em
toda visita. E `arquivar_lidas()` **não** mexe no contador — quem sai da conta é
o LIDO, no momento da leitura. Se o arquivamento descontasse também, descontaria
duas vezes, e um contador que anda sozinho para baixo some com avisos da cara da
pessoa sem nada indicando o que houve.

## Rodar os testes desta célula, do zero

```bash
docker run -d --rm --name notif-pg-dev -e POSTGRES_USER=dev -e POSTGRES_PASSWORD=dev \
  -e POSTGRES_DB=notificacoes_db -p 55450:5432 postgres:17
cd services/notificacoes
DATABASE_URL=postgres://dev:dev@localhost:55450/notificacoes_db \
REDIS_STREAMS_URL=redis://localhost:6379/0 DJANGO_SECRET_KEY=ci python -m pytest -q
```

Os guardas do consumidor **não** precisam de Redis: eles chamam
`processar_envelope()` direto, que é onde mora a decisão. Redis de verdade só
faria a suíte demorar e falhar por motivo alheio.
