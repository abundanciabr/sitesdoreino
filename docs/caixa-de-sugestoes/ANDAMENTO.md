# ANDAMENTO — Caixa de Sugestões

> **Para você, mantenedor.** Uma página, sem jargão: o que já está no ar, o que
> está sendo feito agora e o que espera na fila. Toda sessão que trabalhar na
> Caixa atualiza esta página **e** o painel no fechamento — se os dois
> discordarem, avise: é bug de processo.
>
> Última atualização: **25/08/2026** — EVO-30 entregue: a Caixa ganhou rosto.

**Legenda:** ⬜ na fila · 🔵 em andamento · ✅ entregue (com prova) · 🔴 travado · 🙋 precisa de você

## Onde estamos

**Fase atual: LOTE 3 FECHADO — A CAIXA TEM ROSTO E TEM ROADMAP (25/08/2026).** O EVO-30 e o EVO-31 estão no ar: o aluno abre o quadro em grade, alterna entre *Mais votadas* e *Novas*, vota e desvota no card, abre uma ideia e vê o histórico com a resposta da equipe, manda a dele com a busca de duplicata na frente — e agora vê **por onde as ideias andaram**, nas quatro zonas do roadmap (com as recusadas e as mescladas em "Fora do trilho", nunca escondidas), e a página de avisos ganhou a mesma linguagem visual do quadro. *(Marco anterior: LOTE 2, 24/08/2026 — a Caixa entrou no ar)* em `meshcraft.top/forms/sugestoes/` (medido da internet: `/entrar` responde 200). O plano mestre existe, a auditoria do
terreno foi feita, e o nome e o endereço estão decididos: a ferramenta chama-se
**Caixa de Sugestões** e vai morar em **meshcraft.top/forms/sugestoes/**. Falta
a conversa EVO-01 aconteceu em 23/08/2026 e **o Lote 1 já pode partir**, sem nenhuma pendência sua.

## 🙋 Precisa de você (tudo que o plano inteiro vai pedir)

| Quando | O quê | Como vai chegar |
|---|---|---|
| ~~Antes do Lote 1~~ ✅ | ~~Conversa EVO-01~~ **FEITA em 23/08/2026** — decisão: **Entrar com Google**, e só entra quem tem matrícula. O link mágico foi descartado (a plataforma não manda e-mail). Lei em `DECISAO-EVO-01-identidade.md` | — |
| No Lote 2 | Criar o banco `sugestoes_db` na VPS + preencher o `sugestoes.env` real — **agora inclui criar o aplicativo OAuth no Google** (ID de cliente + segredo, retorno em `/forms/sugestoes/entrar/google/retorno`) e a lista `SUGESTOES_STAFF_EMAILS` | UM bloco de colar, fail-closed, com a janela rotulada |
| No Lote 4 | Assinar `APROVADO_POR` no primeiro ChangeSpec real | Um campo para preencher, nada técnico |

## Lote 0 — Alicerce

| Despacho | O que entrega | Estado | PR | Nota |
|---|---|---|---|---|
| EVO-00 | Auditoria do estado real da plataforma (identidade, bancos, eventos, como nasce célula) | ✅ | #78 | feita em 23/08 — `AUDITORIA-AS-IS.md`; achado maior: não existe login de aluno na plataforma |
| EVO-01 | Decisão de arquitetura que sobrou: **como o aluno se identifica** | ✅ | — | **fechada em 23/08/2026**: Entrar com Google prova quem é, a célula `alunos` decide se pode (só matriculado). Staff por lista de e-mails no env. `DECISAO-EVO-01-identidade.md` é a lei |

## Lote 1 — A célula nasce

| Despacho | O que entrega | Estado | PR | Nota |
|---|---|---|---|---|
| EVO-10 | A célula `sugestoes` existe, sobe e passa no CI | ✅ | #108 | canário; achou que faltava declarar a célula no `rollback.yml` — a auditoria Q4 estava incompleta |
| EVO-11 | Os dados: quadros, sugestões, votos, comentários, histórico | ✅ | #113 | IDs opacos (não UUID); histórico append-only em 3 degraus, o 3º é trigger no Postgres |
| EVO-12a | Entrar com Google (a porta) | ✅ | #116 | dividido do EVO-12 por orçamento; suíte roda com a REDE PROIBIDA, provado |
| EVO-12b | Aluno sugere, vota, desvota, comenta e vê o quadro | ✅ | #122 | busca de duplicata, limite 3/7 dias, avaliação interna invisível ao aluno (3 degraus) |
| EVO-13 | Equipe muda status e avalia (só staff) | ✅ | #126 | histórico na MESMA transação; `nao_planejado` exige justificativa; guarda que protege a §4.1 |

## Lote 2 — Eventos e produção

| Despacho | O que entrega | Estado | PR | Deploy | Nota |
|---|---|---|---|---|---|
| EVO-20 | Cada fato vira evento (outros sistemas podem reagir) | ✅ | #130 | — | 4 eventos congelados pelo Rito (#128); provado em Redis real, XLEN=1 após 4 voltas do relay |
| EVO-21 | Aluno recebe aviso quando a sugestão dele muda de status | ✅ | #133 | — | **NÃO foi na mensageria**: ela não manda e-mail (stub) e exigiria vazar o e-mail do aluno. Decisão do mantenedor: sininho dentro da Caixa |
| EVO-22 | A Caixa entra no ar na VPS | ✅ | #129 | **run verde** | o passo do mantenedor virou script versionado (#131/#132/#134) depois de falhar 3x como bloco de colar |

## Lote 3 — O rosto

| Despacho | O que entrega | Estado | PR | Nota |
|---|---|---|---|---|
| EVO-30 | O quadro visual do protótipo v2: ver, votar, sugerir pelo navegador | ✅ | #166 | **deploy verde 25/08**; coube inteiro em 14 arquivos (sem split 30a/30b); suíte 218 → 233. Achado que vale para a plataforma: `armadilhas/102` — sob prefixo de caminho, `{% static %}` e `{% url %}` leem prefixos DIFERENTES, e a página chega sem estilo **só em produção** |
| EVO-31 | O roadmap público + o sininho de notificação | ✅ | #175 | fecha o Lote 3; coube em 12 arquivos, suíte 233 → 252. A faixa vive DENTRO do quadro (âncora `#roadmap`, sem rota nova) e obedece ao filtro de categoria — quem decidiu isso foi um guarda do EVO-12b, vermelho. `nao_planejado`/`mesclado` ficam em "Fora do trilho", com guarda aritmético: zonas + saídas == quadro. A aba "Em alta" e o "Meu impacto" continuam na V1.2 |

## Lote 4 — O corredor

| Despacho | O que entrega | Estado | PR | Nota |
|---|---|---|---|---|
| EVO-40 | Trava de segurança: nada entra "em desenvolvimento" sem ChangeSpec aprovado por você | ⬜ | — | |
| EVO-41 | MVP declarado pronto, com o checklist da spec conferido item a item | ⬜ | — | fecha o plano |

## Linha do tempo

- **25/08/2026** — **EVO-30: a Caixa ganhou rosto** (PR #166, deploy verde). Despachado dentro de um lote de 5 frentes paralelas; coube inteiro em 14 arquivos. O guarda morde: quebrar o link do estilo deixa 7 testes vermelhos. Prova de fora, ao vivo: o quadro exige login (302 para `/entrar`) e a folha de estilo responde 200 no endereço com o prefixo da célula. Achado promovido a `armadilhas/102` — `funil` e `checkout` estavam certas por **acidente de endereço**, não por desenho.

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
