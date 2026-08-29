# DECISÃO — Mergear é trabalho do agente

> **Decidida pelo mantenedor em 22/08/2026**, em sessão, com estas palavras (resumo
> fiel): *"quero remover essa parte de pedir ao humano pra mergear — os agentes fazem
> essa parte de mergear; isso fazia parte do projeto antigo, obsoleto, e só serviu
> para atrasar tudo."* Este documento registra o que mudou, por quê, e o que
> continua proibido — para que nenhuma sessão futura reintroduza o gargalo por
> arqueologia de documento antigo.

## O problema (medido, não sentido)

- A CI roda em **15–70 s**. A latência PR→merge real: **mediana 22 min, média
  264 min** — o gargalo era a janela de atenção do mantenedor, não a máquina
  (PLANO-10X, Alavanca 1, com as medições de origem).
- A "aprovação do dono" exigida pela antiga Lei 4 era **inexecutável por
  construção**: o repositório tem um único colaborador e o GitHub proíbe aprovar
  o próprio PR (H9 — PRs #38–#42, todos com `reviews=0`). A lei era prosa.
- O mantenedor é leigo em código: a revisão humana de um diff nunca foi uma
  camada real de segurança aqui — as camadas reais sempre foram os portões.

## A decisão

**O agente mergeia. O humano não é mais parte do fluxo de merge — nem como
executor, nem como aprovador prévio.** Em troca, nada do que MEDE ficou mais
frouxo; o que saiu foi só a espera:

| Continua igual (as proteções) | Saiu (o gargalo) |
|---|---|
| `muralhas` + `ci-celula`/`ci-celula-gate` verdes, obrigatórios | pedir ao humano para mergear |
| `ci/mergear.py` recusa vermelho/pendente/ausente/skip não declarado ([INV-CI01]) | esperar a janela de atenção dele |
| labels (`arquitetural`, `contrato`), orçamento de 15 arquivos, cerca de célula | aprovação prévia em caminho CODEOWNERS |
| Rito de Contrato (RITOS §3) por inteiro — sessão de arquitetura com o mantenedor | |
| `alarme-main` (issue se a main quebrar) | |
| **portão de deploy** — commit não-verde não alcança a VPS (provado ao vivo: runs 32567765127 / 32567900961) | |
| botão de merge do site: continua proibido para todos | |

## A mecânica nova

```bash
python ci/mergear.py <N> --conferir     # os checks acabaram? tudo verde?
python ci/mergear.py <N> --confirmo <N> # mergeia e confere state=MERGED
```

- `--confirmo` exige **repetir o número do PR** — preserva, no caminho
  não-interativo, a defesa de identidade da pergunta original (o erro real da
  história foi mergear o PR #21 no lugar do #20, nunca "merge sem querer").
- O script deixou de usar `gh pr merge --yes` (a flag não existe no `gh` 2.97.0
  desta máquina — H6, resolvido junto): o stdin de todo subprocesso de portão é
  fechado por construção (`_nucleo.executar`), e sem TTY o `gh` age sem perguntar.
- Depois de disparar o merge, o próprio script **confere no GitHub** que o PR
  virou `MERGED` (Lei 6: merge não se declara, confere-se) — e lembra o agente
  do painel e do run de deploy.
- Teste-guarda novos em `ci/tests/test_mergear.py`: `--yes` não pode voltar,
  `--confirmo` errado cancela sem chamar o `gh`, e "o gh não reclamou" sem
  `state=MERGED` é FAIL.

## Jurisdição CODEOWNERS: o que substitui a aprovação prévia

Nos caminhos que a antiga lei travava (`contracts/`, `services/pagamentos/`,
`services/checkout/`, `infra/`, `ci/`, `.github/`, arquivos-lei da raiz):

1. **Mandato** — só se mergeia ali o que o despacho do mantenedor pediu. Agente
   não decide sozinho entrar na fortaleza; ele executa o que foi despachado.
2. **Transparência imediata** — todo merge nesses caminhos é **anunciado
   nominalmente** no relatório final da sessão e registrado no painel. O
   mantenedor fica sabendo sempre, sem precisar autorizar antes.
3. **Reversibilidade** — a resposta canônica a qualquer merge ruim continua
   sendo revert por PR (e rollback por tag para produção, RITOS §4). O revert
   da prova vermelha (#55→#56) levou minutos.

O `.github/CODEOWNERS` continua no repositório como **mapa de jurisdição** (é
ele que define onde o anúncio é obrigatório), não como trava.

## O que este documento NÃO muda

- **Push direto na `main`**: continua proibido e bloqueado pelo `.githooks/pre-push`.
- **Rito de Contrato**: mudar `contracts/` continua exigindo sessão de
  arquitetura com o mantenedor, PR só de contrato, label `contrato`. O agente
  passa a executar o merge desse PR — a liturgia antes dele é a mesma.
- **Teste é intocável** (RITOS §2.3), orçamento, cerca, freeze: intactos.
- **O botão do site**: fisicamente ainda funciona com tudo vermelho (H3 — sem
  branch protection possível no plano atual). Não usar. A rede por trás é o
  portão de deploy + `alarme-main`.
- **VPS, segredos, console do provedor, settings do GitHub**: continuam sendo
  exclusivamente do mantenedor.

## Onde a mudança foi escrita

| Arquivo | O quê |
|---|---|
| `CONSTITUICAO.md` Lei 4 | a lei reescrita: certificação mecânica + mandato/transparência no lugar de aprovação prévia |
| `RITOS.md` §2 peça 4 | o rito do fecho da catraca (o passo a passo do merge pelo agente) |
| `ci/mergear.py` | `--confirmo`, remoção do `--yes` (H6), conferência `state=MERGED` embutida |
| `ci/_nucleo.py` | stdin fechado por construção em todo subprocesso de portão |
| `ci/tests/test_mergear.py` | 4 testes-guarda novos (148 no total, verdes; 4 vermelhos sem o fix) |
| `CLAUDE.md` | o fluxo operacional por sessão + gatilhos de painel |
| `PLAYBOOK.md` | tabela de células e §2 atualizados; H6 marcado resolvido |
| `ARMADILHAS.md` | H6 ✅, H9 ✅, §5.9 reescrito, §5.9.1 resolvido |
| `PROMPTS-INICIAIS.md` | nota de atualização no "Como operar" |
| `02-RED-TEAM.md` | golpe 9 reescrito (testa o portão, não a review que nunca existiu) |
| `INVARIANTES.md` | degrau 1 da escada atualizado |

**Primeira prova viva:** o próprio PR desta decisão foi mergeado pelo agente,
pelo fluxo novo (`--conferir` → `--confirmo`), com o número registrado no painel
— nenhum clique humano envolvido.

---

## Emenda de 29/08/2026 — o merge passou do agente para a pista

Esta decisão continua de pé no que ela resolveu: **o mantenedor saiu do caminho
crítico do merge, e não volta.** O que mudou é qual máquina executa o gesto.

**O que a realidade mostrou em sete dias.** A `main` passou a receber ~100
entregas por dia, e desde 28/08 ela exige que o PR esteja em dia com a base no
INSTANTE do merge (`strict_required_status_checks_policy`). O agente mergeia com
o resultado de checks que rodaram ANTES de a fila andar — e, num dia movimentado,
ele perde a corrida contra o próprio relógio: atualiza, espera 90s de checks, a
`main` anda, repete. Medido: **oito voltas num PR de quatro arquivos e nenhuma
linha de código** (`armadilhas/156`). Não é falta de disciplina; é um desenho em
que o agente disputa com um relógio que não controla.

**A decisão do mantenedor** (29/08/2026, registro `20260829-006`, respondendo ao
pedido `20260828-033`): o agente **pede pouso** e vai embora; quem mergeia é a
pista (`.github/workflows/pouso.yml`), que atende um PR por vez, atualiza com a
`main` do momento, confere pelo MESMO `ci/mergear.py` e mergeia. Ela tem a
paciência que o agente não tem, e não gasta franquia esperando.

**O que NÃO muda, e é o coração desta decisão:** ninguém espera pelo mantenedor.
Quem mergeia continua sendo máquina. As jurisdições CODEOWNERS, o mandato e o
anúncio nominal seguem idênticos.

**A honestidade sobre a trava:** a recusa dentro do `ci/mergear.py` é
**disciplina, não muralha** — o agente tem o mesmo `gh` autenticado que a pista.
Ela tira o caminho fácil e aponta o certo, como a muralha da pasta compartilhada.
A muralha de verdade contra merge com base velha é o `strict` do conjunto de
regras da `main`, que roda no servidor e não depende de ninguém se comportar.

Onde a emenda foi escrita: `CONSTITUICAO.md` Lei 4 · `RITOS.md` §2 peças 4 e 5 ·
`CLAUDE.md` · `ci/mergear.py` (`--pousar`, e a recusa do `--confirmo`) ·
`ci/tests/test_mergear.py` (a recusa, a etiqueta, e o guarda de que só o
`pouso.yml` declara a identificação da pista).
