# Célula de Sugestões — Especificação Técnica v1

Caixa de Sugestões: célula de Voice of Customer / Product Discovery reutilizável por qualquer produto da plataforma (curso, comunidade, plataforma geral).

## 1. Propósito

Permitir que alunos de qualquer produto sugiram problemas, votem em sugestões de outros alunos, e acompanhem o ciclo até a entrega — alimentando decisões de produto e, eventualmente, especificações de mudança (ChangeSpec) executadas por agentes.

## 2. Escopo

Dentro do escopo:
- captura de sugestão (problema + solução proposta opcional)
- votação (um voto por ator por sugestão)
- categorização configurável por quadro
- pipeline de status com histórico
- emissão de eventos de domínio
- avaliação interna de produto (staff-only)

Fora do escopo, por design:
- cálculo de XP ou gamificação — a célula de gamificação consome eventos
- disparo de email, push ou WhatsApp — a célula de notificação consome eventos
- geração do ChangeSpec — pertence a um processo/documento separado
- qualquer leitura ou escrita direta no banco de outra célula

## 3. Pressupostos de arquitetura

- Processo próprio, banco de dados próprio, pasta própria.
- Nenhuma ForeignKey para modelos de outra célula. Com banco físico separado por célula isso não é preferência de estilo: o Postgres não sustenta constraint de FK entre bancos diferentes, então a restrição é estrutural.
- Antes de implementar: auditar se as demais células realmente já operam com banco próprio isolado. Não presumir que o estado atual (AS-IS) corresponde ao alvo (target). Reportar qualquer divergência encontrada antes de prosseguir.

## 4. Contrato de identidade

> **Reescrito em 23/08/2026 pela `DECISAO-EVO-01-identidade.md`** (sessão de
> arquitetura com o mantenedor). A versão anterior pressupunha uma "célula de auth"
> que **não existe** — a auditoria EVO-00 (Q2) mediu zero login de usuário final em
> toda a plataforma. Não era campo a confirmar: era mecanismo a criar.

**O Google prova QUEM É; a célula `alunos` decide SE PODE.** A `sugestoes` emite a
própria sessão — não recebe ator pronto de ninguém.

1. Entrar com Google ⇒ e-mail **verificado** (`email_verified` falso é recusado).
2. `GET /alunos/{email}/matriculas` (`listEnrollments`, contrato existente e
   implementado) responde se há matrícula. **Sem matrícula, não entra** — decisão 2
   do EVO-01.
3. Com matrícula ⇒ a `sugestoes` cunha/recupera a `Identidade` e abre a sessão.

```
Ator (interno da sugestoes, nunca vindo de fora)
  actor_id     texto opaco cunhado pela sugestoes  (NÃO é UUID, NÃO é o e-mail)
  site_id      texto opaco (CONV-SITE resolve pelo Host)
  papeis       ["aluno"] | ["staff"] | ambos
```

`actor_id` e `site_id` são **texto opaco** porque é o que a plataforma inteira já faz
(`Site.id`, `product_id`, `site_id`: `type: string` sem `format: uuid`).

**Staff** = lista de e-mails no `.env` da célula (`SUGESTOES_STAFF_EMAILS`), lida no
ponto de uso, nunca fail-hard no import. Staff **não** precisa de matrícula, e a
checagem dele vem ANTES da de matrícula.

Sugestões, votos e comentários referenciam `Identidade.id` — **nunca o e-mail**, que
vive numa linha só. Detalhes, alternativas descartadas e a fricção conhecida do
e-mail divergente: `DECISAO-EVO-01-identidade.md`.

## 5. Fronteira de contexto

`Quadro` é o boundary. Toda sugestão pertence a exatamente um quadro.

```python
class Quadro(models.Model):
    tenant_id = models.UUIDField()
    produto_id = models.UUIDField(null=True, blank=True)  # null = quadro de plataforma inteira
    nome = models.CharField(max_length=100)
```

Optei por não introduzir `scope_type` / `scope_id` aqui. É uma camada de abstração a mais para um problema que o próprio quadro já resolve com um campo nullable. Vale a pena quando existir um terceiro tipo real de escopo (trilha, coorte) — não antes.

## 6. Modelo de dados

```python
class Categoria(models.Model):
    quadro = models.ForeignKey(Quadro, related_name="categorias", on_delete=models.CASCADE)
    slug = models.SlugField()
    nome = models.CharField(max_length=80)
    ordem = models.PositiveIntegerField(default=0)
    ativa = models.BooleanField(default=True)

    class Meta:
        unique_together = ("quadro", "slug")


class Sugestao(models.Model):
    class Status(models.TextChoices):
        EM_ANALISE = "em_analise", "Em análise"
        PLANEJADO = "planejado", "Planejado"
        EM_DESENVOLVIMENTO = "em_desenvolvimento", "Em desenvolvimento"
        IMPLEMENTADO = "implementado", "Implementado"
        NAO_PLANEJADO = "nao_planejado", "Não planejado"
        MESCLADO = "mesclado", "Mesclado"

    quadro = models.ForeignKey(Quadro, related_name="sugestoes", on_delete=models.CASCADE)
    categoria = models.ForeignKey(Categoria, related_name="sugestoes", on_delete=models.PROTECT)
    autor_id = models.UUIDField()  # confirmar contrato de identidade — seção 4
    titulo = models.CharField(max_length=140)
    problema = models.TextField()
    solucao_proposta = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.EM_ANALISE)
    sugestao_canonica = models.ForeignKey(
        "self", null=True, blank=True, related_name="mescladas", on_delete=models.SET_NULL
    )
    criado_em = models.DateTimeField(auto_now_add=True)


class Voto(models.Model):
    sugestao = models.ForeignKey(Sugestao, related_name="votos", on_delete=models.CASCADE)
    autor_id = models.UUIDField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("sugestao", "autor_id")


class Comentario(models.Model):
    sugestao = models.ForeignKey(Sugestao, related_name="comentarios", on_delete=models.CASCADE)
    autor_id = models.UUIDField()
    texto = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)


class HistoricoStatus(models.Model):
    """Append-only. Nunca editar ou apagar uma linha; uma correção é um novo registro."""
    sugestao = models.ForeignKey(Sugestao, related_name="historico", on_delete=models.CASCADE)
    status_anterior = models.CharField(max_length=20, choices=Sugestao.Status.choices, blank=True)
    status_novo = models.CharField(max_length=20, choices=Sugestao.Status.choices)
    nota = models.TextField(blank=True)
    alterado_por_id = models.UUIDField()
    criado_em = models.DateTimeField(auto_now_add=True)


class AvaliacaoInterna(models.Model):
    """Staff-only. Nunca exposta ou editável pelo aluno."""
    sugestao = models.OneToOneField(Sugestao, related_name="avaliacao", on_delete=models.CASCADE)
    impacto_educacional = models.PositiveSmallIntegerField(default=0)
    impacto_comercial = models.PositiveSmallIntegerField(default=0)
    esforco_tecnico = models.PositiveSmallIntegerField(default=0)
    notas = models.TextField(blank=True)
    decisao_produto = models.TextField(blank=True)  # registra a decisão antes de virar ChangeSpec
    avaliado_por_id = models.UUIDField(null=True, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)
```

## 7. Eventos emitidos

A célula nunca decide XP, nunca envia notificação, nunca calcula analytics — só afirma fatos.

- `sugestao.criada` — `{suggestion_id, quadro_id, categoria_id, autor_id}`
- `sugestao.voto-adicionado` — `{suggestion_id, autor_id, total_votos}`
- `sugestao.voto-removido` — `{suggestion_id, autor_id, total_votos}`
- `sugestao.status-alterado` — `{suggestion_id, status_anterior, status_novo, autores_que_votaram[]}`
- `sugestao.mesclada` — `{suggestion_id_origem, suggestion_id_canonica}`

As células de gamificação, notificação e analytics assinam esses eventos e decidem sozinhas o que fazer. A célula sugestoes não sabe que gamificação ou notificação existem.

## 8. Invariantes

- Um ator vota no máximo uma vez por sugestão (`unique_together`); desvotar apaga a linha, nunca marca como inativa.
- `HistoricoStatus` é append-only — nenhuma linha é editada ou apagada depois de criada.
- `AvaliacaoInterna` nunca é lida ou escrita por um endpoint que o aluno acessa.
- Nenhum model desta célula tem ForeignKey apontando para fora do banco da própria célula.
- Merge de sugestão é transacional: ator que votou nas duas sugestões não vira dois votos; comentários e histórico da sugestão mesclada são preservados, nunca apagados; a URL da sugestão mesclada continua resolvendo, redirecionando para a canônica.
- `Sugestao.status` só sai de `PLANEJADO` para `EM_DESENVOLVIMENTO` se existir um ChangeSpec aprovado referenciando aquele `suggestion_id` — ver `FORMATO-CHANGESPEC.md`, seção 5.

## 9. Modos de falha a considerar

- Corrida entre dois cliques de "votar" do mesmo ator — proteger com `unique_together` + tratamento de `IntegrityError`, não com lock otimista no frontend.
- Merge executando no meio de um voto sendo registrado — a transação precisa cobrir leitura e escrita juntas.
- Ator sem matrícula válida tentando votar num quadro de curso que não é o dele — validação de entitlement acontece antes de tocar o banco da célula, usando o contrato de identidade, nunca uma consulta a outra célula.
- Categoria desativada com sugestões antigas ainda vinculadas — desativar oculta da lista de criação, mas não invalida sugestões existentes.

## 10. Fases

**MVP:** quadro por contexto; criar sugestão (problema + solução); categorias configuráveis; votar/desvotar; ranking por total de votos; busca simples de possíveis duplicatas (`icontains` ou similaridade trigram do Postgres) antes de publicar; comentários; status com histórico append-only; "não planejado" com justificativa obrigatória; evento de mudança de status consumido por uma notificação in-app simples; rate limit leve (3 sugestões / 7 dias, sem camadas de reputação ainda); avaliação de produto interna simples.

**V1.1:** merge administrativo transacional; gamificação via consumo de eventos; seguir sugestão.

**V1.2:** ranking "em alta" com peso de recência; "meu impacto" no perfil do aluno.

**Depois, só quando o volume justificar:** busca semântica de duplicata, clustering de necessidades, segmentação por jornada do aluno.

## 11. Definition of Done — MVP

- [ ] Todas as invariantes da seção 8 cobertas por teste automatizado
- [ ] Nenhuma ForeignKey cruzando banco de célula
- [ ] Endpoint de avaliação de produto retorna 403 para qualquer ator sem role de staff
- [ ] Evento de mudança de status é publicado antes do commit da transação de status
- [ ] Auditoria do estado AS-IS das outras células documentada e anexada a este spec antes da implementação

## 12. Da sugestão ao código

Este spec cobre só a camada de captura. O caminho completo, que precisa de uma segunda especificação, é:

```
sugestão (linguagem do aluno)
    → decisão de produto (linguagem do produto)
    → ChangeSpec (linguagem da engenharia: contratos permitidos, células proibidas, critérios de aceitação, Definition of Done)
    → agente implementa
```

Uma sugestão aprovada nunca deveria virar um prompt aberto tipo "implemente isso" para um agente. Vale desenhar o formato do ChangeSpec como o próximo documento, reaproveitando a disciplina que já existe no AGENTS.md.
