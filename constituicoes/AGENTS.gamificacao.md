# Constituição da Célula: gamificacao (Sistema de Formação de Criadores)
> **Jurisdição:** governa apenas `services/gamificacao/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA (nascida em 30/08/2026, PR de gênese) · **Merge:** pela pista (`ci/mergear.py --pousar`), com CI verde

## Missão
Transformar o que a plataforma JÁ afirma — quiz completado, sugestão criada e
votada, e (a partir da Sessão B) o que acontece no fórum — em progresso
visível: XP, níveis, Sequência semanal, Forja, missões, medalhas, **Marcos de
carreira**, Cristais e cosméticos.

A hierarquia que decide todo conflito de desenho:
**Realidade > Criação > Maestria > Comunidade > XP.** A espinha é a trilha de
marcos reais (obra → portfólio → cliente → dólar → contribuição → legado); o
pacote estilo Duolingo é o andaime, e **nenhuma tela mostra o andaime acima da
espinha**.

Lei do assunto: `docs/decisoes/DECISAO-gamificacao.md`. A engenharia (modelo de
dados, eventos, superfícies, a escada de 22 PRs):
`docs/decisoes/PLANO-CELULA-GAMIFICACAO.md`. A rastreabilidade de cada decisão
de produto (6 pareceres + 5 auditorias):
`docs/consultorias/gamificacao/VEREDITO.md`.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/gamificacao/**`
- **SOMENTE LEITURA:** `contracts/identidade.openapi.yaml` (é por ele que se
  pergunta quem é a pessoa), `contracts/alunos.openapi.yaml` (a categoria da
  pessoa), `contracts/notificacoes.openapi.yaml` (o sininho, para as cartas de
  celebração) e `contracts/sugestoes.openapi.yaml` (a Caixa é uma das fontes de
  evento)
- **PROIBIDO (nem ler):** as demais células, `infra/`, qualquer segredo de
  pagamento. **`services/checkout/` e `services/pagamentos/` estão fora de
  mandato inclusive para leitura** — a cobrança está congelada por diretiva do
  mantenedor (22/08/2026), e a lei desta célula §8 proíbe explicitamente
  qualquer caminho de dinheiro real para dentro da economia

## Comunicação
- **Expõe:** páginas em `/conquistas/*` (prefixo do gateway via `SCRIPT_NAME`).
  **O endereço é CAMINHO, nunca subdomínio** — não é gosto, é o que mantém o
  login único de pé (lei §4). A vitrine pública do aluno mora em
  `/estudio/<apelido>`, opt-in e `noindex`. A única rota que responde sem nada
  é `/healthz`
- **Consome:** `identidade` — para saber quem é o dono do cookie (o cliente
  nasce no PR 7 da escada; até lá `celulas.yml` declara `consome: []`, porque
  declaração órfã é FAIL no varredor, e com razão)
- **Emite:** `notificacao.devida.v1` pelo padrão outbox, com os assuntos
  `gamificacao.nivel-alcancado`, `.conquista-concedida`, `.marco-validado` e
  `.destaque-da-semana`. Nasce sem emitir nada
- **Auth:** Bearer dedicado por par, `TOKENS_ACEITOS_<PAR>`. Env ausente ⇒
  conjunto vazio ⇒ 401 para todo mundo (fail-closed sem derrubar o boot)
- **Banco:** `gamificacao_db` (role `gamificacao_user` — não enxerga nenhum
  outro database). Guarda o ledger de XP, os Cristais, a Sequência, a Forja, as
  medalhas, os Marcos e a fila de validação. **Nada de dado de outra célula
  copiado sem necessidade** — `Pessoa` é espelho mínimo (id, e-mail, nome
  exibido), e a matrícula se pergunta à `alunos`

## Invariantes desta célula

- **[INV-P12] Esta célula NÃO assina sessão.** Sem `SessionMiddleware`, sem
  `django.contrib.sessions`, sem `SESSION_ENGINE`. A célula repassa o cookie e
  pergunta quem é. Guarda:
  `tests/test_inv_gamificacao_nao_assina_sessao.py`, plantado na gênese e
  **provado por mutação** (instalar o middleware deixa quatro asserções
  vermelhas). **Aqui a tentação tem nome: a CELEBRAÇÃO VISCERAL** — toda tela
  que comemora precisa lembrar "já viu?", e o caminho curto para isso é
  `request.session[...]`, que deslogaria a plataforma inteira sem erro em lugar
  nenhum (`armadilhas/143`). Por isso `celebracoes_pendentes` mora no MODELO.

- **Os três invariantes da economia** (nascem como teste no PR 3 e nunca se
  flexibilizam): (1) nada por dinheiro real; (2) cosmético é só estética, nunca
  vantagem; (3) aula nunca fica atrás de jogo. O primeiro é garantido pelo
  BANCO — `CheckConstraint` que só permite delta negativo de Cristais com
  referência de compra — e não por convenção.

- **A economia é DADO, nunca código.** Regras de pontuação, missões,
  conquistas, níveis e cosméticos são linhas de tabela com `ativa=False` e
  `versao`. Ajustar a economia é UPDATE + versão, anunciado e **nunca
  retroativo** — se um dia exigir PR de código, isso é critério de morte
  (lei §10.5).

- **Idempotência por construção, não por cuidado.** `LancamentoDeXP` tem
  `Unique(origem_event_id, regra_slug, pessoa)`. Um evento reentregue não paga
  duas vezes porque o banco não deixa, não porque alguém lembrou de conferir.

- **O DIA é a unidade da mecânica, e ele é o dia de São Paulo.** `dia_local` no
  ledger, o dia ativo da Sequência, a janela das missões e o teto diário se
  decidem por `TIME_ZONE = "America/Sao_Paulo"`. Com o default de fábrica do
  Django o esforço das 22h cairia no dia errado, e nada acusaria
  (`armadilhas/099`). Guarda: `tests/test_fuso_horario.py`, provado por mutação
  (apagar a linha faz o guarda mostrar `24/08/2026 23:00` onde devia mostrar
  `25/08/2026 01:00`).

- **O prefixo mora no env, nunca no `urls.py`.** `FORCE_SCRIPT_NAME` é quem
  conhece `/conquistas`. Toda rota leva `name=`, e nenhum template escreve
  caminho à mão — e sob prefixo a folha de estilo sai de `{% url 'estatico' %}`,
  **nunca** de `{% static %}` (`armadilhas/102`). Guarda:
  `tests/test_healthz_script_name.py`, também provado por mutação.

- **A porta de máquina se fecha no Bearer, nunca na topologia.** Esta célula
  TEM `SCRIPT_NAME`, então o `/interno/` dela nascerá **debaixo** do prefixo
  roteado e alcançável pela internet em `/conquistas/interno/…`
  (`armadilhas/186`). Não copie de uma célula vizinha a frase *"nada em
  `/interno` resolve pela borda pública"*: aqui ela é FALSA. O guarda que
  importa é o teste de **401 em todas as operações**, inclusive com o env de
  tokens ausente.

- **Falha desta célula é falha ABERTA para quem a consome.** O fórum sem selo é
  um fórum; o fórum quebrado não é. Consumidores usam cache de 5 min e
  degradam sem o selo.

## Critérios de morte (lei §10)
Se a construção começar a virar **motor de regras genérico ou DSL**, se os
**Cristais ficarem compráveis ou transferíveis**, se **pontos passarem a ser
calculados dentro de outra célula**, se nascer **ranking global público ou
indexável**, se **ajustar a economia exigir PR de código**, ou se **qualquer
invariante do CI precisar de exceção** — **pare e reabra a decisão** com o
mantenedor.

## O que esta célula ainda NÃO resolveu
Registrado para ninguém achar que foi esquecimento:

1. **A calibração fina de XP e da curva de níveis** — a escala de referência do
   parecer 6 é ponto de partida (decisão 4 da Sessão A), não número final.
2. **Onde mora o painel do professor** — dentro de `/conquistas/interno` ou na
   célula `admin`. Decisão da Sessão B.
3. **O portão da Camada 1**: a verificação oficial das regras de idade do
   Roblox e do Fiverr precisa estar feita **antes** de os marcos de carreira
   serem ligados. É bloqueio de produto, não de engenharia.

## Estado da construção
A escada canônica é a tabela do §6 do `PLANO-CELULA-GAMIFICACAO.md` (22 PRs).
Esta tabela é só o começo dela, e **não é painel** — quem responde "isto foi
feito?" é o livro (`painel/registros/`) e a fila (`fila/`).

| PR | O quê | Estado |
|---|---|---|
| — | Sessão A com o mantenedor: aprova a lei, ligas, Forja, Estúdio, validação, Banco de Ideias | **feita em 30/08/2026** |
| 1 | Gênese: esqueleto, `/healthz` nas duas formas, os três guardas, rollback, manifesto, mapa, esta constituição e a lei | **este PR** |
| 3 | Modelo de dados + migração + semeadura + os 3 invariantes da economia | a fazer |
| — | Sessão B: Rito de Contrato (`gamificacao.openapi.yaml` + 4 eventos `forum.*`) | a fazer |
| 4 | Contrato — PR só de `contracts/` | a fazer |
| 5 | `infra/provisionar-gamificacao.sh`, **sozinho** | a fazer |
| H | Passo do mantenedor na VPS: banco + role + env, em UMA linha fail-closed | a fazer |
| 6 | `infra/` — compose + Traefik `/conquistas` + inventário de rotas no MESMO PR (`armadilhas/089`). **PR próprio, sozinho** (`armadilhas/134`) | a fazer |
| 7+ | Porta, telas, motor de XP, cartas, Sequência, missões, medalhas e Marcos | a fazer |

**Até o PR 6, o `deploy-celula` desta célula fica vermelho — isso é esperado**
(`armadilhas/088`): o compose da VPS ainda não conhece a `gamificacao`, e o job
aborta fail-closed de propósito. A imagem é construída e publicada normalmente;
o que falha é o passo de ativar na VPS.
