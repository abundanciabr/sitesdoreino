# DECISÃO — a Fila do Primeiro Dólar nasce como célula própria: `encomendas`

> **Estado: APROVADA pelo mantenedor em 03/09/2026**, em pergunta estruturada
> na mesma sessão que a escreveu (registro `20260904-006` no livro). Ele
> decidiu: a lei vale com as emendas do §3; a escola é 18+ também aqui; a
> Fase 2 (o motor, sem dinheiro) começa em paralelo com o piloto de papel; o
> professor dá o título na tela de plantão até a Banca existir. A gênese
> (TAR-109) está destravada.
>
> Seria a oitava reabertura nominal do congelamento arquitetural, depois de
> `sugestoes`, `identidade`, `notificacoes`, `admin`, `forum`, `gamificacao`
> e `pages` (esta última decidida em 02/09/2026 e ainda não nascida).
>
> **O PRODUTO NÃO SE REPETE AQUI.** Ele mora em
> `docs/decisoes/PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md`: promessa, princípios,
> cardápio, jornadas, livro de regras, modelo de domínio, algoritmo, roadmap,
> métricas, textos de tela e cenários de aceite. Este documento é a **LEI**: o
> que vale, o que é proibido, onde o plano e a casa divergem e quem vence, e o
> que ainda está em aberto e de quem é a decisão.

## 1. A decisão

Nasce a célula **`services/encomendas`**, Django + django-ninja como todas as
outras, com **banco próprio** (`encomendas_db`), **role próprio**
(`encomendas_user`), **processo próprio** e **contrato próprio**.

Ela é o marketplace de encomendas 3D da Meshcraft Academy visto de dentro: os
perfis profissionais dos formados, a fila, as ofertas, as encomendas, as
entregas, as revisões, as correções, as mediações e a tela de plantão. O
plano a resume em uma frase que vira régua aqui: **a plataforma escolhe o
aluno, não o cliente**; uma fila, uma regra (menos entregas primeiro, empate
por quem entrou antes); e **nenhuma primeira entrega chega ao cliente sem um
humano olhar**.

**Nenhum marketplace de prateleira entra.** Não há freelancer a escolher, não
há proposta, não há lance: é exatamente o que os marketplaces de fora vendem,
e é exatamente o que este produto existe para não ter.

## 2. O que fica FORA — a seção 3 do plano, literal

O plano manda copiar esta lista sem mudar uma vírgula, para nenhum agente
"melhorar" o desenho por conta própria. Está copiada:

> ### Fora — dito explicitamente para nenhum agente "melhorar" por conta própria
>
> - Chat livre entre cliente e aluno
> - Escolha de freelancer, propostas, lances, ranking, notas públicas
> - Matriz de competências por categoria (o título da Banca é a matriz)
> - Percentuais de distribuição entre níveis (a cascata faz isso)
> - Orçamento livre nos níveis 1 e 2
> - Equipes, líder de projeto, mais de uma encomenda da fila por vez
> - Matchmaking por IA; classificação de briefing por IA
> - Cliente escolher o nível do modelador
> - App nativo (v1 é web responsiva, mobile-first)
> - Qualquer nome em inglês na interface

Quem se pegar desenhando qualquer item desta lista **para e reabre a decisão
com o mantenedor**. É também o critério de morte 1 do §9.

## 3. As emendas da casa

O plano foi escrito fora deste repositório, com ajuda de duas IAs de fora, e
não conhecia três coisas: os portões desta casa, as decisões anteriores do
próprio mantenedor, e a forma como uma célula nasce aqui. Onde ele pede algo
que um portão recusa ou que uma decisão já fechou, **vale o que está abaixo**.
Nenhuma destas emendas muda o produto; todas mudam a forma de construí-lo.

### 3.1 A escola é 18+ — o "Responsável" não tem sujeito

O mantenedor declarou em 30/08/2026 (*"só temos alunos acima de 18 anos, não
temos e nem teremos alunos menores de idade"*), a lei da gamificação foi
emendada no mesmo dia (`DECISAO-gamificacao.md` §9), e ele **reconfirmou em
03/09/2026** ao recusar a jornada dupla aluno/pagador do painel de gestão. O
plano, escrito por IAs que não sabiam disso, traz o ator **Responsável**, o
princípio 11 ("Menores em primeiro lugar"), a seção 10 inteira, o campo
`responsavel_id`, o invariante D17 e a decisão pendente 5.

**Régua, a mesma da gamificação: guardar o que serve para adulto, remover o
que só existia por causa de idade.**

- **Sai:** o ator Responsável; `responsavel_id` e "repasse ao responsável";
  a cópia de notificações a um adulto vinculado; "sem sobrenome para
  menores"; a decisão pendente 5 (idade mínima), que fica respondida: **18+,
  porque a escola inteira é**.
- **Fica, porque não era sobre idade:** comunicação **estruturada**, sem
  contato direto e sem campo de contato no briefing (S1); nenhum dado de
  contato do aluno para o cliente (S3); o plantão aprovando cliente novo
  (S5); os termos de uso (cessão da peça, direito de exibição, originalidade);
  e o **parecer jurídico** sobre custódia de valores de terceiros, LGPD e
  cessão de direitos, que é portão da Fase 3 (não mais "trabalho de
  menores").
- **D17 é reescrito, e continua sendo invariante:** *repasse só para conta de
  recebimento verificada do próprio aluno; sem conta verificada, o repasse
  fica bloqueado, o plantão é avisado, e o aluno nunca perde o valor.* O
  mecanismo que o plano queria (dinheiro nunca sai para lugar não conferido)
  sobrevive; o sujeito muda.

Se um dia a escola aceitar menores, esta seção é o lugar onde a trava volta,
**antes** de a funcionalidade que a exige ser ligada.

### 3.2 O contrato HTTP congela DEPOIS da porta de máquina existir

O plano diz "contrato OpenAPI v1 congelado na Fase 0". Nesta casa isso trava a
célula: o manifesto de contratos só tem dois estados, e `required` significa
"existe um `manage.py export_openapi` que imprime o schema vivo" (`armadilhas/228`,
que custou uma volta à gamificação em 30/08/2026; e `armadilhas/243`: o
congelado nasce **do export**, nunca de cabeça).

**Então, na Fase 0, o contrato v1 vive escrito em
`docs/decisoes/CONTRATO-encomendas-v1-rascunho.md`** (é o anexo que os
consumidores leem e contra o qual os degraus 2.7 e 2.8 se medem), e o
congelamento em `contracts/encomendas.openapi.yaml` é o degrau **2.8** da
escada, imediatamente depois da porta de máquina (degrau 2.7). Os
**eventos** não têm essa amarra (o manifesto só existe para os
`*.openapi.yaml`), e por isso os 20 esquemas da seção 7.3 do plano **entram
já**, em `contracts/eventos/` (TAR-108).

**E o que É contrato aqui não é o que o plano lista no §8.3.** Nesta casa as
telas do aluno, do cliente e do plantão são páginas servidas pela própria
célula (formulário normal, melhoria progressiva, cookie repassado à
`identidade`), como no fórum e na gamificação; elas **não são contrato**. O
contrato é a **porta de máquina**: o que OUTRA célula chama por Bearer. O
anexo separa as duas coisas (Parte A, o contrato; Parte B, as telas), e a
razão é `armadilhas/103` e `186`: "API interna" sob `SCRIPT_NAME` responde
pela internet, e cada rota a mais no contrato é uma rota a mais a defender.

### 3.3 Teste vermelho não entra na `main`: os invariantes nascem declarados aqui, e viram guarda no PR do motor

O plano pede "testes-guarda J/D/S como esqueleto (falhando)" na Fase 0. A
catraca verde (RITOS.md §2) não admite estado vermelho na `main`, e o guarda
dos guardas recusa teste sem dente (sem `skip`, sem corpo vazio). Um esqueleto
que passa sem medir seria o padrão 1 da retrospectiva (falso-verde).

**A forma da casa, com precedente (TAR-042, gamificação):** os invariantes
ficam **declarados no §5 desta lei** com o caminho do guarda já escolhido, e
entram no `INVARIANTES.md` **no mesmo PR em que o guarda nasce**, provados por
mutação com vermelho na asserção (`armadilhas/195`). Os J no motor e nos
relógios (degraus 2.3 e 2.4); os D na Fase 3; os S nas Fases 3 e 5.

### 3.4 Dinheiro por último — e o piloto roda no site sem uma linha de dinheiro

Diretiva do mantenedor de 22/08/2026, reafirmada desde então: **nenhum
trabalho de cobrança, checkout ou Mercado Pago até ele dizer que o site vai
vender.** A Fase 3 do plano ("Cliente e dinheiro") e a extensão da célula de
pagamentos (§8.4) esperam esse sinal, e ninguém o antecipa.

Isso não para o produto, porque o próprio plano diz que **a escola é o
primeiro cliente** (princípio 9) e que o piloto de papel roda sem custódia. A
tradução para código: **até a Fase 3, a única origem de encomenda que entra
na fila é `escola`**, criada pelo plantão, com a confirmação de pagamento
**registrada com autor** (o plantão declara "pago pela escola", e o registro
guarda quem e quando). O invariante D13 mede a **confirmação registrada**, não
o webhook: o webhook do Mercado Pago passa a ser uma segunda fonte de
confirmação na Fase 3. Com isso, Fase 2 (motor) + Fase 4 (tela do aluno) +
Fase 5 (entrega e revisão) entregam a Fila do Primeiro Dólar **funcionando no
site, com a escola pagando o aluno por fora**, exatamente como o piloto de
papel, e sem tocar a diretiva.

### 3.5 O portfólio já tem casa: o Estúdio, opt-in

O plano diz "na primeira aprovação, `meshcraft.top/@usuario` entra no ar",
automático. A casa já decidiu duas vezes o contrário: a vitrine pública do
aluno mora em **`meshcraft.top/estudio/<apelido>`**, **opt-in**, `noindex`,
só apelido e obras aprovadas (decisão 3 da Sessão A, 30/08/2026), e ela vive
na célula **`pages`** (decisão de 02/09/2026, `PLANO-PORTFOLIO-DO-ALUNO.md`
§4). **Nenhum fato do projeto mora em dois lugares**: esta célula **não
constrói um segundo portfólio**.

O que ela faz: emite `encomenda.aprovada.v1` com a autorização do cliente
(S4) e responde por contrato quais peças de uma pessoa estão aprovadas e
autorizadas (`getApprovedPieces`, Parte A do anexo). O Estúdio, quando quiser,
pergunta e mostra o selo "Encomenda Meshcraft" e os contadores. O botão
**"Encomendar direto"** é um link do Estúdio para o cardápio com o aluno
fixado (`/encomendas/pedir?para=<apelido>`), e a encomenda direta percorre a
mesma esteira (§5.6 do plano).

O que fica em aberto para o mantenedor (decisão pendente **12**, §8):
automático como o plano diz, ou opt-in como a casa decidiu? A recomendação é
a da casa (ninguém tem obra exposta sem ter pedido), e a Fase 6 espera a
resposta.

### 3.6 O título de Banca ainda não existe — o professor É a Banca até ela existir

A elegibilidade (§6.1 do plano) vem do título de Banca "ou curso concluído,
até a formação existir". Medido em `origin/main` de 03/09/2026: **nenhuma
célula serve aula**, não há Banca, não há "curso concluído" mensurável (a
célula de cursos é plano a escrever). A gamificação tem níveis e títulos, mas
eles são **deliberadamente sem vocabulário de credencial** (Aprendiz, Oficial,
Mestre de Ateliê) e **não** dizem o que alguém sabe fazer.

**Então o título (`titulo_banca`: Nível 1, 2 ou 3) é dado pelo professor, na
tela de plantão, com data e autor** — é o que o piloto de papel já faz à mão.
Quando a Banca existir na célula de cursos, ela passa a ser a segunda fonte do
mesmo campo, por evento. Decidido por ele em 03/09/2026 (§8).

### 3.7 Avisos: esta célula emite `notificacao.devida.v1`, e não nasce consumidor novo

O plano prevê um "consumidor de notificações" (item 4.4). Nesta casa quem
avisa é o sininho, alimentado por `notificacao.devida.v1` com um `assunto` por
fato (modelo híbrido de 31/08/2026: serviço no contrato, incentivo na tela do
mantenedor). Esta célula emite esse evento pelo padrão outbox, como a
gamificação; os assuntos `encomendas.*` entram no enum por Rito de Contrato
**aditivo** na Fase 4, e o canal do celular (push) já existe desde 31/08/2026.
A decisão pendente 6 do plano (canal) fica **respondida pela casa**: site +
sininho + aviso no celular; e-mail quando a mensageria ganhar canal de e-mail.

### 3.8 Parâmetros são dado, com histórico, e o dono edita na tela do Admin

Item 0.5 do plano, e a lei da gamificação já tem a mesma regra ("a economia é
dado, nunca código"). A tabela `Parametro` mora nesta célula: `chave`,
`valor`, `desde`, `motivo`, `quem`; **mudar é acrescentar uma linha**, nunca
`UPDATE`; o motor lê o valor vigente **em `agora`** (e por isso um parâmetro
mudado às 15h não reescreve uma oferta feita às 14h). A tela mora no Admin
(`/admin/encomendas/parametros/`), lendo e gravando pela porta de máquina
(Parte A do anexo), no mesmo desenho de `/admin/economia/`. **Nenhum número
da seção 6.12 vive em código**: um teste-guarda lê cada chave do banco e
reprova constante mágica no motor. O rito de mudança é a linha nova com
motivo escrito, e o livro do painel recebe um registro quando o mantenedor
muda um valor (é ele quem muda; o registro é o rastro).

### 3.9 Nomes, endereços e eventos

- **Nome no menu: "Encomendas". Nome da funcionalidade: "Fila do Primeiro
  Dólar."** É a recomendação do plano (decisão pendente 10), adotada; muda
  em uma linha se ele preferir outra coisa.
- **Endereço: caminho, nunca subdomínio** (`DECISAO-forum-da-escola.md` §2:
  é o que mantém o login único de pé). Prefixo **`/encomendas`** (10 letras,
  passa no guarda de locale; inventário de rotas no MESMO PR do Traefik,
  `armadilhas/089`). Nome da célula = nome da rota, de propósito.
- **Eventos com os nomes do plano**, no formato da casa (hífen no fato,
  `.v1`): `encomenda.paga` · `encomenda.oferecida` · `oferta.aceita` ·
  `oferta.passou` · `oferta.expirou` · `encomenda.aberta` ·
  `encomenda.entregue` · `entrega.auditada` · `entrega.revisada` ·
  `encomenda.aguardando-cliente` · `encomenda.correcao-pedida` ·
  `encomenda.aprovada` · `encomenda.concluida` · `encomenda.abandonada` ·
  `encomenda.cancelada` · `encomenda.em-mediacao` · `aluno.pausado` ·
  `aluno.disponivel` · `portfolio.publicado` · `pedido-direto.criado`.
  `aluno.pausado` e `aluno.disponivel` falam do **perfil da fila**, não da
  matrícula. Só ids opacos viajam; briefing, texto e e-mail nunca.
- **Dinheiro em contrato é inteiro em centavos** (`contracts/README.md`, item
  7): `preco_cents`, `taxa_cents`, nunca float.

### 3.10 Quem é quem, na linguagem da casa

| Papel do plano | Como a casa o reconhece |
|---|---|
| **Aluno** (na fila) | pessoa da `identidade` com `PerfilProfissional` nesta célula e `titulo_banca` dado pelo professor (§3.6); a matrícula se pergunta à `alunos` (`getStudentStanding`), nunca se copia |
| **Cliente** | qualquer pessoa cadastrada na `identidade`; "cliente novo" = primeira encomenda dessa pessoa, que passa pelo plantão (S5) |
| **Escola-cliente** | encomenda com `origem = escola`, aberta pelo plantão |
| **Revisor** | o professor até existir Nível 3; depois, aluno com título Nível 3 que **não** é o autor da encomenda |
| **Plantão** | professor ou administrador, as mesmas listas do fórum (`FORUM_PROFESSORES` é a fonte de "quem é professor" até a `identidade` ter o papel) |
| **Dono** | o mantenedor; aprova a lei, os parâmetros e os preços, fecha os portões |

## 4. Endereços, fronteiras e comunicação

- **Expõe (telas):** `/encomendas` (o aluno: uma tela, três estados),
  `/encomendas/pedir` (o cliente: cardápio → briefing → confirmar → pagar),
  `/encomendas/acompanhar/<id>` (o rastreio de uma linha),
  `/encomendas/plantao` (o professor). `/encomendas/healthz` responde sem
  nada. Web responsiva, celular primeiro; sem painel corporativo (§8.7 do
  plano).
- **Expõe (contrato, Parte A do anexo):** os parâmetros (para o Admin), o
  estado da fila de uma pessoa (para a home e o Estúdio), as peças aprovadas
  e autorizadas (para o Estúdio), e as duas portas internas: pagamento
  confirmado (da `pagamentos`, Fase 3) e resultado da auditoria (do worker,
  Fase 5).
- **Consome:** `identidade` (quem é o dono do cookie; **esta célula não assina
  sessão**, INV-P12), `alunos` (categoria da pessoa). Na gênese,
  `celulas.yml` declara `consome: []` com o comentário que explica a lista
  vazia (`armadilhas/224`); cada consumo entra no PR do cliente que o lê.
- **Emite:** os 20 eventos do §3.9 e `notificacao.devida.v1`, ambos por
  outbox transacional (INV-P6) e relay Huey.
- **Não sabe:** o que é Marco (a gamificação escuta `encomenda.aprovada`), o
  que é cobrança (a `pagamentos` cobra, retém, repassa e reembolsa; esta
  célula só sabe "pago", "repassado", "reembolsado"), o que é aula (a Banca
  chegará por evento da célula de cursos).
- **Banco:** `encomendas_db`, role `encomendas_user`. Guarda perfis, fila,
  ofertas, encomendas, entregas (metadados; os arquivos, ver Fase 5),
  revisões, correções, mediações, parâmetros. **Nada de dado alheio copiado
  sem necessidade**: `Pessoa` é espelho mínimo (id da plataforma, nome de
  exibição).

## 5. Os invariantes (declarados aqui; guarda no PR que nasce)

Formato do `INVARIANTES.md`; entram lá **com** o guarda, no PR indicado. Os
códigos são definitivos; o caminho do guarda também.

### Justiça (motor e relógios, degraus 2.3 e 2.4)

| Código | O quê | Guarda |
|---|---|---|
| **[INV-ENC-J1]** | Uma encomenda nunca tem duas ofertas pendentes | `services/encomendas/tests/test_inv_j1_uma_oferta_por_encomenda.py` |
| **[INV-ENC-J2]** | Um aluno nunca tem duas ofertas pendentes | `.../test_inv_j2_uma_oferta_por_aluno.py` |
| **[INV-ENC-J3]** | Toda oferta vai ao elegível disponível com menor `(entregas_aprovadas, data_entrada_fila)` | `.../test_inv_j3_menor_entregas_depois_mais_antigo.py` |
| **[INV-ENC-J4]** | Passar, expirar e pausar nunca alteram `data_entrada_fila`; só abandono | `.../test_inv_j4_so_abandono_muda_o_lugar.py` |
| **[INV-ENC-J5]** | Nenhuma oferta a aluno com título abaixo do nível mínimo da encomenda | `.../test_inv_j5_nivel_minimo.py` |
| **[INV-ENC-J6]** | Nenhum aluno recebe a mesma encomenda duas vezes, salvo em chamada aberta | `.../test_inv_j6_nunca_a_mesma_duas_vezes.py` |
| **[INV-ENC-J7]** | Aluno "trabalhando" não recebe ofertas | `.../test_inv_j7_trabalhando_nao_recebe.py` |
| **[INV-ENC-J8]** | O relógio da oferta não avança fora da janela 8h–22h (São Paulo) | `.../test_inv_j8_relogio_congela_fora_da_janela.py` |
| **[INV-ENC-J9]** | Nenhuma encomenda passa de 24h em `na_fila`/`oferecida` sem virar aberta | `.../test_inv_j9_vira_aberta_em_24h.py` |
| **[INV-ENC-J10]** | Reexecutar o motor sem mudança de estado não cria oferta nova | `.../test_inv_j10_motor_idempotente.py` |

### Dinheiro (somam-se aos 12 existentes; Fase 3, célula `pagamentos` e esta)

| Código | O quê | Guarda |
|---|---|---|
| **[INV-ENC-D13]** | Encomenda só entra na fila após **confirmação de pagamento registrada com autor** (webhook da `pagamentos`, ou o plantão para `origem = escola`) | `services/encomendas/tests/test_inv_d13_so_entra_paga.py` |
| **[INV-ENC-D14]** | Repasse só após `aprovada` | `services/pagamentos/tests/test_inv_d14_repasse_so_apos_aprovada.py` |
| **[INV-ENC-D15]** | Reembolso só antes do aceite (automático) ou por mediação registrada com autor | `services/pagamentos/tests/test_inv_d15_reembolso_so_por_regra.py` |
| **[INV-ENC-D16]** | Para toda encomenda encerrada: pago = repasse + taxa + reembolso | `services/pagamentos/tests/test_inv_d16_conservacao.py` |
| **[INV-ENC-D17]** | Repasse só para conta de recebimento verificada do próprio aluno; sem ela, bloqueado, plantão avisado, valor preservado (§3.1) | `services/pagamentos/tests/test_inv_d17_conta_verificada.py` |

### Segurança (Fases 3 e 5)

| Código | O quê | Guarda |
|---|---|---|
| **[INV-ENC-S1]** | Não existe texto livre trocado entre cliente e aluno fora dos campos estruturados; todos visíveis ao plantão | `services/encomendas/tests/test_inv_s1_sem_texto_livre.py` |
| **[INV-ENC-S2]** | Primeira entrega de um aluno nunca chega ao cliente sem `entrega.revisada` aprovada por humano | `.../test_inv_s2_primeira_entrega_revisada.py` |
| **[INV-ENC-S3]** | Nenhum dado de contato do aluno em resposta ao cliente nem na porta de peças aprovadas | `.../test_inv_s3_sem_contato_do_aluno.py` |
| **[INV-ENC-S4]** | Peça só sai pela porta de peças aprovadas com autorização do cliente registrada | `.../test_inv_s4_so_com_autorizacao.py` |
| **[INV-ENC-S5]** | Encomenda de cliente novo não entra na fila sem aprovação do plantão | `.../test_inv_s5_cliente_novo_passa_pelo_plantao.py` |

Mais o herdado de toda célula nova: **[INV-P12]** (não assina sessão), guarda
`test_inv_encomendas_nao_assina_sessao.py`, plantado na gênese e provado por
mutação.

## 6. Os parâmetros (dado, não código)

As chaves da tabela `Parametro` e os valores iniciais da seção 6.12 do plano.
A semente grava exatamente estes; mudar é linha nova com motivo (§3.8).

| Chave | Valor inicial | Unidade |
|---|---|---|
| `relogio_da_oferta` | 3 | horas úteis |
| `janela_inicio` / `janela_fim` | 08:00 / 22:00 | hora local (`America/Sao_Paulo`) |
| `silencios_para_pausa` | 3 | silêncios consecutivos |
| `horas_para_virar_aberta` | 24 | horas na fila |
| `encomendas_simultaneas_por_aluno` | 1 | encomendas da fila |
| `prazo_producao.simples` / `.vestivel_veiculo` / `.personagem` | 3 / 7 / 14 | dias |
| `dias_de_revisao_no_prazo_prometido` | 1 | dia |
| `extensoes_por_encomenda` / `extensao_horas` / `extensao_pedida_ate_horas_antes` | 1 / 48 / 24 | — |
| `sla_do_revisor` | 24 | horas |
| `amostragem_de_revisao` | 5 | 1 em N, após a primeira entrega |
| `aprovacao_tacita` | 48 | horas |
| `correcoes_incluidas` / `prazo_da_correcao` | 1 / 48 | — / horas |
| `passes_nao_pronto_para_reclassificar` | 2 | na mesma encomenda |
| `passes_nao_pronto_para_aviso` / `janela_dos_passes` | 3 / 30 | passes / dias |
| `repasse_apos_aprovacao` | `proximo_dia_util` | — |
| `meta_aprovacao_cliente_novo` | 4 | horas úteis |
| `entregas_para_nivel_intermediario` / `entregas_para_nivel_avancado` | 1 / 5 | entregas aprovadas |
| `janela_sem_abandono` | 90 | dias |
| `pausa_por_segundo_abandono` | 30 | dias |

Preços, taxa e moeda **não** são parâmetro desta tabela: são a decisão
pendente 1 e 2 do plano, e vivem onde o dinheiro vive (Fase 3).

## 7. A escada

Precedentes: gênese do fórum e da gamificação (`armadilhas/076`, `088`, `089`,
`134`, `224`, `228`, `243`). Cada degrau é uma tarefa na fila com
`depende_de`; o estado de cada uma se lê **no balcão** (`python ci/fila.py
listar --ao-vivo`), nunca aqui.

| Fase | Degrau | O quê | Onde | Tarefa |
|---|---|---|---|---|
| **0** | — | Esta lei, o plano, a constituição em papel, o anexo do contrato, o mapa para IA | docs, painel | **TAR-107** |
| 0 | — | Os 20 eventos v1 em `contracts/eventos/` (PR só de `contracts/`, etiqueta `contrato`) | contracts | **TAR-108** |
| 0 | portão | **O mantenedor aprovou a lei** em 03/09/2026 (registro `20260904-006`) | mantenedor | feito |
| **1** | — | **Piloto de papel**: 5 a 10 encomendas reais da escola, fila mantida à mão pelo professor, tudo em planilha (seção 11 do plano). **Sem código.** Pode correr em paralelo com a Fase 2 se ele decidir assim (decisão 13) | escola | — |
| **2** | 2.1 | Gênese (esqueleto, saúde, os três guardas, `celulas.yml`, manifesto, `rollback.yml`); ~22 arquivos, etiqueta `arquitetural` | encomendas, ci, .github | TAR-109 |
| 2 | 2.2 | Tabelas: perfil, encomenda, oferta, **parâmetros com histórico**, máquinas de estado | encomendas | nasce quando a gênese pousar |
| 2 | 2.3 | Motor de oferta + **J1–J7** como guarda e no `INVARIANTES.md` | encomendas, INVARIANTES.md | nasce quando a gênese pousar |
| 2 | 2.4 | Relógios, horas úteis puras, tique por minuto + **J8–J10** | encomendas, INVARIANTES.md | nasce quando a gênese pousar |
| 2 | 2.5 | Pausa automática, interruptor, chamada aberta, passar com motivo, reclassificação | encomendas | nasce quando a gênese pousar |
| 2 | 2.6 | **Simulador de 100 alunos** (portão da Fase 2) | encomendas | nasce quando a gênese pousar |
| 2 | 2.7 | Porta de máquina (parâmetros, fila de uma pessoa, peças aprovadas, as duas internas em 501) + sessão repassada + `export_openapi` | encomendas | nasce quando a gênese pousar |
| 2 | 2.8 | **Congelar o contrato** a partir do export (PR só de `contracts/` + manifesto) | contracts, ci | nasce quando a gênese pousar |
| 2 | 2.9 | `infra/provisionar-encomendas.sh` + env exemplo (PR sozinho) | infra | nasce quando a gênese pousar |
| 2 | **H** | **Passo do mantenedor na VPS**: banco, papel e env, em UM bloco de colar, janela rotulada | mantenedor | — |
| 2 | 2.10 | Compose + Traefik `/encomendas` + inventário de rotas (PR sozinho); a célula responde `/healthz` pela internet | infra, ci | nasce quando a gênese pousar |
| **3** | — | Cliente e dinheiro: cardápio, briefing, cobrança → webhook → `na_fila`, extensão da `pagamentos` (D13–D17), rastreio, aprovar, cancelar. **Espera o sinal "o site vai vender"** | encomendas, pagamentos | tarefas criadas quando o portão abrir |
| **4** | — | A tela do aluno (três estados, oportunidade, passar com motivo, espera estimada), assuntos `encomendas.*` no sininho | encomendas, contracts | idem |
| **5** | — | Entrega, auditoria automática (worker com Blender), revisão com SLA, correção, extensão, abandono, aprovação tácita (S2) | encomendas, auditoria | idem |
| **6** | — | Peças aprovadas para o Estúdio, pedido direto, Marcos #3 e #4 por evento, cerimônia | encomendas, gamificacao, pages | idem |
| **7** | — | Plantão: lista única por urgência, reclassificação, cliente novo, mediação, repasses bloqueados | encomendas | idem |
| **8** | — | Lançamento assistido: webhook real, rollback cronometrado, turma piloto | infra | idem |
| **9** | — | Métricas (seção 13), calibração, abertura | métricas | idem |

**Por que os degraus 2.2 a 2.10 ainda não estão na fila:** `toca: encomendas`
só é aceito depois de a pasta existir (`ci/tests/test_conferencia_do_toca.py`; a
dispensa `cria` é só da gênese, e dizer que seis tarefas "inauguram" a célula
seria mentira no registro). O despacho da TAR-109 manda criá-las ao pousar,
encadeadas por `depende_de`. Medido em 03/09/2026: nove tarefas criadas antes
da gênese reprovaram o testador (`armadilhas/304`).

**Regras de trânsito:** o compose entra em PR próprio (`armadilhas/134`);
entre 2.1 e 2.10 o `deploy-celula` fica vermelho e **isso é esperado**
(`armadilhas/088`); nunca duas sessões no motor de oferta ao mesmo tempo;
Fases 3, 4 e 5 podem correr em três bancadas depois da 2, cada PR de
`pagamentos` separado; 6 e 7 dependem da 5.

## 8. Decisões do mantenedor: o que já está respondido, o que vai na pergunta de agora, o que fica para a fase

As 11 da seção 15 do plano, mais três que a casa descobriu ao ler o plano
contra o `origin/main`. Cada uma diz **o que bloqueia** e a recomendação.

**Respondidas por decisão anterior dele (não se reabrem por preferência de agente):**

- **5. Idade mínima e responsável** → 18+, sem responsável (§3.1).
- **6. Canal de notificação** → site + sininho + aviso no celular (§3.7).
- **10. Nomes** → "Encomendas" no menu, "Fila do Primeiro Dólar" na
  funcionalidade (§3.9). Muda em uma linha se ele preferir.

**Respondidas na pergunta estruturada da Fase 0 (03/09/2026, registro `20260904-006`):**

- **A. Esta lei vale?** Aprovar promove o plano; recusar ou emendar volta ao
  papel. Recomendação: aprovar, com as emendas do §3. **Resposta: aprovada.**
- **13. A Fase 2 (motor, só código e testes) começa agora, em paralelo com o
  piloto de papel, ou espera o piloto terminar?** O plano manda esperar
  ("cada regra errada descoberta aqui custa uma linha na planilha; depois,
  custa um PR"). Nesta casa um PR custa minutos, os invariantes são testes
  que se ajustam, e o mantenedor já disse que prazo não é freio.
  Recomendação: **em paralelo**; os parâmetros que o piloto corrigir viram
  linha nova na tabela (§3.8), sem PR. **Resposta: em paralelo.**
- **14. Quem dá o título enquanto a Banca não existe?** Recomendação: o
  professor, na tela de plantão (§3.6). **Resposta: o professor.**
- **2 (parcial). Reafirmar que a escola é 18+ para este produto**, já que o
  plano inteiro foi escrito assumindo menores. **Resposta: 18+.**

**Ficam para a fase que as precisa (registradas no livro como pendência, com
a fase escrita):**

- **1. Preços v0 e moeda** (exibir em US$ e cobrar em R$, ou só R$) →
  Fase 3.
- **2. Taxa por nível e destino** (recomendação do plano: nível 1 pequena e
  integral ao revisor) → Fase 3.
- **3. Mecanismo de custódia e repasse** (split do Mercado Pago ou receber
  e repassar via Pix), com o parecer → Fase 3.
- **4. Parecer jurídico** (custódia de valores de terceiros, LGPD, cessão
  de direitos, termos) → portão da Fase 3. Quem escreve não é advogado.
- **7. Compromisso da escola como cliente no lançamento** (quantas por
  semana, por quanto tempo) → Fase 1 (o piloto de papel precisa disso já).
- **8. Quem revisa até existir Nível 3, e quanto vale a revisão** →
  Fase 5; até lá, o professor.
- **9. Amostragem de revisão após a primeira entrega** (1 em 5?) → Fase 5;
  é parâmetro (§6), então muda sem PR.
- **11. Marco #4**: primeira aprovação de cliente que não seja a escola
  (recomendação do plano) ou primeiro pedido direto → Fase 6.
- **12. Portfólio**: automático como o plano, ou o Estúdio opt-in como a
  casa decidiu (recomendação) → Fase 6 (§3.5).

## 9. Critério de morte

**Pare e reabra a decisão com o mantenedor** se qualquer uma destas acontecer:

1. qualquer item do §2 (a lista do "fora") começar a ser desenhado: lista de
   freelancers, propostas, lances, ranking, notas públicas, chat livre,
   matchmaking ou classificação por IA;
2. nascer uma **segunda regra de ordem** na fila (peso, prioridade paga,
   "destaque"): a fila tem uma regra, e ela está no §6.2 do plano;
3. cobrança, retenção, repasse ou reembolso passarem a morar **nesta**
   célula (o dinheiro é da `pagamentos`);
4. um segundo portfólio nascer aqui (o Estúdio é a casa);
5. um parâmetro da seção 6.12 voltar a viver em código;
6. qualquer invariante J, D ou S precisar de exceção;
7. o plantão passar a operar por SQL ou por chat de emergência em vez da
   tela (é o portão da Fase 7, e é o sinal de que a tela falhou).

## 10. Estado

| O quê | Estado | Onde se confere |
|---|---|---|
| O plano v0.1 | no repositório, sem edição | `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` |
| Esta lei | **aprovada em 03/09/2026** | registro `20260904-006` |
| A constituição da célula | promovida na gênese (03/09/2026) | `constituicoes/AGENTS.encomendas.md` |
| O contrato v1 | anexo escrito; congela no degrau 2.8 | `CONTRATO-encomendas-v1-rascunho.md` |
| Os 20 eventos | TAR-108 | `contracts/eventos/encomenda.*`, `oferta.*`, `entrega.*`, `aluno.*`, `portfolio.*`, `pedido-direto.*` |
| A escada | TAR-107 a TAR-109 na fila; os degraus 2.2 a 2.10 nascem quando a gênese pousar | `python ci/fila.py listar --ao-vivo` |
