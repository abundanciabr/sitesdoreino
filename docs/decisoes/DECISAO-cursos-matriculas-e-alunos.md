# DECISÃO: cursos, matrículas e alunos

**Data:** 6 de setembro de 2026
**Quem decidiu:** o mantenedor, com estas palavras: *"nessa tela de liberar o aluno é que você precisa criar uma lista com os cursos que oferecemos, e teremos vários cursos, e vários produtos, que serão liberados tanto aqui quanto diretamente pela página de checkout"*, e *"REGISTRE ISSO PARA DEIXAR REGISTRADO COMO VAI FUNCIONAR DAQUI PRA FRENTE EM RELAÇÃO AOS CURSOS, MATRÍCULAS E ALUNOS"*.

---

## §1 A regra, em uma frase

**Ninguém é "aluno do site". Todo mundo é aluno DE UM CURSO**, e a matrícula é o que diz qual.

Uma pessoa pode ter várias matrículas, uma por curso. Liberar alguém sem dizer em qual curso deixa de ser possível.

## §2 Por que isto é lei, e não preferência

Até 6 de setembro de 2026, ser aluno era um estado binário: a pessoa tinha matrícula ativa, ou não tinha. A sala de aula servia "o curso do site", e enquanto houvesse um curso só isso funcionava por coincidência, não por desenho.

O dia em que nascesse o segundo curso, **todo aluno veria o primeiro**, sem erro, sem aviso, e sem nenhuma tela quebrada. É a mesma classe de defeito que a resolução do curso pelo apelido acabou de curar no endereço, e curá-la num lugar só não bastaria.

## §3 O que já existia, e por isso esta lei é ligação e não construção

Medido no `origin/main` em 6 de setembro de 2026:

- **`Matricula.product_id` já existe** em `services/alunos/apps/matriculas/models.py`, desde a primeira migração da célula.
- **A restrição de unicidade da fila diz, por escrito, que várias matrículas por pessoa são o normal:** *"para não impedir que a mesma pessoa tenha várias matrículas pagas no mesmo site (que é o normal: um curso cada)"*.
- **Quem entra pela compra já informa o curso:** `POST /matriculas` exige `product_id` no corpo, e o checkout o manda.
- **Quem entra pela sala de espera nasce sem curso:** `services.py` cria a linha da fila com `product_id=""`, porque naquele momento ninguém sabia qual curso a pessoa queria.

O buraco é um só, e está na terceira linha desta lista.

## §4 As duas portas de matrícula, e a regra vale nas duas

| Porta | Quem usa | Onde o curso entra |
|---|---|---|
| **A compra** | quem paga pela página de checkout | já vem no pedido, e sempre veio |
| **A liberação** | quem pede entrada em `/cadastro` e o mantenedor libera | **passa a ser obrigatório escolher na tela**, e é a mudança desta lei |

Nenhuma terceira porta nasce sem passar por aqui.

## §5 Os cursos, e a numeração

| Nº | Curso | Quem tem hoje |
|---|---|---|
| **1** | Primeiros Dólares com Roblox | **TODOS** os alunos que já estão no site |
| **2** | O curso do livro (as 33 encomendas mais a Bônus) | ninguém ainda; é o que está sendo construído |

**Toda matrícula que existe hoje passa a apontar para o curso 1.** É o único desfecho verdadeiro: essas pessoas compraram aquele curso, e nenhuma delas comprou o segundo.

Cursos novos ganham o número seguinte. O número é identidade e **não muda**, porque ele entra em matrícula, em pedido de compra e em endereço.

## §6 O que a tela de liberar passa a fazer

Em `/admin/escola/alunos/`, o botão de liberar deixa de ser um botão só. Ele passa a exigir **duas coisas, nesta ordem**:

1. **escolher o curso** (obrigatório, sem valor padrão);
2. liberar.

**Sem curso escolhido, não libera.** Um valor padrão seria pior do que não ter a lista: ele faria a escolha errada parecer escolha, e ninguém veria o erro até o aluno abrir a sala e encontrar o curso errado.

## §7 O que isto NÃO faz

- **Não cria uma tabela de cursos na célula `alunos`.** O catálogo de cursos tem dono, e a matrícula guarda a referência, nunca a cópia. Duas listas de cursos divergiriam no primeiro curso novo.
- **Não decide preço, nem ordem de venda, nem quem pode comprar o quê.** Isso é do catálogo e do checkout.
- **Não muda o conteúdo de nenhum curso.** O texto das aulas continua entrando pela tela do editor, e só por ela.
- **Não retroage sobre quem foi reembolsado ou pausado.** O status da matrícula continua sendo o que decide acesso; esta lei só acrescenta *de qual curso*.

## §8 O invariante

**[INV-ALU-C1] Nenhuma matrícula ativa sem curso.**

- **O quê:** toda matrícula em status que dá acesso aponta para um curso. Liberar sem curso é recusado na porta, não na tela.
- **Por quê:** matrícula sem curso obriga quem lê a adivinhar, e o palpite mais provável ("o primeiro do site") é exatamente o defeito que esta lei existe para impedir.
- **Como se prova:** teste que tenta liberar sem curso e espera recusa, provado por mutação.

## §9 O que acontece quando o terceiro curso nascer

Nada de novo. Ele entra no catálogo, ganha o número seguinte, aparece na lista da tela de liberar e no checkout. Nenhuma linha de código muda por causa dele. **Se um curso novo exigir mudança de código, esta lei falhou** e é ela que se conserta, não o curso.

---

*DECISÃO: cursos, matrículas e alunos · 6 de setembro de 2026 · Ninguém é aluno do site: todo mundo é aluno de um curso, e a matrícula é o que diz qual.*
