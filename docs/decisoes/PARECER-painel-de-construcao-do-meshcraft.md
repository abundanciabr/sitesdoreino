publico-para-ia: true

# PARECER — o "painel de construção do Meshcraft" que o prompt pede, e o que esta casa já tem

**Escrito em 04/09/2026 (noite)**, como o PR 1 do prompt "SESSÃO — PAINEL DE
CONSTRUÇÃO DO MESHCRAFT" que o mantenedor trouxe de uma IA de fora: *leitura e
diagnóstico, sem código; espere a aprovação do mantenedor*. O próprio prompt
manda: "onde este prompt contradisser a Constituição, os Ritos e o mapa para
IA, eles vencem; registre a contradição". Este parecer é o registro.

**Lido em `origin/main` no commit `5c7d992a`:** `CONSTITUICAO.md`, `RITOS.md`
(§1, §2, §5), `painel/ia/INDICE.md`, `painel/ia/03-sistema-do-painel-e-livro.md`
(o schema do registro, as vistas calculadas, a lei anti-duplicação, as regras
sutis), `painel/ia/04-arquitetura-de-celulas-e-contratos.md`,
`painel/ia/06-produto-decisoes-e-roadmap.md`, `painel/LEIA-ME.md`,
`fila/LEIA-ME.md`, `services/admin/apps/core/robos.py` (a aba "Os robôs"),
`docs/decisoes/PLANO-CELULA-CURSOS.md` (a lei aprovada em 04/09/2026) e os
nove documentos do projeto Meshcraft, que moram fora do repositório.

## 1. A resposta em três linhas

O painel de construção que o prompt descreve **já existe nesta casa em quase
tudo**, com outros nomes: a fila de trabalho é o manifesto, os eventos da fila
e os registros do livro são os registros de fato, a aba "Os robôs" e o painel
são as vistas, e as muralhas de todo PR são a auditoria mecânica. Construir o
que o prompt pede, como ele pede, criaria **uma segunda lista do que está por
fazer** e **um segundo lugar para o mesmo fato**: é exatamente o que a lei
anti-duplicação existe para proibir. O que falta de verdade cabe em três PRs
pequenos, e está na seção 5.

## 2. O que o prompt assume, e o repositório contradiz

| O prompt assume | O que existe de fato | Consequência |
|---|---|---|
| `docs/meshcraft/LEIA-ANTES.md` existe | Não existe. A lei do Meshcraft nesta casa é `docs/decisoes/PLANO-CELULA-CURSOS.md`, aprovada pelo mantenedor em 04/09/2026 (registro `20260905-001`), promovida a `DECISAO-celula-de-cursos.md` na gênese | O "LEIA-ANTES" que os documentos de fora propunham foi escrito de forma diferente: como plano com as emendas da casa |
| `docs/meshcraft/fonte/` guarda os nove documentos do curso | Não existe, **e não deve existir**: o repositório é público e o curso é obra não lançada (`armadilhas/331`). Os nove documentos moram fora, por decisão do mantenedor em 04/09/2026 | O prompt manda PARAR se a fonte não existir. A fonte existe; só não mora no repositório. Um portão de CI que confira "toda `origem` aponta para arquivo em `docs/meshcraft/fonte/`" é **impossível por construção**, e um portão impossível não se escreve |
| A Fase 6 vira uma célula `avaliacao` mais extensões | A casa decidiu **uma célula só, `cursos`**, com checkpoint e laudo juntos (plano §1); pares e Bancas são degraus dela | O manifesto não pode ser o remapeamento da revisão de fora; a escada real é a do plano §10 |
| Seis decisões pendentes bloqueiam itens | Quatro já respondidas pela casa: o capítulo é `aula`; o portfólio é da `pages`; `alunos` não tem progresso por lição (é da `cursos`); mantenedor e autora não são a mesma pessoa. Restam duas (contratos entre alunos e Ficha de Delegação; coleção de cartas), mais uma nova (onde moram os vídeos, adiada por ele para o degrau 1.8) | Os bloqueios são três, não seis |
| Conteúdo em `conteudo/meshcraft/`, verificável por "arquivo existe" | O conteúdo do curso entra pela tela do Admin, direto no banco da célula `cursos` (plano §3.1), nunca por arquivo commitado | "Existe" para as 33 encomendas, os 13 instrumentos e as 16 peças de cada aula só é medível **no banco da célula**, por contrato (`checkLesson`, `getContentStatus`), não por portão de CI |
| Os 66 plays não são itens; as portas G0 a G8 entram como itens de tipo `registro` | Concordo nos plays. As "portas" desta casa são as Sessões A e B com o mantenedor e os passos manuais dele: já são registros do livro (`pendencia` com `precisa_do_dono`, fechada por `resposta`), e a caixa "Precisa de você" é calculada deles | Não existe porta a modelar fora do livro |
| Um manifesto YAML `fase → lote → etapa → item` como norma | O "o que está por fazer" tem **uma casa só**: `fila/tarefas/` (RITOS §5), um arquivo por tarefa, com `depende_de`, `evidencia_exigida`, `move` (o cartão do placar que ela move) e estado **calculado** dos eventos | Um manifesto de itens ao lado da fila é uma segunda lista de trabalho: proibido pela lei anti-duplicação e pelo RITOS §5 |
| Tipos novos de registro (`meshcraft.item.iniciado`, `.entregue`, `.aceito`, `.devolvido`, `.porta.*`, `.decisao`, `.excecao`, `.lacuna.*`) | Já existem, com os nomes da casa: `iniciado` = evento `reivindicada` da fila; `entregue` = evento `concluida` (evidência e `verificado_em` obrigatórios); `devolvido` = `devolvida`/`bloqueada`; `aceito` por pessoa = registro `resposta` do mantenedor com `responde_a`; `decisao` (R1) = registro `decisao`; `excecao` (R3) e `lacuna` = `pendencia`/`nota` | Nenhum tipo novo; mudar o vocabulário é mudança em `painel/logica.js`, por PR, e não há razão |
| Sete vistas novas no gerador de `painel/painel.html` | A capa do painel tem **teto de 6 blocos**, proposital e testado reprovando (doc 03, regra 5); a aba "Os robôs" do Admin (`/admin/caixa/robos/`) já é o quadro da fila, calculado no build, com o "ao vivo" vindo do GitHub | Vista nova que só **lê** fila e livro é permitida (doc 03: "não é 'não crie painéis', é 'não crie fatos fora do livro'"); vista que grave veredito próprio, não |
| Três portões novos em `ci/` (manifesto, registros, auditoria por item) | A muralha da fila (`ci/fila.py validar`) já reprova evento sem evidência, `toca` inexistente, `move` sem cartão, evento depois do fim; a conferência do `toca` compara a declaração com o diff; o portão do pouso confere o registro a bordo; o `ci-celula` roda a suíte de cada célula tocada | Falta UM portão, pequeno: a auditoria da evidência (seção 5) |
| Seis PRs, o primeiro sem código e esperando aprovação | Coincide com o rito da casa (Sessão A; registro `pendencia` com `precisa_do_dono`) | Este parecer é o PR 1 |
| "8 portas" (G0 a G8) | O roadmap lista **nove** portas, G0 a G8 | `[VERIFICAR]`: a contagem do prompt tem um a menos |

## 3. O que o prompt pede, traduzido para o que a casa tem

| Entregável do prompt | Onde já mora | O que falta |
|---|---|---|
| 3.1 Manifesto de escopo (norma) | A escada do plano §10 (norma, em documento) + uma tarefa da fila por degrau (`fila/tarefas/`), encadeadas por `depende_de`, com `evidencia_exigida` e `move` | A fila é **plana**: ela não sabe que a TAR-146 é "o degrau 1.1 da Fase 1". A convenção existe no texto (`origem: "degrau 1.1 da escada do PLANO-CELULA-CURSOS.md"`), mas ninguém a lê |
| 3.2 Registros de fato | `fila/eventos/` (o que aconteceu com a tarefa) + `painel/registros/` (o que aconteceu no projeto: decisão, pendência, resposta, entrega com prova) | Nada. O "aceito por uma pessoa" é um registro `resposta` do mantenedor apontando para a entrega |
| 3.3 Vistas | "Os robôs" (`/admin/caixa/robos/`): a fila por urgência, com reservas e PRs ao vivo; o painel (`/admin/painel/`): o livro, a caixa "Precisa de você", o placar | **Uma vista**: a escada da sala de aula, fase por fase e degrau por degrau, com o estado calculado de cada degrau (da fila), o aceite do dono (do livro) e a prova (o PR mergeado) |
| 3.4 Portões | `ci/fila.py validar` (muralha), `ci/conferencia_do_toca.py` (sombra), `ci/mergear.py` (registro a bordo), `ci-celula` (suíte por célula), `ci/verificar_painel.py` | **Um portão**: a auditoria da evidência, que confere que toda `evidencia` de evento `concluida` é um PR **mergeado** de verdade (hoje o balcão só exige que a prova exista como texto) |
| 3.5 Documentação | `fila/LEIA-ME.md`, `painel/LEIA-ME.md`, `painel/ia/03` | A seção da escada no `painel/ia/03` e uma página leiga "como ler a escada" no `documentos/` (bastidor, sem porta pública) |

**E o "tudo o que o escopo pede existe" do fim do projeto**, para o CONTEÚDO
(as 33 encomendas com 16 peças, os 13 instrumentos, os 27 arquivos por link, os
apêndices), não é portão de CI: é a tela do editor no Admin dizendo, aula por
aula, o que está publicado e o que falta, lida do banco da célula `cursos`
pela porta de máquina (`getContentStatus`, a acrescentar ao contrato do
degrau 1.3). O esqueleto do curso (1 curso, 12 blocos, 34 aulas, 13
instrumentos) é semeado no degrau 1.2 justamente para essa conta ter
denominador desde o primeiro dia: "34 aulas, 0 publicadas" é uma frase
honesta; "100%" de uma lista vazia não é.

## 4. As contagens que o prompt manda conferir

| O que | Na fonte (roadmap) | Nesta casa |
|---|---|---|
| Fases | 9 (0 a 8) no roadmap | 6 fases na escada da célula (plano §10), porque as Fases 0 a 5 do roadmap são conteúdo escrito fora, e as Fases 7 a 9 (Atlas, produção física, lançamento) não são plataforma |
| Lotes | 33 nas Fases 5 a 9 (8 consolidados + 25 especificados) | 21 degraus até o fim da Fase 3 da escada, mais as Fases 4 a 6 sem degraus numerados ainda |
| Peças de conteúdo | 66 (33 capítulos + 33 roteiros) | 34 aulas × 16 peças + roteiro + ficha do Guia = 612 peças a publicar pela tela, contadas pelo editor |
| Cartões (instrumentos) | 13 | 13, semeados por slug e nome canônico no degrau 1.2 |
| Modelos e contratos | 16 | ficam na área de documentos (`documentos/`), não na célula |
| Apêndices | 17 (A a Q) | idem: área de documentos, com cabeçalho de apêndice vivo (degrau 3.3) |
| Arquivos de prática | 27 | por link, um a um, nas peças das aulas (a plataforma não guarda arquivo) |
| Pôsteres | 6 | produção editorial, fora da plataforma |
| Portas | o prompt diz 8; o roadmap lista G0 a G8, que são 9 `[VERIFICAR]` | as portas desta casa são as Sessões A e B e o passo da VPS, já no livro |
| Decisões pendentes | 6 no prompt | 3: contratos entre alunos e Ficha de Delegação; coleção de cartas; onde moram os vídeos (adiada para o degrau 1.8) |
| Lacunas | — | 1: onde vive a coleção de cartas ao aprendiz (o roadmap a coloca na plataforma; a casa ainda não tem dona; candidatas `forum` e `documentos`) |

## 5. A recomendação: três PRs pequenos, em vez de cinco entregáveis novos

1. **A escada como norma legível por máquina, sem estado.** Um arquivo
   `fila/escadas/cursos.yaml` com os degraus do plano §10 (id, nome, fase,
   `depende_de`, a seção do plano de onde saiu) e **nada mais**: nenhum
   campo de estado, nenhuma lista de itens de conteúdo. Cada tarefa da fila
   que realiza um degrau o cita no campo `origem` ("degrau 1.2"), que já
   existe; a muralha da fila passa a conferir que o degrau citado existe na
   escada. É o "manifesto" do prompt reduzido ao que é norma de verdade.
2. **A vista "A sala de aula, degrau a degrau"**, na área do Admin ao lado de
   "Os robôs", calculada de três fontes que já existem: a escada (o que deve
   existir), a fila embutida (em que pé está cada degrau: na fila, bloqueado,
   reivindicado, em execução, concluído com prova) e o livro (o aceite do
   dono, quando houver registro `resposta` apontando para a entrega). Mostra
   contadores por fase **com o denominador ao lado**, o caminho crítico (a
   cadeia de `depende_de` mais longa até o próximo passo dele) e as três
   decisões pendentes que bloqueiam degraus. Nenhum campo gravado.
3. **A auditoria da evidência**, um portão em `ci/` com os quatro estados:
   para todo evento `concluida`, a `evidencia` cita um PR, e esse PR está
   **mergeado** (PASS); cita e não está (FAIL); não cita PR (SKIP, dito); o
   GitHub não respondeu (ERROR, nunca PASS). Roda na muralha em sombra
   primeiro, como manda o Sistema Imunológico, e vira reprovação quando a
   sombra ficar limpa. É a única "auditoria mecânica por item" que faz
   sentido aqui, porque o item desta casa é o PR.

O que o prompt pede e **fica de fora, com o motivo**: o manifesto YAML com
itens de conteúdo (duplicaria a fila e o banco da célula); os tipos novos de
registro (já existem com os nomes da casa); as sete vistas no
`painel.html` (teto de 6 blocos; a vista certa é uma, no Admin); o portão de
"origem existe em `docs/meshcraft/fonte/`" (impossível por construção); o
portão de "esquema válido em `conteudo/meshcraft/`" (a pasta não existe e não
vai existir).

**Ordem e dependência:** o PR 1 (a escada) pode nascer assim que a gênese da
célula pousar e as tarefas dos degraus existirem na fila. O PR 2 (a vista)
depende do 1. O PR 3 (a auditoria) não depende de nada e pode correr em
paralelo, em bancada própria: é o candidato a canário de um lote.

## 6. O bloco final que o prompt exige

**RESUMO:** leitura da casa contra o prompt; nenhum código; a recomendação de
três PRs pequenos no lugar de cinco entregáveis novos.

**CONTAGENS:** 6 fases na escada · 21 degraus até a Fase 3 · 612 peças de
conteúdo a publicar pela tela (34 × 18) · 13 instrumentos · 3 decisões
pendentes · 1 lacuna · 1 a verificar.

**LACUNAS:** onde vive a coleção de cartas ao aprendiz (o roadmap diz "na
plataforma"; a casa não tem dona; a decisão é do mantenedor, na fase em que
alguém chegar ao Nível 3).

**A VERIFICAR:** o prompt diz "8 portas (G0 a G8)"; o roadmap, seção 29, lista
nove (G0, G1, G2, G3, G4, G5, G6, G7, G8).

**ORIGENS:** `origin/main` em `5c7d992a`: `CONSTITUICAO.md`, `RITOS.md`,
`painel/ia/03` (seções "A lei anti-duplicação" e "Armadilhas e regras sutis"),
`painel/ia/04`, `painel/ia/06`, `painel/LEIA-ME.md`, `fila/LEIA-ME.md`,
`services/admin/apps/core/robos.py`, `docs/decisoes/PLANO-CELULA-CURSOS.md`
(§1, §3, §8, §10); os nove documentos do curso, fora do repositório (roadmap
seções 7 a 12, 19, 29; "Ajustar o que foi escrito ao que já existe", Parte A
e Parte B §11).

**O QUE ESTE PROMPT ASSUMIU E O REPOSITÓRIO CONTRADIZ:** a tabela da seção 2,
onze linhas.

**PARA O MANTENEDOR:** escolher entre os três PRs pequenos (a recomendação) e
o prompt como está escrito; e, das decisões pendentes, a que mais bloqueia é
**onde moram os vídeos** (trava o degrau 1.8, a sala do aluno), seguida dos
contratos entre alunos (Fase 4) e da coleção de cartas (Fase 5).
