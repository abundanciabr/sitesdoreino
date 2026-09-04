# Constituição da Célula: metricas (o livro de fatos da plataforma)

> **Jurisdição:** governa apenas `services/metricas/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA (nascida em 04/09/2026, PR de gênese, degrau 7.1 do plano
> do painel de gestão) · **Merge:** pela pista (`ci/mergear.py --pousar`), com
> CI verde

## Missão

Guardar a HISTÓRIA dos fatos da escola para que o painel do mantenedor possa
dizer o que mudou, e não só o que é. Hoje toda tela de gestão conta ao vivo,
perguntando às células a cada abertura: isso responde "quantas alunas há
agora", nunca "quantas havia na semana passada". Um número sem passado não
sustenta meta, coorte, marco nem experimento.

Esta célula recebe os eventos que as outras publicam, guarda-os **imutáveis**,
e responde por API de leitura. Ela é **consumidora, nunca dona**: não decide
nada sobre pessoa, matrícula, ponto ou mensagem. O dono de cada fato continua
sendo a célula que o emitiu.

Lei do assunto: `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` §6.2 (o livro de
fatos), §6.4 (marcos, coortes, dimensões), §6.6 (a confiança) e a escada do
§8, degrau 7. A régua de cada número mora nos cartões (`painel/cartoes/`), e
não aqui: esta célula guarda o fato, o cartão diz o que ele significa.

## Fronteiras

- **PERMITIDO ESCREVER:** `services/metricas/**`
- **SOMENTE LEITURA:** `contracts/eventos/*.json` (o que ela recebe) e, quando
  existir, `contracts/metricas.openapi.yaml` (o que ela promete responder)
- **PROIBIDO (nem ler):** as demais células, `infra/`, qualquer segredo.
  Em especial, **é proibido consultar API de outra célula para "completar" um
  fato**: o que o evento não trouxer, esta célula não sabe, e dizer "não sei"
  é resposta legítima. Preencher buraco perguntando ao vivo transformaria o
  livro de fatos num espelho do presente, que é exatamente o que ele não é

## Comunicação

- **Expõe (telas):** nenhuma, hoje e sempre. Quem mostra número é a `admin`,
  que já tem porta, crachá e uma leitora só (o mantenedor). A única rota da
  gênese é `/healthz`, de máquina
- **Expõe (contrato, a partir do degrau 7.4):** a recepção de eventos
  (`/interno/eventos`) e a API de leitura (`/api/metricas/`): fotos de coorte,
  marcos por pessoa, contadores históricos por dia, cobertura de rastreio,
  conciliação e as fotos semanais de que o bloco "o que mudou" precisa. Nada
  responde sem Bearer, e `/interno` **resolve** pela borda pública quando há
  prefixo (`armadilhas/186`): quem fecha a porta é o token, nunca a topologia
- **Consome:** ninguém, por desenho. `celulas.yml` diz `consome: []` e vai
  continuar dizendo mesmo com a célula completa, porque `consome` mede leitura
  de API alheia e esta célula lê EVENTOS. Quem a consome é a `admin`, e é o
  mapa dela que ganha `metricas` no PR do cliente (`armadilhas/224`)
- **Auth:** Bearer dedicado por par, `TOKENS_ACEITOS_<PAR>`. Env ausente ⇒
  conjunto vazio ⇒ 401 para todo mundo (fail-closed sem derrubar o boot)
- **Emite:** nada. Um livro de fatos que emite fato vira fonte de si mesmo, e
  o laço fecharia sem ninguém ver. A exceção prevista é o registro de
  INCIDENTE quando um evento chega inválido, e isso vai para o livro de
  ocorrências (`painel/registros/`), pelo caminho de sempre, não por evento
- **Banco:** `metricas_db` (role `metricas_user`, que não enxerga nenhum outro
  database). Guarda eventos crus, a fila de eventos mortos, marcos derivados e
  fotos. **Só ids opacos viajam e só ids opacos ficam:** nome, e-mail e texto
  de mensagem não entram aqui. Para contar não é preciso saber quem é

## Invariantes desta célula

- **[INV-P12] Esta célula NÃO assina sessão.** Sem `SessionMiddleware`, sem
  `django.contrib.sessions`, sem `SESSION_ENGINE`, sem `django.contrib.auth`,
  cookie de CSRF com nome próprio (`metricas_csrf`). Guarda:
  `tests/test_inv_metricas_nao_assina_sessao.py`, plantado na gênese e provado
  por mutação. A tentação aqui tem forma própria: esta célula guarda fatos
  sobre pessoas, e "de quem é este evento?" aparece em toda linha. A resposta
  vem do CORPO do evento, pelo contrato, nunca de quem fez a chamada

- **O fuso é a unidade da medição, não a exibição.** `TIME_ZONE` é
  `America/Sao_Paulo` e o armazenamento é UTC. Tudo o que esta célula responde
  é contagem por DIA, e um instante perto da virada muda de mês com o fuso
  errado, sem erro em lugar nenhum (`armadilhas/099`). A `admin` já conta
  assim (`placar.py::dia_em_sao_paulo`) e as duas contas têm de concordar.
  Guarda: `tests/test_fuso_horario.py`, provado por mutação

- **Um evento nunca se corrige; corrige-se acrescentando.** Fato gravado é
  imutável: sem `UPDATE`, sem `DELETE`. Correção é evento novo que aponta para
  o anterior. Guarda: nasce com a tabela, no degrau 7.2, e entra no
  `INVARIANTES.md` no mesmo PR

- **Duplicata se recusa pelo id externo, não pelo conteúdo.** Todo evento traz
  id próprio; receber o mesmo duas vezes grava uma vez. Entrega repetida é o
  normal de qualquer fila, e contar duas vezes é como uma métrica mente sem
  parecer errada

- **Fail-closed em fato inválido.** Evento que não casa com o contrato vai
  para a fila de eventos mortos e vira incidente no livro, com as três ações
  do painel (inspecionar, tentar de novo, descartar com motivo). **Nunca é
  aceito pela metade**: meio fato guardado é pior do que fato nenhum, porque o
  número resultante parece medido

- **"Não sei" é resposta.** Onde falta cobertura, a API diz que falta, e a
  `admin` mostra "sem dados" em vez de zero. Zero é uma afirmação sobre o
  mundo; ausência de dado não é

## Escada (o que nasce quando)

| Degrau | O que nasce |
|---|---|
| **7.1 FEITO** | A gênese: esqueleto, `/healthz`, os três guardas, o lugar da célula nos mapas da casa |
| 7.2 | O evento imutável e a fila de eventos mortos (tabela, migração, o guarda da imutabilidade) |
| 7.3 | A recepção (`/interno/eventos`), Bearer de par, teste de 401 em todas as operações, recusa de duplicata |
| 7.4 | A API de leitura, o contrato congelado pelo Rito, a `admin` como cliente |
| 7.5 | O compose (`infra/`), em PR próprio (`armadilhas/134`), com o env e o banco na VPS antes (`armadilhas/088`) |

Até o 7.5, o `deploy-celula` desta célula fica vermelho em todo merge que a
toca, e **isso é esperado**: o compose da VPS ainda não a conhece
(`armadilhas/088`).
