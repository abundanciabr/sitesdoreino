<!--
=============================================================================
MOLDE DE CHANGESPEC — COPIE ESTE ARQUIVO, NÃO O EDITE.

    cp docs/changespecs/CS-TEMPLATE.md docs/changespecs/CS-{CELULA}-{NNNN}.md

Lei do formato: docs/caixa-de-sugestoes/FORMATO-CHANGESPEC.md (§3 campos, §4
validade, §5 gatilho). Quem assina: docs/caixa-de-sugestoes/
DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md. Como se nomeia: README.md
desta pasta.

Apague TODOS os comentários `<!-- … -->` ao preencher. Um molde que sobrevive
dentro do documento final é um documento que ninguém leu até o fim.
=============================================================================
-->

# CS-{CELULA}-{NNNN} — {título curto em linguagem de produto}

## PORTÃO DE VALIDADE — confira ANTES de mandar para aprovação

<!--
São as quatro regras do §4 do formato. Um ChangeSpec que falha em qualquer uma
delas NÃO está pronto para um agente pegar — e um molde que deixasse passar um
ChangeSpec inválido seria pior que molde nenhum, porque daria a aparência do
processo sem a propriedade que o processo garante.
-->

- [ ] **`FORA DO ESCOPO` não está vazio.** Se não dá para dizer o que fica de
      fora, não houve escopo de verdade — houve intenção.
- [ ] **`CÉLULAS PROIBIDAS` lista cada célula do sistema fora da responsável,
      uma por uma.** Nunca resumida como "nenhuma outra": o agente que lê uma
      lista fechada não precisa julgar; o que lê "nenhuma outra" precisa.
- [ ] **Todo item de `CRITÉRIOS DE ACEITAÇÃO` é verificável objetivamente.**
      "Melhorar a experiência" não é AC. "Aluno publica portfólio e recebe URL
      pública em até 3 cliques" é.
- [ ] **`APROVADO_POR` está preenchido** com nome e data de uma pessoa que
      está em `SUGESTOES_APROVADORES` (hoje: só o mantenedor). Lista vazia ⇒
      ninguém aprova ⇒ nada entra em desenvolvimento. É fail-closed de
      propósito.

---

## CHANGE-ID

`CS-{CELULA}-{NNNN}`

<!-- Igual ao nome do arquivo, sem o `.md`. `{CELULA}` em maiúsculas, sem
acento; `{NNNN}` com quatro dígitos, contado por célula, a partir de 0001. -->

## SUBSTITUI

<!-- Só existe em versão nova (`-v2`, `-v3`). O §4 do formato: ChangeSpec
aprovado NÃO se edita; escopo que muda vira arquivo novo apontando para o
anterior, e o anterior fica onde está. Apague esta seção inteira se este é o
primeiro. -->

—

## ORIGEM

<!-- `suggestion_id`(s) REAIS da Célula de Sugestões — o número que aparece na
URL da ideia. Se nasceu de várias sugestões mescladas, ou de um padrão visto em
várias, liste TODAS. ChangeSpec sem origem é escopo inventado. -->

suggestion_id …

## PROBLEMA

<!-- Reescrito em linguagem de PRODUTO. Nunca a frase literal do aluno: a
tradução é o passo que se perde sob pressa, e é justamente ele que separa
"a pessoa pediu um botão" de "a pessoa não consegue fazer X". -->

## EVIDÊNCIAS

<!-- Números puxados da própria Caixa, não impressão: total de votos, autores
únicos, comentários relevantes. É o que sustenta a prioridade quando alguém
perguntar, daqui a três meses, por que isto foi feito antes daquilo. -->

- Votos:
- Autores únicos:
- Comentários relevantes:

## OBJETIVO

<!-- O que muda PARA O ALUNO quando isto for entregue. Uma frase. Se ela
descreve uma mudança técnica e não uma mudança na vida de quem usa, está no
campo errado. -->

## FORA DO ESCOPO

<!-- OBRIGATÓRIO, e não pode ficar vazio (§4). Liste o que NÃO será construído
nesta entrega — inclusive o que parece "óbvio que não". O que não estiver aqui
o agente pode entender como aberto. -->

-
-
-

## CÉLULA(S) RESPONSÁVEL(IS)

<!-- Qual célula este ChangeSpec autoriza a tocar. É também o `{CELULA}` do
CHANGE-ID. -->

`…`

## CONTRATOS PERMITIDOS

<!-- Os contratos inter-célula que o agente pode chamar, POR NOME. Contrato que
não está aqui não pode ser chamado — e contrato que ainda não existe não se
inventa dentro de um despacho: nasce pelo Rito de Contrato (RITOS.md §3), com o
mantenedor presente, e NUNCA dentro de um lote. -->

-

## CÉLULAS PROIBIDAS

<!-- Cada célula do sistema fora da responsável, listada UMA POR UMA (§4).
As 11 de hoje: admin, alunos, catalogo, checkout, funil, identidade, leads,
mensageria, pagamentos, quiz, sugestoes. Confira a lista real em `services/`
antes de copiar — ela cresce. -->

-

## CRITÉRIOS DE ACEITAÇÃO

<!-- Numerados AC-01, AC-02… Cada um verificável objetivamente por alguém que
não participou desta conversa. -->

- **AC-01:**
- **AC-02:**

## TESTES OBRIGATÓRIOS

<!-- O que precisa ter teste automatizado ANTES do merge. Escreva o que o teste
deve conseguir REPROVAR, não o que ele deve confirmar: um guarda que nunca
poderia ficar vermelho é decoração. -->

-
-

## RISCO E ROLLBACK

<!-- Como desfazer se algo sair errado em produção. Se a resposta for "não tem
como desfazer", isso é uma decisão a tomar antes, não depois. -->

## DEFINITION OF DONE

<!-- Checklist final. As três primeiras linhas valem para qualquer célula desta
casa e não se apagam. -->

- [ ] Todos os AC acima com teste automatizado, e cada guarda provado por
      mutação (quebre o código de propósito; se a suíte continuar verde, o
      guarda não existe)
- [ ] Nenhuma ForeignKey cruzando banco de célula
- [ ] `make ci` da célula verde **e** `python ci/ci.py` verde
- [ ] Evento `sugestao.status-alterado` disparado ao mover o(s) `suggestion_id`
      de origem para `IMPLEMENTADO`
- [ ]

## APROVADO_POR

<!-- VAZIO até a aprovação humana explícita. Não preencha com "a equipe", "o
time" nem com o nome de um agente. Nome de pessoa e data (DD/MM/AAAA), e essa
pessoa precisa estar em `SUGESTOES_APROVADORES`.

Enquanto esta linha estiver vazia, a ideia NÃO sai de PLANEJADO — a trava é
mecânica, em três degraus (ponto de estrangulamento, `Sugestao.save()` e um
trigger no Postgres). Não adianta contornar; adianta colher a assinatura. -->

_(vazio — sem isto, o ChangeSpec não está pronto para nenhum agente pegar)_
