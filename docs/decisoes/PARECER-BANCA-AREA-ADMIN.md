# PARECER DA BANCA — auditoria do `PLANO-AREA-ADMIN.md`

> **Quatro cadeiras independentes**, convocadas pelo mantenedor em 25/08/2026,
> logo após o plano ser mergeado (PR #169). Cada uma auditou de um ângulo, sem
> ver o parecer das outras: **arquitetura de plataforma**, **segurança/IAM**,
> **entrega e operação (SRE)** e **produto/mantenedor**. Todas com acesso ao
> repositório e a ordem dura de **não confiar no que o plano afirma** — conferir
> contra o código e a configuração reais, citando arquivo:linha.
>
> Este documento é o **parecer**, não a decisão. O plano segue como está até o
> mantenedor decidir; o §1 abaixo é o que ele precisa decidir, e o §5 lista o
> que já foi corrigido no plano por ser **fato errado**, não divergência de
> opinião.

---

## §1 — O veredito das quatro cadeiras

| Cadeira | Veredito | A frase que resume |
|---|---|---|
| Arquitetura | APROVAR COM RESSALVAS | a célula própria está certa; o §5 (métricas) descreve um endpoint que **não pode existir como escrito** em 3 das 5 provedoras |
| Segurança / IAM | APROVAR COM RESSALVAS | a doutrina da porta está certa; a porta ainda **não aguenta** — cookie de 14 dias, zero CSP, sem re-autenticação para escrever produção |
| Entrega / SRE | APROVAR COM RESSALVAS | a ordem está certa; há um **deadlock que trava o mantenedor**, e a conta é ~30 merges, não 7–9 |
| Produto | **FAZER EM VERSÃO REDUZIDA** | o plano constrói o painel de instrumentos de uma loja que ainda não tem produto, cliente nem venda |

**Nenhuma cadeira recusou a arquitetura.** As três primeiras aprovam o desenho e
cobram correções antes do código. A quarta não discorda do *como* — discorda do
*quando* e do *quanto*, e é a única que propõe alternativa (§4).

---

## §2 — Os cinco achados que duas ou mais cadeiras encontraram sozinhas

Convergência independente é o sinal mais forte que uma banca produz. Estes cinco
foram achados por cadeiras diferentes, por caminhos diferentes:

### 2.1 O passo do mantenedor (H21) está num impasse circular — **corrigido no plano**

O plano entregava o script `provisionar-admin.sh` no PR 2 e mandava o mantenedor
executá-lo **antes** do merge do PR 2. Mas o comando que funcionou nos dois
precedentes busca o script **da `main`** (`infra/provisionar-identidade.sh:16`,
`curl -fsSL .../main/infra/...`) — onde ele ainda não estaria. O mantenedor seria
chamado para rodar um arquivo que não existe.

Os dois nascimentos anteriores já tinham resolvido isso, e o plano não copiou:
`sugestoes` mergeou o **PR #131 (o script sozinho, 1 arquivo)** dez minutos antes
do PR de infra; na `identidade`, o commit `a55a179` diz literalmente *"o script do
passo do mantenedor (H20), separado do compose"*.

A saída tentadora — o agente colar o corpo do script no chat — é a forma que
**falhou três vezes** neste projeto (H18, H19) e que o `RUNBOOK-LOTES.md` §36
proíbe. Achado das cadeiras de **Entrega** e **Produto**.

### 2.2 O PR de nascimento não cabe em 15 arquivos — **corrigido no plano**

O plano afirmava *"cada PR respeita o orçamento de 15 arquivos — a conta já foi
feita no papel"*. A conta refeita pela cadeira de Entrega, item por item, dá
**~21 arquivos**; e os dois precedentes medidos foram **24** (gênese `sugestoes`,
PR #108) e **44** (gênese `identidade`, PR #142) — ambos com a label
`arquitetural`, que é a válvula prevista pelo próprio portão
(`ci/orcamento-de-mudanca.sh:25`).

O esqueleto Django é indivisível: partir o PR é pior, porque meia-célula não passa
no `make ci`. E a `armadilhas/077` fecha o cerco: abrir o PR já com
`--label arquitetural` **não funciona** (o evento `opened` sai com `labels: []`) —
é preciso `gh pr close && gh pr reopen`. Achado das cadeiras de **Entrega** e
**Arquitetura**.

### 2.3 A Fase 2 (métricas) custa o dobro do declarado, e chama o mantenedor 5 vezes

O plano dizia *"uma célula provedora por PR"*. Mas as cinco provedoras são todas
`freeze: required` (`ci/manifesto-de-contratos.json`), o endpoint novo entra no
schema exportado, e `ci/cerca-de-celula.sh:46-51` proíbe `contracts/` no mesmo PR
que `services/`. Logo: **2 PRs por célula**, e cada mudança de contrato exige o
Rito §3 — *"sessão de arquitetura com o mantenedor presente"*.

Conta real: **11 PRs + 5 sessões com o mantenedor**, não 5 PRs de agente. As duas
cadeiras chegaram ao mesmo número por caminhos independentes. É o padrão 5 da
retrospectiva (*humano no caminho crítico*) voltando pela porta dos fundos.

### 2.4 `/interno/metricas` não existe como lugar uniforme — e não é privado

Duas descobertas empilhadas:

**(a) O mount não é o mesmo.** `/interno` só existe em duas células
(`sugestoes`, `identidade`). As outras montam em `/api/<celula>/`
(`leads`, `alunos`, `catalogo`) — e o mount está gravado no `servers:` do contrato
congelado de cada uma. A saída "uma segunda instância `NinjaAPI` montada em
`/interno`" é a pior possível: o exportador importa **um** objeto
(`from config.api import api`), então o endpoint novo **não entraria no schema**,
o freeze continuaria `PASS`, e a plataforma ganharia superfície HTTP autenticada
fora de qualquer contrato — a `armadilhas/041` em pessoa.

**(b) A afirmação "sem rota no Traefik / pela rede interna do Docker" é FALSA
para as células servidas sob prefixo — e eu medi de fora para confirmar:**

```
GET https://meshcraft.top/forms/sugestoes/interno/sessao   → 401 {"detail": "Unauthorized"}
GET https://meshcraft.top/alunos/api/alunos/matriculas     → 405 (rota existe, método errado)
GET https://meshcraft.top/interno/sessao                   → 404 (a identidade, essa sim, é interna)
```

O Traefik **não remove o prefixo** da célula, então tudo que a célula serve —
inclusive a API de máquina — fica alcançável pela internet no endereço com
prefixo. **Não é vazamento**: o Bearer estático protege, e o 401 prova que
protege. Mas é uma topologia diferente da que o plano descreveu, e para o admin
muda o desenho: o endpoint de métricas nasceria exposto à internet, defendido só
por um token que não expira nem rotaciona. Achado das cadeiras de **Arquitetura**
e **Segurança**; medição de fora feita na sessão raiz.

### 2.5 O token do admin nas provedoras concede **escrita**, não leitura

O plano descreve as métricas como *"leitura"* e propõe autenticá-las com
`TOKENS_ACEITOS_ADMIN`. Mas `TOKENS_ACEITOS` é um **conjunto plano, sem escopo**
(`services/catalogo/apps/core/auth.py:15` e idênticos): qualquer token do conjunto
vale para **toda** operação da API daquela célula. Pôr o token do admin nos envs
de `leads` e `alunos` daria à área administrativa autoridade sobre
`POST /leads`, `POST /leads/{id}/tags` e `POST /matriculas`.

E o §4.5 do plano (formulários sobre a API do `catalogo`) piora: no dia em que
existir escrita no catálogo, o mesmo token plano dá poder de **mudar preço de
oferta** — a matéria-prima do `[INV-P2]`, com a seção "Vendas" formalmente
congelada ao lado.

**A plataforma já inventou a solução para exatamente isto**: a `identidade`
resolveu "este par pode ver e-mail?" com uma **segunda lista** conferida no
handler (`TOKENS_COMPLETOS`), não no auth. O mesmo padrão vira
`TOKENS_SOMENTE_LEITURA_<PAR>`, com teste-guarda. Achado da cadeira de
**Arquitetura**.

---

## §3 — Os achados de uma cadeira só que mudam o desenho

### 3.1 Segurança: a porta, hoje, não aguentaria

Quatro defeitos empilhados, todos verificados no código:

1. **Zero CSP no repositório inteiro** (`grep -rn "Content-Security-Policy"` →
   nenhuma ocorrência). O cookie é `Path=/`, então **qualquer XSS em qualquer
   página de `meshcraft.top`** pode fazer `fetch('/admin/...')` com a sessão do
   administrador anexada pelo navegador. O `HttpOnly` não ajuda: o script não
   precisa ler o cookie, só usá-lo. E o próprio plano cria três fontes novas de
   XSS (§4.3 sobe HTML, §4.8 renderiza markdown, §4.2/4.4 exibem dado de outras
   células).
2. **A sessão vale 14 dias** — `SESSION_COOKIE_AGE` não está definido em lugar
   nenhum, então vale o default do Django — **sem revogação que o mantenedor
   alcance** (o guarda `test_inv_revogacao.py` diz, com todas as letras, que a
   única revogação existente é apagar a linha no banco, e não há tela para isso)
   e **sem re-autenticação** para escrever configuração de produção.
3. **A porta fecha mandando para o login — que é exatamente o que caiu.** Se a
   `identidade` sai do ar, `/admin/` responde 302 → tela de login → o botão dela
   aponta para a identidade → 502. O console de operação morre junto com a coisa
   que ele existe para diagnosticar, e não há break-glass (Lei 5 nega SSH ao
   agente). A correção é distinguir duas falhas que o plano fundiu: "não há
   sessão" → 302; "**não consegui perguntar**" → 503 com página em português.
4. **O `frameDeny: true` do Traefik quebra a galeria (§4.3) antes de ela
   existir** — `X-Frame-Options: DENY` bloqueia iframe **inclusive de mesma
   origem**, e só em produção (em dev não há Traefik). O conserto tentador —
   afrouxar o middleware `seguranca` — enfraqueceria `checkout` e `pagamentos`
   junto. A saída é cadeia própria para o router do admin.

### 3.2 Segurança: existe um desenho melhor, que dispensa o e-mail

A `identidade` já devolve, no `/sessao` **simples**, um identificador opaco,
estável e cunhado pela própria plataforma (`Identidade.id`, `token_urlsafe(16)`).
Autorizar por **`ADMIN_IDS`** em vez de `ADMIN_EMAILS`:

- dispensa `TOKENS_COMPLETOS_ADMIN`, o registro na lei da identidade §6.3 e
  **toda a superfície de dado pessoal** na célula admin;
- é mais correto: o e-mail é identificador controlado pelo **Google**, não pela
  plataforma. Se um dia a lista nomear um endereço em domínio administrado por
  terceiro (Workspace de empresa), quem administra aquele domínio cunha uma conta
  naquele endereço e entra;
- o custo é o bootstrap: o mantenedor não lê um id opaco de uma tela onde ele não
  consegue entrar — resolvível exibindo o id na página de conta do `funil`.

A terceira opção (a identidade responder um booleano "é admin?") **deve ser
recusada**, e o plano já a recusa corretamente: moveria a autorização para dentro
da identidade, contra a lei.

### 3.3 Arquitetura: a alternativa que ninguém pôs na mesa — métricas por evento

A tabela de alternativas do plano discute **onde a área admin mora** e nunca
discute **como os dados chegam nela**. A plataforma já tem barramento de eventos
versionado, com consumidor rodando em quatro células — e `contracts/eventos/` já
publica exatamente o que o §4.2 quer da Caixa: `sugestao.criada.v1`,
`voto-adicionado`, `voto-removido`, `status-alterado`, todos com `site_id`.

Um `admin-consumer` construindo read model no `admin_db` é a **Virtude da Lei 3**
literal (*copiar dados; snapshots são sagrados*), e faz `sugestoes` — a **primeira**
da fila do plano — custar **zero**: nenhum Rito §3, nenhum token novo, nenhuma
sessão com o mantenedor. O limite honesto: `leads`, `alunos` e `identidade` não
emitem evento de criação, então o desenho certo é **híbrido** — evento onde já há
evento, HTTP onde não há.

**Isto é uma pergunta para o mantenedor, não para o agente:** a métrica pode ser
de "há alguns segundos" (evento, barato) ou precisa ser "agora" (HTTP, 5 ritos de
contrato)? O plano decidiu por ele, em silêncio.

### 3.4 Arquitetura: a célula nasceria sem constituição — e a `identidade` também não tem

O plano não menciona `constituicoes/AGENTS.admin.md`. Não é esquecimento isolado:
`constituicoes/` tem 9 arquivos e **não tem `AGENTS.identidade.md`** — `grep` no
repositório inteiro devolve zero ocorrências, e nenhum portão cobra isso. Todo
despacho da célula abriria citando um arquivo inexistente, e é justamente ali que
moram **Fronteiras** e **Comunicação**, que a `armadilhas/066` manda ler juntas
quando a célula chama outra API. A `admin` chamaria seis. **Dívida existente,
descoberta de carona** — registrada no `ARMADILHAS-OPERACAO.md` §9.

### 3.5 Produto: o congelamento arquitetural que o plano não mencionou

`SINTESE-E-PLANO.md` §4, citado como *premissa inegociável* em `PLANO-10X.md:14`:
**"nenhuma célula, rito ou generalização nova até um piloto pago rodar"**. Já foi
quebrado duas vezes (`sugestoes`, `identidade`); a `admin` seria a terceira. O
plano não cita essa premissa em lugar nenhum — e citá-la é obrigação de quem
propõe, mesmo que a decisão do mantenedor seja quebrá-la de novo.

### 3.6 Produto: marketing não é venda — e foi congelado por engano

O mantenedor pediu **"vendas, marketing"**; o plano jogou os dois na mesma caixa
congelada. Congelar **vendas** está certo e o plano acertou em blindar isso.
Congelar **marketing** é erro de categoria: quantas pessoas visitam o site,
quantas deixam e-mail no `/cadastro`, quantas completam o quiz, por idioma e por
site — **isso existe hoje, é dado real, e não encosta no Mercado Pago.**

E a inversão que importa: métricas de venda nunca fariam ninguém querer vender —
seriam zeros. O que produz a ordem *"o site vai vender"* é ver **pessoas
deixarem e-mail sem que exista produto**. A recomendação é separar em **Vendas
(congelada)** e **Público & demanda (liberada)** — e esta deveria ser a primeira
seção de métricas, não a última.

### 3.7 Produto: o que ele pediu e o plano não tem

1. **A caixa "Precisa de você agora"** — o bloco mais usado do painel atual, a
   pergunta que ele faz todo dia. Não existe equivalente nas 8 seções.
2. **"O que os robôs fizeram/estão fazendo"** — PRs, merges, deploys. O plano
   oferece `/healthz` no lugar, que é a pergunta de um engenheiro.
3. **Editar o conteúdo do site** — `docs/landing-pages/` está vazia, a vitrine é
   o maior risco declarado do projeto, e nada no plano deixa o dono mudar uma
   palavra. "Área administrativa onde o dono não edita o próprio site" é a
   decepção mais previsível deste desenho.
4. **Aviso que chega até ele.** O plano constrói um lugar para ele *ir olhar*;
   ninguém olha painel às 2h da manhã.

---

## §4 — A alternativa da cadeira de produto: "O Mirante"

> ⚠️ **[SUPERSEDIDO em 25/08/2026]** — o mantenedor decidiu, por escrito, que
> este projeto é para ser feito completo, não minimalista
> (`docs/decisoes/DECISAO-filosofia-de-escopo.md`). A recomendação de adiar a
> área admin por um recorte reduzido **não vale mais como recomendação a
> seguir** — a pergunta 1 do §7 abaixo está fechada: **plano completo.** A
> análise técnica que segue continua registrada porque descreve fatos reais
> (custo de oportunidade, o que já existe na fila) — não porque a conclusão
> dela ("fazer menos") ainda esteja de pé.

Recorte que entrega a dor real (ver os painéis fora do PC) pelo menor custo:

- **1–2 PRs na célula `funil`** — ela já serve páginas, já tem cliente de sessão
  da `identidade`, já faz deploy a cada merge e já está presa a
  `Host(meshcraft.top)`. Rota `/painel/`: exige sessão → confere lista → serve os
  painéis. **Zero célula nova, zero banco novo, zero auditoria** (não há escrita
  para auditar).
- **Os painéis passam a ser versionados** (hoje `arquivos/` está inteiro no
  `.gitignore` e existe só no PC dele), então cada merge republica sozinho — o
  que mata o upload manual da galeria.
  ⚠️ **Ressalva que a própria cadeira levantou e não resolveu:** o repositório é
  público, e os painéis descrevem buracos abertos em português claro. Versioná-los
  exige ou revisar o texto, ou mantê-los fora do git e subi-los por outro caminho.
- **Um passo do mantenedor, de UMA linha**, como script versionado — o molde do
  `provisionar-identidade.sh`, que deu certo de primeira.

**Custo: 1–2 PRs** contra os ~26–33 merges do plano completo.

**E um passo 0, de custo zero, que vale tentar antes de qualquer decisão:** o
repositório inteiro já mora dentro do OneDrive, e o `painel-retomada.html` é
autocontido (nenhum arquivo ao lado). **Abrir o app do OneDrive no celular e
tentar abrir esse arquivo** pode resolver 80% da dor por R$ 0,00. (O
`painel-fundacao.html` não abriria assim — depende do `painel-dados.js` ao lado;
consertar isso é 1 PR, não 20.)

---

## §5 — O que já foi corrigido no plano (fato errado, não divergência)

Três afirmações do plano eram **falsas** e foram corrigidas na mesma sessão, com
ponteiro para este parecer. Deixar afirmação falsa num documento que vira lei é
o padrão 2 da retrospectiva (*garantia declarada sem mecanismo apodrece*):

| Onde | Dizia | Passou a dizer |
|---|---|---|
| §5 | métricas por `/interno/metricas`, "sem rota no Traefik" | o mount varia por célula, e nas células sob prefixo a superfície **é** alcançável pela internet (medição de fora no §2.4) |
| §6 | "cada PR respeita o orçamento de 15 arquivos" | PR 1 é gênese: ~21 arquivos, label `arquitetural`, com o truque do `close && reopen` da `armadilhas/077` |
| §6 | "7–9 merges" | 7–9 abre a porta; o §4 inteiro é da ordem de **30 merges**, e a Fase 2 sozinha são 11 PRs + 5 sessões |

O deadlock do H21 (§2.1) também foi corrigido: o script passa a ter **PR próprio,
mergeado antes** do passo do mantenedor.

---

## §6 — O que a banca confirmou que está certo

Vale registrar, porque um plano só com críticas não ajuda a decidir:

1. **A decisão central — célula própria `admin` — está certa**, e nenhuma das
   quatro cadeiras a contestou. As três alternativas do §2 foram descartadas por
   motivo real (a cadeira de arquitetura conferiu a mais forte: pôr a área admin
   no `funil` é pô-la no catch-all multissítio).
2. **"Só variável de ambiente na `identidade`" é VERDADE** — as duas cadeiras que
   verificaram confirmaram `config/settings.py:108-124`: os conjuntos são montados
   por compreensão sobre `os.environ`. Zero código. Consequência boa que o plano
   nem reivindicou: o PR da porta **não toca `services/identidade`**, logo não
   esbarra na muralha "1 PR = 1 célula".
3. **`admin` passa nas regras de verdade do guarda de rotas** — 5 letras, sem
   forma de locale, sem colisão com idioma declarado. Só o inventário cresce, em
   **três lugares** do mesmo arquivo (a cadeira de entrega localizou os três).
4. **A inversão fail-closed é consistente com a lei**, não a contradiz: o §4 da
   `DECISAO-onde-mora-a-sessao.md` manda fail-OPEN para *reconhecimento* e
   fail-CLOSED para *autorização*, e a porta do admin é autorização.
5. **`Host(meshcraft.top)` explícito, com o motivo transcrito** — o plano leu uma
   auditoria anterior e aplicou, em vez de repetir o erro. É o catálogo de
   armadilhas funcionando como projetado.
6. **Rollback no PR 1** (`armadilhas/076`), **`not-applicable` no manifesto com
   motivo** (economiza um PR inteiro em relação à `identidade`), **a ordem macro
   gênese → provisionamento → infra → porta** (a dos dois precedentes), e **o
   aviso antecipado do vermelho esperado** — todos confirmados corretos.
7. **§8.3 (nada de vendas) é exemplar** — diretiva respeitada por escrito, com
   mecanismo, proibindo até o tile de métrica e declarando fora de mandato quem
   tentar.

---

## §7 — As perguntas que sobraram para o mantenedor

Nenhuma delas é decisão de agente:

1. ~~Fazer agora, ou fazer o Mirante e esperar?~~ **[RESPONDIDA em 25/08/2026]
   — plano completo.** O mantenedor decidiu por escrito
   (`DECISAO-filosofia-de-escopo.md`) que este projeto sempre escolhe a opção
   completa sobre a reduzida, mesmo custando mais tempo — inclusive quebrando
   de novo, deliberadamente, o congelamento arquitetural do §3.5.
2. ~~A área admin vai ESCREVER no catálogo, ou só ler?~~ **[RESPONDIDA] Só
   ler.** Decidido pelo mesmo caminho de pergunta estruturada — §4.5 do plano
   é somente-leitura; editar continua por PR. Fecha o achado A2/2.5 de fato:
   sem escrita nenhuma no catálogo, a autoridade sobre preço de oferta nem
   chega a existir na área admin.
3. ~~A métrica pode ser de "há alguns segundos" (evento, barato) ou precisa
   ser "agora" (HTTP, 5 ritos de contrato)?~~ **[RESPONDIDA] Agora, sempre
   exata.** HTTP direto, aceitando os 5 Ritos de Contrato — vista a opção
   barata, escolhida a cara, de olhos abertos.
4. ~~A área que escreve configuração de produção mora na mesma origem e na
   mesma sessão que os visitantes comuns do site?~~ **[RESPONDIDA] Sim — opção
   (a): mesma origem com compensações** (CSP própria + verificação de frescor
   de sessão para escrita, em vez de encurtar a sessão do site inteiro). Sem
   login próprio, sem domínio separado.
5. ~~Marketing sai do congelamento junto com vendas, ou vira seção própria?~~
   **[RESPONDIDA] Seção própria, liberada desde já** (§4.6b do plano).
6. ~~O que ele faz às 2h quando a porta do admin estiver fechada contra ele?~~
   **[RESPONDIDA] O conserto normal já basta** — PR pequeno pelo pipeline,
   poucos minutos, sem precisar do servidor; nenhum botão de emergência à
   parte. Combina com a Lei 5 da Constituição (emergência é sempre pipeline).

## Estado

**Parecer emitido em 25/08/2026, e as seis perguntas do §7 respondidas pelo
mantenedor no mesmo dia** — todas colhidas por pergunta estruturada de
múltipla escolha, formato que ele confirmou como o certo para toda decisão
dele daqui em diante. O plano (`PLANO-AREA-ADMIN.md`) já reflete as seis
respostas nas seções técnicas. Falta só ele dizer "aprovado" para o PR 1
começar.
