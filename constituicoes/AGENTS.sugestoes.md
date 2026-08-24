# Constituição da Célula: sugestoes (Caixa de Sugestões)
> **Jurisdição:** governa apenas `services/sugestoes/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA (nascida no Lote 1, EVO-10) · **Merge:** auto-merge permitido com CI verde

## Missão
A Caixa de Sugestões: o aluno diz o que dói, vota no que os outros disseram, e
acompanha até a entrega. Voice of Customer reutilizável por qualquer produto da
plataforma. A célula **só afirma fatos** — nunca calcula XP, nunca dispara e-mail,
nunca gera ChangeSpec. Quem faz isso são as células que assinam os eventos dela.
Especificação viva: `docs/caixa-de-sugestoes/ESPECIFICACAO-CELULA.md`.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/sugestoes/**`
- **SOMENTE LEITURA:** `contracts/alunos.openapi.yaml` (é por ele que a identidade
  pergunta se a pessoa tem matrícula — `DECISAO-EVO-01-identidade.md`)
- **PROIBIDO (nem ler):** as demais células, `infra/`, qualquer segredo de pagamento

## Comunicação
- **Expõe:** páginas públicas em `/forms/sugestoes/*` (prefixo do gateway via
  `SCRIPT_NAME`; a superfície HTTP é consumida pelo front-end da própria célula)
- **Consome:** `alunos` — `GET /alunos/{email}/matriculas` (`listEnrollments`),
  server-side, com timeout explícito. Nunca lê o banco de `alunos` (Lei 3)
- **Auth:** Bearer dedicado (`TOKEN_ALUNOS`) para a chamada acima. Para o aluno,
  sessão emitida pela PRÓPRIA célula depois do Google (EVO-01) — a `sugestoes`
  não recebe ator pronto de ninguém
- **Emite:** `sugestao.criada.v1`, `sugestao.voto-adicionado.v1`,
  `sugestao.voto-removido.v1`, `sugestao.status-alterado.v1`,
  `sugestao.mesclada.v1` (via outbox → relay Redis Streams)
- **Banco:** `sugestoes_db` (role `sugestoes_user` — não enxerga nenhum outro database)

## Invariantes desta célula
- **Multissítio (INV-P11):** toda sugestão pertence a um quadro, e o quadro a um
  site resolvido do Host (CONV-SITE); host não cadastrado = 404, nunca um site padrão.
- **Identidade é lei do EVO-01, não decisão de sessão:** o Google prova QUEM É, a
  célula `alunos` decide SE PODE. E-mail não verificado é recusado; sem matrícula
  não entra. Sugestões, votos e comentários referenciam `Identidade.id` — **nunca**
  o e-mail, que vive numa linha só.
- Um ator vota no máximo uma vez por sugestão; desvotar **apaga a linha**, nunca
  marca como inativa.
- `HistoricoStatus` é **append-only**: nenhuma linha é editada ou apagada depois de
  criada — correção é registro novo.
- `AvaliacaoInterna` é staff-only: nunca lida ou escrita por endpoint que o aluno
  alcança.
- **Nenhuma ForeignKey sai do banco desta célula** — o Postgres não sustentaria a
  constraint entre bancos, então a restrição é estrutural, não de estilo.
- Emissão de evento é transacional (outbox na mesma transação do estado).
- `/healthz` sobrevive ao prefixo: qualquer isenção de middleware compara
  `request.path_info`, nunca `request.path` (armadilhas/029; teste-guarda em
  `tests/test_healthz_script_name.py`).

## Definição de Pronto
`make ci` verde · schema de cada evento validado contra o contrato · diff no escopo.

## Ritos
RITOS.md §1, §2. Evento novo ou mudança de payload = rito de contrato (§3), nunca
decisão local. Identidade só se re-decide em sessão de arquitetura com o mantenedor,
como foi o EVO-01.
