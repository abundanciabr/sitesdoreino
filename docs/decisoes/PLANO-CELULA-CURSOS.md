publico-para-ia: true

# PLANO — a célula `cursos` (a sala de aula da Meshcraft, e os agentes de IA que trabalham nela)

**Escrito em 04/09/2026**, a partir de: os nove documentos do projeto Meshcraft
que o mantenedor trouxe nesse dia (o roadmap consolidado do curso, o playbook
de 66 plays, a equipe de agentes, "Como começar a criar os agentes", as doze
alavancas, o plano do Painel do Playbook, "O Meshcraft aplicado ao Meshcraft",
"Onde o Meshcraft entra no sitesdoreino" e "Ajustar o que foi escrito ao que já
existe") + três decisões dele em pergunta estruturada, no mesmo dia + a leitura
dos nove contra o `origin/main` (commit `222d83ce`). Molde:
`PLANO-CELULA-GAMIFICACAO.md` (a escada do §6) e
`DECISAO-fila-do-primeiro-dolar.md` (as emendas da casa a um plano escrito fora).

**Os nove documentos moram FORA deste repositório, de propósito.** O
repositório é público e o curso é obra não lançada (`armadilhas/331`). Este
plano carrega só o que a engenharia precisa: a estrutura, as regras e as
fronteiras. Quem for construir pede ao mantenedor o caminho da pasta e lê os
nove antes do primeiro PR; onde este resumo e o roadmap divergirem, o roadmap
vence, exceto onde o §3 diz que a casa já decidiu diferente.

Este documento NÃO é um painel: não guarda estado e não se atualiza sozinho.
Quem responde "isto foi feito?" é o livro (`painel/registros/`) e a fila
(`fila/`). Na gênese da célula, este plano é promovido a
`DECISAO-celula-de-cursos.md` com a autorização nominal do mantenedor
(Sessão A).

---

## Parte 0 — A visão (o roadmap do curso, em resumo)

O produto é um **livro-curso de modelagem 3D para Roblox em que cada capítulo é
um pedido de cliente**. O aluno não faz exercícios: entrega encomendas. São 33
encomendas (E00 a E32) e uma Bônus, em três Partes (Fundação · Itens que vendem
· Profissional) e doze Blocos (A a L), cada Bloco fechado por um Boss. Toda
habilidade tem uma régua verificável que nasce no capítulo em que a dor aparece
(o Teste STUDS na E01, a Rubrica de Encomenda na E09, a Prova dos 3 Movimentos
na E13, a Ficha de Série na E27, a Ficha de Delegação e a Revisão de Estúdio na
E28, o Laudo de Banca na E32): treze instrumentos ao todo, e a promessa é que
eles continuam funcionando depois do curso. Cada encomenda deixa uma regra no
**Padrão Meshcraft**, uma especificação aberta de 33 seções. A certificação é
por **Banca**, em três níveis (E10, E21, E32).

**A anatomia de uma encomenda, fixa, sempre na mesma ordem (16 peças):**
Pedido · Em jogo · Você vai conseguir · Recall de 2 minutos · Par de comparação
· Erro produtivo · Eu faço · Nós fazemos (com "Você deve ver" em cada passo) ·
Você faz (com "Aceito quando") · Drills · Erros clássicos · Regra que entra no
Padrão · Crítica de atelier / Revisão de estúdio · Checkpoint · Página do
portfólio · Dicionário + Cartão de 1 página + Respostas. A vídeo-aula tem 7 a 8
blocos, com **pausas reais**: o vídeo para, o aluno registra, e só depois
retoma.

**As decisões do roadmap que viram régua nesta célula** (elas estão no registro
de decisões governantes dele, e a execução vai pressionar para mudá-las):

- O checkpoint abre a porta; o calendário, nunca.
- Entregar dá XP; aprovar dá porta. O sistema recompensa quem entrega, não quem
  acerta de primeira.
- Ninguém reprova por tempo, só por nota. **Não existe o estado "reprovado."**
  Toda devolução tem uma mudança única e uma data.
- Todo laudo responde "ele sabe o que fazer amanhã de manhã?", e o formulário
  não envia sem isso.
- Rubrica antes da opinião: os campos livres ficam fechados até a rubrica
  estar completa, com uma frase por nota.
- A fila de revisão tem prazo de 24 horas por item, e **o prazo não se alonga**:
  estouro se registra, nunca se esconde.
- Nenhuma tela compara alunos. Nenhum ranking, nenhuma média de turma.
- A pausa real registra; não se pula, se retoma.
- Marcos validam o processo e carimbam quando o mundo responde; a jornada nunca
  trava esperando o carimbo.
- Botões envelhecem, princípios não: nenhum número de plataforma (limite de
  triângulos, taxa, prazo de moderação) em texto de capítulo. Tudo o que muda
  vive em apêndice vivo, com remissão.

**Quem faz o quê.** Resposta do mantenedor em 04/09/2026: ele e a autora do
livro **não são a mesma pessoa**. A professora (a autora) escreve os capítulos,
grava as aulas, avalia os envios e assina os laudos. O mantenedor decide o
produto, opera a plataforma e edita o que é dado. As sessões de IA constroem. E
os **agentes de IA que vivem dentro desta célula preparam e nunca publicam**: a
IA escreve, a pessoa assina. É o mesmo desenho que o fórum já tem desde
02/09/2026 (`services/forum/apps/core/agente.py`), e é o §7.

## §1 O que é (e o que NÃO é)

**É**: uma célula nova, `services/cursos`, dona de quatro coisas que hoje não
têm casa em lugar nenhum da plataforma:

1. **O conteúdo do curso**: as encomendas com suas 16 peças, o roteiro da aula,
   a ficha do Guia do Mentor, os vídeos (por link), as pausas, os instrumentos.
   Entra pela tela do Admin, direto no banco desta célula; nunca por arquivo
   commitado.
2. **O progresso de cada aluno**: qual porta está aberta, o que foi registrado
   nas pausas, a autoavaliação do quiz.
3. **O checkpoint**: o envio (por link), a fila de revisão com o relógio de 24
   horas, o reenvio.
4. **O laudo**: a avaliação com o instrumento cabível, três forças, uma mudança
   com a encomenda onde se aprende, a decisão, a data se devolvido, e a pergunta
   de amanhã de manhã. E, atrás dele, o **Assistente de laudo**, o primeiro
   agente de IA da célula.

**NÃO é**: o catálogo (o curso como produto à venda é `catalogo`); a matrícula
(quem entrou é `alunos`); XP, medalhas, Marcos e títulos de nível
(`gamificacao`); o portfólio, o Meu Estúdio e as 35 Páginas (`pages`, decisão de
02/09/2026); o marketplace de encomendas reais (`encomendas`); o quiz de
captação, o Crivo (`quiz`); a Biblioteca do Livro (a gaveta dos textos do
mantenedor que não são aula, em `/admin/livro/`); a área de documentos (o
Padrão, os apêndices vivos e o dicionário, em `documentos`, com versão e sem
porta).

**Por que UMA célula, e não duas.** Os documentos de fora propunham conteúdo
como dados no repositório e uma célula `avaliacao` só para o laudo, com o
progresso vivendo em `alunos`. Medido em `origin/main`: `alunos` só sabe
matrícula (categoria e estado), nenhuma célula serve aula, e o mapa da casa já
chamava "a célula de cursos (a nascer)" desde a lei das encomendas. O envio é a
porta da lição, e o laudo é a resposta ao envio: separar os dois faria a
transação mais comum da escola (enviar → receber o laudo → a próxima porta
abrir) atravessar duas células por evento sem ganhar isolamento nenhum. O
mantenedor disse em 02/09/2026 que "já cansou de criar novas células", e a
`pages` nasceu como guarda-chuva por isso. Pares e Bancas entram como degraus
desta mesma célula (Fases 4 e 5); até lá o professor é a Banca, como a lei das
encomendas já decidiu.

## §2 O que a casa já tem, medido

`python ci/reconhecer.py aula curso licao laudo checkpoint`, lido de
`origin/main` no commit `222d83ce`, em 04/09/2026:

- **NÃO serve aula em vídeo.** "O curso NÃO mora no site." É o custo inteiro
  deste plano.
- **NÃO guarda arquivo.** A decisão do portfólio (02/09/2026) foi guardar foto
  por LINK. O checkpoint de modelagem 3D é um arquivo (`.blend`, `.fbx`) mais
  prévias; aqui ele também viaja por link (§3.12).
- **NÃO gera PDF.** O Cartão de 1 página sai como página com desenho de
  impressão; o navegador salva.
- **SIM**: reconhecer quem entrou (`identidade`), trabalhar em segundo plano
  (Huey), avisar no sino e no celular (`notificacoes`), mandar e-mail e
  sequências com estado `cancelada` (`mensageria`), falar com um modelo de
  linguagem com a chave lida no ponto de uso (o agente do fórum), editar texto
  no banco pela tela do Admin com versões (o editor de documentos e a
  Biblioteca do Livro), procurar dentro de texto de aluno (`forum`).
- **Nenhum endereço do site casa com `/cursos`**: o `funil` só o cita num
  exemplo de teste de roteamento. O prefixo tem 6 letras e passa no guarda de
  locale (`armadilhas/089`).

**O que já decide o desenho, e não se reabre por preferência de agente:**

- **A escola é 18+** (30/08/2026; reconfirmado em 03/09/2026 na lei das
  encomendas). Não há responsável, não há trava de idade.
- **O portfólio mora em `pages`** (`/pages/...` e a vitrine
  `meshcraft.top/estudio/<apelido>`, opt-in), plano guardado e construção ainda
  não autorizada.
- **A gamificação já espera esta célula**: a tomada `aula.concluida.v1`
  (`{site_id, curso_id, aula_id}`) está prevista como "uma linha semeada", os
  Marcos #1 a #6 são conquistas dela, e a fila de validação humana
  (`/conquistas/marcos` e `/conquistas/interno`) já está no ar.
- **A lei das encomendas** diz que "dar aula ou o título de Banca" é da célula
  de cursos, e que até ela existir o professor dá o título no plantão.
- **A lista de professores é `FORUM_PROFESSORES`**, vazia na VPS em 30/08/2026:
  pôr um e-mail lá é o gesto do mantenedor que dá as ferramentas a uma
  professora. Esta célula lê a mesma lista sob o próprio nome
  (`CURSOS_PROFESSORES`), até a `identidade` ter o papel.
- **O texto do livro não entra por arquivo no repositório público**
  (`armadilhas/331`, Biblioteca do Livro, 04/09/2026).

## §3 As emendas da casa aos nove documentos

Os nove foram escritos fora, com a suposição de que a plataforma nasceria do
zero, e os dois últimos leram só o índice de `painel/ia/`. Onde eles pedem algo
que um portão recusa ou que uma decisão já fechou, **vale o que está abaixo**.
Nenhuma emenda muda o curso; todas mudam a forma de construí-lo.

### 3.1 O cofre é o banco desta célula, não o repositório

Os documentos põem o conteúdo em `conteudo/meshcraft/` com portão de CI, e os
verificadores (coerência, fidelidade) como testes em `ci/tests/`. Isso deixaria
o curso inteiro num repositório público. Aqui o conteúdo vive nas tabelas do §4,
entra pela tela `/admin/escola/aulas/` (célula `admin`, pela porta de máquina
desta célula, nunca no banco dela e nunca guardando cópia), e os verificadores
viram **botões do editor** que leem o banco (§7). Um teste de CI não enxerga
texto que está no banco; medir a coisa errada com precisão é como um portão
morre.

### 3.2 A escola é 18+

Sai tudo o que só existia por causa de idade: o Apêndice H (dinheiro e idade),
o circuito de responsáveis (P52), o agente Zelador de dados, "com ciência do
responsável" nos Marcos #3, #4 e #6, "menores só avaliam Partes I e II", a
bifurcação por idade do Passaporte. Fica o que não era sobre idade: nenhum dado
de contato entre alunos, comunicação pela plataforma, moderação prévia do que é
público.

### 3.3 O portfólio é do Estúdio

A peça 15 de toda encomenda, "Página do portfólio", é o que o aluno escreve
sobre a entrega; as 35 Páginas e as vitrines 1.0, 2.0 e 3.0 são o Meu Estúdio.
A casa é `pages`. Esta célula só afirma o fato (`aula.concluida.v1`) e responde
`getStudentProgress`; a Página nasce lá, não aqui.

### 3.4 XP, medalhas, Marcos e títulos de nível são da gamificação

Esta célula **nunca calcula ponto** (critério de morte da gamificação: "pontos
calculados dentro de outra célula"). Ela emite `aula.concluida.v1` para toda
porta que abre, com `e_boss` no dado quando a aula fecha um Bloco, e a
gamificação faz o resto: XP por entrega, a medalha do Boss, o Marco #1 pela
fila de validação que já existe. O título de Banca (Modelador Nível 1, 2, 3) é
outra coisa: nasce aqui, na Fase 5, e viaja em `banca.decidida.v1`.

### 3.5 O quiz da encomenda não é a célula `quiz`

A `quiz` é o Crivo: múltipla escolha com pontos, faixas de resultado e e-mail
de lead. O quiz de uma encomenda são cinco perguntas abertas com resposta-modelo
e **autoavaliação** do aluno, sem ponto. Levar isso para o Crivo poria
progresso de aluno numa célula de captação e dobraria o modelo dela. O quiz é
dado da `Aula` (§4) e a autoavaliação grava no `Progresso`. Nenhum evento
`quiz.completado` sai daqui.

### 3.6 O silêncio de 14 e 30 dias é uma jornada da `mensageria`

O agente "Vigia do silêncio" dos documentos já existe como mecanismo: o motor
de jornadas da `mensageria` tem passos com espera e o estado `cancelada`. A
jornada dispara em `checkpoint.devolvido.v1` e cancela em `envio.recebido.v1`.
A frase é a do playbook, fixa: "Você sabe o que fazer amanhã de manhã? Se não,
responda esta mensagem." Nunca cobrança.

### 3.7 O que já tem dono e dissolve agentes dos documentos

| Agente ou peça dos documentos | Onde já mora nesta casa |
|---|---|
| Historiador (registro imutável de quem, quando, o quê) | `painel/registros/` |
| O Painel do Playbook (20 painéis com estado próprio) | `painel/painel.html`, calculado do livro; estados nunca se escrevem à mão |
| Glossarista, resumos leigos, camada de tradução | o editor de documentos (`/admin/documentos/`) |
| Redator de propostas ao Padrão, relato de divergência | a Caixa de Sugestões (`sugestoes`) |
| Verificador de links, Simulador de usuário | `e2e/` |
| Triador da fila | não é agente: é a ordenação da fila (§6), código sem modelo |
| A fila de tarefas do projeto (P42, os lotes, as portas) | `fila/` e o balcão `ci/fila.py` |

### 3.8 O Padrão, os apêndices vivos e o dicionário moram na área de documentos

São peças transversais lidas por todo mundo, públicas e sem porta, com versão:
exatamente o que a área de documentos já faz (`/docs/...`, editor no Admin,
versões). O que ela ainda não tem, e é degrau dela (não desta célula): o
cabeçalho de apêndice vivo (versão, verificado em, próxima verificação) e o
aviso público de verificação vencida.

### 3.9 Nomes, e as colisões que os documentos previram

| Palavra | No livro | Nesta casa | Regra |
|---|---|---|---|
| encomenda | um capítulo (E00 a E32) | a célula `encomendas`, o marketplace | em dado e código, o capítulo é **`aula`** (a casa já fala assim: `aula.concluida.v1`, e o mantenedor guarda o material em "CURSO - AULAS"); `titulo_exibido` guarda "Encomenda 22"; `encomenda` em código é só da célula do marketplace |
| fila | a fila de revisão de 24 h | a Fila do Primeiro Dólar | aqui é `fila_de_revisao`; no site, "Fila de revisão" |
| Marco | os 6 Marcos de carreira | conquista da gamificação | esta célula nunca guarda Marco |
| Ficha | Ficha de Série, Ficha de Delegação | fichas de outras células | `ficha_de_serie`, `ficha_de_delegacao` |
| Mentor | o personagem e quem avalia | o papel `professor` | o personagem é conteúdo; o papel é `professor`, e a professora é uma pessoa desse papel |
| Historiador | o agente que registra | não existe | é o livro |

### 3.10 Os vídeos moram fora, e a pausa real exige um tocador que o site controle

Decisão do mantenedor de 03/09/2026: vídeo fora da plataforma. Aqui ele entra
por link, e a página da aula embute o tocador. A pausa real (o vídeo para no
segundo marcado, o formulário abre, o vídeo retoma depois do registro) exige um
serviço cujo tocador aceite ordem de parar e retomar vinda da página. **Qual
serviço é decisão dele** (§8, decisão B), porque tem custo e porque só alguns
restringem quem assiste.

### 3.11 A ordem de nascimento é a da casa, não a dos documentos

O contrato congela DEPOIS da porta de máquina existir (`armadilhas/228`,
`243`); na gênese `celulas.yml` diz `consome: []` e cada linha entra no PR do
cliente que a lê (`224`); o compose entra em PR próprio (`134`), e entre a
gênese e ele o `deploy-celula` fica vermelho, o que é esperado (`088`); a
etiqueta `arquitetural` só vale depois de fechar e reabrir o PR (`035`, `077`).
Plano escrito fora da casa pede o que o portão recusa: traduz-se a fase para a
escada daqui antes do primeiro PR (`304`), e é o §10.

### 3.12 O checkpoint é por link

A plataforma não recebe arquivo, e a decisão do portfólio (foto por link) vale
aqui pela mesma razão. O envio leva: os links (o arquivo, e as prévias: sólido,
wireframe, silhueta, e o que a encomenda pedir), o README do Pacote, e o laudo
do próprio aluno com o instrumento. O Assistente de laudo lê as prévias pelas
URLs. Se um dia a casa passar a guardar arquivo, esta é a seção onde a decisão
volta.

## §4 O modelo de dados (padrões copiados dos precedentes)

Moldes: espelho `Pessoa` (forum); definições-como-DADO com default fechado
(gamificacao); IDs alheios como CharField opaco; `site_id` em toda entidade
(INV-P11); CheckConstraint no banco; outbox transacional (sugestoes). Unicidade
que atravessa chave estrangeira pede chave composta, não `save()`
(`armadilhas/274`).

**O conteúdo (editado pelo Admin pela porta de máquina):**

- **`Curso`**: `site_id`, `slug`, `nome`, `estado` {rascunho | publicado},
  `versao`. Unique(site_id, slug). Um curso por site no lançamento.
- **`Bloco`**: curso, `ordem` (1 a 12), `letra` (A a L), `parte` (1, 2, 3),
  `nome`, `boss_titulo`. Unique(curso, ordem).
- **`Aula`**: curso, bloco, `ordem`, `numero` ("E00" a "E32", "EB"),
  `titulo_exibido` ("Encomenda 22"), `pedido` (a frase do cliente), `cliente`
  (o personagem), `instrumento` (FK, opcional), `minimo` (o mínimo do contexto,
  texto curto), `aceito_quando` (JSON: a lista de critérios que vira o
  formulário do checkpoint), `quiz` (JSON: cinco {pergunta, resposta_modelo}),
  `video_url`, `e_boss`, `banca_nivel` (1, 2, 3 ou nulo), `estado` {rascunho |
  publicada}, `versao`, `publicada_em`. Unique(curso, ordem) e Unique(curso,
  numero).
- **`Peca`**: aula, `tipo` (as 16 da anatomia, na ordem canônica, mais duas
  internas: `roteiro` da aula e `guia_do_mentor`, que o aluno nunca vê),
  `texto` (Markdown, renderizado por `documentos.para_html`, o renderizador
  único da casa). Unique(aula, tipo).
- **`Pausa`**: aula, `ordem`, `segundo`, `tipo` {erro_produtivo | faca_agora |
  cerimonia}, `pede` (o que o aluno registra), `campos` (JSON: os mínimos).
  Unique(aula, ordem).
- **`Instrumento`**: `slug` canônico (studs, rubrica_de_encomenda,
  rubrica_de_produto, pronto_para_sair, validacao_no_motor,
  prova_dos_3_movimentos, prova_das_5_expressoes, selo_ugc,
  selo_ugc_personagem, ficha_de_serie, ficha_de_delegacao,
  revisao_de_estudio, laudo_de_banca), `nome_canonico`, `cartao` (1 a 13),
  `escala` (JSON: critérios, mínimo e máximo por critério), `minimo_exercicio`,
  `minimo_contrato`, `secao_do_padrao`, `descritores` (JSON 5/3/1), `versao`.
  Só slug e nome canônico nascem semeados; escala e descritores entram pela
  tela. **Avaliação em andamento guarda a versão em que começou** (P04).

**As pessoas e o progresso:**

- **`Pessoa`**: espelho mínimo (`id_da_plataforma` PK, `nome_exibido`). A
  matrícula se pergunta à `alunos`; o e-mail nunca mora aqui.
- **`Progresso`**: pessoa, aula, `estado` {trancada | disponivel | em_producao |
  enviada | devolvida | concluida}, `autoavaliacao` (JSON do quiz),
  `data_de_retorno` (se devolvida), `concluida_em`. Unique(pessoa, aula). A
  porta da aula N só sai de `trancada` quando a aula N-1 está `concluida`; a
  E00 nasce `disponivel` para toda matrícula ativa.
- **`RegistroDePausa`**: pessoa, pausa, `respostas` (JSON), `registrado_em`.
  Unique(pessoa, pausa). O formulário do checkpoint fica fechado até todas as
  pausas da aula terem registro.

**O checkpoint e o laudo:**

- **`Envio`**: pessoa, aula, `numero` (1, 2, 3: o reenvio), `links` (JSON
  [{rotulo, url}]), `readme`, `laudo_do_aluno` (JSON com o instrumento),
  `enviado_em`, `prazo_em` (= `enviado_em` + 24 h, **imutável**), `estado`
  {recebido | em_revisao | aberto | aberto_com_ajuste | devolvido},
  `estourado_em` (nulo ou a hora em que o prazo passou: registra, nunca
  alonga). Unique(pessoa, aula, numero). **Não existe o valor "reprovado"**, e
  um teste procura a palavra no schema inteiro.
- **`Laudo`**: envio (um para um), `avaliador` (Pessoa), `papel` {professor |
  par | banca}, `instrumento_versao`, `notas` (JSON {criterio: {nota,
  frase}}), `forcas` (JSON, exatamente três), `mudanca` (JSON {texto,
  aula_id}), `ajuste_feito` (texto; só com `aberto_com_ajuste`), `decisao`
  {aberto | aberto_com_ajuste | devolvido}, `data_de_retorno` (obrigatória se
  devolvido, ≥ amanhã), `sabe_o_que_fazer_amanha` (só grava `true`),
  `rascunho` (FK opcional para o rascunho da IA que a pessoa leu),
  `emitido_em`. CheckConstraint: devolvido ⇒ data; sabe ⇒ true. As demais
  regras (§9) são do serviço, com teste.
- **`RascunhoDaIA`**: envio, `criado_em`, `modelo` (o id com data),
  `conteudo` (JSON: notas sugeridas com justificativa, três forças, uma mudança,
  lacunas, a verificar, "para a pessoa"), `tokens_entrada`, `tokens_saida`, e
  as medidas preenchidas quando o laudo é emitido: `forcas_mantidas` (0 a 3),
  `mudanca_mantida` (bool). **Nunca tem campo de decisão, data ou pergunta**: a
  ausência é o invariante L4.
- **`OutboxEvent`**: molde byte a byte de `sugestoes`.

**A fila de revisão não é tabela**: é a consulta dos envios em `recebido` ou
`em_revisao`, ordenados por `prazo_em`, os vencidos primeiro.

**Depois (Fases 4 e 5):** `Impedimento` (vínculos lidos por contrato de
`encomendas` e `identidade`), `AmostraDeRevisao` (a revisão de revisões),
`Calibracao`, `Banca`, `MembroDeBanca`, `RubricaIndividual`.

## §5 Eventos e contrato

**Emitidos (outbox + relay Huey; envelope canônico; só ids opacos, nunca texto,
e-mail ou link):**

- `envio.recebido.v1` { site_id, curso_id, aula_id, envio_id, numero }
- `laudo.emitido.v1` { site_id, envio_id, laudo_id, decisao, avaliador_papel }
- `aula.concluida.v1` { site_id, curso_id, aula_id, e_boss } (o dado que a
  gamificação já previu, mais `e_boss`; `ator_id` no envelope é o aluno)
- `checkpoint.devolvido.v1` { site_id, aula_id, envio_id, data_de_retorno }
- `revisao.prazo-estourado.v1` { site_id, envio_id, horas_de_atraso }
- `banca.decidida.v1` { site_id, banca_id, nivel, decisao } (Fase 5)
- `notificacao.devida.v1` com os assuntos `cursos.laudo-chegou`,
  `cursos.porta-abriu`, `cursos.devolvido` (a data antes do texto), pelo Rito
  aditivo, na Fase 2.

**Consumidos:** nenhum evento. Por HTTP: `identidade` (`getSessionFull`, quem é
o dono do cookie) e `alunos` (`getStudentStanding`, a matrícula ativa decide
o acesso, fail-CLOSED). Na gênese `celulas.yml` diz `consome: []`
(`armadilhas/224`); cada linha entra no PR do cliente que a lê.

**Contrato HTTP** (`contracts/cursos.openapi.yaml`, Bearer por par; congela no
degrau 1.4, depois da porta):

- Para o Admin (o editor): `listLessons`, `getLesson`, `putLesson` (as peças,
  as pausas, o vídeo, o instrumento, o "Aceito quando", o quiz; com versão),
  `putInstrument`, `publishLesson`, `checkLesson` (os verificadores do §7
  devolvem os desvios), `getReviewQueue` (o placar da fila: quantos, quantos
  vencidos, o tempo médio; nunca quem).
- Para o Estúdio e a home: `getStudentProgress` (quais portas abriram, para
  uma pessoa; sem nota).

**Regra herdada de toda porta da casa:** consumidor liga com cache e falha
ABERTA quando o dado é decoração (a home, o Estúdio) e falha FECHADA quando é
autorização (a matrícula).

## §6 Superfícies

**Prefixo público: `/cursos`**, host-bound em `meshcraft.top`. Nome da célula =
nome da rota, de propósito (a mesma regra da `pages`). Inventário de rotas no
MESMO PR do Traefik (`armadilhas/089`). Formulário normal com melhoria
progressiva: nenhum caminho existe só com script.

- **`/cursos`**: o mapa das 33 encomendas em três Partes e doze Blocos, com o
  estado de cada porta e a próxima aberta em destaque. É a home do curso:
  "Entre. Entregue. Receba."
- **`/cursos/<numero>`**: a aula. As 16 peças na ordem, o vídeo com as pausas
  reais (o tocador para no segundo marcado; o formulário da pausa abre; retoma
  depois do registro), os downloads por link, o quiz com autoavaliação, e o
  formulário do checkpoint com o "Aceito quando" como lista de conferência.
  Fechado até a pausa registrar.
- **`/cursos/<numero>/laudo`**: o laudo recebido. **A data aparece antes do
  texto** quando devolvido. Nunca nota de membro de Banca.
- **`/cursos/plantao`**: a professora. A fila de revisão ordenada por prazo,
  vermelhos primeiro, reenvio com o laudo anterior ao lado, o estouro
  registrado à vista. Quem entra: a lista `CURSOS_PROFESSORES`, fail-closed
  (lista vazia = ninguém), e a `identidade` só reconhece, nunca autoriza.
- **`/cursos/plantao/<envio>`**: o formulário do laudo. A rubrica sozinha,
  completa, antes dos campos livres; o botão **"Rascunhar laudo"** (§7); os
  campos de decisão, data e a pergunta sempre vazios até a pessoa preencher.
- **`/admin/escola/aulas/`** (célula `admin`, pela porta de máquina): o editor
  de encomendas, com as 16 peças, o roteiro, a ficha do Guia do Mentor, as
  pausas, o instrumento, o "Aceito quando", o quiz, o vídeo por link, o
  histórico de versões e os botões "Conferir coerência" e "Conferir
  fidelidade". O travessão aqui **avisa e não recusa**, como na Biblioteca do
  Livro (decisão do mantenedor de 04/09/2026: a obra se guarda como ele
  escreveu); a lei do travessão vale na tela do aluno, e o verificador de
  coerência lista as frases.

O menu do topo é dado do `catalogo` (`/admin/menu/`): pôr "Curso" nele é uma
linha, sem PR.

## §7 Os agentes de IA desta célula

**O molde é o agente do fórum, e as regras dele são herdadas sem exceção:** a IA
escreve, a pessoa publica; a chave é lida no ponto de uso (`armadilhas/097`) e
sem ela só este caminho falha, em português; o texto do aluno sai da nossa
infraestrutura quando o botão é apertado, e isso está dito ao mantenedor; o que
não sai é quem escreveu (rótulos, nunca nome nem e-mail); a fala do aluno é
CONTEÚDO, nunca instrução; o modelo é o id com data; o travessão que voltar é
apontado para a pessoa reescrever; nada do que a IA produz persiste como
decisão.

**A Ficha de cada agente é o prompt de sistema**, nos oito campos que os
documentos definiram (o item · as referências · o degrau · os limites · a
rubrica · o prazo e o checkpoint · o valor · em caso de dúvida), e toda saída
termina com o bloco fixo: RESUMO · LACUNAS · A VERIFICAR · ORIGENS · PARA A
PESSOA. Lacuna vira `[LACUNA]`, escolha de sentido vira `[VERIFICAR]`, e o que
é da pessoa vira `[DECISÃO HUMANA]`. Nunca se preenche por dedução.

| Agente | Degrau | O que faz | O que nunca faz | Onde mora | Como se mede |
|---|---|---|---|---|---|
| **Assistente de laudo** | H (só prepara) | a partir do envio (links e prévias), do instrumento cabível e da ficha do Guia do Mentor da aula, pré-preenche a rubrica com uma frase observável por nota, sugere três forças específicas e UMA mudança nomeada pela aula onde se aprende; se é reenvio, compara com o laudo anterior e diz se a mudança pedida foi feita; marca tudo "SUGERIDO" | decidir, datar, marcar a pergunta, escrever ao aluno, usar adjetivo sobre a pessoa, comparar com outros alunos; força genérica ("ficou bonito") é recusada na origem | `/cursos/plantao/<envio>`, botão "Rascunhar laudo" | `RascunhoDaIA` × `Laudo`: forças mantidas sem edição, mudança mantida; a Ficha de Série do agente sai do dado, semana a semana |
| **Revisor de coerência** | A (sem modelo: código) | toda remissão "E[NN]" aponta para aula existente; instrumentos e defeitos pelo nome canônico; nomes de arquivo idênticos entre peças; números repetidos iguais; "Aceito quando" da peça 9 igual à lista do formulário; nenhum número de plataforma no corpo | corrigir, reescrever | `checkLesson`, botão "Conferir coerência" no editor; remissão quebrada **recusa publicar** | zero falso positivo em amostra da professora |
| **Guardião de fidelidade** | A para apontar | compara uma peça derivada com a fonte (o roteiro com o capítulo; o Cartão de 1 página com o capítulo; a ficha do Guia com o "Aceito quando") e aponta os sete desvios: invenção, regra que virou sugestão, nome trocado, omissão, sentido alterado, decisão simplificada, comparação entre pessoas | corrigir; aprovar por simpatia | `checkLesson`, botão "Conferir fidelidade" no editor | detecta um desvio plantado de propósito antes de ser aceito |
| **Preparador de Banca** | A (logística) | composição sem impedimentos, dossiês, bloqueio da comparação até as rubricas individuais, rascunho do laudo único a partir das rubricas dos membros | o laudo é dos membros; nota de membro nunca ao aluno | Fase 5 | idem |

O Triador da fila, o Vigia do silêncio, o Historiador, o Glossarista e os
verificadores de link não são agentes aqui: são a ordenação da fila, a jornada
da `mensageria`, o livro, o editor de documentos e o `e2e/` (§3.7).

**O que decide subir de degrau, e o que nunca sobe.** Os documentos manda
começar pelo degrau 1 e subir pela Ficha de Série. Aqui a Ficha de Série do
agente é medida do dado, não anotada. E há um degrau que **nunca sobe, por
invariante**: o Assistente de laudo é H para sempre. A decisão, a data e a
pergunta são o produto; "ele decide os fáceis" é o guardrail 15 dos documentos
e o critério de morte 2 deste plano.

**O modelo e o custo** são decisão do mantenedor no PR de cada agente, com o
número na mesa, como foi no fórum (Haiku 4.5 pelo custo, com a pessoa lendo
antes de publicar). O Assistente de laudo olha prévias de imagem pelas URLs, e
isso pesa na escolha.

**O que espera dele:** nenhum agente do site responde sem a chave da Anthropic
na VPS (`ANTHROPIC_API_KEY`, e o `ANTHROPIC_WORKSPACE_ID` se a chave for
ligada a identidade). Em 02/09/2026 ela ainda não existia. Entra no passo H
da escada, junto com o e-mail da professora.

## §8 As decisões do mantenedor: respondidas, na pergunta de agora, e as que ficam para a fase

**Respondidas por decisão anterior dele (não se reabrem por preferência de agente):**

- A escola é 18+ (30/08 e 03/09/2026).
- O portfólio mora em `pages` (02/09/2026).
- Vídeo fora da plataforma (03/09/2026).
- O professor é a Banca até a Banca existir (03/09/2026).
- Texto do livro não entra por arquivo no repositório (04/09/2026).

**Respondidas em pergunta estruturada em 04/09/2026 (a leitura dos nove documentos):**

- Onde estão os 33 capítulos e roteiros: **ainda só no chat do claude.ai**. Por
  isso os verificadores (Fase 3) esperam, e a sala de aula (Fases 1 e 2) não
  espera.
- O que nasce primeiro: **este plano agora, e os verificadores quando os
  capítulos chegarem**.
- Ele e a autora: **não são a mesma pessoa**.

**Na pergunta de agora (Sessão A, na mesma sessão que escreveu isto):**

- **A. Esta lei vale?** Aprovar promove o plano na gênese; recusar ou emendar
  volta ao papel. Recomendação: aprovar, com as emendas do §3.
- **B. Onde moram os vídeos?** O que a pausa real exige: um tocador que o site
  possa mandar parar e retomar. O que muda entre os serviços: se dá para
  restringir quem assiste, e se custa mensalidade. Recomendação: um serviço de
  vídeo com restrição por domínio (só toca dentro do `meshcraft.top`) e
  tocador controlável, como o Vimeo; o YouTube não listado é grátis, mas quem
  tiver o link assiste, e ele mostra vídeos de outros no fim.

**Ficam para a fase que as precisa (registradas no livro como pendência, com a
fase escrita):**

- Quando abrir a E00 para os alunos que já estão na escola (a "turma zero" dos
  documentos): decisão de produto, depende do conteúdo estar na tela → Fase 2.
- O modelo e o custo do Assistente de laudo → Fase 2, degrau 2.3.
- Quem revisa além da professora, e quando os pares começam → Fase 4.
- A composição das Bancas de Nível 1, 2 e 3 sem pares formados → Fase 5.
- O livro impresso e o livro digital vendido à parte (`catalogo`, `checkout`;
  pagamento por último, diretiva de 22/08/2026) → fora deste plano.

## §9 Os invariantes (declarados aqui; guarda no PR que nasce)

Nascem como teste no degrau que os implementa, entram no `INVARIANTES.md` no
mesmo PR, e nunca se flexibilizam. Os de laudo são **regra de API, não de
tela**: `POST` do laudo devolve 422, e qualquer tela futura herda.

**Do laudo (degrau 2.2):**

- **[INV-CUR-L1]** nenhum laudo devolvido sem `data_de_retorno` ≥ amanhã.
- **[INV-CUR-L2]** o estado "reprovado" não existe: nem em `Envio`, nem em
  `Laudo`, nem em texto de tela; um teste procura a palavra no schema.
- **[INV-CUR-L3]** `prazo_em` de um envio nunca muda por API; o estouro só se
  registra em `estourado_em`.
- **[INV-CUR-L4]** nenhuma decisão, data ou resposta à pergunta vem da IA:
  `RascunhoDaIA` não tem esses campos, e o teste sabota tentando gravá-los
  (degrau 2.3).
- **[INV-CUR-L5]** a rubrica completa, com uma frase por nota, antes de qualquer
  campo livre; nota sem frase é 422.
- **[INV-CUR-L6]** exatamente três forças, nenhuma da lista de genéricos;
  exatamente uma mudança, com a aula onde se aprende.
- **[INV-CUR-L7]** a pergunta de amanhã de manhã: `false` não envia.

**Da porta (degrau 1.8):**

- **[INV-CUR-P1]** nenhuma tela compara alunos, e nenhuma porta devolve dois
  alunos lado a lado.
- **[INV-CUR-P2]** a porta só abre por laudo (`aberto` ou `aberto_com_ajuste`),
  nunca por data, por XP ou por pagamento; o acesso ao curso é a matrícula, e
  só. É o INV-GAM3 da gamificação visto do lado da aula.
- **[INV-CUR-P3]** o formulário do checkpoint fica fechado até todas as pausas
  da aula terem registro.

**Do conteúdo (degraus 1.2 e 3.1):**

- **[INV-CUR-C1]** nenhuma aula publica com remissão "E[NN]" para aula
  inexistente.
- **[INV-CUR-C2]** o conteúdo do curso entra pela porta de máquina, nunca por
  migração que semeie texto (a migração só semeia slug e nome canônico de
  instrumento).

**Da segurança e da casa:**

- **[INV-P12]** esta célula não assina sessão (cookie de CSRF próprio,
  `cursos_csrf`); o estado da cerimônia mora no modelo (`armadilhas/143`).
- **[INV-CUR-S1]** nenhum dado de contato entre alunos; nenhum e-mail nesta
  célula.
- **[INV-CUR-S2]** nota individual de membro de Banca nunca vai ao aluno
  (Fase 5).

## §10 A escada

Precedentes: gênese do fórum, da gamificação e das encomendas
(`armadilhas/076`, `088`, `089`, `134`, `224`, `228`, `243`, `304`). Cada degrau
é uma tarefa na fila com `depende_de`; o estado se lê **no balcão**
(`python ci/fila.py listar --ao-vivo`), nunca aqui. Os degraus 1.2 em diante só
podem existir na fila depois de a pasta existir (`toca: cursos` é conferido;
`armadilhas/304`): o despacho da gênese manda criá-los ao pousar.

| Fase | Degrau | O quê | Onde | Arqs |
|---|---|---|---|---|
| **0** | — | Este plano, a constituição em papel, o mapa para IA, o registro, a tarefa da gênese | docs, painel, fila | este PR |
| 0 | portão | **Sessão A**: o mantenedor aprova a lei e decide os vídeos (§8) | mantenedor | — |
| **1** | 1.1 | **Gênese**: esqueleto no molde da célula mais nova (`encomendas`), settings fail-hard com `TIME_ZONE=America/Sao_Paulo`, CSRF próprio, healthz nas duas formas, `test_inv_cursos_nao_assina_sessao` provado por mutação, `celulas.yml` (`consome: []`), manifesto not-applicable, `rollback.yml`, constituição promovida, plano promovido a DECISAO | cursos, ci, .github, constituicoes, docs | ~22, `arquitetural` |
| 1 | 1.2 | As tabelas de conteúdo (`Curso`, `Bloco`, `Aula`, `Peca`, `Pausa`, `Instrumento`) + semear o esqueleto (um curso, doze blocos, 34 aulas só com número e ordem; os 13 instrumentos só com slug e nome) + C2 como teste | cursos | ~12 |
| 1 | 1.3 | A porta de máquina do editor (`listLessons`, `getLesson`, `putLesson`, `putInstrument`, `publishLesson`, `getStudentProgress`) + sessão repassada (molde `encomendas`) + `export_openapi` + testes de porta (armadilhas do ninja 020/021/022/025) | cursos | ~10 |
| 1 | 1.4 | **Congelar o contrato** a partir do export (PR só de `contracts/` + manifesto, etiqueta `contrato`) | contracts, ci | ~3 |
| 1 | 1.5 | O editor `/admin/escola/aulas/`: 16 peças, roteiro, guia do Mentor, pausas, instrumento, "Aceito quando", quiz, vídeo por link, versões, publicar; `admin.consome += cursos` | admin, celulas.yml | ~10 |
| 1 | 1.6 | `infra/provisionar-cursos.sh` + env exemplo (PR sozinho) | infra | ~4 |
| 1 | **H** | **Passo do mantenedor na VPS**, UM bloco de colar, janela rotulada, fail-closed: banco, papel, env (`CURSOS_PROFESSORES` com o e-mail da professora; `ANTHROPIC_API_KEY` quando existir) | mantenedor | — |
| 1 | 1.7 | Compose + Traefik `/cursos` + inventário de rotas (PR sozinho); a célula responde `/healthz` pela internet | infra, ci | ~3 |
| 1 | 1.8 | **A sala do aluno**: `/cursos` (o mapa das portas), `/cursos/<numero>` (peças, vídeo com pausas, registro de pausa, quiz com autoavaliação), `Pessoa`, `Progresso`, `RegistroDePausa`, acesso pela matrícula (`alunos.consome`), P1, P2, P3 como teste | cursos, celulas.yml | ~14 |
| **2** | 2.1 | **O checkpoint**: `Envio` por link, a fila de revisão, `prazo_em` imutável, o estouro registrado, outbox + relay, `envio.recebido.v1`, `revisao.prazo-estourado.v1` (Rito de eventos), L3 como teste | cursos, contracts | ~12 |
| 2 | 2.2 | **O laudo**: `Laudo`, o formulário do plantão, as regras como 422, L1, L2, L5, L6, L7 como teste, `laudo.emitido.v1`, `aula.concluida.v1`, `checkpoint.devolvido.v1`, `notificacao.devida.v1` com assuntos `cursos.*` (Rito aditivo), a tela `/cursos/<numero>/laudo` com a data antes do texto | cursos, contracts | ~14 |
| 2 | 2.3 | **O Assistente de laudo**: `agente.py` no molde do fórum, `RascunhoDaIA`, o botão "Rascunhar laudo", L4 por sabotagem, as medidas da Ficha de Série do agente, a frase de recusa para força genérica; o modelo escolhido pelo mantenedor com o custo na mesa | cursos | ~9 |
| 2 | 2.4 | O silêncio de 14 e 30 dias: jornada disparada por `checkpoint.devolvido.v1`, cancelada por `envio.recebido.v1`, a frase fixa (célula `mensageria`, PR próprio) | mensageria | ~6 |
| 2 | 2.5 | A gamificação liga a tomada: a regra para `aula.concluida.v1` (XP por entrega, uma linha semeada), a medalha do Boss por `e_boss`, o Marco #1 pela fila que já existe (célula `gamificacao`, PR próprio) | gamificacao | ~6 |
| **3** | 3.1 | **O Revisor de coerência** (código): `checkLesson`, o botão no editor, C1 como recusa de publicar, a lista de nomes canônicos e de defeitos com nome como dado | cursos, admin | ~9 |
| 3 | 3.2 | **O Guardião de fidelidade** (IA): o segundo agente, molde do primeiro, os sete desvios, teste com desvio plantado | cursos, admin | ~7 |
| 3 | 3.3 | Fora desta célula: o cabeçalho de apêndice vivo e o aviso de verificação vencida na área de documentos | admin | ~5 |
| **4** | — | **Pares**: papel `par`, `Impedimento` lido por contrato (`encomendas`: delegação e colaboração; `identidade`: vínculos), as cinco primeiras avaliações 100% amostradas, a revisão de revisões semanal (`AmostraDeRevisao`), a calibração trimestral, co-assinatura após três correções | cursos, contracts | tarefas criadas quando a Fase 2 fechar |
| **5** | — | **Bancas** (E10, E21, E32): `Banca`, composição sem impedimentos, rubrica individual antes da mesa, comparação fora da vista, laudo único com data em voz alta, `banca.decidida.v1`, S2 como teste, o Preparador de Banca; a `encomendas` passa a ler o título daqui | cursos, contracts, encomendas | idem |
| **6** | — | Métricas: a Curva do Aprendiz sai dos eventos desta célula na `metricas` (onde as pessoas param por estado, taxa de abertura contra a dificuldade prevista, mudança repetida); n mínimo e opt-out como invariante lá | metricas, admin | idem |

**Regras de trânsito:** compose em PR próprio (`134`); entre 1.1 e 1.7 o
`deploy-celula` fica vermelho e **isso é esperado** (`088`); nunca duas
sessões no laudo ao mesmo tempo; 2.4 e 2.5 correm em bancadas próprias, em
paralelo com 2.3; a Fase 3 espera os capítulos chegarem ao editor (decisão do
mantenedor de 04/09/2026); as Fases 4 e 5 dependem de haver aluno chegando à
E10.

**Custo honesto:** cerca de 21 merges até o fim da Fase 3, duas sessões com o
mantenedor (A agora; B no degrau 1.4, o Rito de Contrato), um passo manual dele
na VPS, e os capítulos, que só ele pode trazer.

## §11 Critério de morte

**Pare e reabra a decisão com o mantenedor** se qualquer uma destas acontecer:

1. nascer um **segundo lugar** para o texto das aulas (na Biblioteca do Livro,
   na área de documentos, num arquivo do repositório, numa planilha
   "sincronizada");
2. a IA **persistir** decisão, data, resposta à pergunta ou carimbo, ou alguém
   propor que "ela decida os fáceis";
3. o prazo de 24 horas virar parâmetro editável, ou uma tela ganhar um botão de
   alongar;
4. nascer o estado "reprovado", com esse nome ou com outro;
5. nascer ranking, média de turma ou qualquer tela que ponha dois alunos lado a
   lado;
6. uma aula ficar atrás de XP, nível, Cristal ou pagamento **dentro desta
   célula** (o acesso é a matrícula, e só);
7. XP, medalha, Marco ou título de nível serem calculados aqui;
8. o conteúdo do curso entrar por arquivo commitado ou por migração com texto;
9. um chat livre entre aluno e professor nascer fora do laudo (a conversa da
   escola é o fórum; o laudo é estruturado de propósito);
10. qualquer invariante do §9 precisar de exceção.

## §12 Armadilhas já mapeadas deste caminho

020/021/022/025 (django-ninja) · 029/083/102/186 (`SCRIPT_NAME`, estáticos,
`/interno` exposto) · 035/077 (orçamento e etiqueta) · 076 (`rollback.yml`) ·
088 (deploy vermelho até o compose é esperado) · 089 (inventário de rotas no
mesmo PR) · 097 (env no ponto de uso) · 099 (o dia é America/Sao_Paulo) · 134
(compose em PR próprio) · 143 (`request.session` desloga o site inteiro) · 185
(o registro cita o número do PR) · 224 (`consome: []` na gênese) · 228/243 (o
contrato congela depois da porta) · 274 (unicidade através de chave
estrangeira) · 304 (plano de fora pede o que o portão recusa) · 331 (obra do
mantenedor no repositório público).

## §13 O que fica decidido para o próximo agente

1. **Ler os nove documentos** na pasta do mantenedor antes de qualquer PR desta
   célula (pedir o caminho a ele; eles não estão no repositório). O roadmap
   vence este resumo; este plano vence o roadmap onde o §3 diz que a casa já
   decidiu.
2. A escada do §10 se executa por lotes, com TAR-NNN encadeadas na fila.
3. Sessões A e B são com o mantenedor presente e nunca entram em lote.
4. **Decisões fechadas, não parâmetros:** 24 horas é constante com teste;
   "reprovado" não existe; a IA nunca decide; o conteúdo entra pela tela; o
   capítulo se chama `aula` em dado e código; a fila de revisão é da
   professora até a Fase 4.
5. Os invariantes do §9 nascem como teste no degrau que os implementa e nunca
   se flexibilizam.

## Estado

Plano escrito em 04/09/2026. Aguarda: Sessão A (a aprovação e a decisão dos
vídeos) → a gênese (TAR criada neste PR) → a escada.
