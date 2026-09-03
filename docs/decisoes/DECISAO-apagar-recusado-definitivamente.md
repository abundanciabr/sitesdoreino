# DECISÃO — apagar de vez, mas só quem foi recusado

> **Decidida pelo mantenedor em 03/09/2026**, por pergunta estruturada, com o
> preço do caminho pedido apresentado ANTES da escolha:
>
> - *"Você quer mesmo trazer de volta a capacidade de apagar de vez, só para
>   quem foi recusado (nunca chegou a ser aluno)?"* → **"Sim, apagar para
>   sempre"**, contra a recomendação de só esconder da lista sem apagar de
>   verdade.
>
> **Status:** *isto é lei*, e ela **reverte, só para uma fatia**, a
> `DECISAO-a-ficha-nao-se-apaga.md`. A reversão está escrita aqui inteira, com
> o que se ganha e o que se perde, para ninguém no futuro achar que foi
> descuido — a mesma disciplina que aquela lei usou ao reverter a
> `DECISAO-administradores-e-apagar.md` §4.

---

## 1. O que muda, em uma frase

**Um pedido de entrada RECUSADO — que nunca chegou a virar aluno — pode ser
apagado de vez**, pelo botão "Apagar de vez" na tela
`/admin/escola/alunos/recusados`. É irreversível: depois de apagado, não sobra
prontuário nem histórico daquela linha.

## 2. O que NÃO muda — e é o que mantém a lei de 29/08 de pé

**Quem já foi aluno, mesmo que só uma vez e mesmo que tenha saído, continua
com a ficha protegida para sempre.** A `DECISAO-a-ficha-nao-se-apaga.md`
continua valendo integralmente para:

- quem está `ativa`, `suspensa`, `reembolsada` ou `encerrada` — ou seja,
  qualquer estado de `STATUS_QUE_JA_DERAM_ACESSO`;
- quem está `aguardando` na fila (ainda não foi decidido);
- o prontuário de qualquer pessoa, em qualquer situação.

A distinção é a mesma que a lei de 29/08 já usa em `passado_de_quem_espera`:
**"foi recusado" não é "foi aluno".** Uma pessoa recusada nunca teve acesso à
escola — não há aula assistida, não há progresso na Caixa, não há nada que a
trajetória de aluno precise contar. O que existe é um pedido que o mantenedor
julgou e negou, e ele decidiu que, para ESSE caso específico, o direito de
apagar pesa mais que o direito de manter prova.

**A porta continua fechada para toda matrícula real.** `DELETE
/matriculas/{id}` não existe — a ausência dele é a lei de 29/08, intacta
(`test_nao_existe_porta_que_apague_uma_ficha` continua vermelho para qualquer
`DELETE` ali). O que nasce é uma porta NOVA, `DELETE
/pre-matriculas/{id}`, e ela só alcança linhas com `status = recusada`: quem
tenta apagar uma linha `aguardando` recebe 409, e quem tenta apagar por essa
porta uma matrícula que não nasceu na fila (sem o prefixo `pre:`) recebe 404 —
o mesmo desenho de fronteira que `POST /pre-matriculas/{id}/decisao` já usa.

## 3. Por que o mantenedor decidiu assim, e o preço dito com todas as letras

A `DECISAO-a-ficha-nao-se-apaga.md` §2 explicou o preço de apagar: destrói a
única prova de que a pessoa existiu na escola. Isso continua verdadeiro aqui
— **depois de apagado, não há como saber que aquele pedido existiu.** Nenhum
prontuário, nenhuma auditoria do lado da `alunos` (a auditoria da célula
`admin` continua guardando QUE o gesto foi feito, por quem e sobre qual `id`
— nunca o nome nem o WhatsApp da pessoa, pela mesma regra de sempre — mas o
`id` deixa de apontar para linha nenhuma).

**O que fica no lugar, para quem quiser voltar atrás sem apagar:** o botão
"Aceitar mesmo assim" (`DECISAO`s de 02/09, a tela de recusados) continua ao
lado do novo, e continua sendo o caminho reversível. Apagar é para quando o
mantenedor não quer mais aquela linha na lista — spam, teste, pedido
duplicado, pessoa que pediu para sumir — e sabe que não há volta.

## 4. O contrato — porta nova, e a que morreu continua morta

`docs/decisoes/DECISAO-a-ficha-nao-se-apaga.md` §2 já registrou que remover
capacidade é diferente de remover botão, e exige o Rito §3
(`RITOS.md`). Esta porta nasce pelo mesmo rito, na direção contrária: PR
próprio, só `contracts/`, com a label `contrato`; a implementação em
`services/alunos` e o botão em `services/admin` vêm em PR seguinte, contra o
contrato já congelado — crescer é aditivo (`ci/contrato_aditivo.py`), e não
precisa de autorização especial.

## 5. A auditoria — verbo próprio

`Registro.APAGAR_RECUSADO` é verbo NOVO, e não o `Registro.APAGAR`
aposentado em 29/08 (esse continua no vocabulário só para linhas antigas
continuarem legíveis — nenhum caminho novo o escreve). Quem ler a tabela em
meses precisa distinguir "apaguei a ficha de um aluno" (nunca mais acontece)
de "apaguei um pedido recusado" (o gesto novo) — os dois com a palavra
"apagar" no meio confundiriam qual dos dois era possível na data em que a
linha foi escrita.

---

*Relacionados: `DECISAO-a-ficha-nao-se-apaga.md` (revertida aqui, só para
recusados) · `DECISAO-administradores-e-apagar.md` §4 (o botão original, e a
razão pela qual ele morreu — continua morta para matrícula real) ·
`docs/decisoes/DECISAO-fila-de-liberacao.md`.*
