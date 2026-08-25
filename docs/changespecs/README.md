# `docs/changespecs/` — onde os corredores moram

Esta pasta guarda os **ChangeSpecs**: o documento que fica entre uma decisão de
produto já tomada e a implementação por um agente. É o que impede uma ideia
aprovada de virar um prompt aberto do tipo *"implemente isso"*.

Um ChangeSpec por arquivo. Nada mais mora aqui.

---

## A lei mora em outro arquivo, e é de propósito

**A lei deste formato é [`../caixa-de-sugestoes/FORMATO-CHANGESPEC.md`](../caixa-de-sugestoes/FORMATO-CHANGESPEC.md).**

Este README **aponta** para ela; não a repete. Uma segunda cópia do mesmo
documento pareceria mais cômoda ("a lei ao lado dos arquivos que ela rege") e
seria a armadilha §5.11 desta casa: **duas cópias derivam, e derivam em
silêncio** — no lote de 25/08/2026 isso já custou dois PRs, num script de
provisionamento cujo texto embutido divergiu do molde e teria derrubado a Caixa
em produção. Quem for editar o formato edita **um** arquivo, e este ponteiro
continua certo sem manutenção.

O que este README acrescenta é só o que a lei não podia saber quando foi
escrita: **como se nomeia um arquivo aqui**, e **quem assina**.

---

## Como se nomeia um arquivo

```
CS-{celula}-{sequencial}.md
```

- `{celula}` é a **célula responsável** — a que o ChangeSpec autoriza a tocar
  (campo `CÉLULA(S) RESPONSÁVEL(IS)`), em MAIÚSCULAS, sem acento.
  Ex.: `PORTFOLIO`, `SUGESTOES`, `CATALOGO`.
- `{sequencial}` é um número de quatro dígitos, contado **por célula**, começando
  em `0001`. Não é global: `CS-PORTFOLIO-0001` e `CS-SUGESTOES-0001` convivem.
- O nome do arquivo é **igual ao campo `CHANGE-ID`** de dentro dele, mais `.md`.
  Se os dois discordarem, quem manda é o campo — e o arquivo está com o nome
  errado.

**Versão nova é arquivo novo.** O §4 do formato é explícito: depois de aprovado,
um ChangeSpec **não é editado**. Se o escopo mudar durante a implementação,
nasce `CS-PORTFOLIO-0001-v2.md`, com o campo `SUBSTITUI` apontando para o
anterior, e o anterior **fica onde está**. É o mesmo princípio do histórico
append-only da Célula de Sugestões, aplicado a documento.

---

## Quem escreve, e quem assina

Duas regras, e nenhuma das duas é formalidade.

### 1. Quem escreve o ChangeSpec nunca é quem o implementa

É o §1 do formato, e é a propriedade de segurança que justifica o documento
existir: se o mesmo agente que desenha o próprio escopo também o executa, o
ChangeSpec vira uma folha que ele preenche para si mesmo. Um agente pode ajudar
a **redigir o rascunho**; a aprovação é humana e nominal.

### 2. Quem aprova é só o mantenedor — e isso agora é mecânico

Decidido em 25/08/2026 e registrado em
[`../caixa-de-sugestoes/DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md`](../caixa-de-sugestoes/DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md).
O campo `APROVADO_POR` deixou de ser prosa:

- a célula `sugestoes` reconhece como aprovador **apenas** quem estiver na
  variável de ambiente **`SUGESTOES_APROVADORES`** (hoje, só o mantenedor);
- a lista é **fail-closed**: ausente ou vazia ⇒ **ninguém** aprova ⇒ nenhuma
  ideia sai de `PLANEJADO` para `EM_DESENVOLVIMENTO`. Isto é o comportamento
  **certo**, não um defeito a consertar: *"não sei quem pode aprovar"* jamais
  pode virar *"então pode qualquer um"*;
- **ser da equipe não basta.** `SUGESTOES_STAFF_EMAILS` (modera, muda status,
  escreve avaliação interna) e `SUGESTOES_APROVADORES` (autoriza entrar em
  desenvolvimento) são papéis diferentes, e há teste-guarda para a diferença.

### 3. O que a Caixa confere, e o que ela não confere

A célula **não lê este repositório em runtime**. Ela guarda um **registro
mínimo** — id do ChangeSpec, quem aprovou, quando, e o link para o documento
aqui — e a trava do status lê a existência desse registro.

A garantia, escrita por extenso para ninguém supor mais do que existe:
**"uma pessoa autorizada afirmou que este ChangeSpec está aprovado, e ficou
registrado quem foi e quando"** — nunca "o documento existe e está bem
preenchido". Quem confere o documento é gente.

---

## O caminho completo, do aluno ao código

```
sugestão (linguagem do aluno)
    → decisão de produto (linguagem do produto)   ← AvaliacaoInterna.decisao_produto
    → ChangeSpec (linguagem da engenharia)        ← ESTA PASTA
    → agente implementa
```

Passo a passo, na prática:

1. Uma sugestão real acumula votos e comentários na Caixa
   (`meshcraft.top/forms/sugestoes/`).
2. A equipe escreve a decisão de produto em `AvaliacaoInterna.decisao_produto` —
   uma linha, não um documento novo.
3. Alguém (pessoa ou agente-redator, **nunca o agente que vai implementar**)
   copia o [`CS-TEMPLATE.md`](CS-TEMPLATE.md) para `CS-{celula}-{sequencial}.md`
   e o preenche inteiro.
4. O mantenedor lê, e assina `APROVADO_POR` com **nome e data**.
5. Alguém em `SUGESTOES_APROVADORES` registra a aprovação na Caixa, na tela de
   moderação da ideia ("Registrar ChangeSpec aprovado"). Só então a ideia sai de
   `PLANEJADO`.
6. O despacho do agente implementador **cita este arquivo** e não inventa escopo
   fora dele.

---

## Ainda não há nenhum ChangeSpec aqui, e isso está certo

Em 25/08/2026 a Caixa está no ar e o corredor inteiro existe (trava, registro,
tela), mas **nenhuma sugestão real chegou ainda**. Escrever um ChangeSpec de
exemplo para "estrear a pasta" seria criar exatamente a formalidade vazia que
este documento existe para impedir — e ainda por cima com o `APROVADO_POR`
assinado por ninguém.

O primeiro arquivo desta pasta nasce quando houver uma ideia de gente para virar
trabalho. O exemplo preenchido, para quem quiser ver a forma final, está no §6
do próprio [`FORMATO-CHANGESPEC.md`](../caixa-de-sugestoes/FORMATO-CHANGESPEC.md).

---

*Relacionados: [`FORMATO-CHANGESPEC.md`](../caixa-de-sugestoes/FORMATO-CHANGESPEC.md)
(a lei) · [`DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md`](../caixa-de-sugestoes/DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md)
(quem assina) · [`ESPECIFICACAO-CELULA.md`](../caixa-de-sugestoes/ESPECIFICACAO-CELULA.md)
§8 e §12 · `INVARIANTES.md` [INV-SUG10].*
