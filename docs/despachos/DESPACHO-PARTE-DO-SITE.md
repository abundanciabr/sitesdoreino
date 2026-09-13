# DESPACHO — PARTE DO SITE (o super prompt reutilizável)

> Criado em 30/08/2026 a pedido do mantenedor: **um único prompt, detalhado,
> que qualquer sessão nova recebe para construir uma parte específica do site**
> — um menu, um rodapé, uma página de perfil, uma seção nova. O mantenedor
> preenche duas linhas; todo o resto já está decidido aqui ou nas leis.
>
> **Se este documento divergir de uma lei do repositório** (`CLAUDE.md`,
> `RITOS.md`, `CONSTITUICAO.md`, `CAMINHO-DOURADO.md`, `armadilhas/`), **a lei
> vence** — e quem percebeu a divergência corrige este arquivo no mesmo PR.

---

## §1 — Para o mantenedor: como usar

Copie o bloco abaixo, troque as duas linhas de preencher e cole numa sessão
nova do Claude Code, a maestro (pode ser na pasta principal). A maestro cria a
tarefa na fila com o brief e o Codex constrói pela ficha `despacho`; para
começar a obra, cole na sessão do Codex "pegue a TAR-NNN", com o número que a
maestro devolver (`docs/decisoes/DECISAO-triade-de-ias.md`):

```text
Leia o arquivo docs/despachos/DESPACHO-PARTE-DO-SITE.md na versão mais nova do
projeto (origin/main) e execute o §2 dele de ponta a ponta, sem me perguntar o
que já está decidido lá.

PARTE DO SITE QUE EU QUERO: (escreva aqui — ex.: um rodapé em todas as páginas)
COMO EU QUERO QUE SEJA (opcional): (detalhes; ou deixe em branco que o robô propõe)
```

**Suas três regras de ouro:**

- **Uma parte por sessão.** Quer três partes? Abra três sessões, cada uma com
  o bloco preenchido com a sua parte.
- **Sessões ao mesmo tempo: só de áreas diferentes do site.** Página inicial e
  fórum ao mesmo tempo = pode. Menu e rodapé ao mesmo tempo = **não** — os
  dois moram no mesmo arquivo e os robôs colidem. Na dúvida, uma de cada vez.
- **O robô termina sozinho:** PR, atestado, pedido de pouso e registro no livro.
  A pista mergeia e publica sem ninguém esperar; o endereço para você VER a
  parte no ar vem na sessão seguinte, quando a maestro confere o merge e a
  publicação. Se ele parar com uma pergunta de múltipla escolha, é porque a
  decisão é sua mesmo. Quem te pergunta é só a maestro: o executor nunca fala
  com você, devolve a dúvida à maestro.

**Exemplos de preenchimento:**

| PARTE DO SITE QUE EU QUERO | COMO EU QUERO QUE SEJA |
|---|---|
| um menu de navegação no topo do site público | com links para a página inicial, o fórum e o cadastro |
| um rodapé em todas as páginas do site público | com o nome da escola, links úteis e o aviso de direitos |
| uma página de perfil do aluno | onde o aluno logado vê os dados dele e o que já conquistou |

---

## §2 — Para o robô: o contrato (execute na ordem, sem pular passo)

### Passo 0 — quem você atende

O mantenedor é leigo em código e lê SÓ português: **toda resposta em PT-BR**,
relatório em linguagem de resultado ("o rodapé está no ar em…"), e qualquer
decisão que sobrar para ele vira `AskUserQuestion` com opções explicadas sem
jargão — nunca frase solta. Só a maestro (Claude Code) pergunta ao mantenedor;
o executor (Codex) nunca pergunta, devolve a dúvida à maestro. As leis do
`CLAUDE.md` (que você já carregou ao abrir a sessão) valem inteiras. Três delas, repetidas porque já foram
violadas: **escopo completo por padrão** (nunca propor a versão mínima para
economizar); **nunca tocar nem propor pagamento/checkout** (diretiva ativa do
mantenedor — pagamento fica por último); **prazo apertado é motivo para
acelerar, nunca para recomendar esperar**.

**A tríade** (`docs/decisoes/DECISAO-triade-de-ias.md`): papéis e limites das
três IAs moram lá. O que muda o seu gesto aqui: você é o executor; dúvida que
só o mantenedor decide vai à maestro por `python ci/fila.py bloquear`; tarefa
que você descobrir no caminho vai para a fila (`python ci/fila.py criar`) e
volta à maestro, que decide se entra no lote.

### Passo 1 — leituras (dieta de contexto; leia SEMPRE do `origin/main` — o espelho local envelhece sem avisar)

1. Contexto direcionado por caminho e sintoma na abertura: confira origens e limitações
   e abra as entradas do brief e as recuperadas. Para aprofundamento, refine a busca
   ou consulte `armadilhas/INDICE.md`.
2. Os 8 títulos de `docs/decisoes/RETROSPECTIVA-FASE-D.md` (30 segundos).
3. `CAMINHO-DOURADO.md`: §0 a §3 + **R6** (página/tela nova) + **R12**
   (idiomas) — e R1/R2 apenas se a parte precisar de endpoint novo ou de dado
   de outra célula.
4. `services/<celula>/LICOES.md` da célula onde a parte vai morar (§3 abaixo).
5. `painel/mapa-do-site.json` — todo endereço que o site já tem, descrito para
   leigo; é também onde a sua rota nova vai precisar de uma entrada.

### Passo 2 — descubra a casa da parte

Use a tabela do §3 e **confirme lendo a configuração real** (`config/urls.py`
da célula, o mapa do site, o Traefik se a dúvida for de alcance) — nunca
afirme viabilidade sem ler a configuração (Retrospectiva §8). Parte que
atravessa células (ex.: rodapé em todas as páginas de todas as células
públicas): **replique o padrão em cada célula** (Lei 7 — copie o padrão,
nunca importe o arquivo de outra célula), de preferência um PR por célula, e
declare a escada de PRs na primeira resposta.

### Passo 3: bancada e baseline

```bash
make sessao CELULA=<celula> TAREFA=<parte> TAR=TAR-NNN
```

Consulte `python ci/fila.py listar --ao-vivo` para identificar tarefa existente.
Omita `TAR` se ainda não houver tarefa. A abertura cria a bancada antes de pegar
no balcão e emite baseline e contexto (RITOS §1). Entre no caminho informado,
confira a Declaração e o log antes de editar. Falha herdada exige parar e reportar.
Recusa de reserva exige conferir o dono; não force nem apague a bancada.

### Passo 4: registre tarefa nova, quando necessária

Se a consulta não encontrou tarefa, crie-a DENTRO da bancada:

```bash
python ci/fila.py criar --titulo "<a parte, em uma linha para leigo>" \
  --move <cartao do placar, ou manutencao> \
  --toca <celula> --evidencia-exigida "URL do PR mergeado + a parte visível no site" \
  --origem "despacho do mantenedor (super prompt de parte do site)"
```

Repita a abertura do passo 3 com o número retornado em `TAR`, para reivindicar
pela mesma entrada. A retomada preserva arquivos e estado da bancada.

### Passo 5 — as regras duras de toda parte visível do site

- **Mobile-first**, estendendo o template-base da célula
  (`base_mobile.html` no funil; `forum/base.html` no fórum) — e `{% extends %}`
  na **linha 1** do template, sempre (até um `{% load %}` antes quebra o parse).
- **Cada página é uma ilha Alpine** (R6): estado próprio, status vem do
  servidor, zero variável compartilhada entre páginas, nada de framework novo
  (sem React, sem Tailwind, sem build de JS). Visual: **copie o padrão que a
  célula já usa**, inclusive o CSS dela.
- **Multilíngue desde o nascimento** (R12, fluxo A): página nova nasce com
  **todos os idiomas do site no mesmo PR** — confira `infra/sites.json` (hoje:
  `pt-br` padrão na raiz nua, `en`, `es`). Texto visível SÓ via `{% t %}` com
  chave literal; link interno SÓ via `{% url_i18n %}` (a tag `url` crua
  funciona no idioma padrão e quebra nos outros em silêncio); strings que o JS
  troca moram na subárvore `js.*` do catálogo; `title`/`meta` saem do catálogo;
  o resto do SEO o template-base emite sozinho — não escreva à mão.
- **Multissítio**: a célula pública serve N sites — leia tudo de
  `request.site`, nunca escreva "meshcraft" fixo em código ou template
  (INV-P11).
- **Rota nova exige entrada em `painel/mapa-do-site.json`** — o portão reprova
  sem ela e a recusa dita o que escrever (título e descrição em português de
  leigo).
- Identificadores em inglês, comentários e prosa em português; dinheiro sempre
  em centavos inteiros; `contracts/` **nunca** muda no mesmo PR (rito próprio,
  RITOS §3).

### Passo 6 — prova

- Guarda nova apresenta evidência **vermelho→verde** no PR ("eu arrumei" não
  é aceito).
- Depois do deploy, **prova de fora**: `curl` na borda pública
  (`https://meshcraft.top/<rota>`) mostrando a parte no ar — em cada idioma do
  site, porque o link cru quebrado só aparece fora do idioma padrão.
- Veredito de run SEMPRE por `gh run view <id> --json status,conclusion` —
  nunca pelo exit de um pipe.

### Passo 7 — entrega e fechamento

1. PR pequeno (teto 15 arquivos; estourou = escada de PRs, declarada desde o
   início), título em PT no padrão `feat(<celula>): …`.
2. Feche por `make pr` conforme `painel/LEIA-ME.md`, informando os comandos de
   validação e `TAR=TAR-NNN`. O comando reserva e embarca recibo, eventos e
   metadados no próprio PR; não repita esses efeitos manualmente.
3. O despacho devolve o PR à maestro; ela publica o atestado da revisão
   independente, pede pouso com `python ci/mergear.py <N> --pousar` e encerra,
   sem esperar check em laço (RUNBOOK §5). Revisão de código continua obrigatória.
4. Na sessão seguinte (a maestro deixa registro `pendencia` com o PR e o que
   conferir; o mantenedor cola "confira a entrega do PR N" numa sessão nova), a
   maestro confere o merge por `gh pr view <N> --json state,mergeCommit` e,
   tocando `services/**` ou `painel/**`, a publicação por consulta única:
   `python ci/esperar.py --entrega <N>`.
5. Depois do merge, a sentinela (Antigravity) verifica a entrega alheia contra
   o aceite (`verificacao`); você não espera por isso. O revisor da casa lê
   todo PR antes do pouso para o atestado que a maestro publica; check pendente
   não impede o pedido de pouso, a pista aguarda.
6. Fato posterior, como deploy e verificação pública, exige registro novo no livro.
7. Aprendeu algo que vai morder o próximo robô? `armadilhas/NNN-slug.md` novo
   + `make indice` (arquivo NOVO, nunca append). O que só o mantenedor resolve:
   registro tipo `pendencia` com `precisa_do_dono: true` + texto claro no
   relatório.
8. **Não apague a bancada `wt-*`** — pedido do mantenedor (29/08/2026).

### Passo 8 — relatório final

Em linguagem de resultado, com: o número do PR e o SHA · o atestado publicado
e o pedido de pouso feito · o que ficou de fora e por quê · e, se sobrou
decisão dele, devolvida à maestro, que abre a `AskUserQuestion`. O endereço
para VER a parte no ar e o veredito da publicação entram no registro da sessão
seguinte (Passo 7, item 4). Marco entregue
merece celebração — o ânimo do mantenedor é infraestrutura do projeto.

---

## §3 — Mapa: que parte mora em qual célula

| Parte do site | Célula | Onde olhar primeiro |
|---|---|---|
| Página inicial, páginas de venda, cadastro e login (as telas), **menu e rodapé do site público** | `funil` | `templates/base_mobile.html` (o esqueleto de TODA página pública — menu/rodapé nascem nele), `templates/funil/`, `traducoes/` |
| Fórum (`meshcraft.top/forum`) | `forum` | `apps/core/templates/forum/base.html`, `static/forum.css` |
| Área do aluno logado (perfil, minhas turmas, conquistas na tela) | `alunos` | hoje a célula só tem API e eventos — telas novas nascem nela; sessão/login vêm da célula `identidade` (lei em `docs/decisoes/DECISAO-celula-de-identidade.md`) |
| Contas, senhas, sessão (o motor por trás do login) | `identidade` | as telas de login/cadastro moram no `funil`; aqui é o serviço |
| Quiz | `quiz` | copie o padrão que a célula já tem |
| Pontos e conquistas (o motor) | `gamificacao` | a TELA que mostra conquista mora na célula da página, lendo a API daqui |
| Painel do dono (`/admin/painel/`) e área admin | `admin` | `painel/` tem leis próprias — `painel/LEIA-ME.md` |
| Checkout, pagamentos, Mercado Pago | 🚫 **proibido** | diretiva do mantenedor: pagamento fica por último; não tocar nem propor |

Na dúvida entre duas células, o desempate é o `painel/mapa-do-site.json` + o
`config/urls.py` de cada uma — e, persistindo a dúvida, ela vira
`AskUserQuestion` para o mantenedor com as opções traduzidas, feita só pela
maestro; o executor não pergunta, devolve a dúvida à maestro.
