# DECISÃO — a gamificação da escola nasce como célula própria (Sistema de Formação de Criadores)

> **Aprovada pelo mantenedor em 30/08/2026, na Sessão A** (registro
> `20260830-061` no livro), depois de ele ler o plano traduzido. É a sexta vez
> que o congelamento arquitetural é reaberto nominalmente — depois de
> `sugestoes`, `identidade`, `notificacoes`, `admin` e `forum`.
>
> **A ENGENHARIA NÃO SE REPETE AQUI.** Ela mora em
> `docs/decisoes/PLANO-CELULA-GAMIFICACAO.md` — modelo de dados, eventos,
> superfícies, a escada de 22 PRs, riscos e critério de morte. A
> RASTREABILIDADE de cada decisão de produto mora em
> `docs/consultorias/gamificacao/VEREDITO.md` (6 pareceres + 5 auditorias). O
> manual de produto é o **Playbook da Gamificação** (artefato do mantenedor,
> 30/08/2026).
>
> Este documento é a **LEI**: o que vale, o que é proibido, quem decidiu o quê,
> e o que já está fechado e não se reabre.

## 1. A decisão

Nasce a célula **`services/gamificacao`**, Django + django-ninja como todas as
outras, com **banco próprio** (`gamificacao_db`), **role próprio**, **processo
próprio** e **contrato próprio**.

Ela transforma o que a plataforma JÁ afirma por evento (quiz completado,
sugestão criada e votada, e — com os eventos novos da Sessão B — o fórum) em
XP, níveis, Sequência semanal, Forja, missões, medalhas, Marcos de carreira,
Cristais e cosméticos.

**Nenhum plugin ou SaaS de gamificação entra.** Os três motivos, na ordem em
que pesaram: dados de menores em terceiro (Lei 2); economia *earn-only* com
marcos validados por gente não existe de prateleira; e calcular XP dentro do
fórum ou da Caixa violaria a Lei 3 e o §4.7 do fórum.

**A objeção do fórum, respondida:** a lei do fórum manda parar se alguém
recriar um framework de reputação do zero. Esta decisão É a reabertura formal
daquele ponto, e a resposta é que a reputação **não mora no fórum** — ele só
(a) afirma fatos por evento e (b) exibe um selo vindo por HTTP, com falha
ABERTA. O critério de morte do fórum permanece intacto.

## 2. A hierarquia que decide todo conflito de desenho

> **Realidade > Criação > Maestria > Comunidade > XP.**

A espinha do sistema é a trilha de **marcos reais** (obra → portfólio →
cliente → dólar → contribuição → legado). O pacote no estilo Duolingo (XP,
níveis, missões, sequência) é o **andaime** — e nenhuma tela mostra o andaime
acima da espinha.

Pergunta de ouro de toda mecânica nova: *"Se o aluno parar de receber esta
recompensa amanhã, ele continuará valorizando o que aprendeu e criou?"*

E o objetivo declarado, que soa estranho e é sério: **a gamificação existe para
se tornar progressivamente menos necessária.**

## 3. Os três invariantes da economia — com teste no CI

Nascem como testes no PR 3 da escada e **nunca se flexibilizam**:

1. **Nada por dinheiro real.** Nenhum item, moeda, proteção ou vantagem se
   compra. Cristais são *earn-only* por construção do banco
   (`CheckConstraint`), não por convenção.
2. **Cosmético é só estética.** Nunca vantagem em XP, ranking ou visibilidade.
3. **Aula nunca fica atrás de jogo.** Conteúdo educacional jamais trancado por
   XP, nível ou Cristal.

## 4. O endereço é lei

A célula serve em **`meshcraft.top/conquistas` — caminho, NUNCA subdomínio**,
pela mesma razão do fórum: o cookie `meshcraft_sessao` é de host, e em
`conquistas.meshcraft.top` ele não viaja — a célula passaria a exigir um
segundo login.

`/conquistas` e não `/xp`: dez letras, longe de qualquer forma de código de
idioma (`armadilhas/089`). O inventário de rotas
(`ci/tests/test_rotas_sem_forma_de_locale.py`) entra no **mesmo PR** do
Traefik, não antes.

A vitrine pública do aluno mora em **`meshcraft.top/estudio/<apelido>`**
(decisão 3 da Sessão A). O prefixo `/estudio` precisa ser **conferido contra o
guarda de rotas** antes de alguém assumir que passa.

## 5. Esta célula NÃO assina sessão

Herdado de `DECISAO-celula-de-identidade.md` §6.4 e do **[INV-P12]**: não há
`SessionMiddleware`, não há `django.contrib.sessions` em `INSTALLED_APPS`, não
há `SESSION_ENGINE`. A célula **repassa** o cookie recebido para a `identidade`
e pergunta quem é — nunca o lê, nunca o escreve.

Guarda: `services/gamificacao/tests/test_inv_gamificacao_nao_assina_sessao.py`,
plantado na gênese e provado por mutação.

**Aqui a tentação tem nome: a celebração visceral.** A comemoração de nível e
de marco aparece em tela cheia, uma vez só, no segundo da validação — e toda
tela assim precisa lembrar "esta pessoa já viu?". O caminho de menor esforço
para essa lembrança é `request.session[...]`, que deslogaria a plataforma
inteira sem erro em lugar nenhum (`armadilhas/143`). Por isso o estado mora no
MODELO (`celebracoes_pendentes`), e não na sessão.

E a regra que vem junto: **reconhecer não é autorizar.** O `papel` que a
`identidade` devolve é de exibição. Quem decide o que alguém pode fazer aqui é
esta célula, fail-CLOSED.

## 6. As sete decisões do mantenedor na Sessão A (30/08/2026)

Fechadas. Não se reabrem por preferência de agente (`PLANO` §10.1).

1. **Ligas: Bronze, Prata, Ouro, Platina.** **Diamante está PROIBIDO** — colide
   com os Cristais, que são a moeda.
2. **O medidor de esforço por desafio chama-se FORJA**, não Têmpera. O selo na
   obra diz *"forjada em 14 tentativas"*. **Onde o plano e o VEREDITO dizem
   Têmpera, leia Forja.**
3. **A vitrine pública do aluno mora em `meshcraft.top/estudio/<apelido>`** —
   opt-in, só apelido, obras aprovadas e marcos escolhidos, `noindex`.
4. **Tabela de pontos:** a escala de referência do parecer 6 fica como está,
   com a propriedade que importa preservada — **validação humana vale ~10x
   consumo**.
5. **Validação: escadinha de três degraus** — o autor marca "resolveu", um
   monitor confere, o mantenedor entra só no que envolve dinheiro.
6. **Banco de Ideias.** **PROMOVIDAS oito:** Museu da Evolução, Oficina Aberta,
   Cerimônia dos Criadores, Legado, perfil-currículo, dicas de veterano, obra
   coletiva, Ciência da Transformação. **FICAM NA GAVETA quatro:** Atlas de
   Criador, sistema de reflexão, números reais da obra, Grande Obra.
7. **Quatro decisões fechadas, que não são parâmetros** (`PLANO` §10.4): marco
   real vale **0 XP**; login vale **0 XP**; **o Escudo nunca está à venda** —
   nem por Cristais; **consentimento padrão = privado** — nada é exposto sem
   ação explícita do aluno.

## 7. A ordem de construção

A escada canônica é a tabela do **§6 do `PLANO-CELULA-GAMIFICACAO.md`**: 22 PRs,
2 sessões com o mantenedor e 1 passo manual dele. Ela não se repete aqui — mas
três regras dela são lei, porque já custaram caro em outras gêneses:

- **Modelo de dados e contrato antes de qualquer tela** (como no fórum e na
  identidade).
- **O provisionamento vai SOZINHO, antes do passo manual do mantenedor**; o
  `infra/` vai SOZINHO depois dele (`armadilhas/134`, `PLANO-AREA-ADMIN` §6).
- **Entre a gênese e o PR de infra, o `deploy-celula` desta célula fica
  VERMELHO — e isso é ESPERADO** (`armadilhas/088`): o compose da VPS ainda não
  conhece a célula, e o job aborta fail-closed de propósito. Não é defeito da
  célula, e não se conserta na célula.

## 8. Proibido, por escrito

Vetado agora para não entrar depois disfarçado de novidade (VEREDITO §4):

- **Gorjeta de Cristais entre alunos** e qualquer transferência de moeda entre
  menores. A intenção sobrevive no botão Parabéns.
- **Comprar destaque** para um post, ou qualquer visibilidade paga.
- **Itens-relâmpago com cronômetro** e loot box (ECA Digital, 17/03/2026).
- **Ranking global público, vitalício ou indexável.**
- **Pontos de personalidade** ("Resiliência 73/100") — gamificam-se
  comportamentos observáveis, nunca traços de criança.
- **XP proporcional a volume** ("10 XP por polígono").
- **Detecção de texto de IA** — falso positivo com criança custa caríssimo.
- **Voto popular no desafio** ("Escolha da Galera").
- **Corações/vidas, notificação de culpa, aposta de sequência, boost com
  cronômetro, mascote que cobra.**

## 9. Menores, e o que isso obriga

Modo Júnior **obrigatório** abaixo de 13 anos (trava de sistema, não escolha).
Sem mensagem direta entre alunos. Moderação humana **antes** de qualquer
publicação pública. Links externos só de lista permitida. Meu Estúdio público é
opt-in. Marcos de dinheiro são faixa 13+, validados **sempre por adulto da
equipe**, com a evidência em camada privada. "Com ajuda do responsável" em todo
marco que envolva contato externo. Nenhum marco induz menor a mentir a idade ou
a abordar estranhos.

**PORTÃO DA CAMADA 1:** a verificação oficial das regras de idade do Roblox e
do Fiverr acontece **antes** de os marcos de carreira serem ligados.

E a promessa que a escola faz: *"primeiros dólares"* é **possibilidade, nunca
promessa**.

## 10. Critério de morte

**Pare e reabra a decisão com o mantenedor** se qualquer uma destas acontecer:

1. a célula virar motor de regras genérico ou ganhar uma DSL;
2. Cristais ficarem compráveis ou transferíveis;
3. pontos passarem a ser calculados dentro de outra célula;
4. nascer ranking global público ou indexável;
5. ajustar a economia passar a exigir PR de código (ela é dado: UPDATE +
   versão, anunciado, nunca retroativo);
6. qualquer invariante do CI precisar de exceção.

## 11. Estado

Lei promulgada em 30/08/2026 com a gênese da célula (PR 1 da escada). A
construção segue pela fila (`fila/`), uma TAR por degrau, e o estado de cada
degrau se lê no livro (`painel/registros/`) — **nunca neste documento**, que
não guarda estado e não se atualiza sozinho.
