# Constituição da Célula: forum (O Fórum da Escola)
> **Jurisdição:** governa apenas `services/forum/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA (nascida em 28/08/2026, PR de gênese) · **Merge:** auto-merge permitido com CI verde

## Missão
O lugar onde a Meshcraft Academy conversa: alunos, professores e
administradores. Dúvida que se pergunta uma vez e fica respondida para sempre,
trabalho que se mostra e recebe crítica, e conhecimento que vira patrimônio da
escola em vez de sumir na rolagem de um bate-papo.

Lei do assunto: `docs/decisoes/DECISAO-forum-da-escola.md`. A análise que
levou a construir em vez de instalar (com os dois pareceres externos):
`docs/consultorias/forum-da-escola/VEREDITO.md`.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/forum/**`
- **SOMENTE LEITURA:** `contracts/identidade.openapi.yaml` (é por ele que se
  pergunta quem é a pessoa), `contracts/alunos.openapi.yaml` (é por ele que se
  sabe se ela é aluna) e `contracts/notificacoes.openapi.yaml` (o sininho)
- **PROIBIDO (nem ler):** as demais células, `infra/`, qualquer segredo de
  pagamento. **`services/checkout/` e `services/pagamentos/` estão fora de
  mandato inclusive para leitura** — a cobrança está congelada por diretiva do
  mantenedor (22/08/2026), e a lei do fórum §5 proíbe explicitamente desenhar
  fórum pago ou nível de acesso por plano

## Comunicação
- **Expõe:** páginas em `/forum/*` (prefixo do gateway via `SCRIPT_NAME`).
  **O endereço é CAMINHO, nunca subdomínio** — não é gosto, é o que mantém o
  login único de pé (lei §2). A única rota que responde sem nada é `/healthz`
- **Consome:** `identidade` — `GET /interno/sessao/completa`
  (`getSessionFull`), server-side, com timeout explícito, para saber quem é o
  dono do cookie; `alunos` — `GET /alunos/{email}/situacao`
  (`getStudentStanding`), a porta única que responde a categoria da pessoa;
  `notificacoes` para entregar aviso no sininho
- **Auth:** Bearer dedicado por par. Para ver e-mail na resposta da
  `identidade`, o par precisa estar TAMBÉM em `TOKENS_COMPLETOS_FORUM` — e
  isso se registra por escrito em `DECISAO-celula-de-identidade.md` §6.3 antes
  de entrar no env
- **Emite:** eventos de participação (tópico criado, resposta dada) pelo
  padrão outbox, quando houver quem os consuma. Nasce sem emitir nada
- **Banco:** `forum_db` (role `forum_user` — não enxerga nenhum outro
  database). Guarda áreas, tópicos, mensagens, marcas de leitura, anexos e
  estados de moderação. **Nada de dado de outra célula copiado sem
  necessidade** — a matrícula se pergunta à `alunos`, não se espelha aqui

## Invariantes desta célula

- **[INV-P12] Esta célula NÃO assina sessão.** Sem `SessionMiddleware`, sem
  `django.contrib.sessions`, sem `SESSION_ENGINE`. O fórum repassa o cookie e
  pergunta quem é. Guarda:
  `tests/test_inv_forum_nao_assina_sessao.py`, plantado na gênese e **provado
  por mutação** (instalar o middleware deixa o guarda vermelho).
  **Neste fórum o risco é maior que o normal**, porque foi um requisito de
  login que o criou: uma segunda assinatura de cookie quebraria exatamente a
  coisa que justificou construir em vez de instalar.

- **Reconhecer não é autorizar.** O `papel` que a `identidade` devolve é de
  EXIBIÇÃO. Quem decide o que alguém pode fazer numa área do fórum é o fórum,
  fail-CLOSED, conferindo as listas dele. Nunca ponha papel, matrícula ou
  permissão dentro do cookie nem espere que a `identidade` os forneça — foi
  exatamente onde um consultor externo tropeçou (`VEREDITO.md`, "duas
  correções").

- **O prefixo mora no env, nunca no `urls.py`.** `FORCE_SCRIPT_NAME` é quem
  conhece `/forum`. Toda rota leva `name=`, e nenhum template escreve caminho
  à mão. Guarda: `tests/test_healthz_script_name.py`, também provado por
  mutação (cravar `forum/` numa rota deixa os três casos vermelhos).

- **O modelo de dados fica no formato normal de fórum** — área → tópico →
  mensagem. É o que mantém aberta a porta de migrar para o Discourse se a
  escola crescer muito (lei §4.2). Formato esquisito transforma uma decisão
  reversível em casamento.

- **Marca de leitura por marca-d'água**, nunca uma linha por pessoa por
  mensagem (lei §4.3). Com 200 alunos e 20 mil mensagens, a forma ingênua
  fabrica milhões de linhas para responder uma pergunta boba.

- **Busca do PostgreSQL em coluna indexada**, calculada na escrita e não na
  consulta (lei §4.4). Funciona lindamente com 500 mensagens e trava com 50
  mil — e só se descobre em produção.

## Critérios de morte (lei §4.7)
Se a construção começar a recriar do zero um **motor de busca**, um **editor
sofisticado**, **resposta por e-mail** ou um **framework de reputação**,
**pare e reabra a decisão** com o mantenedor. A partir dali estaríamos
reinventando o Discourse, e mal.

## O que esta célula ainda NÃO resolveu
Registrado para ninguém achar que foi esquecimento (lei §6):

1. **O salão vazio** — o fórum nasce sem comunidade nenhuma. Como não parecer
   deserto nos primeiros 90 dias não foi respondido pela rodada de consultoria.
2. **Menores de idade, moderação e lei brasileira.** O público da escola é
   majoritariamente jovem. Idem.
3. **Quem escreve nas áreas públicas** — só aluno, ou também cadastrado?

Os itens 1 e 2 pedem rodada própria e **precisam estar respondidos antes de o
fórum abrir ao público** — não antes de construir.

## Estado da construção
| PR | O quê | Estado |
|---|---|---|
| 1 | Gênese: esqueleto, `/healthz` nas duas formas, os dois guardas, rollback, manifesto, esta constituição e a lei | **este PR** |
| 2 | Modelo de dados (área, tópico, mensagem, marca de leitura, moderação) | a fazer |
| 3 | Contrato (`contracts/forum.openapi.yaml`), PR só de `contracts/` | a fazer |
| — | Passo do mantenedor na VPS: `infra/provisionar-forum.sh` | a fazer |
| 4 | `infra/` — compose + traefik + env. **PR próprio, sozinho** (`armadilhas/134`) | a fazer |
| 5+ | Telas, e o `funil` linkando o fórum | a fazer |

**Até o PR 4, o `deploy-celula` desta célula fica vermelho — isso é esperado**
(`armadilhas/088`): o compose ainda não conhece o `forum`.
