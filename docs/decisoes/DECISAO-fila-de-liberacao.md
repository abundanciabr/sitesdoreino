# DECISÃO — a fila de liberação: quem não tem matrícula entra numa fila, não num beco

> **Decidida pelo mantenedor em 27/08/2026**, na sessão em que ele tentou usar a
> Caixa pela primeira vez e recebeu, com a própria conta, a tela
> *"Não encontramos matrícula para esse e-mail"*. As palavras dele: *"quero que
> ao invés de falar que não foi encontrada a matrícula, o usuário que tentar
> entre em uma parte aguardando a liberação por parte dos administradores do
> site"*.
>
> **Status:** *isto é lei.* É também o **Rito de Contrato** (`RITOS.md` §3)
> cumprido: sessão com ele presente, e a autorização explícita para abrir o
> contrato congelado da `alunos` — perguntada e respondida nominalmente.

---

## 1. O problema, medido antes de decidir

Hoje `services/sugestoes/apps/core/views.py::entrar` tem três saídas, e uma
delas é um beco:

| Estado | O que a pessoa vê |
|---|---|
| `DENTRO` | a Caixa |
| `INDISPONIVEL` | "tente de novo em alguns minutos" (fail-closed, correto) |
| `SEM_MATRICULA` | **403 e um beco** — "fale com a gente que a gente resolve" |

O beco não é falta de capricho: é falta de **destino**. Não existe, em lugar
nenhum da plataforma, um lugar onde alguém possa esperar. Quem chega sem
matrícula só tem o e-mail do suporte, e o mantenedor não tem como saber quantas
pessoas bateram nessa porta.

## 2. A decisão

**A fila de espera É a própria matrícula, num status novo.** Não nasce cadastro
paralelo.

A `Matricula` da célula `alunos` — hoje `ativa | suspensa | reembolsada` — ganha
`aguardando` e `recusada`. Liberar alguém é mudar o status para `ativa`.

**A alternativa recusada, nominalmente: uma tabela separada de "pré-cadastros".**
Ela criaria **duas listas que respondem à mesma pergunta** ("quem é aluno?"), e
elas discordariam no primeiro caso de borda — alguém pré-cadastrado que depois
compra pelo site, por exemplo. É a lei anti-duplicação do `CLAUDE.md`, e é a
doença que este projeto passou o mês curando.

**A consequência boa, e é ela que torna a decisão barata:** a Caixa **não muda**.
Ela já pergunta à `alunos` *"esta pessoa tem matrícula?"*. Quando o status vira
`ativa`, a resposta muda sozinha e a pessoa entra. Nenhuma linha da Caixa
precisa saber que uma fila existe.

## 3. A ARMADILHA que esta decisão cria — e que se fecha no mesmo PR

Medido em 27/08/2026, e é o achado mais importante desta sessão:

```python
# services/alunos/apps/core/api.py::list_enrollments
matriculas = Matricula.objects.filter(email=email).order_by("enrolled_at")
```

**Não há filtro de status.** E do lado da Caixa:

```python
# services/sugestoes/apps/core/sessao.py
tem = bool(AlunosClient().matriculas_de(chave))
```

Qualquer linha serve. Portanto, **no instante em que uma matrícula `aguardando`
existir, a pessoa entra na Caixa** — o oposto exato do que esta decisão quer.

Isto **não** é defeito do código atual: com três status que todos significam
"comprou", devolver tudo estava certo, e o mantenedor decidiu em 24/08/2026 que
`reembolsada` continua entrando. O defeito nasceria com o status novo.

**Regra:** o status `aguardando` **não pode existir no banco antes** de a
consulta que decide acesso passar a excluí-lo. As duas coisas entram no MESMO
PR, com teste que sabota (uma matrícula `aguardando` NÃO pode abrir a Caixa).

## 4. Onde cada porta fica, e por que não são as mesmas

O contrato da `alunos` ganha superfície nova. **`GET /matriculas?email=` não
muda de significado** — ela continua respondendo *"as matrículas que VALEM"*, e
passa a excluir `aguardando` e `recusada` explicitamente. Nenhum consumidor
existente muda de comportamento, e o risco para a Caixa é zero por construção.

A fila ganha porta **própria**, e é isso que mantém as duas perguntas separadas:

| Porta | Quem usa | Para quê |
|---|---|---|
| `POST /pre-matriculas` | a Caixa | guardar quem pediu entrada |
| `GET /pre-matriculas` | o painel admin | ver a fila |
| `POST /pre-matriculas/{id}/decisao` | o painel admin | liberar ou recusar |

**Por que não esticar `POST /matriculas`:** aquela porta significa *"alguém
pagou"* — é chamada pelo fluxo de pagamento e é idempotente por `order_id`.
Misturar as duas deixaria o caminho do dinheiro capaz de criar linha em espera,
e a fila capaz de criar matrícula paga. Duas intenções diferentes, duas portas.

**`order_id` de uma linha em espera:** ninguém pagou, então não há pedido. A
linha nasce com `pre:<uuid>` — sintético e impossível de colidir com pedido real
(que vem do provedor). Guarda: pedido real não pode começar com `pre:`.

## 5. Privacidade do WhatsApp — decidida nominalmente

**O número mora ao lado da matrícula e aparece SÓ no painel do mantenedor.**
Perguntado a ele em 27/08/2026, com a alternativa (a Caixa também poder ler)
oferecida e **recusada**.

É a mesma disciplina que a `DECISAO-EVO-01` §3 deu ao e-mail (*"vive numa linha
só e não circula"*), pela mesma razão: cada peça a mais que guarda um telefone é
mais um lugar de onde ele pode vazar. Consequência de desenho, e ela tem guarda:
**`whatsapp` não aparece na resposta de `GET /matriculas`, e nunca viaja em
evento nenhum.** Só `GET /pre-matriculas` — a porta do admin — o devolve.

## 6. O formulário: uma tela, não três

O mantenedor imaginou 2–3 passos; a recomendação de uma tela só foi apresentada
com o motivo e **aceita por ele**. São quatro campos (dois opcionais) e a pessoa
acabou de fazer login — está no pico da motivação, e cada passo a mais é um
ponto de desistência. Formulário em etapas paga a si mesmo em cadastros longos,
não em quatro campos.

Campos: **nome completo** e **WhatsApp com DDD** (obrigatórios); **data da
compra** e **turma** (opcionais). Os dois opcionais são *pistas de conferência*
— servem para o mantenedor achar a pessoa na lista dele — e a tela diz isso, para
que ninguém invente um valor achando que é obrigatório.

## 7. O que fica FORA, de propósito

- **Aprovação automática de qualquer espécie.** Toda liberação é humana. Qualquer
  pessoa com conta Google consegue entrar na fila — é porta aberta para spam, e a
  única defesa que não erra é alguém olhar.
- **Aviso por WhatsApp.** O número é guardado, não usado. Mandar mensagem é
  decisão de canal, exige a `mensageria` (cujo envio ainda é *stub*) e não entra
  aqui.
- **Editar os dados depois.** V1 recebe e mostra; correção é o admin recusando e
  a pessoa reenviando.

## 8. As fases

1. **A fila existe** — `alunos` ganha os status, os campos e as portas novas; a
   consulta de acesso passa a excluir os status que não valem (§3); a Caixa troca
   o beco pelo formulário.
2. **O admin libera** — página da fila no painel, com liberar e recusar (com
   motivo), e "há quantos dias espera" visível.
3. **O aviso e a porta** — a pessoa liberada é avisada pela caixa de
   notificações (o primeiro uso dela fora da Caixa), e a home ganha o botão.

---

*Relacionados: `RITOS.md` §3 (o rito cumprido aqui) · `CLAUDE.md` (lei
anti-duplicação) · `docs/caixa-de-sugestoes/DECISAO-EVO-01-identidade.md` §3 (o
e-mail numa linha só — a disciplina que a §5 copia) ·
`docs/decisoes/DECISAO-celula-admin.md` (a porta do painel) ·
`docs/notificacoes/PLANO-MESTRE.md` (a caixa de avisos que a fase 3 usa).*
