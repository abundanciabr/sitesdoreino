# ANDAMENTO — Caixa de Sugestões

> **Para você, mantenedor.** Uma página, sem jargão: o que já está no ar, o que
> está sendo feito agora e o que espera na fila. Toda sessão que trabalhar na
> Caixa atualiza esta página **e** o painel no fechamento — se os dois
> discordarem, avise: é bug de processo.
>
> Última atualização: **23/08/2026** — nome e endereço definidos; auditoria feita.

**Legenda:** ⬜ na fila · 🔵 em andamento · ✅ entregue (com prova) · 🔴 travado · 🙋 precisa de você

## Onde estamos

**Fase atual: Lote 0, quase fechado.** O plano mestre existe, a auditoria do
terreno foi feita, e o nome e o endereço estão decididos: a ferramenta chama-se
**Caixa de Sugestões** e vai morar em **meshcraft.top/forms/sugestoes/**. Falta
só a conversa EVO-01 (abaixo) para o Lote 1 poder começar.

## 🙋 Precisa de você (tudo que o plano inteiro vai pedir)

| Quando | O quê | Como vai chegar |
|---|---|---|
| Antes do Lote 1 | Conversa EVO-01: decidir **como o aluno entra** na Caixa (proposta: link mágico pelo e-mail da matrícula, sem senha) | Uma conversa numa janela raiz; o agente prepara tudo antes |
| No Lote 2 | Criar o banco `sugestoes_db` na VPS + preencher o `sugestoes.env` real | UM bloco de colar, fail-closed, com a janela rotulada |
| No Lote 4 | Assinar `APROVADO_POR` no primeiro ChangeSpec real | Um campo para preencher, nada técnico |

## Lote 0 — Alicerce

| Despacho | O que entrega | Estado | PR | Nota |
|---|---|---|---|---|
| EVO-00 | Auditoria do estado real da plataforma (identidade, bancos, eventos, como nasce célula) | ✅ | #78 | feita em 23/08 — `AUDITORIA-AS-IS.md`; achado maior: não existe login de aluno na plataforma |
| EVO-01 | Decisão de arquitetura que sobrou: **como o aluno se identifica** (proposta: link mágico pelo e-mail da matrícula) | 🙋 | — | única reunião do plano; nome, endereço e nomes de evento já foram decididos em 23/08 |

## Lote 1 — A célula nasce

| Despacho | O que entrega | Estado | PR | Nota |
|---|---|---|---|---|
| EVO-10 | A célula `sugestoes` existe, sobe e passa no CI | ⬜ | — | canário do lote |
| EVO-11 | Os dados: quadros, sugestões, votos, comentários, histórico | ⬜ | — | |
| EVO-12 | Aluno consegue sugerir, votar e comentar (via API) | ⬜ | — | |
| EVO-13 | Equipe consegue mudar status e avaliar (só staff) | ⬜ | — | |

## Lote 2 — Eventos e produção

| Despacho | O que entrega | Estado | PR | Deploy | Nota |
|---|---|---|---|---|---|
| EVO-20 | Cada fato vira evento (outros sistemas podem reagir) | ⬜ | — | — | |
| EVO-21 | Aluno recebe aviso quando a sugestão dele muda de status | ⬜ | — | — | célula mensageria |
| EVO-22 | A Caixa entra no ar na VPS | ⬜ | — | — | inclui o passo 🙋 do banco |

## Lote 3 — O rosto

| Despacho | O que entrega | Estado | PR | Nota |
|---|---|---|---|---|
| EVO-30 | O quadro visual do protótipo v2: ver, votar, sugerir pelo navegador | ⬜ | — | |
| EVO-31 | O roadmap público + o sininho de notificação | ⬜ | — | |

## Lote 4 — O corredor

| Despacho | O que entrega | Estado | PR | Nota |
|---|---|---|---|---|
| EVO-40 | Trava de segurança: nada entra "em desenvolvimento" sem ChangeSpec aprovado por você | ⬜ | — | |
| EVO-41 | MVP declarado pronto, com o checklist da spec conferido item a item | ⬜ | — | fecha o plano |

## Linha do tempo

- **23/08/2026 (noite)** — **Nome e endereço decididos pelo mantenedor:**
  *Caixa de Sugestões*, em `meshcraft.top/forms/sugestoes/`. A célula passa a
  chamar-se `sugestoes` e os eventos ganham nomes no padrão da casa
  (`sugestao.criada`, `sugestao.votada`…). Renomeado enquanto ainda era papel:
  zero linha de código escrita, custo zero.
- **23/08/2026 (tarde)** — **O apagão do CI acabou**: o mantenedor tornou o
  repositório público (saída C do H3), depois de varredura de segredos limpa
  no histórico completo. Minutos de Actions ilimitados; este PR pôde ser
  mergeado e o plano entrou na `main`.
- **23/08/2026** — A auditoria EVO-00 foi executada (não precisa de CI): as 5
  perguntas respondidas com evidência em `AUDITORIA-AS-IS.md`. Achado maior:
  **não existe login de aluno em nenhuma célula** — a decisão de identidade é
  o coração da reunião EVO-01. O plano ganhou a seção 5.1 com 4 ajustes.
  O apagão do CI foi re-testado no mesmo dia (rerun dos checks do PR #78):
  **continua** — mesma mensagem de cobrança do GitHub.
- **22/08/2026 (noite)** — O PR do próprio plano (#78) ficou **represado**: o
  GitHub parou de executar qualquer CI (suspeita de cota de minutos esgotada —
  ARMADILHAS H14, item 1 do "Precisa de você agora" no painel). O plano está
  pronto; o merge acontece assim que o CI voltar. Nenhum lote dispara antes disso.
- **22/08/2026** — Plano mestre em 5 lotes criado a partir das duas
  especificações e do protótipo v2. Modelo de despacho e esta página criados.
