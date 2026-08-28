# DECISÃO — "ex-aluno", e a porta que explica por que não abriu

> **Pedida pelo mantenedor em 28/08/2026**, depois de usar o botão de apagar
> pela primeira vez: *"Ao APAGAR um aluno apareceu essa mensagem onde
> aparentemente ele voltou para o nível/status/situação de pré-cadastro. O que
> eu queria era colocar ele como 'ex-aluno' onde ele ficaria em uma categoria
> onde ele é deslogado da plataforma, mas o cadastro dele permanece no sistema
> como 'ex-aluno' onde o Admin poderá visualizar os dados do cadastro dele (…)
> Porém, como ex-aluno ele não consegue logar na plataforma porque mostra que
> esse cadastro foi excluído do sistema ao tentar logar."*
>
> **Status:** *isto é lei.* Emenda a `DECISAO-categorias-de-usuario.md` §2
> (o vocabulário) e a `DECISAO-gestao-de-alunos.md` §2 (os estados).

---

## 1. O buraco real, e ele não era o botão

O botão de apagar fez exatamente o que o nome dele diz. **O defeito estava
antes: a porta da Caixa só sabe responder "tem matrícula?" — sim ou não.** Com
um `não`, ela sempre mostra a mesma tela: o formulário da fila de liberação.

Isso estava certo quando só existiam dois mundos (é aluno / nunca foi). Desde
28/08/2026 existem quatro maneiras diferentes de não ter acesso, e a porta
mostra a mesma tela para todas:

| Situação real da pessoa | O que ela via | O que ela devia ver |
|---|---|---|
| nunca pediu nada | o formulário | o formulário ✅ |
| pediu e espera | o recibo "seu pedido está com a gente" | o recibo ✅ |
| foi recusada | o formulário de novo | o formulário de novo ✅ |
| **teve o acesso pausado** | o formulário | *"seu acesso está pausado"* ❌ |
| **saiu da escola (ex-aluno)** | o formulário | *"seu acesso foi encerrado"* ❌ |
| **teve a ficha apagada** | o formulário | o formulário ✅ (não há mais ficha) |

**Foi por isso que o mantenedor viu "seu pedido já está com a gente" depois de
apagar alguém**: sem ficha, a pessoa virou "nunca pediu nada" — e o navegador
dela ainda tinha a lembrança do pedido antigo, que a tela usa para mostrar o
recibo. Duas coisas certas somando uma tela errada.

**A causa profunda:** a Caixa pergunta uma coisa (`tem matrícula?`) e precisa
saber outra (`em que situação a pessoa está?`). A segunda pergunta já existe
desde 28/08 — `GET /alunos/{email}/situacao` —, criada para a home. A Caixa
nunca migrou para ela.

## 2. "Ex-aluno" passa a ser uma categoria de gente, não só um estado de linha

O vocabulário da `DECISAO-categorias-de-usuario` §2 tinha cinco nomes. Ganha
dois, e os dois já existiam como ESTADO da matrícula desde a manhã — o que
faltava era o sistema saber dizê-los quando alguém pergunta "quem é essa
pessoa?":

| Categoria | Como o sistema sabe | Entra na Caixa? |
|---|---|---|
| Visitante | não há sessão | não |
| Cadastrado | sessão, e nenhuma ficha | não |
| Na fila | ficha `aguardando` ou `recusada` | não |
| **Pausado** *(novo nome)* | ficha `suspensa` | **não** |
| **Ex-aluno** *(novo nome)* | ficha `encerrada` | **não** |
| Aluno | ficha `ativa` ou `reembolsada` | **sim** |
| Administrador | lista da célula `admin` | (ortogonal) |

**Nada muda no banco.** Os estados `suspensa` e `encerrada` já existem e já
bloqueiam desde a manhã de 28/08. O que muda é que a resposta de
`GET /alunos/{email}/situacao` passa a distingui-los — hoje os dois voltam
como `cadastrado`, que é **mentira sobre a pessoa** e é o que produz a tela
errada.

## 3. O que cada porta faz com "ex-aluno"

**A Caixa** deixa de perguntar *"tem matrícula?"* e passa a perguntar *"em que
situação está?"* — a mesma pergunta que a home já faz. Uma pergunta, uma
resposta, para a plataforma inteira; é a razão de a porta da situação existir.

Cada situação ganha a sua tela:

- **ex-aluno:** *"Seu acesso à escola foi encerrado."* Sem formulário e sem
  relógio de espera — não há nada acontecendo do outro lado, e um relógio
  girando seria uma promessa falsa;
- **pausado:** *"Seu acesso está pausado."* Também sem formulário, mas o texto
  diz que é temporário — a diferença entre os dois é a única coisa que a
  pessoa realmente quer saber;
- os outros três casos seguem exatamente como estão.

**A home** mostra a mesma verdade em uma linha, sem o caminho da Caixa.

**Pedir de novo:** ex-aluno e pausado **não** ganham o formulário de volta.
Quem saiu ou foi pausado não está numa fila — está numa decisão do mantenedor,
e um botão de "pedir de novo" ali convidaria a pessoa a insistir contra uma
decisão que ela não conhece. Quem quiser voltar fala com a escola; o mantenedor
religa com um clique, que é o caminho que já existe.

## 4. "Deslogado da plataforma" — o que se faz e o que NÃO se faz

O pedido dizia *"ele é deslogado da plataforma"*. **Isso não é implementado, e
a ausência é decisão.**

Derrubar a sessão de alguém exigiria a área administrativa revogar sessão na
`identidade` — poder novo, numa célula que hoje só LÊ quem é a pessoa. E o
efeito prático seria o mesmo: a pessoa entra de novo com o Google (a porta do
site é pública e continua sendo) e vê a mesma tela dizendo que o acesso
acabou. O que muda é um passo a mais para ela e um poder a mais para a área
administrativa — a troca é ruim nos dois lados.

**O que o mantenedor pediu de fato — "ele não consegue logar na plataforma
porque mostra que esse cadastro foi excluído" — é o §3, e esse está feito.**

## 5. A URL sugerida, e por que não

O pedido sugeriu `…/entrar?esperando=2` para a tela nova. **A tela não vem da
URL, e isso não é preciosismo:**

- qualquer pessoa poderia digitar `?esperando=2` e ver a tela de ex-aluno sem
  ser uma — e alguém, um dia, acreditaria nela;
- e o contrário é pior: a tela passaria a depender de quem MONTOU o link, não
  do que o sistema sabe. Duas fontes para o mesmo fato, que é a doença que
  este projeto passou o mês curando.

O `?esperando=1` que existe hoje continua sendo o que sempre foi: um **sinal
de origem** ("cheguei aqui pelo relógio do recibo"), nunca uma credencial nem
um seletor de tela. Ele nunca abriu porta nenhuma, e há guarda para isso.

## 6. E o botão de apagar, que continua existindo

Apagar e virar ex-aluno passam a ser visivelmente diferentes na tela:
**"Ex-aluno"** é um estado no mesmo seletor dos outros (a ficha fica, o
mantenedor vê tudo), e **"Apagar de vez"** continua embaixo, com a palavra
digitada e o aviso de que não há desfazer — agora dizendo, com todas as
letras, que **não é** o mesmo que tornar alguém ex-aluno.

---

*Relacionados: `DECISAO-categorias-de-usuario.md` §2 (emendada aqui) ·
`DECISAO-gestao-de-alunos.md` §2 (os estados, que não mudam) ·
`DECISAO-fila-de-liberacao.md` §5 e §7 · `DECISAO-administradores-e-apagar.md`
§4 (o apagar).*
