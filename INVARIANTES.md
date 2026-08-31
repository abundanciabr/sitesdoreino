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
  `services/forum/tests/test_inv_forum_nao_assina_sessao.py` e
  `services/gamificacao/tests/test_inv_gamificacao_nao_assina_sessao.py` —
  medem a
  CONFIGURAÇÃO da célula (sem SessionMiddleware, sem django.contrib.sessions
  e sem SESSION_ENGINE no settings dela), porque sem essas três
  `request.session` nem existe. Provados por mutação na gênese de cada uma:
  instalar o SessionMiddleware deixa o guarda vermelho. O do `forum`
  (28/08/2026) acrescenta um quarto caso, o do cookie de CSRF com nome
  próprio — não é sessão, mas é o mesmo problema de vizinhança: quatro células
  no mesmo host gravando `csrftoken` é uma invalidando o formulário da outra.
- **Célula dona:** identidade (única emissora) — guarda plantado em `admin`,
  a primeira célula a nascer **depois** da regra, e replicado em `forum` e em
  `gamificacao`;
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

---

## Invariantes da própria CI

Os invariantes acima protegem a plataforma. Este protege o INSTRUMENTO que
verifica os outros — porque um portão que erra para o lado do verde não protege
coisa alguma, e ainda gasta a confiança de todo mundo.

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
