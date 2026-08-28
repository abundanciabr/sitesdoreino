# DECISÃO — administrador por botão, e apagar de vez

> **Decidida pelo mantenedor em 28/08/2026**, por pergunta estruturada, com o
> preço de cada caminho apresentado ANTES da escolha e recusado por ele:
>
> - *"Quer um botão na tela para tornar alguém administrador?"* → **"Sim —
>   quero promover com um clique"**, contra a recomendação de deixar como
>   estava.
> - *"E o botão de apagar DE VEZ os dados de uma pessoa?"* → **"Quero o botão
>   agora"**, contra a recomendação de esperar o primeiro pedido real.
>
> **Status:** *isto é lei*, e ela **reverte** parte da `DECISAO-celula-admin`
> §2. A reversão está escrita aqui inteira, com o que se ganha e o que se
> perde, para ninguém no futuro achar que foi descuido.

---

## 1. O que muda, em uma frase

A lista de quem é administrador **deixa de morar só no servidor** e passa a ter
uma metade no banco da célula `admin`, editável por botão. E o painel ganha um
botão que **apaga de verdade** os dados de uma pessoa, em vez de só encerrar o
acesso dela.

## 2. Administrador por botão — o que se perde, dito com todas as letras

A `DECISAO-celula-admin` §2 dizia: *"quem decide quem entra é esta lista, na
hora, **derivada e nunca gravada**"*, e *"trocar quem é admin = editar env +
reiniciar"*. Essa propriedade tinha um nome prático:

> **Hoje, para alguém virar administrador da plataforma, é preciso ter as
> chaves do servidor.**

Com o botão, isso deixa de ser verdade. Passa a ser possível ganhar acesso de
administrador **sem tocar no servidor** — bastaria uma falha na própria área
administrativa (uma sessão roubada de quem já é admin, um defeito de
autorização numa tela). É a diferença entre *"precisa das chaves da casa"* e
*"precisa achar uma janela aberta"*.

**O mantenedor foi informado disso nessas palavras e escolheu assim mesmo.**
Não é ingenuidade: é a mesma filosofia de escopo que ele fixou em 25/08 —
prefere a ferramenta completa e assume o custo.

## 3. As quatro travas que tornam a troca aceitável

A reversão não vem sozinha. Cada trava abaixo fecha um modo de falha que a
propriedade antiga fechava de graça.

**3.1 O env continua sendo o CHÃO, e ninguém o remove por botão.** A lista
efetiva é `ADMIN_EMAILS` (do servidor) **∪** os ativos no banco. Consequências,
as duas desejadas:

- **não existe como se trancar para fora.** Quem está no env entra sempre, e o
  botão de remover recusa mexer nele — a saída continua sendo o servidor;
- **um banco vazio, corrompido ou restaurado de backup não fecha a porta.**

**3.2 Banco fora do ar não tranca ninguém, e também não abre.** Se a consulta
falhar, a lista efetiva é **só o env**, com ERROR no log. Fail-closed no
sentido certo: erro nunca AMPLIA quem entra.

**3.3 Toda promoção e toda remoção geram linha de auditoria** — append-only,
com quem fez, quando e sobre quem. É o que a propriedade antiga não precisava
ter (mexer no servidor já deixa rastro de outro tipo) e que a nova exige.

**3.4 Ninguém se remove sozinho.** O botão recusa a própria conta. Um
administrador que se remove por engano vira um chamado ao servidor — e, se for
o único, vira uma casa sem dono.

## 4. Apagar de vez — e o conflito que ele cria com a auditoria

**O botão apaga a matrícula de verdade** (a linha some da `alunos`), e não
apenas troca o estado. É o direito da pessoa de sumir do sistema.

**O conflito, e ele é real:** a auditoria da área administrativa é
**append-only por trigger no banco** — nem eu nem um comando direto conseguem
editar ou apagar uma linha dela. Se ela guardasse dado pessoal, apagar a
pessoa seria impossível sem furar a própria trava.

**A regra que resolve, e ela vale daqui em diante:**

> **A auditoria nunca guarda dado que a PESSOA forneceu.** Ela guarda o que o
> OPERADOR fez e escreveu.

Na prática: a linha registra *quem* mudou, *quando*, *sobre qual ficha* (um
identificador opaco), *quais campos* foram tocados e *o desfecho* — mas **não**
os valores de nome, WhatsApp, turma ou data. Motivo de recusa continua, porque
é texto do mantenedor, não da pessoa.

**Isto corrige algo entregue horas antes, no mesmo dia:** o formulário de
gestão gravava `nome_completo=...`, `whatsapp=...` no detalhe da auditoria.
Ficaria impossível de apagar. Passa a gravar só os NOMES dos campos.

**O que sobra depois de apagar:** uma linha dizendo *"em tal dia, o mantenedor
apagou a ficha X"*. Sem nome, sem telefone, sem e-mail. É o mínimo para a
auditoria continuar respondendo *"o que foi feito nesta área?"* e o máximo que
o direito da pessoa permite.

**Apagar é irreversível, e a tela diz isso antes.** Não há desfazer: a ficha
não existe mais. Encerrar continua existindo ao lado, para o caso comum.

## 5. O que continua igual

- **`administrador` não é um campo da `alunos`.** A `DECISAO-categorias-de-usuario`
  §2.1 segue intacta: quem responde isso é a célula `admin`. O que mudou foi
  ONDE a `admin` guarda a lista, não QUEM a responde.
- **A porta continua sendo o único ponto de autorização da célula**, conferindo
  a lista na hora, a cada requisição.
- **O e-mail continua não sendo editável** no formulário de aluno.

---

*Relacionados: `DECISAO-celula-admin.md` §2 (revertida em parte aqui) e §3 (a
auditoria) · `DECISAO-categorias-de-usuario.md` §2.1 (intacta) ·
`DECISAO-gestao-de-alunos.md` §4 e §5 (as duas perguntas que esta lei responde)
· `DECISAO-filosofia-de-escopo.md` (por que a opção completa venceu).*
