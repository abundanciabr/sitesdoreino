# Constituição da Célula: notificacoes (A Caixa Central de Avisos)
> **Jurisdição:** governa apenas `services/notificacoes/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA (nascida em 26/08/2026, PR de gênese) · **Merge:** auto-merge permitido com CI verde

## Missão
Guardar os avisos de cada pessoa da plataforma, num lugar só, e responder barato
à pergunta que o site vai fazer em toda página: *"quantos avisos eu tenho?"*.
Lei da gênese: `docs/decisoes/DECISAO-notificacoes.md`. As três escolhas de
desenho do mantenedor: `docs/decisoes/DECISAO-fase-2-do-sininho.md`. Mapa das
sete fases: `docs/notificacoes/PLANO-MESTRE.md`.

**Ela é BURRA de propósito.** Não faz leque, não pergunta nada a ninguém e não
decide quem deve ser avisado. Uma carta que chega já vem endereçada a uma pessoa
e vira uma linha. É isso que a mantém barata quando dez células estiverem
publicando — e é decisão registrada, não simplicidade acidental.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/notificacoes/**`
- **SOMENTE LEITURA:** `contracts/eventos/notificacao.devida.v1.json` — o
  contrato da carta, congelado no Rito de 26/08/2026
- **PROIBIDO (nem ler):** as demais células, `infra/`, qualquer segredo.
  **Especialmente o banco da `sugestoes`:** a tentação de "só dar um SELECT para
  saber quem votou" é a Lei 2 sendo desfeita, e o desenho existe justamente para
  essa consulta nunca ser necessária

## Comunicação
- **Expõe:** `/healthz`, e **mais nada**. A célula nasce sem tela e sem
  superfície de máquina (`freeze: not-applicable` no
  `ci/manifesto-de-contratos.json`). Quem for consumi-la passa pela **Fase 4** do
  PLANO-MESTRE, que é Rito de Contrato (`RITOS.md` §3, com o mantenedor
  presente). Rota nova aqui antes disso é fronteira fabricada dentro de um
  despacho — e o `tests/test_healthz.py` reprova
- **Consome:** o fio, stream `eventos.notificacao.devida`. Só isso. Nenhuma
  chamada HTTP a ninguém, nem para saber quem é a pessoa: a carta já chega
  endereçada pelo id da plataforma
- **Emite:** nada. Esta célula é ponto final, não intermediária
- **Banco:** `notificacoes_db` (role `notificacoes_user` — não enxerga nenhum
  outro database). Provisionado por `infra/provisionar-notificacoes.sh`

## Invariantes desta célula
- **[INV-NOT1] Uma linha por carta, e o contador anda junto.** A mesma carta
  reentregue não vira duas (o fio entrega *pelo menos uma vez* por desenho), e o
  `ContadorDeNaoLidos` é somado na MESMA transação da linha. Ler o contador custa
  o mesmo com 1 e com 50 avisos. Teste-guarda:
  `tests/test_inv_contador_bate_com_a_tabela.py` e
  `tests/test_inv_carta_entregue_duas_vezes_vira_uma_linha.py`.
- **[INV-NOT2] O que a célula consome casa com o contrato congelado**, lido do
  arquivo — nunca copiado para dentro do teste. Teste-guarda:
  `tests/test_inv_carta_casa_com_o_contrato.py`.
- **Notificação é DADO, jamais frase pronta.** Guardamos `assunto` +
  `parametros`; a frase nasce na LEITURA, no idioma de quem lê. O site serve três
  idiomas: gravar o texto congela o idioma de quem gravou, e **texto já gravado
  não se traduz depois** (`DECISAO-notificacoes` §5.1). É irreversível — por isso
  é lei, não recomendação.
- **`F("nao_lidos") + 1`, nunca ler-somar-gravar.** Duas cartas chegando ao mesmo
  tempo para a mesma pessoa leriam o mesmo valor e gravariam o mesmo `+1`; uma
  das somas se perderia, sem erro nenhum.
- **Arquivar é mover de tabela, e NUNCA toca no contador.** Quem sai da conta é o
  lido, no momento da leitura. Descontar de novo ao arquivar faria o contador
  andar sozinho para baixo — e contador baixo demais some com aviso da cara da
  pessoa sem nada indicando o que houve.
- **Nada de e-mail entra aqui.** A trava é do contrato
  (`additionalProperties: false` no `data` e em cada forma de `parametros`), e o
  INV-NOT2 prova que ela morde deste lado também. O e-mail vive numa linha só,
  dentro da Caixa (`DECISAO-EVO-01` §3).

## Definição de Pronto
`make ci` verde (lint · type · testes · `contrato-check`, que hoje responde SKIP
declarado) + evidência vermelho→verde de todo guarda novo no corpo do PR.

## Ritos
- Sessão nasce em worktree próprio (`RITOS.md` §1), citando este arquivo.
- Superfície pública nova ⇒ **Rito de Contrato** (`RITOS.md` §3), nunca dentro de
  um lote (`RUNBOOK-LOTES.md` §7).
- Assunto novo de notificação é **um PR pequeno**: um valor no `enum` do contrato
  e um ramo em `parametros`. Se exigir mexer na forma da tabela, do consumidor ou
  do contador, o desenho está errado e se conserta ANTES — é requisito do
  primeiro PR (`DECISAO-notificacoes` §3).
