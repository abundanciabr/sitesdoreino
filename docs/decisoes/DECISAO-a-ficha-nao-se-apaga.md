# DECISÃO — a ficha não se apaga, e o ex-aluno pode pedir para voltar

> **Decidida pelo mantenedor em 29/08/2026**, por pergunta estruturada, com o
> preço de cada caminho apresentado ANTES da escolha:
>
> *"Eu quero que o cadastro do aluno NUNCA SEJA APAGADO, mas que ele mude para
> 'ex-aluno'. Onde quando ele tentar fazer um novo cadastro que ele vá
> novamente para a lista onde ficam os cadastros aguardando a
> aprovação/liberação, com a indicação na tela de que se trata de um ex-aluno,
> e mostre o link para o prontuário do mesmo."*
>
> - *"O botão de apagar — o que faço com ele?"* → **"Tirar da tela de vez"**,
>   com a consequência legal na mesa (§2 abaixo).
> - *"Quando um ex-aluno voltar, como fica a ficha?"* → **"Nasce ficha nova, o
>   prontuário junta tudo"**.
>
> **Status:** *isto é lei*, e ela **reverte** a `DECISAO-administradores-e-apagar.md`
> §4 (o botão de apagar de vez) e o §3 da `DECISAO-ex-aluno-e-a-porta-que-explica.md`
> (ex-aluno não ganhava o formulário de volta). As duas reversões estão escritas
> aqui inteiras, com o que se ganha e o que se perde, para ninguém no futuro
> achar que foi descuido.

---

## 1. O que muda, em uma frase

**Nenhum caminho do sistema apaga a ficha de uma pessoa.** Tirar o acesso passa
a ter uma forma só — *ex-aluno* —, a ficha fica, e quem saiu pode **pedir para
voltar**: o pedido cai na mesma fila de quem nunca entrou, com a tarja
**ex-aluno** e o link para o **prontuário**, onde a história inteira daquela
pessoa aparece em ordem.

## 2. Apagar sai — e a ausência tem preço, dito com todas as letras

A `DECISAO-administradores-e-apagar` §4 criou o botão em 28/08/2026, um dia
antes desta lei, e chamou-o de *"o direito da pessoa de sumir do sistema"*.
Esse direito é real: a Lei Geral de Proteção de Dados dá a qualquer pessoa o
poder de exigir a eliminação dos dados dela.

**A partir de agora não há botão para isso, e o mantenedor escolheu assim com
a consequência na mesa.** O raciocínio dele, e ele está certo no caso comum:
apagar destrói o único registro de que aquela pessoa existiu na escola, e o
caso que ele vive todo dia não é o pedido formal de exclusão — é tirar o acesso
de alguém que saiu.

**O que fica no lugar:** quando um pedido formal de exclusão chegar, ele não é
um clique de rotina — é um pedido raro, que merece ser tratado com cuidado, uma
vez, à mão. O caminho se constrói na hora, com o rito que uma exclusão
irreversível merece. **Registrar isso aqui é o que impede que o próximo agente
leia a ausência do botão como esquecimento.**

**Não é remoção de botão: é remoção de capacidade.** A porta interna que
apagava (`DELETE /matriculas/{id}`) sai do contrato junto. Um botão removido
volta com uma linha de template; uma porta removida do contrato exige o Rito
§3 e a etiqueta `contrato-remocao`. A diferença é o que separa promessa de
mecanismo — o padrão *"garantia sem mecanismo"* da `RETROSPECTIVA-FASE-D`.

## 3. Ex-aluno pode pedir para voltar — a reversão do §3 de ontem

A `DECISAO-ex-aluno-e-a-porta-que-explica` §3 dizia:

> *"Pedir de novo: ex-aluno e pausado **não** ganham o formulário de volta.
> (…) um botão de 'pedir de novo' ali convidaria a pessoa a insistir contra
> uma decisão que ela não conhece."*

**O mantenedor decidiu o contrário, e o argumento dele é mais forte:** a escola
é um lugar de onde se sai e para onde se volta. Quem terminou um curso em março
e quer o do semestre seguinte não está *insistindo contra uma decisão* — está
se matriculando de novo, que é o fluxo mais normal que existe numa escola.

**O que evita o abuso que o §3 temia:** o pedido não devolve acesso nenhum. Ele
entra na **fila**, exatamente como o de qualquer pessoa nova, e espera decisão
humana. A diferença é que a fila agora **avisa quem é**: a tarja *ex-aluno* e o
prontuário existem para que o mantenedor decida sabendo de tudo — inclusive
para recusar de novo, em dois cliques, se foi por isso que a pessoa saiu.

**`pausado` continua sem formulário, e a diferença é a decisão.** Pausado é
temporário e volta sozinho, sem a pessoa pedir nada; um formulário ali
convidaria alguém a pedir o que já vai acontecer. Ex-aluno é o fim de uma
passagem — e o fim de uma passagem é justamente quando faz sentido pedir outra.

## 4. Ficha nova a cada passagem, e o prontuário que as junta

Quem volta **não reaproveita a ficha antiga**: nasce uma linha nova, e a antiga
fica como está, `encerrada`.

**O que se ganha:** a data em que a pessoa saiu, o motivo, e quem decidiu —
tudo sobrevive. Reaproveitar a linha apagaria a saída no instante da volta, e a
pergunta *"quando ele saiu, mesmo?"* não teria mais resposta em lugar nenhum.
É a mesma disciplina do livro de ocorrências do projeto: **fato novo é registro
novo, nunca edição do anterior.**

**O que se paga:** a mesma pessoa passa a ter mais de uma linha na lista de
alunos — uma por passagem. **O prontuário é a resposta a isso**, e é por isso
que ele nasce nesta mesma lei em vez de ser um enfeite: ele agrupa por e-mail e
mostra a trajetória inteira em ordem, do primeiro pedido ao último.

## 5. O prontuário

Uma página por pessoa, dentro da área administrativa, atrás da mesma porta que
tudo o mais. Ela responde *"quem é esta pessoa para a escola?"* e mostra:

- **os dados de cadastro** da passagem mais recente (nome, e-mail, WhatsApp,
  turma, quando comprou);
- **a situação de agora**, com todas as palavras — aluno, ex-aluno, pausado, na
  fila;
- **a trajetória**, uma linha por passagem, em ordem: quando pediu, quem
  liberou ou recusou, com que motivo, quando encerrou.

**A trajetória é DERIVADA das fichas, nunca uma tabela nova.** É a lei
anti-duplicação do `CLAUDE.md`: um histórico gravado à parte discordaria das
fichas no primeiro caso de borda, e as duas telas mostrariam pessoas
diferentes.

## 6. O que continua igual

- **Encerrar não desloga ninguém na hora**, e a `DECISAO-ex-aluno` §4 explica
  por quê — a pessoa entra de novo com o Google e lê que o acesso acabou.
  Derrubar sessão exigiria um poder novo, e o efeito prático seria o mesmo.
- **A fila continua sendo decisão humana**, uma por vez, com motivo obrigatório
  para recusar.
- **A auditoria continua append-only** e continua sem guardar dado que a pessoa
  forneceu (`DECISAO-administradores-e-apagar` §4, a única parte daquele §4 que
  sobrevive — e agora ela é fácil de cumprir, porque não há mais exclusão para
  cumprir).
- **O verbo `apagar` continua no vocabulário da auditoria.** Aquela tabela não
  se edita: se alguma linha antiga o usou, ela precisa continuar legível.

---

*Relacionados: `DECISAO-administradores-e-apagar.md` §4 (revertida aqui) ·
`DECISAO-ex-aluno-e-a-porta-que-explica.md` §3 (revertido aqui) e §2 (o
vocabulário, intacto) · `DECISAO-fila-de-liberacao.md` §5 e §7 ·
`DECISAO-gestao-de-alunos.md` §2 · `DECISAO-filosofia-de-escopo.md`.*
