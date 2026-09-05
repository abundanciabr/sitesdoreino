publico-para-ia: true

# DECISÃO — a sala de aula da Meshcraft nasce como célula própria: `cursos`

> **Estado: APROVADA pelo mantenedor em 04/09/2026**, em pergunta estruturada
> na mesma sessão que escreveu o plano (registro `20260905-001` no livro,
> PR #1044). Ele decidiu: a lei vale com as emendas da casa; onde moram os
> vídeos fica para a fase da sala de aula (degrau 1.8). A gênese (TAR-146)
> nasceu no PR seguinte, e é ela que promove este documento.
>
> É a nona reabertura nominal do congelamento arquitetural, depois de
> `sugestoes`, `identidade`, `notificacoes`, `admin`, `forum`, `gamificacao`,
> `pages` (decidida em 02/09/2026 e ainda não nascida) e `encomendas`.
>
> **O PLANO NÃO SE REPETE AQUI.** Ele mora em
> `docs/decisoes/PLANO-CELULA-CURSOS.md`: a visão (o roadmap do curso em
> resumo), as doze emendas da casa aos nove documentos do projeto, o modelo de
> dados, os eventos e o contrato, as superfícies, os agentes de IA com suas
> Fichas, os invariantes, a escada e o critério de morte. Este documento é o
> **ato**: o que foi decidido, por quem, quando, e onde cada coisa mora.

## 1. A decisão

Nasce a célula **`services/cursos`**, Django + django-ninja como todas as
outras, com **banco próprio** (`cursos_db`), **role próprio** (`cursos_user`),
**processo próprio** e **contrato próprio** (a congelar no degrau 1.4, depois
da porta de máquina).

Ela é a sala de aula da Meshcraft vista de dentro: o conteúdo do curso (33
encomendas e uma Bônus, cada uma com 16 peças, o roteiro da aula, a ficha do
Guia do Mentor, o vídeo por link, as pausas reais, os 13 instrumentos), o
progresso de cada aluno, o checkpoint por link na fila de revisão de 24 horas,
e o laudo. E os agentes de IA que trabalham nela, começando pelo Assistente de
laudo: **a IA prepara, a professora assina.**

**Uma célula, não duas.** Os documentos de fora propunham conteúdo no
repositório e uma célula `avaliacao` separada. O repositório é público e o
curso é obra não lançada; o envio é a porta da lição e o laudo é a resposta ao
envio. Checkpoint e laudo ficam juntos (plano §1).

## 2. As decisões da Sessão A (04/09/2026)

| Pergunta | Resposta |
|---|---|
| A lei vale, com as emendas da casa? | **Vale, com as emendas** (plano §3: o cofre é o banco e não o repositório; escola 18+; portfólio na `pages`; o quiz da encomenda não é a célula `quiz`; o silêncio de 14 dias é jornada da `mensageria`; a IA prepara e nunca decide; 24 horas é constante) |
| Onde moram os vídeos? | **Decide na fase da sala de aula** (degrau 1.8). A gênese e o editor não dependem do vídeo; a sessão desse degrau reabre a caixa com as mesmas opções |

E as três respostas dele da leitura dos nove documentos, no mesmo dia: os
capítulos ainda estão só no chat do claude.ai; o plano nasce primeiro e os
verificadores esperam os capítulos; ele e a autora do livro não são a mesma
pessoa.

## 3. Onde cada coisa mora

| O quê | Onde | Onde se confere |
|---|---|---|
| A lei (visão, emendas, modelo, eventos, agentes, invariantes, escada) | `docs/decisoes/PLANO-CELULA-CURSOS.md` | — |
| A constituição da célula | `constituicoes/AGENTS.cursos.md`, promovida na gênese | `ci/tests/test_constituicoes.py` |
| O código | `services/cursos/` (na gênese: `/healthz` e os três guardas) | `make ci` da célula |
| O mapa para IA | `painel/ia/04-arquitetura-de-celulas-e-contratos.md` | `ci/tests/test_painel_ia_atualizado.py` |
| O estado de cada degrau | a fila (`python ci/fila.py listar --ao-vivo`) | o balcão |
| O que aconteceu | o livro (`painel/registros/`) | o painel |

## 4. O que fica decidido, e não se reabre por preferência de agente

1. O capítulo se chama `aula` em dado e código; `encomenda` em código é só da
   célula do marketplace.
2. "Reprovado" não existe; devolvido leva mudança única e data.
3. A IA nunca persiste decisão, data ou a pergunta de amanhã de manhã.
4. O prazo de 24 horas é constante com teste, nunca parâmetro.
5. O conteúdo entra pela tela do Admin, pela porta de máquina; nunca por
   arquivo commitado nem por migração com texto.
6. XP, medalha, Marco e título de nível são da `gamificacao`; o portfólio é da
   `pages`; a matrícula é da `alunos`.
