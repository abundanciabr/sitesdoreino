<!--
=============================================================================
MOLDE HISTÓRICO DE CHANGESPEC — uso opcional.

    cp docs/changespecs/CS-TEMPLATE.md docs/changespecs/CS-{CELULA}-{NNNN}.md

O formato de agosto de 2026 não exige campos, assinatura, outra sessão ou
imutabilidade para trabalho atual. AGENTS.md prevalece.

Se usar este molde, adapte ou retire os comentários que não ajudarem.
=============================================================================
-->

# CS-{CELULA}-{NNNN} — {título curto em linguagem de produto}

## Referências do modelo antigo (opcionais)

<!--
Os itens abaixo descrevem o desenho de agosto de 2026. Não bloqueiam a execução.
-->

- [ ] **`FORA DO ESCOPO` não está vazio.** Se não dá para dizer o que fica de
      fora, não houve escopo de verdade — houve intenção.
- [ ] **`CÉLULAS PROIBIDAS` lista cada célula do sistema fora da responsável,
      uma por uma.** Nunca resumida como "nenhuma outra": o agente que lê uma
      lista fechada não precisa julgar; o que lê "nenhuma outra" precisa.
- [ ] **Todo item de `CRITÉRIOS DE ACEITAÇÃO` é verificável objetivamente.**
      "Melhorar a experiência" não é AC. "Aluno publica portfólio e recebe URL
      pública em até 3 cliques" é.

---

## CHANGE-ID

`CS-{CELULA}-{NNNN}`

<!-- Igual ao nome do arquivo, sem o `.md`. `{CELULA}` em maiúsculas, sem
acento; `{NNNN}` com quatro dígitos, contado por célula, a partir de 0001. -->

## SUBSTITUI

<!-- Referência opcional a uma versão anterior; edições também podem ser feitas
no mesmo arquivo, com histórico no Git. -->

—

## ORIGEM

<!-- Se nasceu de sugestão da Caixa, cite o suggestion_id. Pedido direto não
precisa dessa origem. -->

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

<!-- Se útil, liste o que NÃO será construído
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

<!-- Contratos inter-célula pertinentes ao trabalho. -->

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

## Testes previstos no modelo de 2026

<!-- O que precisa ter teste automatizado ANTES do merge. Escreva o que o teste
deve conseguir REPROVAR, não o que ele deve confirmar: um guarda que nunca
poderia ficar vermelho é decoração. -->

-
-

## RISCO E ROLLBACK

<!-- Como desfazer se algo sair errado em produção. Se a resposta for "não tem
como desfazer", isso é uma decisão a tomar antes, não depois. -->

## DEFINITION OF DONE

<!-- Exemplo histórico de checklist; ajuste ao trabalho real e a AGENTS.md. -->

- [ ] Todos os AC acima com teste automatizado, e cada guarda provado por
      mutação (quebre o código de propósito; se a suíte continuar verde, o
      guarda não existe)
- [ ] Nenhuma ForeignKey cruzando banco de célula
- [ ] `make ci` da célula verde **e** `python ci/ci.py` verde
- [ ] Evento `sugestao.status-alterado` disparado ao mover o(s) `suggestion_id`
      de origem para `IMPLEMENTADO`
- [ ]

## APROVADO_POR

<!-- Registro histórico opcional; não condiciona a execução. -->

_(se houver registro)_
