# DECISÃO — reembolso tira o acesso, e a ficha continua guardada

> **Decidida pelo mantenedor em 31/08/2026**, depois de ele encontrar o texto
> errado no próprio site:
>
> *"Essa informação precisa ser revista, e a verdade sobre o reembolso é que a
> pessoa é removida do site, e perde totalmente o acesso ao curso e ao site."*
>
> Perguntado, por pergunta estruturada, com o preço de cada caminho na mesa
> ANTES da escolha:
>
> - *"O cadastro dela some do sistema, ou só o acesso acaba?"* → **"Só o acesso
>   acaba"**. A ficha continua guardada, como história.
> - *"O que ela vê quando tenta entrar, e pode pedir para voltar sozinha?"* →
>   **"Tela própria de reembolso"**, sem formulário de pedir de volta.
>
> **Status:** *isto é lei*, e ela **reverte** a decisão do mantenedor de
> 24/08/2026 (*"quem já foi aluno mantém a voz"*), que está escrita em
> `docs/caixa-de-sugestoes/DECISAO-EVO-01-identidade.md` §4.1 e citada como
> definitiva em outros cinco documentos. A reversão está escrita aqui inteira,
> com o que se ganha e o que se perde, para ninguém no futuro achar que foi
> descuido.

---

## 1. O que muda, em uma frase

**`reembolsada` deixa de dar acesso.** Quem foi reembolsado não entra no curso,
não entra na Caixa de Sugestões, não entra no fórum, não entra em nada que
pergunte *"esta pessoa é aluna?"*. A ficha dela **continua guardada**, e o
mantenedor religa com um clique se tiver sido engano.

## 2. Por que a decisão de 24/08 caiu

Ela não caiu por defeito de raciocínio. Ela caiu porque descrevia um mundo que
não é o do mantenedor.

Em 24/08/2026 a pergunta feita a ele foi estreita: *"quem pediu reembolso perde
a voz na Caixa de Sugestões?"*. Naquele recorte, "manter a voz" é generoso e
custa pouco: a Caixa é um quadro de ideias, e a opinião de quem já pagou pelo
curso tem valor mesmo depois de o dinheiro voltar.

O que ninguém perguntou é o que o reembolso significa **no negócio**. E ali a
resposta dele é outra: reembolso é a compra sendo desfeita. Quem desfez a
compra não é mais aluno, e continuar entrando no curso depois de receber o
dinheiro de volta é o curso saindo de graça.

**A lição que fica registrada, porque ela é maior que este caso:** a decisão de
24/08 foi tomada sobre uma tela (a Caixa) e depois virou regra da plataforma
inteira, porque `STATUS_QUE_VALEM` é uma fonte só. Uma decisão de recorte
estreito, promovida por herança a uma regra geral, não foi revista quando o
alcance dela cresceu. **Quando uma resposta do mantenedor sobre UMA tela virar
o critério de acesso da plataforma, isso se pergunta de novo, com o alcance
novo na frente dele.**

## 3. As duas escolhas dele, e o que cada uma recusou

### 3.1 A ficha fica (recusado: apagar)

Foi oferecido apagar o cadastro do banco. Ele recusou, e a recusa é coerente
com a `DECISAO-a-ficha-nao-se-apaga.md` (29/08/2026), que já é lei: nenhum
caminho do sistema apaga a ficha de uma pessoa.

O que se ganha: desfazer continua possível (reembolso lançado por engano volta
com um clique), o prontuário continua contando a história inteira, e o texto já
publicado para os alunos (*"a sua ficha nunca é apagada"*) continua verdadeiro.

O que se perde: o direito de a pessoa sumir do sistema (LGPD) continua sem
botão próprio. Isso **não é criado aqui**, e continua sendo o que a
`DECISAO-administradores-e-apagar.md` deixou em aberto: apagar de vez merece
botão próprio, aviso próprio e uma conversa dele.

### 3.2 Tela própria (recusados: reusar a do ex-aluno, e deixar pedir de volta)

Foi oferecido reusar a tela que já existe para o ex-aluno (*"Seu acesso à
escola foi encerrado"*). Ele recusou: a pessoa ficaria sem saber que o motivo
foi o reembolso dela.

Foi oferecido também dar a ela o botão **Pedir para voltar**, que o ex-aluno
tem desde 29/08. Ele recusou. E a diferença entre os dois casos é justamente o
que a `DECISAO-a-ficha-nao-se-apaga.md` §3 usou para devolver o formulário ao
ex-aluno: *"a escola é um lugar de onde se sai e para onde se volta, e quem
terminou um curso e quer o do semestre seguinte não está insistindo contra uma
decisão"*. Quem foi reembolsado **está** insistindo contra uma decisão, e a
decisão é comercial. Quem quiser voltar compra de novo, ou fala com a escola.

## 4. O que `reembolsada` passa a ser, ao lado dos outros estados

| Estado | Dá acesso? | O que significa |
|---|---|---|
| `aguardando` | não | está na fila |
| `recusada` | não | pediu e não foi aprovada |
| `ativa` | **sim** | é aluno |
| `suspensa` | não | acesso pausado, volta com um clique |
| `encerrada` | não | saiu da escola, e pode pedir para voltar |
| `reembolsada` | **não** *(mudou em 31/08/2026)* | o dinheiro voltou, e o acesso acabou junto |

**`reembolsada` NÃO vira apelido de `encerrada`, e a distinção é a decisão.**
Os dois tiram o acesso, e param aí. `encerrada` é o mantenedor dizendo *"você
saiu"*; `reembolsada` é *"a compra foi desfeita"*. Elas diferem em três coisas
que a pessoa e o mantenedor veem:

1. a tela que a pessoa recebe nomeia o reembolso;
2. o reembolsado **não** ganha o formulário de pedir para voltar;
3. o painel continua contando os dois separados, porque a pergunta *"quantos
   pediram o dinheiro de volta?"* é uma pergunta de negócio que o mantenedor
   faz, e ela morreria se os dois virassem o mesmo estado.

## 5. A categoria nova: `reembolsado`

`GET /alunos/{email}/situacao` ganha uma sexta categoria, **`reembolsado`**
(ficha `reembolsada`). É **adição** ao contrato, e por isso não quebra
consumidor nenhum.

Sem ela, o reembolsado cairia em `cadastrado` — que é **mentira sobre a
pessoa**, e exatamente o defeito que a
`DECISAO-ex-aluno-e-a-porta-que-explica.md` §2 nasceu para curar: quem já teve
uma ficha veria o formulário de pedir entrada como se nunca tivesse pedido
nada.

**Quem autoriza continua olhando só `aluno`.** Todo consumidor que decide
acesso lê `ESTADO_POR_CATEGORIA`, que é lista de PERMISSÃO: categoria que não
esteja no mapa cai fora, sem acesso. Por isso a categoria nova nasce **fechada**
mesmo em quem ainda não souber o nome dela.

## 6. Os três guardas que caem, e por que isso não é vandalismo

A decisão de 24/08 foi **travada de propósito**, e a trava funcionou: ela
existia para que nenhum agente "consertasse" a regra de boa-fé achando que
`reembolsada` dando acesso era um bug esquecido. Três testes quebram o sistema
quando alguém tenta mudá-la:

| Guarda | Onde |
|---|---|
| `test_toda_situacao_de_matricula_entra` | `services/sugestoes/tests/test_inv_matricula_reembolsada_entra.py` |
| `test_so_aluno_e_reembolsado_entram` | `services/admin/tests/test_jornada_na_tela.py` |
| a lista escrita à mão em `STATUS_QUE_VALEM` | `services/alunos/tests/test_categorias_de_usuario.py` |

Os três são revertidos **por esta lei**, que é o que eles pediam: as três
mensagens de falha dizem, com todas as letras, *"mudar isto é decisão do
mantenedor, nunca de um despacho"*. A decisão do mantenedor está no cabeçalho
deste documento, com as palavras dele.

**E os três são substituídos, não apagados.** Cada um vira o guarda da regra
nova, com a mesma força e a mesma mensagem: quem tentar devolver `reembolsada`
ao acesso encontra um teste vermelho dizendo que isso foi decidido em
31/08/2026 e apontando para cá. Trava que some depois de usada não protege a
decisão seguinte.

## 7. O que NÃO muda

- **Ninguém em produção perde acesso hoje por causa desta lei.** Medido em
  31/08/2026, antes de escrever: `grep` em `services/` não encontra uma única
  linha de código que jamais atribua `reembolsada` a alguém. O único caminho
  que existe é o mantenedor pôr à mão, pela tela de gestão. Se houver uma linha
  posta à mão, ela perde o acesso, e é o que a palavra sempre prometeu.
- **O checkout não muda.** `services/checkout` tem um estado de pedido chamado
  `reembolsado`, sobre o dinheiro. Ele nunca falou de acesso e continua não
  falando.
- **O evento `notificacao.devida.v1` não muda.** Ele já lista os seis estados,
  e `reembolsada` continua sendo um deles.
- **Apagar a ficha continua não existindo.** Ver §3.1.

---

**Quem faz valer:** `services/alunos/tests/test_reembolso_tira_o_acesso.py` (a
porta que decide acesso, e a categoria nova) · `services/sugestoes/tests/test_reembolso_nao_entra.py`
(a Caixa recusa, e a tela nomeia o reembolso) · `services/admin/tests/test_jornada_na_tela.py`
(a jornada mostra o reembolsado sem acesso).
