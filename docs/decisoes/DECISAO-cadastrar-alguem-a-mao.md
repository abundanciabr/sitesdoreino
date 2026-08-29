# DECISÃO — cadastrar alguém à mão

**Data:** 29/08/2026 · **Quem decidiu:** o mantenedor · **Estado:** valendo

## O buraco

Até hoje, **toda ficha nascia de um pedido da pessoa ou de uma compra**. Não
existia, em lugar nenhum do sistema, como o mantenedor pôr alguém na escola.

Um aluno que não conseguisse usar o formulário do site — que errasse o e-mail da
conta Google, que não achasse a página, que simplesmente pedisse por WhatsApp —
não tinha como entrar. E o mantenedor não tinha o que fazer a respeito.

É a lacuna nº 3 do mapa da jornada, aprovada por ele em 29/08/2026 junto com as
outras quatro.

## §1 — O caminho é o MESMO de todo mundo, só que depressa

A pessoa **entra na fila** (`POST /pre-matriculas`, a porta que o formulário do
site usa) e é **liberada na sequência** (`POST /pre-matriculas/{id}/decisao`).

**Nenhuma porta nova, e nenhuma mudança de contrato.** Uma operação capaz de
criar matrícula direto seria uma segunda forma de virar aluno, com outras
regras — e as duas discordariam na primeira mudança de lei. Também exigiria um
terceiro valor de `origem` (hoje: *comprou* / *liberado*), que todo consumidor
teria de aprender.

Do jeito que ficou, quem foi cadastrado à mão aparece como **`liberado`**, que é
a verdade: o mantenedor liberou. E aparece na mesma lista, com o mesmo
prontuário, decidido pela mesma porta.

> **A alternativa considerada e recusada:** uma operação nova na `alunos`
> (`POST /matriculas/manuais`) com prefixo e origem próprios. Ela evitaria as
> duas chamadas — e custaria um rito de contrato, um terceiro vocabulário de
> origem, e uma segunda regra sobre quem vira aluno. A recusa é por desenho, não
> por pressa: menos verdades sobre o mesmo fato.

## §2 — A falha do meio é segura, visível e DITA

São dois passos. Se o segundo falhar, **a pessoa não some**: ela fica na fila,
aparecendo na mesma tela, com o botão *Liberar* do lado.

E a tela diz exatamente isso:

> Cadastrei a pessoa, mas não consegui liberar o acesso dela agora. Ela está
> aqui em cima, na fila, esperando — é só clicar em Liberar. **Não cadastre de
> novo.**

O "não cadastre de novo" é a metade que importa. Um *"não deu certo"* genérico
faria o mantenedor tentar outra vez e criar confusão sobre a mesma pessoa.

Pelo mesmo motivo, **`não respondeu` nunca vira `recusado`**: quando a `alunos`
não responde, a criação *pode* ter acontecido, e a tela manda procurar a pessoa
na lista antes de tentar de novo.

## §3 — A escola: quem descobre é o servidor

Com **uma escola só**, o formulário **não pergunta qual**. O identificador
interno é ruído numa tela feita para leigo, e existe um teste-guarda de
28/08/2026 que o proíbe de aparecer (`test_com_uma_escola_so_o_codigo_interno_
dela_nao_aparece`). Quem a descobre é o servidor, no envio — custa uma leitura a
mais, e só nesse caminho.

Com **duas ou mais**, o campo aparece, com as opções tiradas dos dados de hoje
(nunca de uma lista configurada — uma lista própria seria uma segunda verdade
sobre quais escolas existem).

Com **nenhuma ficha**, não há de onde derivar: o campo aparece vazio e a tela
explica. Adivinhar seria pior que parar.

## §4 — A conferência é a mesma do site

Nome, e-mail e WhatsApp com DDD passam pelas **mesmas regras** do formulário da
Caixa. Se esta fosse mais frouxa, a pessoa cadastrada à mão apareceria na lista
com um telefone que o site nunca teria aceitado — e a lista deixaria de ser
comparável consigo mesma.

O e-mail viaja **em minúsculas**: a Caixa pergunta por `email.strip().lower()`,
e uma ficha gravada com maiúsculas seria liberada e continuaria invisível para
ela. A pessoa veria *"não encontramos matrícula"* depois de ter sido aprovada —
o pior desfecho possível deste formulário.

## §5 — Verbo próprio na auditoria

`Registro.CADASTRAR`, migração `0005_verbo_de_cadastrar`.

*"Liberei quem pediu"* e *"cadastrei alguém que não pediu"* são gestos
diferentes, e quem ler essa tabela em meses precisa saber qual dos dois
aconteceu. Mesma razão pela qual `EDITAR`, `PROMOVER` e `DESPROMOVER` nasceram
separados.

A linha é gravada **depois de saber o desfecho e antes de responder**, inclusive
quando dá errado — e **sem PII**: nem nome, nem telefone. A tabela é append-only
por trigger, e PII ali é PII que nunca mais sai.

## §6 — Onde ele fica

Dentro de um `<details>` fechado, entre a fila e a lista. Cadastrar à mão é a
**exceção**, não a rotina — quase todo mundo entra pelo formulário do site. Um
formulário grande e sempre aberto empurraria para baixo as duas coisas que o
mantenedor de fato abre essa tela para fazer.

## Guardas

`services/admin/tests/test_cadastrar_a_mao.py` — 18 testes, entre eles:

- `test_cadastrar_poe_na_fila_e_libera_na_sequencia` (o que carrega o arquivo);
- `test_liberacao_falhando_deixa_a_pessoa_na_fila_e_a_tela_diz_onde`;
- `test_a_alunos_fora_do_ar_diz_que_o_cadastro_PODE_ter_sido_feito`;
- `test_corpo_2xx_fora_do_contrato_nao_vira_sucesso`;
- `test_com_uma_escola_so_o_formulario_nao_pergunta_qual` e o par dele,
  `test_sem_o_campo_o_servidor_descobre_a_escola_sozinho`;
- `test_a_auditoria_nao_guarda_o_nome_nem_o_telefone_de_ninguem`.

## Fatia 4 de 5

Falta uma: **avisar pelo sino quando a situação de alguém muda**.
