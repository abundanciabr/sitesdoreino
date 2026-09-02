---
schema_version: 2
armadilha: 281
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  dono: services/admin/tests/test_telefone.py
sinal:
  - `não achei no site`
  - `nao achei no site`
  - `whatsapp.*==.*whatsapp`
  - `chave_de`
---

# Cruzar telefone entre duas listas: o nono dígito e o DDI derrubam o casamento, e a direção de normalizar decide quem é liberado

**Sintoma.** Um cruzamento de números de WhatsApp entre uma lista de fora e o
banco marca como *"não achei"* gente que está no sistema. Nada quebra, nada
fica vermelho: a tela simplesmente diz que dezenas de pessoas não existem, e
quem lê sai procurando por elas.

**Causa.** Comparar telefone como string é comparar duas grafias, não duas
pessoas. Medido em 02/09/2026, na lista real do mantenedor (345 números) contra
o formulário do site:

| o mesmo aparelho, escrito por mãos diferentes |
|---|
| `11 99999-8888` (como ele anota) |
| `+55 (11) 99999-8888` (como a pessoa digita no cadastro) |
| `5511999998888` (como um export de WhatsApp entrega) |
| `11 9999-8888` (a mesma linha, anotada antes de 2012) |

São quatro strings diferentes e uma pessoa só. O nono dígito é a pior das
quatro porque é *opcional na prática*: celular brasileiro ganhou um `9` em
2012, e o mesmo número circula das duas formas até hoje.

**Solução.** Uma chave canônica, e ela **derruba** o nono dígito em vez de
acrescentá-lo. A direção não é gosto:

- **derrubar** nunca inventa nada — só remove o que é opcional;
- **acrescentar** exige adivinhar se aquele número é celular, e o fixo
  `11 3333-4444` viraria `11 93333-4444`, **que é o telefone de outra pessoa**.

Num cruzamento que LIBERA ACESSO, essa diferença é a diferença entre a pessoa
certa entrar e um estranho entrar. O código está em
`services/admin/apps/core/telefone.py`, com os quatro casos travados em teste.

**As duas armadilhas de dentro da armadilha:**

1. **`55` não é só DDI.** É também um DDD válido (Santa Maria/RS). Derrubar o
   prefixo sem conferir o TAMANHO junto faz um `55 9999-8888` perder o próprio
   DDD. Confira os dois, sempre: `len(d) in (12, 13) and d.startswith("55")`.

2. **A sua lista não é toda brasileira, e você não vai saber disso antes de
   medir.** Nove dos 345 números não eram: seis de Portugal (9 dígitos), um da
   França, um da Espanha e dois truncados, sem DDD. Um normalizador que
   assumisse "todo mundo é BR com DDD" marcaria esses nove como *"não achei"* —
   silenciosamente, e justamente para as pessoas mais difíceis de rastrear
   depois. **Meça a forma dos dados ANTES de escrever a regra**: dez linhas de
   `Counter(len(digitos(x)))` responderam isso em segundos.

**A regra que ficou, e vale para qualquer casamento aproximado:** igualdade e
semelhança precisam ser DUAS funções com nomes diferentes. Aqui, `chave_de`
(igualdade exata, autoriza sozinha) e `sufixo_de` (os 8 dígitos finais, só
sugere e chega desmarcada na tela). Fundi-las numa "comparação esperta" é como
um cruzamento de dados libera a pessoa errada: dois números de DDDs diferentes
terminam iguais com frequência, e no dia em que isso acontecer ninguém vai
conseguir dizer se foi decisão de alguém ou palpite do código.
