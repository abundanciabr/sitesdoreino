# DECISÃO: cursos, matrículas e alunos

**Data:** 6 de setembro de 2026
**Quem decidiu:** o mantenedor, com estas palavras: *"nessa tela de liberar o aluno é que você precisa criar uma lista com os cursos que oferecemos, e teremos vários cursos, e vários produtos, que serão liberados tanto aqui quanto diretamente pela página de checkout"*, e *"REGISTRE ISSO PARA DEIXAR REGISTRADO COMO VAI FUNCIONAR DAQUI PRA FRENTE EM RELAÇÃO AOS CURSOS, MATRÍCULAS E ALUNOS"*.

---

## §1 A regra, em uma frase

**Ninguém é "aluno do site". Todo mundo é aluno DE UM PRODUTO**, e a matrícula é o que diz qual.

Uma pessoa pode ter várias matrículas, uma por produto. Liberar alguém sem dizer qual produto deixa de ser possível.

**Por que "produto" e não "curso"** (emenda do mantenedor, 6 de setembro de 2026, com as palavras dele: *"o aluno é aluno da escola, mas ele está na escola matriculado em algum curso. Ou ele comprou algum produto, seja um PDF ou outro produto, mas ele sempre entra pela via da compra de algo, e daí ao entrar ele já deve estar vinculado a um curso ou produto"*).

Um curso **é** um produto. Um livro em PDF também. A escola vende coisas, e cada coisa vendida é a razão de alguém estar dentro. Escrever a lei em cima de "curso" faria o primeiro produto que não fosse curso quebrar a regra ou virar exceção. Escrever em cima de "produto" cobre os dois casos sem uma linha a mais.

Isso também explica por que o campo no sistema já se chama `product_id`, e não `curso_id`: quem desenhou a célula acertou antes de a lei existir.

**Sempre pela compra.** A porta principal não é a liberação: é a compra. A liberação existe para quem entra pela sala de espera (as turmas anteriores, os convites), e não para criar aluno do nada.

## §2 Por que isto é lei, e não preferência

Até 6 de setembro de 2026, ser aluno era um estado binário: a pessoa tinha matrícula ativa, ou não tinha. A sala de aula servia "o curso do site", e enquanto houvesse um curso só isso funcionava por coincidência, não por desenho.

O dia em que nascesse o segundo curso, **todo aluno veria o primeiro**, sem erro, sem aviso, e sem nenhuma tela quebrada. É a mesma classe de defeito que a resolução do curso pelo apelido acabou de curar no endereço, e curá-la num lugar só não bastaria.

## §3 O que já existia, e por isso esta lei é ligação e não construção

Medido no `origin/main` em 6 de setembro de 2026:

- **`Matricula.product_id` já existe** em `services/alunos/apps/matriculas/models.py`, desde a primeira migração da célula.
- **A restrição de unicidade da fila diz, por escrito, que várias matrículas por pessoa são o normal:** *"para não impedir que a mesma pessoa tenha várias matrículas pagas no mesmo site (que é o normal: um curso cada)"*.
- **Quem entra pela sala de espera nasce sem produto:** `services.py` cria a linha da fila com `product_id=""`, porque naquele momento ninguém sabia o que a pessoa queria.

### A frase errada que esta lei teve por algumas horas

A versão de 6 de setembro de 2026 dizia: *"quem entra pela compra já informa o curso: `POST /matriculas` exige `product_id` no corpo, e o checkout o manda"*.

**Era falso, e quem mediu foi o robô da TAR-220**, não eu. Eu li a assinatura da operação e não segui quem a chama. A porta real da compra **não é** aquela operação: é o evento `pagamento.aprovado.v1`, e o contrato dele carrega `site_id`, `payment_id`, `order_id`, `amount_cents`, `method`, `mp_payment_id` e `customer`. **Nenhum produto.** O tratador grava `product_id=""`, e a matrícula paga nasce ativa sem produto, sem passar por decisão nenhuma.

Fica escrito porque o erro é instrutivo: **assinatura de função não é caminho de dado.** Só seguir quem chama responde por onde a coisa entra de verdade.

### Os dois buracos, então, e não um

| # | Onde | Estado |
|---|---|---|
| 1 | a sala de espera nasce sem produto | fechado pela TAR-220: liberar passa a exigir |
| 2 | **o aviso da compra não carrega o produto** | **aberto**, e é a TAR-225 |

O segundo é o mais grave dos dois, porque é a porta principal: **é por ela que entra quem paga.**

## §4 As duas portas de matrícula, e a regra vale nas duas

| Porta | Quem usa | Onde o produto entra |
|---|---|---|
| **A compra**, que é a principal | quem paga pela página de checkout | **precisa passar a vir no aviso da compra**, e hoje não vem (TAR-225) |
| **A liberação** | quem pede entrada em `/cadastro` e o mantenedor libera | **passa a ser obrigatório escolher na tela** (TAR-220) |

Nenhuma terceira porta nasce sem passar por aqui.

**A compra é a porta principal, e a lei se lê nessa ordem.** A liberação existe para quem vem das turmas anteriores e para convite; ela não é o caminho normal de virar aluno. Uma lei que só fechasse a liberação deixaria aberta justamente a porta por onde entra quem paga.

## §5 Os cursos, e a numeração

| Nº | Curso | Quem tem hoje |
|---|---|---|
| **1** | Primeiros Dólares com Roblox | **TODOS** os alunos que já estão no site |
| **2** | O curso do livro (as 33 encomendas mais a Bônus) | ninguém ainda; é o que está sendo construído |

**Toda matrícula que existe hoje passa a apontar para o curso 1.** É o único desfecho verdadeiro: essas pessoas compraram aquele curso, e nenhuma delas comprou o segundo.

### O "1" e o "2" são apelidos de conversa, e não identidade no sistema

Medido em 6 de setembro de 2026, depois de escrita a primeira versão desta lei: **número de ordem de curso não existe em lugar nenhum do sistema**. Este parágrafo corrige a versão anterior, que dizia que o número "entra em matrícula, em pedido de compra e em endereço".

O que existe são dois identificadores, e são eles que não mudam:

| onde | o que identifica |
|---|---|
| catálogo, matrícula, pedido de compra | um **UUID**, sorteado quando o produto é criado |
| endereço da sala de aula | o **apelido** do curso (`/cursos/profissional/parte-1/E00`) |

E número de ordem **não vai passar a existir**: ele obrigaria alguém a renumerar o mundo no dia em que um curso saísse do meio da lista, e um número que muda é pior do que nenhum.

Os apelidos de conversa continuam valendo entre nós, porque são como o mantenedor pensa nos cursos, e ele os usou ao pedir isto. Cursos novos ganham o número seguinte **na conversa**. O que a máquina guarda é o UUID e o apelido.

**A mesma lição, pela segunda vez no mesmo dia e na mesma página:** eu escrevi um mecanismo na lei sem medir se ele existia. É irmã da frase sobre a compra, corrigida algumas horas antes, e a régua que faltava é a mesma: ir ver.

## §6 O que a tela de liberar passa a fazer

Em `/admin/escola/alunos/`, o botão de liberar deixa de ser um botão só. Ele passa a exigir **duas coisas, nesta ordem**:

1. **escolher o produto** (obrigatório, sem valor padrão);
2. liberar.

**Sem produto escolhido, não libera.** Um valor padrão seria pior do que não ter a lista: ele faria a escolha errada parecer escolha, e ninguém veria o erro até o aluno abrir a sala e encontrar o curso errado.

## §7 O que isto NÃO faz

- **Não cria uma tabela de cursos na célula `alunos`.** O catálogo de cursos tem dono, e a matrícula guarda a referência, nunca a cópia. Duas listas de cursos divergiriam no primeiro curso novo.
- **Não decide preço, nem ordem de venda, nem quem pode comprar o quê.** Isso é do catálogo e do checkout.
- **Não muda o conteúdo de nenhum curso.** O texto das aulas continua entrando pela tela do editor, e só por ela.
- **Não retroage sobre quem foi reembolsado ou pausado.** O status da matrícula continua sendo o que decide acesso; esta lei só acrescenta *de qual curso*.

## §8 O invariante

**[INV-ALU-C1] Nenhuma matrícula ativa sem produto.**

- **O quê:** toda matrícula em status que dá acesso aponta para um produto. Liberar sem produto é recusado na porta, não na tela. **O invariante só estará inteiro quando a TAR-225 fechar o caminho da compra**: hoje ele vale na liberação e não vale no pagamento, e isso está dito na cara em vez de escondido atrás de um verde.
- **Por quê:** matrícula sem produto obriga quem lê a adivinhar, e o palpite mais provável ("o primeiro do site") é exatamente o defeito que esta lei existe para impedir.
- **Como se prova:** teste que tenta liberar sem produto e espera recusa, provado por mutação.

## §9 O que acontece quando o terceiro curso nascer

Nada de novo. Ele entra no catálogo, ganha o número seguinte, aparece na lista da tela de liberar e no checkout. Nenhuma linha de código muda por causa dele. **Se um curso novo exigir mudança de código, esta lei falhou** e é ela que se conserta, não o curso.

---

*DECISÃO: cursos, matrículas e alunos · 6 de setembro de 2026, emendada no mesmo dia · Ninguém é aluno do site: todo mundo é aluno de um PRODUTO, e sempre entra pela compra de algo.*
