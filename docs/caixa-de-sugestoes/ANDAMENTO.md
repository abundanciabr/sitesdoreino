# ANDAMENTO — Caixa de Sugestões

> **Para você, mantenedor.** Uma página, sem jargão: o que já está no ar, o que
> está sendo feito agora e o que espera na fila. Toda sessão que trabalhar na
> Caixa atualiza esta página **e** o painel no fechamento — se os dois
> discordarem, avise: é bug de processo.
>
> Última atualização: **25/08/2026** — Lote 4 fechado: a Caixa tem corredor, e o MVP foi auditado.

**Legenda:** ⬜ na fila · 🔵 em andamento · ✅ entregue (com prova) · 🔴 travado · 🙋 precisa de você

## Onde estamos

**Fase atual: LOTE 4 FECHADO — O MVP ESTÁ PRONTO E AUDITADO (25/08/2026).** A
Caixa deixou de ser só um lugar de escrever ideia: agora tem **corredor**. Nada
entra "em desenvolvimento" sem um ChangeSpec que **você** assinou (a trava é
mecânica, em três camadas — não há como contornar por engano), e **todo mundo
que interagiu com uma ideia** fica sabendo quando ela anda, não só quem a
escreveu. A pasta `docs/changespecs/` nasceu, com um molde pronto para copiar.

E o checklist do MVP foi **conferido item a item contra o código de verdade**,
com o método caro: quebrar o programa de propósito para ver se os testes
reclamam. Os cinco itens fecharam sem nenhum FAIL —
[`AUDITORIA-MVP.md`](AUDITORIA-MVP.md) tem os vereditos e as evidências. Três
achados vieram junto, e os três são de **texto do plano**, não de defeito no que
está no ar (detalhe na linha do tempo abaixo).

*(Marcos anteriores: LOTE 3, 25/08 — a Caixa ganhou rosto e roadmap · LOTE 2,
24/08 — a Caixa entrou no ar em `meshcraft.top/forms/sugestoes/`.)*

## 🙋 Precisa de você (tudo que o plano inteiro vai pedir)

| Quando | O quê | Como vai chegar |
|---|---|---|
| ~~Antes do Lote 1~~ ✅ | ~~Conversa EVO-01~~ **FEITA em 23/08/2026** — decisão: **Entrar com Google**, e só entra quem tem matrícula. O link mágico foi descartado (a plataforma não manda e-mail). Lei em `DECISAO-EVO-01-identidade.md` | — |
| No Lote 2 | Criar o banco `sugestoes_db` na VPS + preencher o `sugestoes.env` real — **agora inclui criar o aplicativo OAuth no Google** (ID de cliente + segredo, retorno em `/forms/sugestoes/entrar/google/retorno`) e a lista `SUGESTOES_STAFF_EMAILS` | UM bloco de colar, fail-closed, com a janela rotulada |
| ~~No Lote 4~~ ✅ | ~~Ligar a lista de quem pode aprovar na VPS~~ **FEITO em 25/08/2026** (H22 no `ARMADILHAS-OPERACAO.md`): `SUGESTOES_APROVADORES` está no ar, e hoje só você está nela | — |
| **Quando houver uma ideia de gente para virar trabalho** | **Assinar `APROVADO_POR` no primeiro ChangeSpec real.** É um nome e uma data num arquivo de texto (molde pronto em `docs/changespecs/CS-TEMPLATE.md`), nada técnico — e enquanto ninguém assinar, nenhuma ideia sai de "Planejado", que é o lado seguro | Alguém escreve o rascunho e te mostra; você lê e assina |

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
| EVO-40 | Trava de segurança: nada entra "em desenvolvimento" sem ChangeSpec aprovado por você | ✅ | #187 | trava em **três camadas** (a tela, o programa e o próprio banco de dados), cada uma provada separadamente. Quem aprova é só quem está em `SUGESTOES_APROVADORES` — **lista vazia = ninguém aprova**, de propósito. Lei em `DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md` |
| EVO-42 | O aviso deixa de ser só do autor: quem votou e quem comentou também fica sabendo | ✅ | #193 | um aviso por pessoa distinta, com o motivo escrito ("sua ideia" × "ideia em que você votou"), tudo na mesma transação da mudança de status. O custo em consultas ao banco **não** cresce com o tamanho da plateia — está medido |
| EVO-41 | MVP declarado pronto, com o checklist da spec conferido item a item | ✅ | *(este)* | fecha o plano. `docs/changespecs/` nasceu (ponteiro para a lei + molde); os 5 itens do checklist auditados por mutação em [`AUDITORIA-MVP.md`](AUDITORIA-MVP.md): **nenhum FAIL**, 3 ressalvas, todas de redação do plano |

## Linha do tempo

- **25/08/2026 (noite)** — **LOTE 4 FECHADO: o MVP está pronto, e foi auditado
  de fora.** O EVO-40 pôs a trava (#187), o EVO-42 abriu o leque de avisos
  (#193) e o EVO-41 fechou o registro: a pasta `docs/changespecs/` existe, com
  um **ponteiro** para a lei do formato (não uma cópia — duas cópias derivam em
  silêncio, e isso já custou dois PRs neste mesmo lote) e um molde pronto para
  copiar, com o campo da sua assinatura **em branco**.

  A auditoria do checklist do MVP foi feita pelo método caro: **quebrar o
  programa de propósito, 15 vezes, e exigir que os testes reclamem** em cada
  uma. Todas reclamaram. Resultado: **nenhum item reprovado**, e três achados —
  os três de *texto do plano*, não de defeito no que está no ar:

  1. o plano exigia, para declarar o MVP pronto, um teste de uma
     funcionalidade que o **próprio plano** adiou para a versão seguinte
     (juntar ideias repetidas). As duas exigências não cabiam juntas; o que
     existe hoje é o portão que impede alguém de *marcar* uma ideia como
     "juntada" sem que nada tenha sido juntado;
  2. o plano dizia "a página da equipe responde *proibido* a qualquer um sem
     crachá". Medido: ela responde *proibido* a quem já entrou e não é da
     equipe, e manda para a tela de entrada quem nem entrou — que é o certo, e
     o texto é que estava largo demais;
  3. o plano pedia que o aviso ao resto da plataforma fosse enviado *antes* de
     a mudança ser gravada. O código faz o contrário e faz certo: **grava
     junto, envia depois** — enviar antes é o jeito clássico de anunciar um
     fato que ainda pode ser desfeito.

  Junto veio um recado de manutenção: a **auditoria do terreno de 23/08**
  (`AUDITORIA-AS-IS.md`) envelheceu em quatro pontos — o maior deles é a frase
  *"não existe login de aluno na plataforma"*, que era o achado principal dela
  e hoje está falsa (a célula de identidade nasceu e está no ar). Ela continua
  valendo como fotografia datada; a tabela do que mudou está no item 5 da
  [`AUDITORIA-MVP.md`](AUDITORIA-MVP.md).

  **Fica de fora, e é rito, não esquecimento:** o sininho ao lado do seu nome em
  **todo** o site (hoje ele só aparece dentro da Caixa). Para isso, o site
  precisaria perguntar à Caixa quantos avisos a pessoa tem — uma conversa nova
  entre duas partes do sistema, e essas conversas só se abrem numa sessão
  dedicada, com você presente. Também de fora: a aba "Em alta" e o painel "Meu
  impacto", que são V1.2.

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
