# Constituição da Célula: pages (a casa das Páginas do aluno)
> **Jurisdição:** governa apenas `services/pages/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA (nascida em 05/09/2026, PR de gênese, TAR-169; o corredor
> `docs/changespecs/CS-PAGES-0001.md` foi assinado pelo mantenedor na ideia 21
> no mesmo dia) · **Merge:** pela pista (`ci/mergear.py --pousar`), com CI verde

## Missão
Tirar o aluno do ponto em que ele termina as aulas e trava: ele não sabe o que
entra no portfólio, o que fica de fora, quando a peça está boa o bastante para
mostrar a um cliente pagante, nem para onde mandar o resultado quando termina.
A célula guarda o roteiro, a curadoria, o semáforo por peça, o pedido de
conferência humana, o selo da escola e o link que ele manda ao cliente.

**E ela é a ÚLTIMA casa nova do site**, de propósito. `pages` não é a célula do
portfólio: é o guarda-chuva das Páginas do aluno, e o portfólio é a primeira
delas. Palavras do mantenedor em 02/09/2026: *"quero `pages` porque podemos
criar todo tipo de ferramentas, portfólio, estúdio, e etc"*. O caro nesta
plataforma nunca foi a tela, foi a fundação (banco, provisionamento, rota e o
passo manual que só ele executa); com a casa guarda-chuva esse pedágio é pago
UMA vez, e da segunda página em diante o custo é um PR de tela e zero passo
dele.

Lei do assunto: `docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md` (a casa, os dois
endereços, a escada de 18 degraus, as duas decisões do mantenedor, o que
ninguém pode inventar e os critérios da professora). O corredor assinado, com
os vinte critérios de aceitação e a lista nominal de células proibidas:
`docs/changespecs/CS-PAGES-0001.md`.

**Esta constituição foi escrita a partir do CÓDIGO desta gênese**, não da
intenção: na gênese a célula tem UMA rota (`/healthz`), nenhuma tabela, nenhum
cliente e nenhuma tela. Tudo o que está descrito abaixo como "expõe" e
"consome" é o destino da escada, não o estado do disco, e cada linha diz em que
degrau ela vira código.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/pages/**`
- **SOMENTE LEITURA:** `contracts/identidade.openapi.yaml` (é por ele que se
  pergunta quem é a pessoa), `contracts/alunos.openapi.yaml` (é por ele que se
  sabe se ela tem matrícula ativa), `contracts/eventos/pages.portfolio.*` (o
  que esta célula promete emitir, congelado no degrau 03) e
  `contracts/eventos/notificacao.devida.v1.json` (o sininho)
- **PROIBIDO (nem ler):** as demais células, `infra/`, qualquer segredo de
  pagamento. O corredor lista uma por uma: `alunos`, `catalogo`, `checkout`,
  `cursos`, `encomendas`, `forum`, `identidade` (escrita proibida; só a leitura
  de quem é a pessoa pelo contrato), `leads`, `metricas`, `notificacoes`,
  `pagamentos`, `quiz` e `sugestoes` (leitura direta proibida; só o fluxo
  normal de fases pela gestão)
- **Os degraus vizinhos são de OUTRAS células, cada um em PR próprio:**
  `gamificacao` (15, acender o marco), `admin` (16, os guias no editor de
  documentos), `mensageria` (17, a sequência do convite), `funil` (18, o
  caminho no menu). Nenhum deles se escreve daqui. `contracts/` (03) e `infra/`
  (04 e 05) são caminho CODEOWNERS e pedem mandato escrito no despacho

## Comunicação
- **Expõe (telas):** DOIS endereços públicos, e essa é a marca desta casa
  (plano §4). `meshcraft.top/pages/...` é a área do aluno logado, onde mora a
  Prancheta (degrau 07) e as peças (08); `meshcraft.top/estudio/<apelido>` é a
  vitrine pública (13), endereço curto de propósito, porque é o link que o
  aluno manda ao cliente no chat de um freelancer. Os dois prefixos apontam
  para a mesma célula no Traefik. **Como os dois entram no Django é decisão do
  degrau 05**, e o motivo de ela não estar tomada na gênese está escrito em
  `config/settings.py`: `FORCE_SCRIPT_NAME` carrega um prefixo só. Na gênese a
  única rota que responde é `/healthz`. Telas são formulário normal com
  melhoria progressiva: nenhum caminho desta célula pode existir só com script
  (regra do fórum, herdada)
- **Expõe (contrato):** os eventos `pages.portfolio.*`, congelados no degrau
  03, em PR próprio. É por eles que a gamificação sabe do selo. Nada responde
  pela borda pública sem Bearer, e `/interno` **não** fica escondido pela
  topologia: com `SCRIPT_NAME` ligado, tudo o que estiver na raiz do urlconf é
  alcançável em `/pages/<caminho>` pela internet (`armadilhas/186`, provado em
  `tests/test_healthz_script_name.py`). Quem fecha a porta é o Bearer
- **Consome:** `identidade` (quem é o dono do cookie) e `alunos` (matrícula
  ativa), server-side, com timeout explícito, a partir do degrau 06. Na gênese
  `celulas.yml` diz `consome: []`, com o comentário que explica a lista vazia
  (`armadilhas/224`); cada linha entra no PR do cliente que a lê
- **Auth:** Bearer dedicado por par, `TOKENS_ACEITOS_<PAR>`. Env ausente ⇒
  conjunto vazio ⇒ 401 para todo mundo (fail-closed sem derrubar o boot)
- **Emite:** `pages.portfolio.*` e `notificacao.devida.v1` (o sininho avisa o
  selo, no degrau 12, e a peça quebrada, no 08), pelo padrão outbox + relay
  Huey. **Só ids opacos viajam**: legenda, link, e-mail e nome nunca
- **Banco:** `pages_db` (role `pages_user` — não enxerga nenhum outro
  database). Guarda o portfólio, as peças, os itens de conferência e o estado
  do aluno (degrau 02). **Nenhuma chave estrangeira cruzando banco de célula**
  (critério AC-02): quem é a pessoa se pergunta à `identidade`, e a matrícula à
  `alunos`

## Invariantes desta célula

- **[INV-P12] Esta célula NÃO assina sessão.** Sem `SessionMiddleware`, sem
  `django.contrib.sessions`, sem `SESSION_ENGINE`, cookie de CSRF com nome
  próprio (`pages_csrf`). A célula repassa o cookie recebido à `identidade` e
  pergunta quem é. Guarda: `tests/test_inv_pages_nao_assina_sessao.py`,
  plantado na gênese e **provado por mutação**. Aqui a tentação tem nome: a
  **Prancheta guarda progresso**, e "o que esta pessoa já marcou?" pede
  memória. O caminho curto é `request.session[...]`, que deslogaria o site
  inteiro sem erro em lugar nenhum (`armadilhas/143`) — e que reprovaria o
  próprio critério AC-06 antes disso, porque ele exige que a marcação
  atravesse APARELHOS, coisa que sessão não faz. O estado mora no MODELO, por
  aluno.

- **A foto entra por LINK COLADO, e esta célula NUNCA guarda arquivo.**
  Decisão do mantenedor em 01/09/2026 (plano §6.2), tomada com o preço na mão.
  O aluno cola o endereço do render que já está no Drive, no ArtStation ou onde
  ele guarda. Três consequências foram aceitas por escrito e não se
  redescobrem por acidente: link de aluno quebra e a escola não consegue
  consertar (mitigação nos critérios AC-08 e AC-09: conferir o link quando ele
  é colado, medir depois, avisar pelo sininho, **nunca apagar sozinho**); a
  página pública passa a exibir imagem de domínio de terceiro, e nenhuma outra
  tela desta plataforma faz isso hoje, então a política de conteúdo da página
  é decisão de segurança com teste próprio no degrau 13; e o selo "conferido
  pela escola" vale para o que o monitor VIU no dia, o que o texto do selo tem
  de dizer. **O envio de imagem hospedada por nós (degrau 09) está FORA do
  escopo e não se constrói antes de ele pedir** — a porta de volta é barata (o
  campo do link e o de uma imagem nossa cabem no mesmo modelo), e é isso que a
  mantém fechada sem custo.

- **A vitrine é opt-in, e o `noindex` não é negociável.**
  `/estudio/<apelido>` só existe se o aluno ligar; despublicar tira a página do
  ar imediatamente; e a página **não expõe e-mail, telefone nem nome
  completo** — só apelido, obras aprovadas e marcos escolhidos (critérios
  AC-13 e AC-14, plano §7). Padrão é privado.

- **A peça tem UMA casa.** O portfólio não guarda cópia de medalha, a
  gamificação não guarda cópia de peça, a `encomendas` não constrói um segundo
  portfólio. A tela que precisa das duas pergunta por HTTP com falha ABERTA, o
  mesmo desenho já usado entre fórum e gamificação, e nunca por chave
  estrangeira cruzando banco.

- **Isolamento entre alunos.** O progresso e as peças de um aluno nunca
  aparecem para outro, em nenhuma tela e em nenhuma resposta de API
  (critério AC-07). Vale inclusive para a vitrine: o que ela mostra é o que
  aquele aluno publicou, e nada mais.

## O que ninguém pode inventar aqui (plano §7)
Sete itens, e a lista é fechada:

1. **Nota, estrela, ranking ou voto popular** em portfólio ou em peça de aluno.
2. **Detecção de "isto foi feito por IA"** — proibida por escrito.
3. **Trancar aula ou conteúdo do curso** atrás de check-list, ponto ou nível
   (invariante 3 da economia: aula nunca fica atrás de jogo).
4. **E-mail, telefone ou nome completo na página pública**; padrão é privado e
   o `noindex` não é negociável.
5. **Guardar a peça em duas células.**
6. **Travessão em texto que o aluno lê** (`ci/travessao.py`).
7. **Marco real pagando XP** (decisão 7 da Sessão A: o marco do portfólio vale
   zero, de propósito).

## Critérios de morte
Se a construção começar a desenhar qualquer um dos sete acima, ou um segundo
portfólio, ou armazenamento de arquivo nesta célula sem o mantenedor ter pedido
o degrau 09, **pare e reabra a decisão** com ele.

## O que esta célula ainda NÃO resolveu
Registrado para ninguém achar que foi esquecimento:

1. **Como os dois prefixos entram no Django** (`/pages` e `/estudio` com um
   `FORCE_SCRIPT_NAME` só). Decisão do degrau 05, com o inventário de rotas na
   mão; as duas mecânicas candidatas estão nomeadas em `config/settings.py`.
2. **O texto dos guias**, que é do mantenedor ou é a aprovação do rascunho que
   o degrau 16 deixa pronto no editor de documentos. O rascunho da professora
   está no §8 do plano, sem correção e sem reescrita, e as quatro regras
   objetivas que saem dele (pelo menos 3 tipos, pelo menos 3 peças de cada,
   maioria high poly, não repetir o modelo da aula) são o que o degrau 07 lê do
   banco.
3. **Quem confere o portfólio na fila da equipe** e com que prazo (degrau 11,
   pelo molde da tela de marcos).

## Estado da construção
O estado de cada degrau se lê **no balcão** (`python ci/fila.py listar
--ao-vivo`), nunca aqui. A escada inteira (18 degraus, sem o 09) está no §5 do
plano. **Até o degrau 05 (compose + Traefik), o `deploy-celula` desta célula
fica vermelho — isso é esperado** (`armadilhas/088`), e o degrau 04 (o
provisionamento sozinho) tem de vir antes, em PR próprio, porque compose junto
com a gênese trava os DOIS deploys sem rerun que resolva (`armadilhas/134`).
