# INVARIANTES — Jurisprudência Pré-Paga da Plataforma

Formato: **o quê / por quê / teste-guarda / célula dona**. Os invariantes de dinheiro
nascem ANTES da primeira feature, com guarda no mesmo PR — a lei existe antes da
primeira oportunidade de violá-la.

**Regras de trabalho:**
1. Código que toca um invariante referencia o código dele em comentário (ex.: `[INV-P3]`).
2. Teste-guarda é intocável: nunca deletar, desativar ou afrouxar para passar.
3. Evidência falsificável: correção em invariante apresenta a saída crua vermelho→verde.
4. Invariante sem guarda no mesmo PR só entra na seção final (dívida), com dono e prazo.

---

### [INV-P1] Snapshot do Pedido é Create-Only
- **O quê:** `Order.items`, `Order.total_cents` e `Order.customer` são congelados na
  criação. Nenhum caminho de código os atualiza depois — nem UPSERT, nem reprocesso,
  nem admin. Correção de pedido = novo pedido + cancelamento do antigo.
- **Por quê:** snapshot mutável é recibo que mente — um UPSERT descuidado zera campos,
  um reajuste de preço reescreve o passado do cliente, e o suporte nunca mais sabe o
  que a pessoa realmente comprou e por quanto.
- **Teste-Guarda:** `services/checkout/tests/test_inv_p1_snapshot.py` — cria pedido,
  tenta alterar itens/total por todos os caminhos públicos, assert de imutabilidade.
- **Célula dona:** checkout

### [INV-P2] Dinheiro é Calculado no Servidor
- **O quê:** o cliente envia intenção (`bump_ids`, `method`, dados); o servidor
  recalcula itens e total a partir do catálogo. Qualquer valor monetário vindo do
  navegador é ignorado. Padrão client-sends-intent / server-validates.
- **Por quê:** total computado no cliente é superfície de manipulação de preço —
  basta editar o payload no DevTools para comprar por um centavo.
- **Teste-Guarda:** `services/checkout/tests/test_inv_p2_server_money.py` — payload
  adulterado com `total_cents` falso e `price_cents` falsos ⇒ snapshot sai com os
  valores do catálogo.
- **Célula dona:** checkout

### [INV-P3] Webhook Idempotente por mp_payment_id
- **O quê:** o mesmo webhook entregue N vezes produz UMA transição de estado e UM
  evento na outbox. Chave de deduplicação: `mp_payment_id` + status alvo.
- **Por quê:** o Mercado Pago reentrega webhooks por design (retry, timeout,
  reprocessamento). Sem deduplicação, cada reentrega duplicaria matrícula, e-mail
  e linha de ledger.
- **Teste-Guarda:** `services/pagamentos/tests/test_inv_p3_webhook_idempotente.py` —
  POST do mesmo webhook assinado 3×; assert: 1 transição, 1 linha de outbox.
- **Célula dona:** pagamentos

### [INV-P4] Criação de Intent Idempotente por X-Idempotency-Key
- **O quê:** `POST /intents` com a mesma chave devolve a MESMA intent (200), sem nova
  tentativa de cobrança. Toda escrita ao MP também leva `X-Idempotency-Key` própria.
- **Por quê:** refresh na página de pagamento, retry de rede e double-click são
  comportamento normal de usuário — e nenhum deles pode virar dupla cobrança.
- **Teste-Guarda:** `services/pagamentos/tests/test_inv_p4_intent_idempotente.py` —
  2× POST mesma chave ⇒ mesma intent, 1 chamada ao provider (mock).
- **Célula dona:** pagamentos

### [INV-P5] Matrícula sob Lock, Idempotente por order_id
- **O quê:** o consumer de `pagamento.aprovado` matricula dentro de
  `transaction.atomic()` + `select_for_update()`, com unicidade por `order_id`.
  Evento duplicado ou concorrente ⇒ UMA matrícula.
- **Por quê:** eventos chegam duplicados e concorrentes por natureza (é a garantia
  at-least-once do transporte). Duplicar matrícula duplica acessos, e-mails de
  boas-vindas e tickets de suporte.
- **Teste-Guarda:** `services/alunos/tests/test_inv_p5_matricula_lock.py` — dois
  consumers processando o mesmo evento em threads ⇒ 1 matrícula no banco.
- **Célula dona:** alunos

### [INV-P6] Outbox Transacional
- **O quê:** todo evento emitido é gravado na tabela outbox NA MESMA transação da
  mudança de estado que o justifica. O relay (Huey) publica no Redis Streams depois.
  Estado sem evento e evento sem estado são ambos impossíveis.
- **Por quê:** "pagou mas não matriculou" e "matriculou sem pagar" são as duas
  falhas que destroem confiança num funil. O outbox elimina a janela entre commit e
  publicação.
- **Teste-Guarda:** `services/pagamentos/tests/test_inv_p6_outbox.py` — aprovação ⇒
  na mesma transação existe linha de outbox; falha simulada do relay ⇒ evento
  permanece pendente e é republicado, nunca perdido.
- **Célula dona:** pagamentos (padrão replicado em quiz e checkout para seus eventos)

### [INV-P7] Status na UI Deriva do Servidor
- **O quê:** as páginas de pagamento fazem polling de `GET /pedidos/{id}` (ou intent).
  Nenhuma máquina de estado no navegador decide "pago"; nenhum status é inferido do
  passo do wizard ou de índice de array.
- **Por quê:** status inferido de estado local quebra com refresh, aba duplicada e
  o retorno do app do banco após o Pix. Dados do servidor sobrevivem a tudo isso.
- **Teste-Guarda:** `services/checkout/tests/test_inv_p7_status_servidor.py` +
  revisão de `pix.js`/`cartao.js`: os arquivos não contêm transição local para "pago".
- **Célula dona:** checkout

### [INV-P8] Segredo de Produção Só Existe em Produção
- **O quê:** `MP_ACCESS_TOKEN` de produção (`APP_USR-…`) existe em UM lugar no
  universo: `/opt/plataforma/env/pagamentos.env` na VPS, escrito manualmente pelo
  mantenedor. Dev, CI, worktrees e agentes conhecem apenas `TEST-…`.
- **Por quê:** credencial cara alcançável de ambiente de teste queima dinheiro real
  mais cedo ou mais tarde — um loop de testes com a chave errada cobra de verdade.
  Aqui isso não é proibido: é inexistente.
- **Teste-Guarda:** `ci/guarda-de-segredos.sh` (roda em todo PR — reprova `APP_USR-`
  e chaves privadas no repo) + red-team golpe nº 10.
- **Célula dona:** plataforma (CI)

### [INV-P9] Pix e Cartão Mutuamente Invisíveis
- **O quê:** `methods/pix` e `methods/card` não se importam (independência), e nenhum
  importa `providers/*` diretamente (só via `core.gateway`). No front, `pix.js` e
  `cartao.js` não compartilham estado nem funções além de `api.js`.
- **Por quê:** mudança num método de pagamento não pode alcançar o outro — nem por
  import, nem por estado compartilhado. Enquanto um método estiver em manutenção,
  o outro continua vendendo. A arquitetura diz "não" em check time.
- **Teste-Guarda:** `services/pagamentos/.importlinter` (`lint-imports` no `make ci`)
  + cross-smoke (`ci/cross-smoke.sh`): tocou um método, o smoke do outro roda.
- **Célula dona:** pagamentos

### [INV-P10] Webhook Sem Assinatura Válida ⇒ 403 e Zero Efeito
- **O quê:** todo webhook valida `x-signature` (HMAC com `MP_WEBHOOK_SECRET`) ANTES de
  qualquer leitura de payload com efeito. Inválido ⇒ 403, nada gravado, nada emitido.
- **Por quê:** um webhook forjado que aprovasse pedidos seria matrícula grátis em
  escala. Autenticação de origem vem antes de qualquer efeito colateral.
- **Teste-Guarda:** `services/pagamentos/tests/test_inv_p10_assinatura.py` — payload
  válido sem assinatura e com assinatura errada ⇒ 403 + banco intacto + outbox vazia.
- **Célula dona:** pagamentos

### [INV-P11] Fronteira de Site (multissítio)
- **O quê:** o site é resolvido do Host UMA vez por requisição (middleware
  CONV-SITE) e toda consulta pública é filtrada por `site_id`. Host não cadastrado
  ⇒ 404 — nunca "cai" num site padrão. Oferta, sessão, pedido, lead e matrícula de
  um site jamais aparecem em outro.
- **Por quê:** com dezenas de marcas em teste no mesmo deploy, o vazamento clássico
  de multi-tenant (preço/oferta de um site aparecendo em outro, ou host
  desconhecido servindo o site nº 1) contamina experimentos e quebra confiança —
  e é silencioso até acontecer em público.
- **Teste-Guarda:** `services/catalogo/tests/test_inv_p11_fronteira_site.py`
  (dois sites com o mesmo slug e preços distintos ⇒ cada host vê só o seu; host
  aleatório ⇒ 404) + `services/checkout/tests/test_inv_p11_fronteira_site.py`
  (sessão criada no site A não fecha pedido com oferta do site B).
- **Célula dona:** catalogo + checkout (padrão replicado em quiz, leads e alunos)

### [INV-P12] Um Único Assinante do Cookie de Sessão do Site
- **O quê:** o cookie `meshcraft_sessao` (`Path=/`, alcance de site inteiro) é
  emitido e assinado por **uma só célula: `identidade`**. Nenhuma outra célula
  escreve `request.session`, instala `SessionMiddleware`, declara
  `SESSION_ENGINE` ou assina cookie com esse nome — as demais **perguntam**
  quem é a pessoa por HTTP (`getSession`/`getSessionFull`).
- **Por quê:** duas células assinando o MESMO cookie com chaves diferentes
  produzem um cabo-de-guerra invisível — entrar por uma desloga da outra, e
  vice-versa — **sem erro em lugar nenhum, sem log, sem alarme**. Ninguém
  reporta "fui deslogado": as pessoas reentram e seguem, e a plataforma perde
  sessão o dia inteiro sem nada acusar. A `DECISAO-celula-de-identidade.md` §5
  registra o episódio em que isso quase entrou em produção, e a §6.4 o proíbe
  por escrito; este invariante é o mecanismo que faltava à proibição.
- **Teste-Guarda:**
  `services/admin/tests/test_inv_admin_nao_assina_sessao.py`,
  `services/forum/tests/test_inv_forum_nao_assina_sessao.py`,
  `services/gamificacao/tests/test_inv_gamificacao_nao_assina_sessao.py` e
  `services/encomendas/tests/test_inv_encomendas_nao_assina_sessao.py`,
  `services/metricas/tests/test_inv_metricas_nao_assina_sessao.py`,
  `services/cursos/tests/test_inv_cursos_nao_assina_sessao.py` e
  `services/pages/tests/test_inv_pages_nao_assina_sessao.py` —
  medem a
  CONFIGURAÇÃO da célula (sem SessionMiddleware, sem django.contrib.sessions
  e sem SESSION_ENGINE no settings dela), porque sem essas três
  `request.session` nem existe. Provados por mutação na gênese de cada uma:
  instalar o SessionMiddleware deixa o guarda vermelho. O do `forum`
  (28/08/2026) acrescenta um quarto caso, o do cookie de CSRF com nome
  próprio — não é sessão, mas é o mesmo problema de vizinhança: quatro células
  no mesmo host gravando `csrftoken` é uma invalidando o formulário da outra.
- **Célula dona:** identidade (única emissora) — guarda plantado em `admin`,
  a primeira célula a nascer **depois** da regra, e replicado em `forum`, em
  `gamificacao`, em `encomendas` (03/09/2026; ali a tentação é a cerimônia
  do primeiro dólar, tela cheia uma vez só — o estado mora no modelo, como
  as celebrações da gamificação) e em `cursos` (04/09/2026; ali são duas, a
  cerimônia do Boss e "o aluno já leu o laudo?", e o estado mora no
  `Progresso`) e em `pages` (05/09/2026; ali a tentação é a Prancheta do
  portfólio, que guarda o que o aluno já marcou na lista de conferência — e o
  critério AC-06 do `CS-PAGES-0001` exige justamente que essa marcação
  atravesse aparelhos, coisa que sessão não faz, então o caminho curto
  reprovaria o próprio critério antes de deslogar a plataforma);
  toda célula futura que consuma sessão herda a mesma obrigação. **No `forum`
  a obrigação pesa mais que o normal:** foi um requisito de login que criou a
  célula (`DECISAO-forum-da-escola.md` §2 — *"logado uma única vez, o site
  todo"*), e foi ele que eliminou os motores de fórum de prateleira. Uma
  segunda assinatura de cookie ali quebraria exatamente a coisa que justificou
  construir em vez de instalar. **Na `gamificacao` (30/08/2026) a tentação tem
  nome próprio: a celebração visceral.** O desenho manda a comemoração de nível
  e de marco aparecer em tela cheia, uma vez só, no segundo da validação
  (`DECISAO-gamificacao.md` §5) — e toda tela assim precisa lembrar "já viu?".
  O caminho de menor esforço para essa lembrança é `request.session[...]`, que
  ali deslogaria a plataforma inteira; por isso o estado mora no MODELO
  (`celebracoes_pendentes`), e não na sessão.

### [INV-SUG09] Quem Foi Reembolsado Não Entra, e a Porta Diz Por Quê
- **O quê:** a Caixa recusa quem a `alunos` classifica como `reembolsado`, e a
  recusa vem com a **tela própria do reembolso** — nunca a tela genérica de
  desconhecido, nunca a do ex-aluno, e **sem** o formulário de *Pedir para
  voltar* que o ex-aluno tem desde 29/08.
- **Por quê:** decisão do mantenedor em 31/08/2026
  (`docs/decisoes/DECISAO-reembolso-tira-o-acesso.md`), revertendo a dele
  própria de 24/08 (*"quem já foi aluno mantém a voz"*) ao encontrar o texto
  antigo publicado no site. **A regra já foi decidida duas vezes, em sentidos
  opostos**, e é isso que a torna cara de deixar sem guarda: um agente futuro
  que só conheça a versão de 24/08 vai "consertar" de boa-fé.
  O *"diz por quê"* é metade do invariante, e não enfeite: sem a linha no mapa
  de categorias a pessoa já seria barrada (a lista é de PERMISSÃO), mas leria
  *"não conseguimos conferir sua entrada agora"* — o sistema culpando a si
  mesmo por uma situação que conhece perfeitamente.
- **Teste-Guarda:** `services/sugestoes/tests/test_inv_reembolso_nao_entra.py` —
  a categoria está no mapa e não dá acesso; a pessoa recebe 403; o corpo nomeia
  o reembolso e **não** é a tela do ex-aluno; nenhum formulário é oferecido; a
  identidade não é cunhada para quem não entra; e o aluno continua entrando (o
  contraste, sem o qual tudo isso ficaria verde numa porta que barra todo mundo).
- **Célula dona:** sugestoes

### [INV-SUG10] Corredor do ChangeSpec (nada entra em desenvolvimento sem ele)
- **O quê:** `Sugestao.status` só sai de `PLANEJADO` para `EM_DESENVOLVIMENTO` se
  existir um ChangeSpec **aprovado** registrado referenciando aquela sugestão
  (`docs/caixa-de-sugestoes/FORMATO-CHANGESPEC.md` §5 e a última linha da §8 da
  `ESPECIFICACAO-CELULA.md`). Quem registra é só quem está em
  `SUGESTOES_APROVADORES` — lista **fail-closed**: ausente ou vazia ⇒ ninguém
  aprova ⇒ nada entra em desenvolvimento. Estar em `SUGESTOES_STAFF_EMAILS` não
  basta: moderar e autorizar desenvolvimento são dois papéis. O registro é
  append-only, como o histórico de status.
- **Por quê:** o corredor existe para que uma ideia aprovada **nunca** vire um
  prompt aberto do tipo "implemente isso" para um agente. Sem ele, o passo em que
  se decide escopo, células proibidas e critérios de aceitação é justamente o que
  desaparece sob pressa — e o agente escreve o próprio mandato. Fail-closed no
  aprovador pelo mesmo motivo: "não sei quem pode aprovar" não pode virar "então
  pode qualquer um".
- **Teste-Guarda:**
  `services/sugestoes/tests/test_inv_changespec_trava_o_desenvolvimento.py` —
  a trava reprovando nos três degraus (ponto de estrangulamento, `Sugestao.save()`
  e o trigger `sugestoes_exige_changespec` do Postgres, que pega `QuerySet.update()`
  e SQL cru), passando com ChangeSpec registrado, sem quebrar as outras transições,
  e o registro recusando edição e remoção. O portão do aprovador (lista ausente,
  lista vazia, staff sem mandato) está em `services/sugestoes/tests/test_changespecs.py`.
- **Célula dona:** sugestoes

### [INV-P13] A Porta da Área Administrativa é Fail-CLOSED
- **O quê:** a célula `admin` tem UM ponto de autorização (o middleware da
  porta) e ele nega por padrão. Não conseguir perguntar quem é a pessoa ⇒
  **503, nunca abre e nunca redireciona**; sessão válida cujo e-mail não está
  em `ADMIN_EMAILS` ⇒ **404**; sem sessão ⇒ 302 para o login. A resposta da
  `identidade` — inclusive o campo `papel` — nunca autoriza nada: quem decide
  é a lista desta célula, na hora.
- **Por quê:** é a segunda metade de *reconhecer não é autorizar*
  (`DECISAO-onde-mora-a-sessao.md` §4), e a que faltava ter mecanismo.
  Reconhecimento falha ABERTO porque não saber o nome de alguém não pode
  derrubar a vitrine; autorização falha FECHADO porque não saber QUEM é
  alguém não pode virar permissão. Os três casos se parecem de dentro (nenhum
  renderiza a página) e são completamente diferentes de fora: trocar o 503 por
  302 manda o mantenedor a um login que também caiu; trocar o 404 por 200 abre
  a operação da plataforma para qualquer conta Google.
- **Teste-Guarda:**
  `services/admin/tests/test_inv_porta_fail_closed.py` — uma linha da tabela,
  um teste, com a rede dublada por `respx`. Provado por mutação na entrega da
  porta: redirecionar em vez de 503 ⇒ 5 vermelhos; deixar passar quem não está
  na lista ⇒ 3; `frame-ancestors 'none'` ⇒ 1; isentar um caminho a mais ⇒ 15.
- **Célula dona:** admin

### [INV-P14] `/mapa-ia/` é a Única Fresta Pública na Porta, e Só Ela
- **O quê:** além de `/healthz` (rota de máquina), a célula `admin` responde
  **sem sessão** a exatamente 9 caminhos — `/mapa-ia/` e os 8 documentos de
  `painel/ia/*.md` — servidos como `text/plain`, nunca HTML. `CAMINHOS_ISENTOS`
  (`apps/core/porta.py`) lista cada um por igualdade EXATA, não por prefixo:
  qualquer outro caminho sob `/mapa-ia/*` continua atrás da porta, com a
  mesma resposta de sempre (302 sem sessão, 404 para quem não está
  autorizado). A view (`apps/core/mapa_ia.py`) tem uma segunda checagem
  independente — extensão `.md` e a pasta resolvida continuando ancestral do
  arquivo — que protegeria mesmo se a primeira um dia virasse prefixo por
  engano.
- **Por quê:** o mantenedor pediu (28/08/2026) um link público do mapa
  técnico do projeto para poder mandar a IAs externas sem exigir login.
  `painel/ia/` já foi escrito para não conter segredo nenhum (varredura
  dedicada antes de existir); tornar exatamente esses arquivos públicos, e só
  eles, atende ao pedido sem abrir mão do resto do invariante [INV-P13] — a
  porta continua fail-closed para tudo que não está nomeado aqui, um a um.
- **Teste-Guarda:**
  `services/admin/tests/test_inv_porta_fail_closed.py` (o conjunto exato de
  `CAMINHOS_ISENTOS`, teste `test_os_caminhos_isentos_sao_exatamente_estes_e_so_estes`)
  e `services/admin/tests/test_mapa_ia_publico.py` (cada arquivo responde 200
  sem cookie e é byte-a-byte o do repositório; qualquer caminho não listado
  fica atrás da porta como antes; a view recusa sozinha, chamada direto, mesmo
  sem a porta — extensão errada e travessia de diretório, provado com um
  arquivo real de fora da pasta).
- **Célula dona:** admin

### [INV-P15] Falha do Provedor ⇒ 502 no Contrato, Nunca 2xx
- **O quê:** quando o Mercado Pago não responde, responde erro, ou responde 2xx com
  um corpo que **não descreve** a cobrança pedida (`id` ausente ou vazio, Pix sem
  `qr_code`, cartão sem `status`), as quatro operações que atravessam o provedor —
  `createIntent`, `confirmCard`, `webhookMpPix`, `webhookMpCard` — respondem **502**
  (`FalhaDoProvedor`, `contracts/pagamentos.openapi.yaml`) e nenhuma intent nasce
  incompleta. Nunca 2xx; nunca 422 (o payload do checkout estava correto — quem
  falhou foi o provedor); e nunca um `qr_code` vazio numa releitura da mesma intent.
  A ação prescrita ao consumidor viaja no próprio contrato: repetir com a **MESMA**
  `X-Idempotency-Key`, jamais uma chave nova. `getIntent` fica de fora por ler só o
  banco.
- **Por quê:** foi o bug mais caro da Fase D — o cliente traduzia um corpo de erro em
  `201 Created` com QR vazio (`str(resposta.get("id", ""))` → string vazia → seguiu
  adiante como sucesso), e o comprador via uma tela de pagamento que não pagava
  (`RETROSPECTIVA-FASE-D` §4: em borda externa, 2xx não é sucesso). Corrigir o código
  sem escrever a regra deixou uma meia-verdade de uma semana: até 28/08/2026 o
  sistema já respondia certo e **nenhum documento** dizia ao checkout que aquele
  status existia nem o que fazer com ele — e a saída intuitiva, chave nova a cada
  tentativa, é exatamente a dupla cobrança que [INV-P4] existe para impedir.
  A trava que mantém os dois lados batendo é o freeze de contrato
  (ci/contract_freeze.py): quem tirar o 502 do código deixa o check
  contrato/pagamentos VERMELHO — foi essa a evidência vermelho→verde do par de
  PRs 417/420.
- **Teste-Guarda:** `services/pagamentos/tests/test_transporte_mp_fail_closed.py` —
  o mock desce até o HTTP (respx), então o transporte roda de verdade em vez de ser
  substituído por um MagicMock, que é o furo da armadilha 061: status de erro,
  timeout, corpo não JSON, 200 sem id, Pix 200 sem qr_code e cartão 200 sem status —
  nenhum vira intent criada; e o replay com o provedor ainda quebrado não devolve QR
  vazio.
- **Célula dona:** pagamentos

### [INV-SUG11] Identidade Cunhada Guarda o Id da Plataforma
- **O quê:** toda `Identidade` cunhada pela célula `sugestoes` depois da migration
  `0006` guarda, ao lado do id opaco que ela mesma cunha, o **id da identidade da
  plataforma** que a resposta do contrato entregou (`SessionFull.id` de
  `getSessionFull`, `contracts/identidade.openapi.yaml`). A linha que já existia
  sem ele o ganha **na reentrada** da pessoa; uma linha que já tem um id **não é
  sobrescrita** por outro. Nada disto autoriza nem recusa ninguém: id ausente,
  nulo ou colidindo com outra linha local não fecha a porta — quem autoriza
  continua sendo e-mail + (staff | matrícula). E o casamento por **e-mail**
  continua sendo a chave de recuperação: o id novo é dado a mais, não substituto.
- **Por quê:** hoje não existe um identificador de pessoa que atravesse a
  plataforma — `identidade` e `sugestoes` cunham dois ids opacos diferentes para a
  mesma pessoa, e o único elo entre eles é o e-mail, que por decisão do mantenedor
  (`DECISAO-EVO-01-identidade.md` §3) vive numa linha só e não circula. Sem este
  invariante, todo evento que a Caixa publica carrega um id que **não significa
  nada fora dela**, e uma caixa central de notificações receberia o fato sem
  conseguir endereçar ninguém (`docs/notificacoes/PLANO-MESTRE.md` §2). O elo que
  faltava já passava na mão a cada entrada e era descartado na porta; é a Fase 1
  do plano, e sem ela nenhuma das outras funciona.
- **Teste-Guarda:**
  `services/sugestoes/tests/test_inv_id_da_plataforma.py` — cunhagem, reentrada,
  não-sobrescrita, a porta abrindo com id ausente/nulo/em branco, a colisão de
  unicidade não derrubando nem a cunhagem nem a reentrada, e a varredura de AST
  que mantém **um único** caminho de cunhagem no código de produção (um segundo
  nasceria sem o campo). A forma da coluna (`null=True, unique=True` +
  `CheckConstraint` contra `''`) tem guarda próprio no mesmo arquivo: é ela que
  decide se a migration sobe sobre uma tabela cheia. O antídoto operacional que a
  §9 do plano exige é `manage.py relatorio_id_da_plataforma`, com guarda em
  `services/sugestoes/tests/test_relatorio_id_da_plataforma.py`.
- **Célula dona:** sugestoes (obrigação herdada por qualquer célula que cunhe
  identidade local a partir da resposta da `identidade`)

### [INV-SUG12] A Carta Endereça pelo Id da Plataforma, ou Não Sai
- **O quê:** todo evento `notificacao.devida` que a `sugestoes` publica endereça
  pelo **id da plataforma** (`destinatario_id`), nunca pelo id local. Interessado
  que ainda não tem esse id **não recebe carta** — e continua recebendo o `Aviso`
  local, sem que a moderação seja interrompida. Já **quem modera** sem id de
  plataforma interrompe tudo: nada é escrito, a transação inteira volta atrás e a
  pessoa recebe uma tela em português dizendo para entrar de novo.
- **Por quê:** os dois ids são strings opacas parecidas e o contrato aceita as
  duas formas, então trocar um pelo outro **não faz barulho nenhum** — a falha só
  apareceria na Fase 3, com a caixa central cheia de cartas para ninguém. A
  assimetria entre as duas ausências é decisão de desenho, não descuido: um
  votante pode ter entrado pela última vez meses atrás, e travar a moderação de
  uma ideia popular por causa dele seria absurdo — a carta é aditiva. Quem modera,
  ao contrário, está autenticado NESTA requisição; chegar sem id significa que
  algo quebrou agora, e o contrato `sugestao.status-alterado.v2` exige `ator_id`.
  Como o INV-P6 não admite estado sem evento, recusar os dois juntos é a única
  saída correta. Lei: `docs/decisoes/DECISAO-fase-2-do-sininho.md` (Rito de
  Contrato de 26/08/2026, com o mantenedor presente).
- **Teste-Guarda:**
  `services/sugestoes/tests/test_inv_carta_endereca_pelo_id_da_plataforma.py` — o
  id da carta é o da plataforma e é DIFERENTE do local; quem não tem id é pulado
  e ainda assim avisado; o ator sem id reverte tudo (status intacto, zero eventos,
  zero avisos, 409 com instrução em português); a carta aponta para o fato que a
  gerou; e nada de e-mail, título ou texto do aluno viaja nela. O custo do leque
  não crescer com a plateia tem guarda próprio, provado por sabotagem:
  `services/sugestoes/tests/test_volume_das_cartas.py` (com `create()` por pessoa,
  10 consultas para 5 destinatários viram 46 para 41).
- **Célula dona:** sugestoes

### [INV-SUG13] A Caixa Conta, Não Guarda e Não Escreve pelo Caminho de Leitura

- **O quê:** a superfície de gestão da Caixa **não tem estado próprio**, e ler por
  ela **não escreve nada**. Tudo que ela responde é derivado do que a célula já
  registrou — `Sugestao.status`, a existência (ou não) de `AvaliacaoInterna`, a
  existência (ou não) de `ChangeSpecAprovado`, e as datas de `HistoricoStatus`.
  Não existe coluna de "pendente", "visto" ou "resolvido": *esperando assinatura*
  **é** `PLANEJADO` sem ChangeSpec registrado, e a ideia sai dessa condição no
  instante em que o corredor passa a existir, sem ninguém marcar nada.
  Duas metades, e a segunda é a que costuma escapar: o número de pessoas que a
  resposta carrega atrás de cada ideia (`gestao.plateia_de`) é **exatamente** o
  conjunto que receberá o aviso quando ela andar (`avisos.interessados_em`) —
  autor, quem comentou e quem votou, cada pessoa contada uma vez.
- **Por quê:** uma superfície de acompanhamento que mantém lista própria é a
  doença que a reforma dos painéis de 26/08/2026 curou no livro do dono, e ela
  volta pela porta de qualquer código novo que ache mais simples gravar um
  sinalizador do que recalcular. Uma coluna `pendente=True` pareceria mais barata
  no primeiro dia e seria a primeira coisa a divergir da realidade no segundo — e
  divergir em silêncio, porque ninguém confere um marcador contra o fato que ele
  deveria refletir. As duas implementações da plateia existem separadas por custo
  (duas consultas para a lista inteira, contra duas *por sugestão*, que seria N+1
  numa tela de lista); sem um guarda que as case, elas divergem no primeiro
  ajuste que só uma delas receber — e a gestão passaria a prometer uma audiência
  que o sininho não entrega.
- **Onde isso vive desde 28/08/2026:** as TELAS mudaram de casa para
  `/admin/caixa/` (`docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md`), e
  o agrupamento — colunas, baldes, o que é pendência — foi com elas. **O
  invariante não foi junto**: ele é sobre o DADO, e o dado ficou. Quem lê agora é
  a superfície de máquina (`apps/core/api_gestao.py`), e é dela que se exige não
  escrever.
- **Teste-Guarda:**
  `services/sugestoes/tests/test_inv_a_mesa_nao_inventa_espera.py` — a igualdade
  entre as duas contas de plateia (com sobreposição de papéis: quem vota **e**
  comenta, e o autor votando na própria ideia; sem a sobreposição as duas
  passariam erradas), o autor contando como uma pessoa em ideia sem voto nenhum,
  e o retrato de oito contagens do banco antes e depois de ler o quadro pelo
  contrato duas vezes. Que a plateia atravessa a fronteira igual à do sininho, e
  que a ideia sai da condição de pendente sozinha quando o corredor é assinado,
  têm guarda em `services/sugestoes/tests/test_api_gestao.py`.
- **Célula dona:** sugestoes (o dado). O consumidor que agrupa —
  `services/admin/apps/core/caixa.py` — herda a obrigação de não recalcular a
  plateia: somar as contagens por ideia contaria duas vezes quem está atrás de
  duas, e há guarda disso em `services/admin/tests/test_caixa_no_admin.py`.

### [INV-NOT1] A Caixa Central Escreve UMA Linha por Carta, e o Contador Anda Junto
- **O quê:** cada `notificacao.devida` que chega ao fio vira **uma** linha em
  `Notificacao` — a mesma carta reentregue não vira duas — e o
  `ContadorDeNaoLidos` da pessoa é somado na **mesma transação** da linha. Ler o
  contador custa o mesmo com 1 e com 50 avisos.
- **Por quê:** o fio entrega **pelo menos uma vez** por desenho, então sem dedup
  a pessoa veria o mesmo aviso duas, três vezes e o número no sino subiria
  sozinho — o defeito mais visível que uma caixa de notificações pode ter, e o
  que nunca vira chamado de suporte: só corrói a confiança de quem lê. E o
  contador é uma **cópia**: existe porque o sino aparece em TODA página e um
  `COUNT(*)` numa tabela que só cresce fica lento exatamente quando o produto
  der certo (`DECISAO-notificacoes` §5.2) — mas toda cópia pode divergir, e uma
  atualizada fora da transação diverge no primeiro erro de rede e nunca mais
  volta sozinha ao lugar.
- **Teste-Guarda:**
  `services/notificacoes/tests/test_inv_contador_bate_com_a_tabela.py` (a
  igualdade contra o `COUNT(*)` que ele substitui, o isolamento entre pessoas, o
  custo O(1) medido com 1 e com 50, e a transação única provada sabotando o
  contador) e
  `services/notificacoes/tests/test_inv_carta_entregue_duas_vezes_vira_uma_linha.py`
  (a reentrega escreve uma linha só e soma uma vez; duas cartas DIFERENTES da
  mesma mudança viram dois avisos — a contraprova de um dedup errado por fato; e
  o handler que falha no meio não deixa a carta marcada como vista).
- **Célula dona:** notificacoes

### [INV-NOT2] O Que a Caixa Consome é Exatamente o Que o Contrato Promete
- **O quê:** o envelope que a célula aceita do fio valida contra
  `contracts/eventos/notificacao.devida.v1.json`, o schema **lido do arquivo**;
  todo campo que o contrato promete é guardado; `ator_id` ausente vira `NULL`
  (uma só forma de "não sei"); e e-mail não entra — nem no `data`, nem de carona
  nos `parametros`.
- **Por quê:** a `sugestoes` já prova que o que ela PUBLICA casa com o contrato.
  Um contrato provado só na origem garante que a mensagem sai certa e **não diz
  nada** sobre o consumidor ter entendido os campos que ela traz — é a lição do
  elo EVO-40: escada testada só por fora prova o andar de cima e mente sobre os
  de baixo. Campo prometido e ignorado é campo que some sem ninguém notar. E o
  e-mail vive numa linha só, dentro da Caixa (`DECISAO-EVO-01` §3): a trava é do
  contrato, e este guarda prova que ela morde do lado de cá também.
- **Teste-Guarda:**
  `services/notificacoes/tests/test_inv_carta_casa_com_o_contrato.py` — inclusive
  o guarda de que o arquivo do contrato EXISTE, sem o qual a suíte inteira
  passaria no vazio [INV-CI01].
- **Célula dona:** notificacoes

### [INV-GAM1] Nada na Gamificação se Compra com Dinheiro Real
- **O quê:** nenhum item, moeda, proteção ou vantagem da célula `gamificacao` é
  vendável. Cristais são *earn-only* **por construção do banco**, e não por
  convenção: a origem de um movimento vem de vocabulário fechado no PostgreSQL
  (`origem_de_cristal_no_vocabulario_fechado`), crédito nunca nasce de compra
  (`cristal_positivo_nunca_vem_de_compra`) e débito só existe como compra de
  cosmético com o recibo junto (`cristal_negativo_so_com_referencia_de_compra`) —
  o que também torna a moeda intransferível na prática, porque uma “gorjeta”
  precisaria de uma porta de saída que não existe. Somam-se a isso quatro
  ausências de forma: nenhum campo nomeia instrumento de pagamento (cartão,
  boleto, Pix, gateway, fatura), nenhum campo que CARREGUE valor nomeia dinheiro
  real, nenhum módulo importa SDK de cobrança, e a proteção de sequência não tem
  tipo de item que a represente — o escudo é 1 por mês, automático e grátis,
  dentro da `Sequencia`.
- **Por quê:** a escola vende formação, e quem paga por ela não pode descobrir
  depois que o progresso do filho, do colega ou o dele próprio também estava à
  venda. (Esta justificativa dizia “o público é criança” até 30/08/2026; a escola
  é 18+ desde a emenda do §9 da `DECISAO-gamificacao.md`, e o invariante não
  perdeu um grama de força ao perder esse argumento: vender vantagem numa escola
  de adultos é a mesma traição.) “Nós não vendemos vantagem” escrito num
  documento e a mesma frase conferida pelo PostgreSQL são coisas diferentes:
  documento não sobrevive a seis meses e quatro sessões
  (`RETROSPECTIVA-FASE-D` §2), restrição de banco sobrevive — e continua
  valendo numa madrugada de incidente, com alguém logado no `psql`. Lei:
  `DECISAO-gamificacao.md` §3.1 e §8 (“nenhum item, moeda, proteção ou vantagem se
  compra”). Cristal comprável ou transferível é o critério de morte nº 2 da célula,
  e este guarda precisar de exceção é o nº 6: nos dois casos a resposta certa é
  parar e reabrir a decisão com o mantenedor, nunca afrouxar o teste.
- **Teste-Guarda:**
  `services/gamificacao/tests/test_inv_economia_nada_por_dinheiro_real.py` — as
  quatro frentes de forma (campo com nome de instrumento de pagamento, campo
  portador de valor com nome de dinheiro, escolha declarada, import de cobrança)
  mais as recusas do banco provadas até em SQL cru, o caminho feliz que impede um
  banco que recusa TUDO de passar por engano, e a ausência do escudo na loja.
  Provado por mutação em 30/08/2026: `ItemCosmetico.preco_em_reais` e a remoção da
  restrição `cristal_positivo_nunca_vem_de_compra` deixam o guarda vermelho.
- **Célula dona:** gamificacao

### [INV-GAM2] Cosmético é Só Estética
- **O quê:** o que se compra com Cristais muda a APARÊNCIA e não muda mais nada:
  nunca vantagem em XP, ranking ou visibilidade. `ItemCosmetico` tem quatro tipos,
  todos visuais (título, moldura, tema, decoração de estúdio), e o banco recusa um
  quinto (`tipo_de_cosmetico_e_so_estetica`). A forma do item é fechada: não há
  onde guardar multiplicador, bônus, peso, prioridade, destaque ou posição — e
  nenhuma tabela que calcula XP, nível ou liga conhece um cosmético.
- **Por quê:** dos três, este é o mais fácil de perder. Os outros dois se quebram
  por uma decisão grande, que alguém tomaria de olhos abertos; este se quebra por
  uma boa ideia numa tarde qualquer — *“e se a moldura dourada desse 5% a mais de
  XP?”*, *“e se quem comprou o tema aparecesse antes na galeria?”*. Cada uma parece
  um detalhe simpático e, juntas, transformam a loja no lugar onde se compra
  posição, que é exatamente o que a economia earn-only existe para tornar
  impossível. Por isso a garantia é de FORMA e não de intenção: um cosmético que
  não tem onde guardar um multiplicador não multiplica nada, mesmo que o motor de
  XP de amanhã queira. Lei: `DECISAO-gamificacao.md` §3.2.
- **Teste-Guarda:**
  `services/gamificacao/tests/test_inv_economia_cosmetico_e_so_estetica.py` — o
  vocabulário da vantagem recusado em qualquer campo de cosmético, a forma fechada
  do item de loja, os quatro tipos visuais exatos, a recusa do quinto tipo pelo
  PostgreSQL e a prova de que nenhuma tabela de XP, nível ou ranking referencia um
  cosmético. Provado por mutação em 30/08/2026: `ItemCosmetico.multiplicador_de_xp`
  deixa o guarda vermelho.
- **Célula dona:** gamificacao

### [INV-GAM3] Aula Nunca Fica Atrás de Jogo
- **O quê:** conteúdo educacional jamais fica trancado por XP, nível ou Cristal. A
  garantia é por AUSÊNCIA: esta célula não sabe o que é uma aula — nenhum campo,
  modelo ou chave estrangeira nomeia aula, curso, módulo, lição, material ou
  matrícula — e nenhum nome de campo ou de modelo é um portão (verbo de porteiro
  somado a substantivo de conteúdo ou de economia). `NivelDefinicao` tem forma
  fechada: um nível dá um título, e mais nada. A direção importa e está preservada:
  a `RegraDePontuacao` vai LER `aula.concluida.v1` um dia (a tomada já está
  semeada, desligada), e ler que a aula terminou é o oposto de decidir se ela pode
  começar — por isso a régua mede NOME de campo e de modelo, nunca o valor de um
  `evento_gatilho`.
- **Por quê:** a família pagou por um curso. No dia em que uma aula estiver atrás
  de “chegue ao nível 4”, a escola terá vendido uma coisa e entregado outra, e a
  gamificação terá deixado de ser andaime para virar pedágio. A hierarquia da lei
  (*Realidade > Criação > Maestria > Comunidade > XP*, `DECISAO-gamificacao.md`
  §2) põe o XP em último; trancar aula com XP a inverte por completo. E a ausência
  é a garantia mais durável disponível numa célula que ainda não tem tela nem
  motor: quem não consegue nomear uma aula não consegue trancá-la, e nenhum motor
  futuro consegue trancá-la sem antes acrescentar aqui um campo que a CI recusa.
  Lei: `DECISAO-gamificacao.md` §3.3.
- **Teste-Guarda:**
  `services/gamificacao/tests/test_inv_economia_aula_nunca_atras_de_jogo.py` — o
  inventário de campos e de modelos contra o vocabulário de conteúdo educacional,
  a régua combinatória do portão (que deixa `liberado_em` em paz por ser inocente
  sozinho) e a forma fechada do nível. Provado por mutação em 30/08/2026:
  `NivelDefinicao.aulas_desbloqueadas` deixa três asserções vermelhas.
- **Célula dona:** gamificacao

### [INV-ENC-J1] Uma Encomenda Nunca Tem Duas Ofertas Pendentes
- **O quê:** em nenhum instante existem duas `Oferta` com `resultado="pendente"`
  para a mesma encomenda. A garantia é em três camadas, e a de fora é a que vale:
  a varredura do motor só olha `na_fila` (e a encomenda oferecida sai desse
  estado), o motor recusa com desfecho nomeado a encomenda que já tem oferta
  viva, e o índice único parcial `uma_oferta_pendente_por_encomenda` do
  PostgreSQL recusa a segunda linha. O motor trata o `IntegrityError` como
  veredito, não como erro: ele vira o desfecho `corrida_perdida`.
- **Por quê:** duas ofertas pendentes da mesma encomenda são duas pessoas
  trabalhando de graça na mesma coisa, e uma delas descobrindo depois — a falha
  que mais rápido destrói a confiança de quem está esperando a primeira chance.
  E a corrida que a produz é entre dois PROCESSOS do motor, que nenhum `if` em
  Python resolve: por isso a trava tem de ser do banco. Lei:
  `DECISAO-fila-do-primeiro-dolar.md` §5; produto: plano §6.3 e §7.4.
- **Teste-Guarda:**
  `services/encomendas/tests/test_inv_j1_uma_oferta_por_encomenda.py` — o caso
  feliz, a segunda passada sobre o mesmo estado, a encomenda devolvida à fila com
  oferta viva, a recusa do PostgreSQL provada de fora do motor, e o par verde do
  índice ser PARCIAL (oferta respondida não ocupa a vaga; um índice total travaria
  a fila na primeira recusa). Provado por mutação em 04/09/2026.
- **Célula dona:** encomendas

### [INV-ENC-J2] Um Aluno Nunca Tem Duas Ofertas Pendentes
- **O quê:** em nenhum instante uma pessoa tem duas `Oferta` pendentes. Vale
  DENTRO de uma passada do motor (que avança o próprio estado enquanto varre) e
  ENTRE passadas (o candidato lido do banco já vem marcado), e o índice único
  parcial `uma_oferta_pendente_por_aluno` recusa a segunda linha.
- **Por quê:** com três encomendas na fila e um só aluno disponível, um motor que
  consultasse os candidatos uma vez e não avançasse ofereceria as três à mesma
  pessoa, sem nenhuma linha parecer errada. O efeito é ela abrindo o celular e
  vendo três relógios correndo ao mesmo tempo, sabendo que só pode aceitar um —
  o oposto exato da promessa da tela do aluno, que é uma oportunidade por vez.
  Lei: `DECISAO-fila-do-primeiro-dolar.md` §5; produto: plano §6.3.
- **Teste-Guarda:** `services/encomendas/tests/test_inv_j2_uma_oferta_por_aluno.py`
  — três encomendas e um aluno numa passada só, a passada seguinte, a razão
  NOMEADA da recusa (`com_oferta_pendente`, e não outra), o par verde de quem
  respondeu voltar a receber, e a recusa do PostgreSQL. Provado por mutação em
  04/09/2026.
- **Célula dona:** encomendas

### [INV-ENC-J3] A Oferta Vai a Quem Tem Menos Entregas, e no Empate a Quem Entrou Antes
- **O quê:** toda oferta vai ao elegível disponível de menor
  `(entregas_aprovadas, data_entrada_fila)`. A chave de ordenação tem exatamente
  três termos: os dois da lei e um desempate determinístico (`perfil_id`),
  consultado só quando os dois primeiros empatam ao microssegundo. E o
  `Candidato` tem forma FECHADA: nenhum campo de peso, prioridade, destaque,
  nota, ranking, patrocínio ou afinidade — quem não pode nomear não pode ordenar.
- **Por quê:** é o invariante do produto inteiro. A promessa da Fila do Primeiro
  Dólar não é "há trabalho": é que quem nunca entregou passa na frente. Trocar a
  ordem dos dois termos — igualmente "justa" à primeira vista — faz o veterano de
  365 dias levar tudo para sempre, e a fila vira o marketplace que este produto
  existe para não ser. Uma SEGUNDA regra de ordem (peso, prioridade paga,
  destaque) é o **critério de morte 2** da lei §9: pare e reabra a decisão com o
  mantenedor, nunca afrouxe o guarda. Lei: `DECISAO-fila-do-primeiro-dolar.md`
  §5 e §9; produto: plano §6.2.
- **Teste-Guarda:**
  `services/encomendas/tests/test_inv_j3_menor_entregas_depois_mais_antigo.py` —
  as duas metades da regra, o cenário que separa a ordem certa da inversa, a
  independência da ordem de entrada, o empate total, a FORMA da chave (três
  termos, nesta ordem) e a ausência do vocabulário da vantagem no `Candidato`.
  Provado por mutação em 04/09/2026.
- **Célula dona:** encomendas

### [INV-ENC-J4] Só o Abandono Muda o Lugar na Fila
- **O quê:** passar, expirar e pausar nunca alteram `data_entrada_fila`. A
  garantia é de FORMA além de comportamento: um varredor `ast` percorre
  `services/encomendas/apps/` e exige que toda ESCRITA no campo (atribuição de
  atributo, argumento de `create`/`update`/`bulk_*`, citação em
  `save(update_fields=...)`) esteja numa função declarada na lista
  `QUEM_PODE_MOVER_O_LUGAR` — hoje VAZIA, porque nenhum código da célula move o
  lugar de ninguém. A leitura do campo fica em paz, de propósito.
- **Por quê:** protege uma frase que o aluno vai ler na tela: *"você mantém o seu
  lugar"*. Comportamento mede os gestos que existem hoje, e o degrau 2.5 traz
  gestos novos — a pausa automática por três silêncios, a chamada aberta, a
  reclassificação. É exatamente ali que alguém, com toda a boa intenção, escreve
  `perfil.data_entrada_fila = agora` para "reiniciar a espera" de quem ficou
  muito tempo pausado, e nenhum teste de comportamento escrito hoje pegaria isso:
  o gesto ainda não existe. Lei: `DECISAO-fila-do-primeiro-dolar.md` §5;
  produto: plano §6.2, §6.3 e §6.6.
- **Teste-Guarda:**
  `services/encomendas/tests/test_inv_j4_so_abandono_muda_o_lugar.py` — a
  varredura com a lista declarada, a prova de que o varredor enxerga as quatro
  formas de gravar E deixa a leitura em paz, os três gestos da lei um a um, e o
  efeito visível (quem voltou da pausa recupera a vez que tinha, na frente de
  quem entrou depois). Provado por mutação em 04/09/2026.
- **Célula dona:** encomendas

### [INV-ENC-J5] Nenhuma Oferta Abaixo do Nível Mínimo da Encomenda
- **O quê:** Iniciante pede título Nível 1; Intermediário, Nível 2 e as entregas
  aprovadas do parâmetro; Avançado, Nível 3, mais entregas e nenhum abandono na
  janela. Título vazio é "ninguém avaliou" e fica abaixo de tudo. O título é um
  PISO, não uma faixa: Nível 3 continua atendendo trabalho simples. **Os três
  números vêm do banco**, no valor vigente em `agora`.
- **Por quê:** protege os dois lados, e a segunda metade é a esquecida. O cliente
  não recebe um personagem articulado feito por quem nunca fez um cubo; e o aluno
  não recebe uma encomenda grande demais cedo demais, que é a forma mais rápida
  de alguém abandonar, perder o lugar e sair da escola achando que não serve para
  isto. Sem este invariante, a ordem da fila sozinha entregaria a encomenda mais
  difícil da casa a quem menos pode fazê-la, porque é ele quem está em primeiro
  lugar. Um dos três números em código é o **critério de morte 5**. Lei:
  `DECISAO-fila-do-primeiro-dolar.md` §5, §3.6 e §6; produto: plano §6.1.
- **Teste-Guarda:** `services/encomendas/tests/test_inv_j5_nivel_minimo.py` — o
  título exato e o título curto de cada um dos três níveis, o título acima, o
  perfil sem título, as duas condições do avançado com razão nomeada, a janela de
  abandono que só pesa no avançado, a data ilegível que conta como recente em vez
  de derrubar a rodada de todos, e a prova de que mudar o parâmetro no banco muda a régua
  sem PR — e de que o valor lido é o vigente em `agora`, não o mais recente.
  Provado por mutação em 04/09/2026.
- **Célula dona:** encomendas

### [INV-ENC-J6] Ninguém Recebe a Mesma Encomenda Duas Vezes
- **O quê:** um aluno que já recebeu uma oferta de uma encomenda não a recebe de
  novo, qualquer que tenha sido o desfecho (passou, expirou, foi cancelada) e
  qualquer que seja a rodada. A memória é da `Oferta`, que é registro de primeira
  classe, e é do PAR (aluno, encomenda) — nunca da pessoa. A exceção da lei
  ("salvo em chamada aberta") vale para o estado `aberta`, que nasce no degrau
  2.5; o motor da fila varre `na_fila`, e aqui a regra vale sem exceção.
- **Por quê:** sem ela a fila com poucos alunos vira um carrossel: quem passa
  recebe a mesma encomenda de volta em minutos, porque continua sendo o primeiro
  da ordem e a ordem não tem memória. A pessoa que disse "não curto esse tipo"
  acaba dizendo isso quatro vezes por dia até desligar o interruptor. E a rodada
  nova não limpa a memória: o plano manda a encomenda abandonada voltar à fila
  *"sem esse aluno"*, e zerar ali devolveria a encomenda justamente a quem a
  abandonou. Lei: `DECISAO-fila-do-primeiro-dolar.md` §5; produto: plano §6.3,
  §6.4 e §6.6.
- **Teste-Guarda:**
  `services/encomendas/tests/test_inv_j6_nunca_a_mesma_duas_vezes.py` — o
  carrossel impedido, a encomenda descendo a fila inteira sem repetir ninguém, o
  silêncio queimando a vez nesta encomenda (sem custar o lugar), o par verde da
  memória ser por encomenda e não por pessoa, a memória atravessando rodadas, e a
  prova de que o motor nunca abre rodada nova sozinho. Provado por mutação em
  04/09/2026.
- **Célula dona:** encomendas

### [INV-ENC-J7] Aluno Trabalhando Não Recebe Ofertas
- **O quê:** só o perfil com `disponibilidade="disponivel"` recebe oferta. Quem
  está `trabalhando` (aceitou uma encomenda) e quem está `pausado` (o interruptor
  do aluno, ou a pausa automática) ficam fora — sem perder o lugar na fila. O
  guarda cobre o vocabulário INTEIRO de `disponibilidade` e reprova se ele
  crescer sem alguém decidir o que o valor novo faz.
- **Por quê:** é o que faz a fila DISTRIBUIR em vez de acumular. Sem ele, o
  primeiro da fila (zero entregas, entrou primeiro) receberia todas as encomendas
  de todos os dias, porque a chave de ordem o mantém em primeiro lugar até a
  primeira entrega ser aprovada — e a Fila do Primeiro Dólar entregaria o
  primeiro dólar a uma pessoa só. Lei: `DECISAO-fila-do-primeiro-dolar.md` §5;
  produto: plano §6.5 e §6.3.
- **Teste-Guarda:**
  `services/encomendas/tests/test_inv_j7_trabalhando_nao_recebe.py` — as duas
  indisponibilidades recusadas com razão nomeada, o par verde de quem está
  disponível, o inventário do vocabulário, o primeiro da fila cedendo a vez sem
  perder o lugar, uma pessoa não levando cinco encomendas, e o ciclo completo
  (recebe, aceita, vira trabalhando, some das ofertas). Provado por mutação em
  04/09/2026.
- **Célula dona:** encomendas

### [INV-ENC-J8] O Relógio da Oferta Não Anda Fora da Janela
- **O quê:** entre o instante em que uma oferta é feita e o `expira_em` gravado
  existem exatamente `relogio_da_oferta` horas **dentro da janela**
  `janela_inicio`–`janela_fim` (hoje 8h–22h de São Paulo). Fora dela o relógio
  congela: a oferta feita às 21h vence às 10h do dia seguinte, e a feita às 2h da
  manhã só começa a contar às 8h. A conta é uma função pura de (instante,
  duração, janela) em `services/encomendas/apps/encomendas/relogio.py`, e os
  três números vêm do banco no valor vigente em `agora`. **"Horas úteis" aqui
  são horas da JANELA, e fim de semana conta como qualquer dia** — não existe
  chave `dias_uteis` na lei §6, e o vocabulário de parâmetros é fechado no banco.
- **Por quê:** protege a frase que o produto inteiro promete ao aluno, e que
  ninguém escreve porque parece óbvia demais: *ninguém perde a oportunidade
  dormindo*. Sem a janela, uma encomenda paga às 23h chega com prazo até as 2h
  da manhã, e a pessoa acorda com "você perdeu esta oportunidade". Ela não
  passou; ela dormiu — e na segunda vez desliga o interruptor. Um dos três
  números em código é o **critério de morte 5** da lei §9. Lei:
  `DECISAO-fila-do-primeiro-dolar.md` §5 e §6; produto: plano §6.3 e §7.4.
- **Teste-Guarda:**
  `services/encomendas/tests/test_inv_j8_relogio_congela_fora_da_janela.py` — a
  propriedade varrida nas 24 horas do dia (medida pela INVERSA, `horas_uteis_entre`,
  para o guarda não recalcular com a função que ele mede), as horas concretas que
  o aluno lê na tela, a contraprova do congelamento (nove horas de parede para
  três de janela) com o par verde de dentro da janela, o caminho real pelo motor,
  a janela mudando no banco sem PR, o valor vigente em `agora`, e o fail-closed da
  janela ausente. Mais
  `services/encomendas/tests/test_relogio_horas_uteis.py`, que mede a função pura:
  as bordas, a virada de dia, a virada de ano, o fim de semana e a janela
  impossível. Provado por mutação em 04/09/2026.
- **Célula dona:** encomendas

### [INV-ENC-J9] Nenhuma Encomenda Espera na Fila Além do Prazo
- **O quê:** nenhuma encomenda passa de `horas_para_virar_aberta` (hoje 24h, de
  PAREDE) em `na_fila`/`oferecida` sem virar `aberta`. O tique de um minuto vira
  o estado e cancela a oferta viva, se houver. O marco não é `criada_em`: é a
  última entrada na espera vinda de FORA do par `na_fila`/`oferecida` — as idas e
  vindas internas (o silêncio de um aluno) não zeram nada, e voltar do plantão ou
  do abandono começa uma espera nova.
- **Por quê:** é o único dos dez de justiça que protege o CLIENTE. Sem ele, uma
  encomenda desce a fila para sempre — cada aluno silencia, a oferta expira, ela
  volta para `na_fila`, o próximo silencia — e quem pagou fica olhando "estamos
  procurando um modelador" por uma semana, sem nada errado acontecendo em lugar
  nenhum: nenhum erro, nenhum alarme, só uma fila que anda e nunca chega. O
  relógio é de parede, e não de janela, porque a lei §6 escreve a unidade
  ("horas na fila", contra "horas úteis" do relógio da oferta): quem espera é o
  cliente, que não dorme junto com a janela. Lei:
  `DECISAO-fila-do-primeiro-dolar.md` §5 e §6; produto: plano §6.4 e §7.4.
- **Teste-Guarda:**
  `services/encomendas/tests/test_inv_j9_vira_aberta_em_24h.py` — a virada no
  prazo com o par verde de um minuto antes, o rastro no histórico com motivo e
  sem ator, a oferta viva cancelada (e não expirada) no minuto das 24h, o marco
  que NÃO zera nas idas e vindas da fila, a encomenda devolvida pelo plantão
  ganhando o prazo inteiro, o prazo mudando no banco sem PR, a encomenda sem
  elegível esperando como as outras, e a varredura universal ("ninguém esperou
  mais que o prazo"). Provado por mutação em 04/09/2026.
- **Célula dona:** encomendas

### [INV-ENC-J10] Reexecutar Não Cria Oferta Nova, e Nada é Agendado
- **O quê:** rodar o motor ou o tique duas vezes sobre o mesmo estado não muda
  coisa alguma — nem uma oferta, nem um status, nem um `atualizada_em`. E a
  outra metade, que é o mecanismo: **não existe timer agendado nesta célula**.
  Há UM `crontab(minute="*")` na árvore inteira, e nenhum `schedule`, `revoke`,
  `eta=` ou `delay=` — garantia de FORMA, por varredor `ast`, além do
  comportamento.
- **Por quê:** é o que torna a fila operável no pior dia. Um timer agendado vive
  fora do banco (na fila do Redis, ou na memória de um processo): o deploy troca
  o container, o Redis cai, a máquina reinicia — e o timer que morre **não deixa
  rastro**. A oferta fica pendente para sempre, a encomenda nunca volta para a
  fila, e ninguém recebe erro nenhum. Com reavaliação periódica a verdade inteira
  está nas colunas: seis horas fora do ar se resolvem numa passada, porque ela
  não pergunta "o que devia ter acontecido às 14h?", pergunta "o que está vencido
  AGORA?". Lei: `DECISAO-fila-do-primeiro-dolar.md` §5; produto: plano §7.4, §8.6
  e o cenário 15 do anexo B.
- **Teste-Guarda:**
  `services/encomendas/tests/test_inv_j10_motor_idempotente.py` — a segunda
  passada inerte no motor, no tique e na abertura, sempre com o par que prova que
  a PRIMEIRA fez algo (idempotência é verdade trivial para quem não faz nada), e
  o cenário 15 nas duas metades: relógios que não se mexem no reinício e nenhuma
  duplicata em quatro passadas seguidas, mais as seis horas fora do ar resolvidas
  numa passada só. A forma (nenhum agendamento por oferta, um batimento na
  célula, e o varredor provado contra código que agenda) está em
  `services/encomendas/tests/test_tique.py`. Provado por mutação em 04/09/2026.
- **Célula dona:** encomendas

### [INV-ALU-C1] Nenhuma Matrícula Ativa Sem Curso
- **O quê:** liberar alguém da sala de espera EXIGE dizer em qual curso a pessoa
  está matriculada. `POST /pre-matriculas/{id}/decisao` com `decisao=liberar` e
  sem `product_id` responde 422, com frase em português que diz o que faltou e o
  que fazer, e **nada muda**: a linha continua `aguardando`. Não existe valor
  padrão. Com o curso, ele é gravado na MESMA transação e no mesmo `save` que
  põe a linha em `ativa`. `recusar` não pede curso, e curso mandado junto de uma
  recusa é ignorado: quem foi recusado não é aluno de nada. E a outra metade,
  que é o que impede a duplicação: **esta célula não tem tabela de cursos** — a
  lista é do `catalogo`, e a matrícula guarda a referência (`product_id`).
- **Por quê:** até 6 de setembro de 2026 ser aluno era binário, e enquanto
  houvesse um curso só isso funcionava por coincidência. No dia do segundo curso,
  **todo aluno veria o primeiro**, sem erro, sem aviso e sem nenhuma tela
  quebrada, porque a única resposta possível para "de qual curso é esta pessoa?"
  seria um palpite. Um valor padrão seria pior do que não ter lista: faria a
  escolha errada parecer escolha, e ninguém veria o erro até o aluno abrir a sala
  e encontrar o curso errado. Duas listas de cursos (uma no `catalogo`, outra
  aqui) divergiriam no primeiro curso novo. Lei:
  `docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md` §6, §7 e §8.
- **Teste-Guarda:**
  `services/alunos/tests/test_inv_alu_c1_a_matricula_diz_o_curso.py` — a recusa
  com frase em português e efeito zero, o curso em branco recusado igual, a
  metade positiva (sem a qual "recusar tudo" satisfaria o invariante), a
  varredura universal com a prova contra verdade vazia, a recusa que não grava
  curso, o inventário de modelos por igualdade exata, e o acerto das matrículas
  que já existiam, sempre fabricando primeiro o estado de produção (linha que dá
  acesso com `product_id` vazio, inclusive pelo caminho real do pagamento).
  Provado por mutação em 06/09/2026.
- **O que este invariante NÃO alcança, e está dito na cara:** a matrícula que
  nasce do EVENTO. `pagamento.aprovado.v1` não carrega `product_id`
  (`contracts/eventos/pagamento.aprovado.v1.json`), então
  `apps/matriculas/handlers.py` grava `""` e essa linha nasce `ativa` sem curso
  sem passar pela decisão da fila. **A lei §3 supõe o contrário** ("quem entra
  pela compra já informa o curso"), e a suposição vale só para `POST /matriculas`,
  que é o reprocesso manual. Fechar a metade que falta é Rito de Contrato no
  evento, e o evento é de outra célula. Enquanto ele não acontece, quem cura o
  passado é `apontar_o_curso_das_matriculas`, e ele precisa ser rodado de novo
  depois de cada compra nova.
- **Célula dona:** alunos

---

## Invariantes da própria CI

Os invariantes acima protegem a plataforma. Este protege o INSTRUMENTO que
verifica os outros — porque um portão que erra para o lado do verde não protege
coisa alguma, e ainda gasta a confiança de todo mundo.

### [INV-CUR-C2] O Conteúdo do Curso Entra Pela Porta de Máquina, Nunca Por Migração
- **O quê:** nenhuma migração de `services/cursos/apps/cursos/migrations/` roda
  código (nenhum `RunPython`), e o banco recém-migrado não tem `Peca` nenhuma nem
  `Aula` com `pedido`. O esqueleto (um curso, doze blocos, 34 aulas só com número
  e título exibido, treze instrumentos só com slug, nome canônico e cartão) entra
  pelo comando `semear_esqueleto`, idempotente; o texto das aulas entra pela
  porta de máquina (o editor do Admin, degrau 1.5 da escada), e só por ela.
- **Por quê:** o repositório é público e o curso é obra não lançada
  (`armadilhas/331`): uma migração com o capítulo dentro publicaria o livro para
  sempre, inclusive no histórico. E conteúdo em dois lugares (arquivo e banco) é
  a doença que a lei anti-duplicação existe para curar. Lei:
  `docs/decisoes/PLANO-CELULA-CURSOS.md` §3.1 e §9.
- **Teste-Guarda:**
  `services/cursos/tests/test_inv_c2_conteudo_so_pela_porta.py` — nenhuma
  migração da célula roda código (medido pelo `MigrationLoader`), zero `Peca` e
  zero `Aula` com `pedido` depois de migrar. Provado por mutação em 05/09/2026
  (um `RunPython` que cria uma peça deixa três asserções vermelhas), PR #1052.
- **Célula dona:** cursos

### [INV-CUR-P1] Nenhuma Tela Compara Alunos
- **O quê:** nenhuma tela da sala de aula (`/cursos`, `/cursos/<numero>`) devolve
  dados de mais de uma pessoa, e nenhuma rota lista alunos, recebe o id de outra
  pessoa ou desenha ranking. Toda consulta de `Progresso` e de `RegistroDePausa`
  nas views é filtrada pela pessoa da sessão, e o urlconf é inventariado por
  igualdade: as rotas de hoje são cinco, e nenhuma delas fala de duas pessoas.
- **Por quê:** "ranking ou dois alunos lado a lado" é critério de morte da
  célula (`constituicoes/AGENTS.cursos.md` §11 da lei). A sala é da pessoa que a
  abriu: o que ela vê é a própria porta, o próprio registro, a própria resposta.
  Uma tela que comparasse transformaria o curso em placar, e o placar é da
  gamificação, por evento, nunca daqui. Lei: `docs/decisoes/PLANO-CELULA-CURSOS.md` §9.
- **Teste-Guarda:**
  `services/cursos/tests/test_inv_p1_nenhuma_tela_compara_alunos.py` — duas
  pessoas no banco, cada uma com progresso, registro de pausa e autoavaliação
  próprios; toda tela percorrida como uma delas não carrega nome, id, registro
  nem resposta da outra; o inventário de rotas por igualdade; e a medição no
  código das views (`pessoa=` em toda consulta). Provado por mutação em
  05/09/2026: tirar o `pessoa=` da consulta do mapa deixa 2 vermelhos, da
  consulta de registros deixa 3, e uma rota nova de lista de alunos deixa 1.
- **Célula dona:** cursos

### [INV-CUR-P2] A Porta Só Abre Por Laudo
- **O quê:** `concluida` só entra em `Progresso` por `progresso.concluir`, que
  EXIGE um laudo com decisão `aberto` ou `aberto_com_ajuste` como argumento, por
  nome, e recusa qualquer outra coisa (sem laudo, devolvido, decisão inexistente,
  uma data, um número de XP, um pagamento). A assinatura da função não tem
  parâmetro de data, XP nem pagamento; gravar `data_de_retorno` não muda o
  estado; nenhuma view grava `concluida`; a aula N só sai de `trancada` quando a
  N-1 conclui; a bônus (EB) abre quando a E32 conclui e não tranca ninguém.
- **Por quê:** "o checkpoint abre a porta; o calendário, nunca" é a missão da
  célula. É o [INV-GAM3] visto do lado da aula: aula atrás de XP ou de pagamento
  dentro desta célula é critério de morte, e uma porta que abrisse por data
  entregaria ao aluno uma aula que ele não provou saber fazer. O acesso ao curso
  é a matrícula, e só. Lei: `docs/decisoes/PLANO-CELULA-CURSOS.md` §9.
- **Teste-Guarda:**
  `services/cursos/tests/test_inv_p2_a_porta_so_abre_por_laudo.py` — os oito
  substitutos de laudo recusados, a porta trancada recusada mesmo com laudo, a
  conclusão por laudo abrindo só a `ordem + 1`, a assinatura fechada medida por
  `inspect`, a data que não abre (no serviço e pela tela), a única gravação de
  `concluida` medida no código, e a vizinhança da bônus. Provado por mutação em
  05/09/2026: apagar a exigência do laudo deixa 8 vermelhos; trocar `ordem + 1`
  por `ordem + 2` deixa 6.
- **Célula dona:** cursos

### [INV-CUR-P3] O Checkpoint Fica Fechado Até Todas as Pausas Terem Registro
- **O quê:** `progresso.pausas_registradas` só é verdadeira quando TODAS as
  pausas da aula têm `RegistroDePausa` da própria pessoa (registro de outra
  pessoa não conta; aula sem pausa é verdadeira, porque não há o que registrar),
  e a tela da aula diz "fechado" enquanto falta pausa. O formulário do checkpoint
  (degrau 2.1) consome esta função e nunca a reescreve.
- **Por quê:** a pausa é o lugar onde a pessoa faz o que o vídeo pediu, e o
  checkpoint é a prova de que fez. Um envio antes de todas as pausas seria uma
  entrega sem o meio do caminho, e o laudo da professora chegaria a um trabalho
  que pulou etapas. Lei: `docs/decisoes/PLANO-CELULA-CURSOS.md` §4 e §9.
- **Teste-Guarda:**
  `services/cursos/tests/test_inv_p3_checkpoint_fechado_ate_as_pausas.py` —
  nenhuma, uma de duas, todas, a de outra pessoa, a aula sem pausa, e a tela nos
  dois lados. Provado por mutação em 05/09/2026: trocar `all` por `any` deixa 4
  vermelhos.
- **Célula dona:** cursos

### [INV-CUR-L3] O Prazo de Revisão do Checkpoint Nunca Alonga
- **O quê:** `Envio.prazo_em` é `enviado_em + 24 horas`, calculado uma única
  vez no `save()` que insere a linha. Depois disso não muda por caminho
  nenhum: nem por `save()` normal ou com `update_fields`, nem por
  `QuerySet.update()`, nem por `bulk_update()`, e o banco tem a restrição
  `prazo_em = enviado_em + 24 h`, que vale até para um `UPDATE` cru pelo
  `psql`. Quando as 24 horas passam sem laudo, `envio.registrar_estouros`
  grava a hora em `estourado_em` e nunca no prazo, e a passada seguinte não
  regrava nem reemite (idempotente pelo filtro `estourado_em IS NULL`).
  `envio.entregar` não tem parâmetro de prazo, de hora nem de estado.
- **Por quê:** "24 horas é constante, com teste; `prazo_em` não muda por API;
  o estouro se registra em `estourado_em`. Não é parâmetro" é a constituição
  da célula, e o critério de morte da lei (§11) é justamente "o prazo de 24
  horas como parâmetro ou com botão de alongar". Um prazo que alonga vira
  favor negociável por aluno; o que a professora vê é sempre o fato: passou,
  ou não passou. Lei: `docs/decisoes/PLANO-CELULA-CURSOS.md` §4 e §9.
- **Teste-Guarda:** `services/cursos/tests/test_inv_l3_prazo_imutavel.py` — o
  prazo nasce da constante, um prazo mandado na criação é ignorado, atribuir e
  salvar recusa (com e sem `update_fields`), `update()` do queryset recusa,
  `bulk_update()` recusa, o banco recusa um `UPDATE` cru, o estouro registra
  sem alongar, e a assinatura de `entregar` e as fontes do serviço são
  varridas por atribuição a `prazo_em`/`enviado_em`. Provado por mutação em
  05/09/2026: apagar o `else` do `Envio.save()` deixa 1 dente vermelho (2
  failed, um por campo); esvaziar `update()`/`bulk_update()` de
  `EnviosQuerySet` deixa 2 dentes vermelhos (3 failed).
- **Célula dona:** cursos

### [INV-CUR-L1] Nenhum Laudo Devolvido Sem Data de Retorno de Amanhã em Diante
- **O quê:** `Laudo.data_de_retorno` é obrigatória quando `decisao` é
  `devolvido` (e proibida nas outras duas decisões) — garantido pelo BANCO,
  sozinho, com um `CheckConstraint`; e é sempre amanhã ou depois no dia de São
  Paulo — garantido pelo SERVIÇO (`apps/cursos/laudo.py::emitir`), porque essa
  metade depende do relógio no instante da escrita, e um `CheckConstraint` não
  o consulta.
- **Por quê:** a escola devolve com data marcada, nunca sem ela: a data é a
  promessa de quando o aluno volta, e sem ela "devolvido" seria indistinguível
  de "abandonado". Lei: `docs/decisoes/PLANO-CELULA-CURSOS.md` §9.
- **Teste-Guarda:**
  `services/cursos/tests/test_inv_l1_devolvido_exige_data_de_retorno.py` — o
  banco recusa devolvido sem data e recusa qualquer outra decisão COM data; o
  serviço recusa data de hoje, de ontem e ausente; aceita amanhã e datas mais à
  frente. Provado por mutação em 05/09/2026: comentar a checagem do serviço
  deixa 3 vermelhos (hoje passa, ontem passa, ausente passa).
- **Célula dona:** cursos

### [INV-CUR-L2] O Estado "Reprovado" Não Existe no Laudo
- **O quê:** a palavra proibida não aparece em `Laudo.Decisao`, no serviço do
  laudo nem nas telas do plantão e do laudo; `emitir()` recusa explicitamente
  quem tentar mandar essa decisão.
- **Por quê:** a escola devolve com data de retorno; nunca reprova. Uma quarta
  decisão negativa encerraria o aluno em vez de pedir mais uma volta, e é
  exatamente o que a missão da célula proíbe. Lei:
  `docs/decisoes/PLANO-CELULA-CURSOS.md` §4 e §9; critério de morte da
  constituição da célula.
- **Teste-Guarda:** `services/cursos/tests/test_inv_l2_laudo_sem_reprovado.py`
  — a palavra ausente do serviço e de toda tela da célula, o vocabulário de
  `Laudo.Decisao` é exatamente os três da lei, e o serviço recusa a decisão
  explicitamente. `services/cursos/tests/test_sem_reprovado.py` cobre o
  `models.py` e as migrações da célula inteira (e por isso já inclui
  `Laudo`, sem código novo lá). Provado por mutação em 05/09/2026: acrescentar
  a decisão ao vocabulário do modelo deixa 2 vermelhos entre os dois arquivos;
  acrescentar a palavra a um template do plantão deixa 1 vermelho.
- **Célula dona:** cursos

### [INV-CUR-L4] Nenhuma Decisão, Data ou Resposta à Pergunta Vem da IA
- **O quê:** o Assistente de laudo (`apps/cursos/agente.py`) prepara a rubrica,
  as três forças e a mudança, e NADA além disso: nem `RascunhoDaIA` nem
  `agente.Sugestao` têm campo de decisão, de data de retorno ou de resposta à
  pergunta de amanhã de manhã, e a tela volta com os três em branco mesmo
  quando a IA os responde no JSON dela. Um laudo pedido sem decisão é recusado
  em vez de a decisão do rascunho preencher o buraco.
- **Por quê:** o degrau deste agente é H, "só prepara". A decisão, a data e a
  pergunta são o produto do trabalho da professora, e uma coluna para guardá-los
  seria o primeiro passo silencioso para a tela mostrá-los já marcados: o degrau
  que a lei diz que nunca sobe. Lei: `docs/decisoes/PLANO-CELULA-CURSOS.md` §7 e
  §9; critério de morte 2 da constituição da célula.
- **Teste-Guarda:**
  `services/cursos/tests/test_inv_l4_a_ia_nao_decide.py` — a lista INTEIRA de
  campos dos dois objetos é fixada (campo novo reprova, chame-se ele como se
  chamar); a IA responde os três e a tela volta sem decisão marcada, com a data
  em branco e a caixa desmarcada; o `conteudo` guardado não leva os três; e
  `emitir` recusa um laudo sem decisão mesmo recebendo um rascunho que a traz
  escrita. Provado por mutação em 05/09/2026: acrescentar `decisao` ao modelo,
  com a migração junto, deixa 2 vermelhos; acrescentar `decisao: str = ""` ao
  fim do dataclass deixa 2; copiar os três para o formulário deixa 1; completar
  a decisão vazia com a do rascunho deixa 1.
- **Célula dona:** cursos

### [INV-CUR-L5] A Rubrica Completa Antes de Qualquer Campo Livre
- **O quê:** o laudo exige uma nota (dentro da escala do instrumento da aula)
  e uma frase por critério antes de aceitar forças, mudança ou decisão; nota
  sem frase é recusada com a frase certa, e o mesmo vale para nota fora da
  escala ou booleana.
- **Por quê:** uma nota sem justificativa observável não ensina nada à pessoa
  que recebe o laudo, e é a mesma régua que já vale para a autoavaliação do
  aluno (`apps/cursos/envio.py`), reaproveitada em vez de reimplementada. Lei:
  `docs/decisoes/PLANO-CELULA-CURSOS.md` §9.
- **Teste-Guarda:** `services/cursos/tests/test_inv_l5_rubrica_completa.py` —
  critério ausente, nota fora da escala, nota booleana, nota sem frase, frase
  só com espaço, rubrica completa aceita, e chave estranha ignorada em
  silêncio. Provado por mutação em 05/09/2026: aceitar nota sem frase deixa 2
  vermelhos; aceitar qualquer valor não nulo como nota deixa mais 2.
- **Célula dona:** cursos

### [INV-CUR-L6] Exatamente Três Forças e Exatamente Uma Mudança
- **O quê:** o laudo exige exatamente três forças (nenhuma da lista de
  genéricos: "bonito", "legal", "bom trabalho", "ficou bom", "parabéns", sem
  acento na comparação e sem diferença de maiúscula) e exatamente uma mudança,
  com uma aula que existe no mesmo curso.
- **Por quê:** menos de três forças é elogio raso, mais de três dilui o que
  importa, e uma força genérica não diz nada específico sobre o trabalho da
  pessoa; mais de uma mudança tira o foco de onde a próxima entrega precisa
  melhorar. Lei: `docs/decisoes/PLANO-CELULA-CURSOS.md` §9.
- **Teste-Guarda:**
  `services/cursos/tests/test_inv_l6_forcas_e_mudanca.py` — duas, quatro e
  três forças vazias recusadas; cada uma das cinco frases genéricas recusada,
  em maiúscula e com espaço nas pontas; zero e duas mudanças recusadas;
  mudança com aula de outro curso, com id não numérico e sem texto recusada.
  Provado por mutação em 05/09/2026: aceitar mais de três forças deixa 1
  vermelho; esvaziar a lista de genéricos deixa 6; aceitar mais de uma
  mudança deixa 1.
- **Célula dona:** cursos

### [INV-CUR-L7] A Pergunta de Amanhã de Manhã: `false` Não Envia
- **O quê:** `sabe_o_que_fazer_amanha` só grava `true` — o BANCO recusa a
  linha se o valor não for verdadeiro, mesmo por fora do serviço, e o SERVIÇO
  recusa `false` e ausência (`None`) com a MESMA frase: a pergunta não tem uma
  terceira resposta que "envia mesmo assim".
- **Por quê:** não se registra recusa: se a professora não tem certeza de que
  o aluno sabe o que fazer amanhã, a conversa acontece antes do laudo, nunca
  depois de um "não" gravado que ninguém mais revê. Lei:
  `docs/decisoes/PLANO-CELULA-CURSOS.md` §9.
- **Teste-Guarda:**
  `services/cursos/tests/test_inv_l7_pergunta_de_amanha.py` — o banco recusa
  `false` mesmo bypassando o serviço; o serviço recusa `false` e `None` com a
  mesma frase; `true` é aceito e é o único valor gravado. Provado por mutação
  em 05/09/2026: trocar a checagem do serviço por uma que só barra `false`
  deixa 1 vermelho (ausência passa a ser aceita).
- **Célula dona:** cursos

### [INV-CI01] Portão Crítico é Fail-Closed
- **O quê:** todo portão crítico prova positivamente que executou a medição
  antes de devolver sucesso. A semântica é de quatro estados, e não de dois:

  | Situação | Estado | Exit |
  |---|---|---|
  | mediu e o estado está correto | `PASS` | 0 |
  | mediu e encontrou violação | `FAIL` | 1 |
  | **não conseguiu medir** | `ERROR` | 2 |
  | medição DECLARADA não aplicável | `SKIP` | 0 |

  É proibido o caminho `não conseguiu validar → PASS`. Em particular:
  ferramenta ausente, arquivo obrigatório ausente, raiz não resolvida, stdout
  vazio, exceção engolida, subprocesso sem propagação de exit code e `SKIP`
  inferido da ausência de evidência são todos `ERROR`. `SKIP` só existe quando
  alguém o declarou por escrito (ex.: `ci/manifesto-de-contratos.json`).
- **Por quê:** em 2026-08 o freeze de contrato imprimiu
  `✅ Freeze de contrato: OK` **com o contrato divergente**. O script chamava
  `python3`, que não existia naquela máquina; as duas pontas de
  `diff <(norm A) <(norm B)` viraram vazio; `diff(vazio, vazio)` deu igualdade.
  Uma ferramenta ausente virou aprovação. Um portão que só sabe dizer "não
  observei diferença" é indistinguível de um portão desligado — e o dia em que
  ele desliga sozinho é justamente o dia em que ninguém percebe.
- **Teste-Guarda:** `ci/tests/test_contract_freeze.py` — suíte adversarial que
  prova o portão reprovando quando deve: contrato divergente ⇒ `FAIL`;
  exportador quebrado, silencioso, ausente ou cuspindo lixo ⇒ `ERROR`;
  congelado ausente ou malformado ⇒ `ERROR`; raiz não resolvida ⇒ `ERROR`;
  dois lados vazios ⇒ `ERROR` (nunca `PASS`); `not-applicable` sem motivo
  declarado ⇒ `ERROR`. Roda no workflow `muralhas` a cada PR.
- **Célula dona:** o repositório (`ci/`) — não pertence a nenhuma célula.

#### Escopo de conformidade (atualize junto com a realidade)

INV-CI01 vale para os portões migrados. Declarar "CI fail-closed global" sem
esta tabela seria a mesma classe de erro que o invariante combate: afirmar mais
do que foi medido.

| Portão | Onde roda | Conforme? |
|---|---|---|
| freeze de contrato (`ci/contract_freeze.py`) | local + `make ci` da célula | **sim** |
| sonda de autenticação efetiva | junto do freeze | **sim** |
| cerca de célula · orçamento · guarda de segredos | workflow `muralhas` | **sim** |
| detecção de escopo + gate terminal (`ci-celula.yml`) | workflow `ci-celula` | **sim** |
| runner canônico (`ci/ci.py`) | local, `make`, workflow | **sim** |
| `contrato-check` dos 8 `services/*/Makefile` | `make ci` da célula | **não** — decide pelo disco em vez do manifesto (mitigado: a auditoria do manifesto roda em `muralhas` a cada PR) |
| merge guardado (`ci/mergear.py`) | terminal, antes do merge | **sim** — recusa check vermelho, ausente ou pulado sem declaração |
| **portão de deploy** (`ci/portao_de_deploy.py`) | workflows `deploy-celula` e `deploy-infra`, ANTES de build/SSH | **sim** — 25 testes adversariais (tabela de estados completa) em `muralhas` e `alarme-main`; **provado ao vivo em 22/08/2026**: commit vermelho mergeado de propósito ⇒ `portao: failure`, `deploy: skipped` (run 32567765127); revert verde ⇒ deploy executado (run 32567900961) |
| alarme da `main` (`alarme-main.yml`) | GitHub, após push na main | **não é portão** — avisa depois; modo de falha é "não avisou" |
| **branch protection** | GitHub | **sim, desde 26/08/2026** — ruleset `main protegida` (id 21570247): PR obrigatório, sem deleção, sem force-push, required checks `muralhas` + `ci-celula-gate`, `bypass_actors` vazio (`current_user_can_bypass: "never"`). Ver abaixo |

#### A cadeia de merge FECHOU em 26/08/2026

Um portão fail-closed só protege se algo exigir que ele passe. De 19/08 a
26/08/2026 nada exigia: o GitHub respondia à API de branch protection deste
repositório `Upgrade to GitHub Pro or make this repository public to enable this
feature. (HTTP 403)`, e o estado honesto era "o merge não é barrável; o deploy
é — e está barrado desde 22/08/2026".

**Deixou de ser.** Com o repositório público (23/08/2026), a proteção nativa
ficou disponível de graça e foi ligada em 26/08/2026 pelo agente, via API:
ruleset `main protegida` (id 21570247) — PR obrigatório na `main`, sem deleção,
sem force-push, e **required status checks `muralhas` + `ci-celula-gate`**,
ambos pinados ao app do GitHub Actions (`integration_id: 15368`).

Três escolhas de desenho que são parte do invariante, não detalhe:

- `required_approving_review_count: 0` e `require_code_owner_review: false` —
  obrigatórios num repositório de UM colaborador, que não pode aprovar o
  próprio PR (§1 H9): qualquer valor acima trancaria todo PR para sempre.
  A força aqui vem dos required checks, não de aprovação humana (Lei 4).
- **`ci-celula` NÃO é required check; `ci-celula-gate` é.** O primeiro fica
  `skipped` em PR que não toca célula, e required check `skipped` conta como
  satisfeito — seria [INV-CI01] violado pela porta da frente. O gate é o job
  terminal `if: always()` que consolida a tabela-verdade.
- `bypass_actors` vazio: `current_user_can_bypass: "never"`, inclusive para o
  dono da conta e para o agente que usa o token dele. Rulesets, ao contrário
  da branch protection clássica, não isentam administrador por padrão — foi
  por isso que se escolheu o ruleset. A saída de emergência é **desligar** o
  ruleset (`-f enforcement=disabled`), ato visível e auditável, nunca um
  bypass silencioso.

Prova de fora, medida no dia: escrita direta na `main` pela API — que ignora o
`.githooks/pre-push` local — recusada com **HTTP 409** `Repository rule
violations found / Changes must be made through a pull request. / 2 of 2
required status checks are expected.` Nada foi gravado. As regras que o GitHub
considera ativas se consultam em `repos/<owner>/<repo>/rules/branches/main`,
nunca na tela de settings.

O que isto **não** fecha: o run de deploy continua rodando depois do merge e
não é required check de nada — quem o barra é o portão de deploy (terceiro
degrau abaixo), e quem confere o veredito é o agente (CLAUDE.md). Armadilhas de
quem for mexer no ruleset: `armadilhas/126-ruleset-de-main-que-trava-todo-merge.md`.

(Correção de registro, 21/08/2026: o parágrafo anterior desta seção dizia
"decisão de custo consciente enquanto o projeto não fatura". Está incorreto —
é **impossibilidade de pagamento**: o cartão do mantenedor não é aceito pelo
GitHub e não há outra forma disponível. Não recomende "assine o Pro" — essa
porta está fechada. Ver ARMADILHAS-OPERACAO.md §1 H3.)

Os degraus grátis da Escada da Imposição (RITOS.md §2), em ordem de força:

1. `ci/mergear.py` — recusa mergear PR com check vermelho quando o merge sai
   do terminal. Não vê o botão do site. Desde 22/08/2026 é o caminho único
   legítimo de merge, executado pelo agente (Lei 4 — mergear é trabalho do
   agente; `--confirmo <N>` no lugar do prompt, e conferência `state=MERGED`
   embutida no próprio script).
2. `alarme-main` — abre issue se a `main` quebrar. Avisa depois; não impede.
3. **Portão de deploy** (`ci/portao_de_deploy.py`, 22/08/2026) — o degrau que
   faltava: ANTES de qualquer build ou SSH, prova que `ci-celula`,
   `alarme-main` e as muralhas do PR de origem estão verdes no commit;
   `skipped` não é verde; push direto na main não vira deploy; workflow novo
   e vermelho no mesmo SHA também barra. **Provado ao vivo**: merge vermelho
   deliberado ⇒ `deploy: skipped` (run 32567765127); revert verde ⇒ deploy
   executado (run 32567900961). O clique no botão continua livre — mas deixou
   de alcançar a produção, que é onde mora o cliente.

---

## Dívida de invariantes (nasce vazia — que permaneça assim)

| Código | O quê | Dono | Prazo | Motivo de estar sem guarda |
|---|---|---|---|---|
| — | — | — | — | — |

> Se esta tabela crescer, cada linha é uma esperança no lugar de uma lei.
