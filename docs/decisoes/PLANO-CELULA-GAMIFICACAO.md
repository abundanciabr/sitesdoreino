# PLANO — a célula `gamificacao` (Sistema de Formação de Criadores)

**Escrito em 30/08/2026**, a partir de: consultoria de 6 IAs + 5 auditorias
(`docs/consultorias/gamificacao/` — o VEREDITO.md de lá é parte deste plano) +
4 decisões do mantenedor em pergunta estruturada + exploração da arquitetura
em `origin/main`. Molde: `docs/decisoes/PLANO-AREA-ADMIN.md` (escada §6) e
`docs/caixa-de-sugestoes/PLANO-MESTRE.md` (lotes).

Este documento NÃO é um painel: não guarda estado e não se atualiza sozinho.
Quem responde "isto foi feito?" é o livro (`painel/registros/`) e a fila
(`fila/`). Na gênese da célula, este plano é promovido a
`DECISAO-celula-gamificacao.md` com a autorização nominal do mantenedor
(Sessão A).

---

## Parte 0 — A visão (o Documento-Mãe, em resumo)

A Meshcraft não constrói "Duolingo aplicado a um curso": constrói um **RPG de
carreira em que o personagem que evolui é o próprio aluno** — e o tesouro são
competências, obras e conquistas reais. A hierarquia que decide todo conflito
de desenho:

> **Realidade > Criação > Maestria > Comunidade > XP.**

Constituição da gamificação (do VEREDITO §3.1 e parecer 3): a pessoa é maior
que a métrica · aprendizagem > engajamento · maestria > XP · criação >
consumo · evolução > perfeição · cooperação > status · autonomia >
manipulação · contribuição > popularidade · realidade > gamificação · **o
objetivo final da gamificação é torná-la progressivamente menos necessária**.

Três invariantes com TESTE NO CI da célula:
1. **Nada por dinheiro real** — nenhum item, moeda, proteção ou vantagem.
2. **Cosmético é só estética** — nunca vantagem em XP, ranking ou visibilidade.
3. **Aula nunca fica atrás de jogo** — conteúdo educacional jamais trancado
   por XP, nível ou Cristal.

Pergunta de ouro de toda mecânica nova: *"Se o aluno parar de receber esta
recompensa amanhã, ele continuará valorizando o que aprendeu e criou?"*

O manual completo de produto (regras, telas, vocabulário) é o **Playbook da
Gamificação** (artefato do mantenedor, 30/08/2026); o VEREDITO.md guarda a
rastreabilidade de cada decisão. Este plano é a engenharia.

## §1 O que é (e o que NÃO é)

**É**: uma célula nova `services/gamificacao` — consumidora de fatos por
evento e provedora de leitura por HTTP. Ela transforma o que a plataforma JÁ
afirma (quiz completado, sugestão criada/votada, e — com eventos novos —
fórum) em XP, níveis, Sequência semanal, Têmpera, missões, medalhas, Marcos
de carreira, Cristais e cosméticos. A previsão de célula-consumidora-de-
eventos já existia por escrito em 3 documentos (`ESPECIFICACAO-CELULA.md` da
caixa, `AGENTS.sugestoes.md` "nunca calcula XP", `FORMATO-CHANGESPEC.md`).

**NÃO é**: reputação dentro do fórum; nota pedagógica; economia comprável;
ranking global público; fonte de verdade sobre pessoas, matrículas ou
conteúdo.

**A objeção do §4.7 do fórum, antecipada**: a lei do fórum manda parar se
alguém recriar um framework de reputação do zero. Este plano É a reabertura
formal — e a resposta é que a reputação NÃO mora no fórum: ele só (a) afirma
fatos por evento e (b) exibe um selo vindo por HTTP com falha aberta. O
critério de morte do fórum permanece intacto; o desta célula está no §8.

## §2 A decisão de arquitetura: célula própria

| Alternativa | Por que não |
|---|---|
| Calcular XP dentro do fórum/sugestões | Viola a Lei 3 e o §4.7 do fórum; espalha a economia por N células |
| Plugin/SaaS de gamificação | Dados de menores em terceiro; economia earn-only e marcos validados não existem de prateleira; Lei 2 (dados) |
| Esperar a trilha de aulas | A gamificação v1 se alimenta dos eventos que JÁ existem; a trilha pluga depois por 1 linha de regra (tomada `aula.concluida.v1`) |

Célula própria: banco + role próprios (Lei 2), `site_id` em toda entidade
(Lei 9/INV-P11), sem sessão própria (INV-P12), comunicação só por contrato
congelado + eventos versionados (Lei 3).

## §3 O modelo de dados (padrões copiados dos precedentes)

Moldes: espelho `Pessoa` (forum/models.py) · definições-como-DADO com default
fechado (fórum) · marca-d'água em vez de linha-por-item (MarcaDeLeitura) ·
livro-razão idempotente (pagamentos) · CheckConstraint no banco · IDs alheios
como CharField opaco · remoção suave · outbox transacional (sugestoes).

- **`Pessoa`** — espelho local (id_da_plataforma PK, email unique,
  nome_exibido). `quiz.completado.v1` chega por e-mail → resolve via espelho
  ou `identidade.findPersonByEmail` (já congelada).
- **`PerfilJogador`** — xp_total/nivel/cristais_saldo DESNORMALIZADOS do
  ledger (+ comando `reconciliar_perfis`); `modo` (junior/teen — junior
  OBRIGATÓRIO <13, trava de sistema); `modo_foco` bool; `participa_de_ligas`;
  `celebracoes_pendentes` (celebração visceral sem `request.session` —
  armadilha 143); Unique(pessoa, site_id).
- **`RegraDePontuacao` (dado)** — slug, evento_gatilho, beneficiario
  {ator|autor_do_alvo}, pontos, cristais, `decaimento` (teto SUAVE: N ações
  cheias/dia, depois rendimento decrescente até zero — nunca parede muda),
  `quarentena_horas` (0 = imediato; 24–72 p/ XP social), ativa=False,
  versao. Economia é UPDATE + versão, nunca PR; mudanças anunciadas, nunca
  retroativas. A tomada futura `aula.concluida.v1` = 1 linha semeada.
- **`LancamentoDeXP`** — o ledger: pontos (negativo = estorno),
  origem_event_id, regra_slug, **regra_versao**, occurred_at, `dia_local`
  (America/Sao_Paulo materializado — armadilha 099), `status`
  {pendente|definitivo|estornado} + liberado_em (a quarentena);
  **Unique(origem_event_id, regra_slug, pessoa)** = idempotência por
  construção (1 evento pode creditar votante E autor por regras distintas).
  Estorno em cascata quando o conteúdo de origem é moderado.
- **`MovimentoDeCristais`** — ledger de moeda; Unique(pessoa, referencia);
  CheckConstraint: delta negativo SÓ com referência de compra → earn-only por
  construção. Cristais intransferíveis (não existe caminho de escrita).
- **`Sequencia`** (semanal — marca-d'água, nunca linha-por-dia): meta_dias
  escolhida pelo aluno (leve/normal/intensa; <13 padrão 3),
  dias_ativos_na_semana, semana_corrente, semanas_atuais, recorde_semanas,
  dias_totais (permanente), escudos (1/mês automático e GRÁTIS — nunca à
  venda), modo_ferias. Semana falhada sem escudo → regride UM degrau, nunca
  zera. Dia ativo = lançamento DEFINITIVO de XP de aprendizado no dia
  (America/Sao_Paulo). + `UsoDeEscudo` (semana protegida) +
  `HistoricoDeSequencia`. Varredura semanal Huey fecha a contabilidade.
- **`Tempera`** — pessoa, desafio_ref (CharField opaco), medidor (só cresce:
  tentativa, pedido de feedback, revisão; teto por desafio), selada_em, selo
  ("forjada em N tentativas") — vira atributo exibível da obra. Zero XP.
- **`ConquistaDefinicao` (dado)** — classe {medalha|marco}, familia {oficio|
  comunidade|epoca|secreta|carreira|espelho}, criterio JSON de vocabulário
  FECHADO (não DSL — critério de morte) ou "manual", faixa_etaria
  {todas|13mais}, secreta, ativa=False. Marcos de dinheiro = faixa 13mais e
  validação SEMPRE adulta. **Marco rende ZERO XP** (VEREDITO §5.B).
- **`Concessao`** — pessoa, conquista, concedida_em, origem_event_id null,
  `validador_id` + `validador_papel` {professor|monitor|par|sistema}
  (auditável), `consentimento` {privado|turma|publico} **default privado**
  (nada é exposto sem ação explícita do aluno; <13 além da turma envolve
  responsável); Unique(pessoa, conquista) → backfill re-executável
  (Fundador: comando `conceder_fundador`).
- **`PedidoDeValidacao`** — a fila: tipo, evidencia (camada PRIVADA para
  marcos sensíveis — pares nunca veem), estado {em_analise|aceito|devolvido}
  ("em análise" nunca parece recusa; devolução privada com o que falta),
  SLA (48h úteis respostas / 5 dias úteis marcos), atribuído_a, motivo
  ESTRUTURADO obrigatório na devolução; N devoluções de pares → escala para
  adulto (anti-bullying); autor oculto ao validador quando possível.
- **`MissaoDefinicao` (dado)** + **`ProgressoDeMissao`** — diárias/semanais/
  de dupla; janela em America/Sao_Paulo; linha preguiçosa no 1º incremento
  (Lei 7); diversidade forçada de categorias; nenhuma missão exige presença
  diária. A missão semanal grande é a **Encomenda da Semana**.
- **Ligas (Camada 3; modelo pronto, feature desligada)** — `LigaDefinicao`
  (dado: tiers, tamanho ~15, limiar ABSOLUTO de promoção, SEM rebaixamento),
  `GrupoDaSemana`, `ParticipacaoNaLiga` (inscrição preguiçosa; pontos = XP
  da semana COM teto diário; marco fora; temporada 6–8 semanas; exibe top 3
  + vizinhança; nunca o último lugar; opt-in <13 = off por trava).
- **`ItemCosmetico` (dado)** + **`Aquisicao`** — tipos {titulo, moldura,
  tema, decoracao_estudio (o sumidouro principal)}; sazonal volta todo ano;
  sem cronômetro; Escudo NÃO é item de loja. **`NivelDefinicao` (dado)** —
  10 níveis no lançamento, curva acelerada no início; títulos de nível SEM
  vocabulário de credencial (base: Aprendiz → Oficial → Mestre de Ateliê);
  forma feminina opcional. `ConfiancaDaComunidade` — peso INTERNO de
  reputação de ajuda (nunca exposto).
- **`OutboxEvent`** — molde byte-a-byte de sugestoes, para emitir
  `notificacao.devida.v1` (celebrações via sininho).

## §4 Eventos e contrato

**Consumidos (já congelados)**: `quiz.completado.v1` (XP só na 1ª aprovação
por quiz) · `sugestao.criada.v1` · `sugestao.voto-adicionado/removido.v1`
(estorno espelhado) · `sugestao.status-alterado.v2` (implementado →
prestígio + medalha + Cristais + aviso público, POUCO XP). Eventos de
pagamento NÃO consumidos (pagamento por último; Fundador via backfill).

**Novos a congelar (UMA Sessão B / Rito de Contrato cobre todos)** — envelope
canônico, `ator_id` no envelope, additionalProperties:false, só IDs opacos
(nunca e-mail/texto; `caracteres` numérico opcional na mensagem, a decidir):
- `forum.topico-criado.v1` { site_id, topico_id, area_id }
- `forum.mensagem-criada.v1` { site_id, mensagem_id, topico_id, area_id }
- `forum.mensagem-removida.v1` { site_id, mensagem_id, topico_id } — estorno
- `forum.resposta-aceita.v1` { site_id, topico_id, mensagem_id,
  autor_da_resposta_id } — o evento mais valioso (+150, validado)
- Aditivo em `notificacao.devida.v1`: assuntos `gamificacao.nivel-alcancado`,
  `.conquista-concedida`, `.marco-validado`, `.destaque-da-semana` (+ ramos)
- Tomada futura: `aula.concluida.v1` { site_id, curso_id, aula_id }

**Presença**: NÃO nasce evento de presença. Dia ativo deriva do ledger.
Login = 0 XP, sempre.

**Contrato HTTP** (`contracts/gamificacao.openapi.yaml`, padrão Bearer por
par + cookie opaco; visitante = 200 autenticado:false):
- `getPublicProfiles` — GET /api/gamificacao/perfis?ids=... (lote ≤50): mapa
  id → { nivel, titulo_slug, moldura_slug } — o fórum decora N autores com 1
  chamada; id desconhecido é omitido; nunca e-mail nem XP bruto.
- `getMyStatus` — GET /api/gamificacao/eu: xp, nivel, xp_para_proximo,
  sequencia {semanas, dias_da_semana, meta, escudos}, cristais, missões,
  celebracoes_pendentes.
Consumidores: cache 5 min + falha ABERTA (página sem selo, nunca quebrada).
`celulas.yml`: gamificacao.consome [identidade]; depois forum/funil.consome
+= gamificacao (GAMIFICACAO_API_URL).

## §5 Superfícies

**Prefixo público: `/conquistas`** (10 letras — passa no guarda de locale;
"xp" é proibido; inventário `test_rotas_sem_forma_de_locale.py` no MESMO PR
do Traefik — armadilha 089). Host-bound em meshcraft.top.

- `/conquistas` (a Base): nível+barra, chama da Sequência, missões, Têmpera
  dos desafios ativos, celebrações pendentes (visceral: tela cheia, título
  troca na hora; POST marca vista — estado no MODELO, armadilha 143). Regra
  de tela: XP nunca maior que a imagem da obra. Encerramento do dia após
  meta+tetos: "você já fez o que importava — mostre para alguém".
- `/conquistas/medalhas` (coleção; secretas ocultas) · `/conquistas/jornada`
  (Passaporte: SÓ o próximo marco e o que falta PARA ELE + normalizador de
  tempo; bifurcação etária — Modo Júnior termina em obra) ·
  `/conquistas/loja` ("Cristais não se compram. Só se ganham.") ·
  `/conquistas/estudio` (Meu Estúdio interno; versão pública OPT-IN, só
  apelido + obras aprovadas + marcos escolhidos, noindex, links de lista
  permitida; rota pública final na Sessão B).
- **Galeria/Encomenda da Semana (Camada 1, via fórum)**: sem pipeline novo de
  upload — post do fórum com imagem é PROMOVÍVEL a card de galeria
  (curadoria + checklist técnico-objetivo); Destaques do professor (3/semana,
  com a frase do porquê); reações categorizadas sem placar. Tela da galeria
  na célula gamificacao consumindo os eventos do fórum + moderação prévia.
- **Painel do professor/moderação** (dentro do /conquistas/interno ou da
  célula admin — decidir na Sessão B): fila única com SLA, ações de 1
  clique, reverter/zerar/conceder auditável, delegação escalonada
  (autor "resolveu" → monitor → professor), auditoria amostral.
- Fórum: selo "Nv · título" via getPublicProfiles. Funil: widget da
  Sequência na home logada. Sininho: cartas de celebração.
- Notificações: só boas notícias, máx 1/dia, nunca >20h nem horário escolar.

## §6 A escada de entrega (ordem canônica; custo honesto: ~22 merges + 2
sessões com o mantenedor + 1 passo manual dele)

Precedentes: gênese do fórum (armadilhas 076/088/089/134), PLANO-AREA-ADMIN
§6 (provisionamento SOZINHO antes do passo H; infra SOZINHO).

| # | PR | Conteúdo | Arqs |
|---|---|---|---|
| — | **Sessão A** | Arquitetura com o mantenedor: aprova esta lei (vira DECISAO), calibração de XP/níveis, nomes finais (tema das ligas c/ a restrição Diamante×Cristais; nome da Têmpera; rota do Estúdio), equipe adulta de validação, P0/P1/P2 do Banco de Ideias | — |
| 0 | mapa | painel/ia citando a célula que nasce | 1–2 |
| 1 | **gênese** | Esqueleto services/gamificacao (settings fail-hard TIME_ZONE=America/Sao_Paulo, CSRF próprio, healthz 2 formas — 029/083/102/186; INV-P12 test_inv_gamificacao_nao_assina_sessao; Dockerfile/Makefile/pytest) + celulas.yml (consome:[identidade]) + manifesto not-applicable + rollback.yml (076) + constituicoes/AGENTS.gamificacao.md + DECISAO | ~22, label `arquitetural` (035/077: fechar e reabrir p/ label valer) |
| 2 | registro | livro em PR próprio (armadilha 151) | 1–2 |
| 3 | modelos | Tabelas do §3 + migração + semear (tudo ativa=False) + **os 3 testes-invariante do CI** + testes de constraint | ~14 |
| — | **Sessão B** | Rito de Contrato: gamificacao.openapi.yaml + 4 eventos forum.* + aditivo notificacao.devida | — |
| 4 | contrato | SÓ contracts/ (label `contrato`; manifesto flip) | ~7 |
| 5 | provisionamento | SOZINHO, antes do passo H: infra/provisionar-gamificacao.sh + env exemplo | ~5 |
| H | **mantenedor** | UMA LINHA fail-closed (banco+role+env; PRONTO:/PAROU POR SEGURANÇA:) | — |
| 6 | infra | SOZINHO (134): compose + Traefik /conquistas + inventário de rotas no MESMO PR (089). Deploy vermelho entre PR1 e cá é ESPERADO (088) | ~3 |
| 7 | porta+base | clients/sessao (molde fórum), espelho Pessoa, /conquistas mínima | ~12 |
| 8 | motor | consumer idempotente (molde notificacoes/alunos) + motor de XP (regras c/ decaimento, quarentena, dia_local, versão) + perfil/nível | ~13 |
| 9 | cartas | OutboxEvent + relay Huey + notificacao.devida + celebração visceral | ~10 |
| 10 | sequência | Modelo semanal + escudo automático + varredura + Modo Férias + widget | ~10 |
| 11 | missões | Progresso preguiçoso + diversidade + Encomenda da Semana (regra) | ~9 |
| 12 | medalhas+marcos | Motor de critérios + Concessao c/ consentimento + fila PedidoDeValidacao c/ SLA + Passaporte bifurcado por idade | ~14 |
| 13 | painel do professor | Fila única, 1 clique, delegação, auditoria, estorno | ~10 |
| 14 | têmpera | Medidor + selo na obra | ~7 |
| 15 | loja | Cristais + decoração do Meu Estúdio + equipar | ~10 |
| 16 | porta de máquina | Contrato implementado + export_openapi + testes de porta (armadilhas ninja 020/021/022/025) | ~8 |
| 17 | fórum emite | outbox no fórum + 4 eventos + testes (célula forum) | ~10 |
| 18 | fórum exibe | cliente em lote + cache + selo + celulas.yml | ~6 |
| 19 | galeria | Promoção de post→card + curadoria + Destaques + reações (consome eventos do fórum; moderação prévia) | ~12 |
| 20 | funil exibe | widget home logada | ~6 |
| 21 | sininho redige | frases dos assuntos novos | ~4 |
| 22 | backfill | conceder_fundador re-executável + registro | ~4 |

Paralelismo: 10/11/14/15 serializáveis em qualquer ordem após o 9; 17 em
paralelo (célula distinta). Execução por LOTES (RUNBOOK-LOTES): canário na
frente; mesma célula = fila interna; lote seguinte só com o anterior fechado.
Cada PR vira TAR-NNN na fila com `--depende-de` encadeando.

## §7 Camadas de produto (portões de ligar E desligar)

- **Camada 1** (PRs 0–13 + 16–19): XP/tetos, 10 níveis, galeria + Encomenda,
  medalhas de ofício, Marcos + Fundador, fila com SLA, painel do professor,
  onboarding (primeira vitória nos primeiros minutos, desembocando no
  Blender). **PORTÃO: verificação oficial das regras de idade Roblox/Fiverr
  ANTES de ligar os marcos de carreira.**
- **Camada 2** (30–60d/trilhas): missões + duplas, Cristais/loja, Sequência +
  Têmpera, mapa de habilidades, Antes/Depois, Painel do Responsável, XP de
  aula (semear 1 regra).
- **Camada 3** (~150 ativos/semana): ligas (fórmula travada no VEREDITO),
  Meta da Turma, temporadas temáticas, sazonais, secretas, quórum de pares,
  Guildas, Missões de Impacto, Meshjam.
- **Banco de Ideias declarado** (fora do escopo até promoção na Sessão A):
  Museu da Evolução, sistema de reflexão único (Arquivo do Impossível + Mapa
  de Evidências + Livro de Descobertas), Grande Obra/Desafio sem Tutorial,
  Atlas de Criador, Cerimônia dos Criadores, Legado, Oficina Aberta, dicas
  de veterano, obra coletiva, perfil-currículo, números reais da obra,
  Ciência da Transformação.
- **Critérios de DESLIGAR** (todo interruptor com gatilho): XP÷obras subindo
  → revisar regras; retorno pós-quebra < churn médio → mexer na Sequência;
  marco-e-some → revisar recompensas; quartil de baixo caindo → desligar a
  mecânica social; padrão bater-ponto (sessões <2min) → revisar; relato de
  responsável = alarme prioritário. Dashboard Engajamento × Transformação ×
  Bem-estar; norte = Progresso Significativo Semanal; medir por quartil.

## §8 Riscos, segurança e critério de morte

- **Validação**: escalada autor→monitor→professor (Camadas 1–2); pares só
  para ARTEFATOS PÚBLICOS e só com população (Camada 3); marcos de DINHEIRO
  sempre com adulto, evidência em camada privada; papel de ajuda ≠ papel de
  validação (validador sem status público); anti-bullying (motivo
  estruturado, nunca terminal/público, anéis de rejeição detectados,
  auditoria amostral).
- **Menores**: Modo Júnior obrigatório <13; sem mensagem direta entre
  alunos; moderação prévia de tudo público; links de lista permitida;
  encomenda interna COM dinheiro fora do escopo gamificado até desenho
  jurídico; "com ajuda do responsável" em todo marco com contato externo;
  nunca valores, nome real, idade; consentimento padrão privado.
- **Antifraude**: "prefira teto a punição"; idempotência; quarentena; grafo
  de pares e anéis; multiconta (e-mail do responsável, limite, fingerprint,
  conta 7+ dias); velocity check/shadowban; Protocolo de Autoria (.blend +
  viewport com apelido + processo + similaridade); sem detector de texto de
  IA (teto de não-validadas + razão respostas/aceitas); punição restaurativa
  e privada; transparência (regras publicadas, nunca retroativas).
- **Conformidade**: ECA Digital (uso compulsivo, loot box), CONANDA 163,
  LGPD art. 14/ANPD, Roblox UGC 13+, Fiverr 13–17 via responsável;
  "primeiros dólares" = possibilidade, nunca promessa.
- **Critério de morte** (parar e reabrir a decisão se): (1) virar motor de
  regras genérico/DSL; (2) Cristais compráveis ou transferíveis; (3) pontos
  calculados dentro de outra célula; (4) ranking global público/indexável;
  (5) ajuste de economia exigir PR de código; (6) qualquer invariante do CI
  precisar de exceção.

## §9 Armadilhas já mapeadas deste caminho

020/021/022/025 (django-ninja) · 029/083/102/186 (SCRIPT_NAME/estáticos/
interno exposto) · 035/077 (orçamento/label) · 076 (rollback.yml) · 088
(deploy vermelho até o PR de infra é esperado) · 089 (inventário de rotas no
mesmo PR) · 097 (env no ponto de uso) · 099 (USE_TZ não escolhe fuso — dia =
America/Sao_Paulo) · 134 (compose em PR próprio) · 143 (request.session
desloga o site inteiro — celebração no modelo) · 151/156 (registro/painel em
PR próprio) · 170 (conn_max_age sob ASGI).

## §10 O que fica decidido para o próximo agente

1. Ler o VEREDITO.md antes de qualquer PR — a rastreabilidade de cada
   decisão está lá; este plano não se reabre por preferência de agente.
2. A escada do §6 se executa por lotes, com TAR-NNN encadeadas na fila.
3. Sessões A e B são com o mantenedor presente e NUNCA entram em lote.
4. Marco real = 0 XP; login = 0 XP; escudo nunca à venda; padrão de
   consentimento = privado — são decisões fechadas, não parâmetros.
5. Os 3 invariantes nascem como testes no PR 3 e nunca se flexibilizam.

## Estado

Plano escrito e consultoria arquivada em 30/08/2026 (PRs desta entrega no
livro). Aguarda: Sessão A (arquitetura com o mantenedor) → fila → lotes.
