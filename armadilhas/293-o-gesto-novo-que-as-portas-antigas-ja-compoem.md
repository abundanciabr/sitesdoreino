---
schema_version: 2
armadilha: 293
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: a escolha acontece na cabeça de quem desenha, antes de existir código para medir; nenhum portão sabe distinguir "o contrato precisava mesmo mudar" de "o autor não leu a porta vizinha" — o que existe é a leitura do contrato antes de abrir o rito, e o próprio rito, que é caro o bastante para fazer alguém reler
sinal:
  - `esta linha já foi decidida`
  - `contracts/ não muda junto com services/`
  - `exige a label 'contrato'`
---

# O gesto "novo" que as portas antigas já compõem: leia o contrato antes de abrir o rito

**Sintoma.** Você precisa de um gesto que o sistema aparentemente não sabe
fazer, olha a célula dona e encontra a recusa cravada:

```python
if linha.status != Matricula.STATUS_AGUARDANDO:
    return None, "ja-decidida"
```

Daí a conclusão parece óbvia: *"preciso alargar essa porta"*. E alargá-la é
caro. O Rito de Contrato (`RITOS.md` §3) pede sessão de arquitetura com o
mantenedor presente, um PR só de `contracts/` com a etiqueta `contrato`, e os
consumidores em PRs seguintes. `ci/cerca-de-celula.sh` reprova qualquer tentativa
de fazer tudo junto:

```
❌ MURALHA: contracts/ não muda junto com services/.
```

De um pedido de uma frase ("deixe eu aceitar de novo quem eu recusei") nasce um
plano de três PRs, dois ritos e uma conversa que o mantenedor não pediu.

**Causa — a porta que você procura raramente é a que tem o nome do gesto.**
A recusa acima é sobre *redecidir a mesma linha*. Ela não é sobre *o estado
`recusada` ser final*: duas portas adiante, a de CRIAR o pedido já documentava
o caminho de volta, e há semanas.

```
Idempotente por (site_id, email): reenviar atualiza os dados e devolve 200.
Quem foi recusado e reenvia volta para `aguardando` com o motivo limpo.
```

Ou seja: a reversão já existia, já estava testada, e já era o caminho que a
PRÓPRIA pessoa usava para desfazer uma recusa. O que faltava não era porta
nenhuma: era o mantenedor poder percorrê-la em nome dela. Duas chamadas às
portas que já existem (voltar para a fila, depois liberar) entregam o gesto
inteiro, num PR só, sem tocar em `contracts/`.

Em 02/09/2026 esse foi o desenho da lista de recusados de `/admin/escola/`, e é
o MESMO desenho do "cadastrar alguém à mão" de 29/08 — que também parecia pedir
uma porta capaz de criar matrícula direto, e também não precisou dela.

**Regra prática.** Antes de escrever "isto exige mudar o contrato", faça as três
perguntas, nesta ordem:

1. **Alguém já faz este gesto hoje?** Se a própria pessoa, o formulário do site
   ou outra tela já produzem o efeito que você quer, o caminho existe — você só
   não é quem o percorre. Copie o caminho, não abra outro.
2. **As portas existentes COMPÕEM o gesto?** Duas chamadas na ordem certa
   custam uma ida a mais à rede e zero rito. Uma porta nova custa dois ritos e
   passa a ser uma segunda forma de chegar ao mesmo estado — e as duas
   discordarão na primeira mudança de lei.
3. **A recusa que eu li fala do meu caso?** *"Já foi decidida"* recusa
   redecidir; não diz que o estado é final. Leia a descrição inteira da porta
   vizinha antes de concluir pela primeira que te disse não.

**A conta que fecha o argumento.** Compor: 1 PR, 1 célula, 2 idas à rede, o
comportamento já coberto pelos testes da célula dona. Abrir porta: 2 a 3 PRs, o
Rito de Contrato, caminho CODEOWNERS, e um segundo jeito de virar aluno para o
sistema manter para sempre.

**O preço de compor, que é real e se paga na hora.** A porta de criar REESCREVE
os dados da linha (nome, WhatsApp, turma, data da compra) — é o que ela faz, por
contrato. Então quem a chama para reverter uma decisão precisa mandar de volta os
dados que já estavam lá, e **relê-los do lado da célula dona, nunca de campos
escondidos no HTML**: com campos escondidos, um botão de "aceitar de novo" vira
uma porta de edição silenciosa do cadastro de qualquer pessoa da fila. Uma ida a
mais à rede fecha isso. Campo ausente também não viaja: mandar `turma: None`
apagaria o que a pessoa escreveu, e apagar dado é o oposto do que o botão promete.

**Onde isto NÃO vale.** Se as portas existentes não compõem o gesto, ou se
compô-las deixaria o sistema num estado intermediário que ninguém consegue ver,
o rito é o caminho certo e não há atalho. Aqui a composição só é honesta porque
a falha do meio é VISÍVEL: se a segunda chamada falha, a pessoa fica esperando
na fila, na tela que o mantenedor já abre todo dia, com o botão que termina o
serviço do lado.

**Onde já mordeu:** o desenho da lista de recusados (02/09/2026), e antes dele o
`DECISAO-cadastrar-alguem-a-mao.md` §2, que chegou à mesma conclusão pelo mesmo
caminho e escreveu a razão por extenso: *"uma porta capaz de criar matrícula
direto seria uma segunda forma de virar aluno, com outras regras"*.
