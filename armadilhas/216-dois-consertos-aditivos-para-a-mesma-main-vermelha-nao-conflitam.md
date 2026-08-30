---
schema_version: 2
armadilha: 216
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nada no CI compara DOIS pedaços de código por EFEITO — só por texto. Duas fixtures autouse com corpos diferentes e resultado idêntico passam em qualquer linter, em qualquer detector de duplicata e em qualquer teste, porque cada uma sozinha está certa. Exigiria um vigia que soubesse o que cada fixture FAZ, não como ela se escreve.
sinal: null
---

# Dois consertos aditivos para a mesma `main` vermelha **não conflitam no Git** — e é por isso que a duplicata sobrevive invisível

**Sintoma.** Não há sintoma. É o ponto inteiro desta entrada.

Semanas depois, alguém lendo o arquivo por outro motivo repara que **duas peças
diferentes fazem a mesma coisa** — duas fixtures `autouse`, dois passos de
workflow, dois hooks, duas chamadas do mesmo gerador. Nenhum teste reprovou,
nenhuma muralha apitou, nenhum PR foi devolvido. Ninguém nunca viu erro, porque
**não há erro**: as duas peças rodam, a segunda não desfaz a primeira, e o
sistema fica verde com o trabalho feito duas vezes.

**Medido em 30/08/2026** (TAR-028, PR #619): `ci/tests/conftest.py` tinha DUAS
fixtures `scope="session", autouse=True` materializando `armadilhas/INDICE.md`,
`GUARDAS.json` e `SINAIS.json`. Vieram dos commits `f9988c5` e `dbfbf80` — **do
mesmo dia**, de duas sessões diferentes consertando **a mesma `main` vermelha**
(a da `armadilhas/206`). Nenhuma das duas viu a outra, e a duplicata só apareceu
porque uma terceira sessão (a da TAR-025) foi ler o conserto por outro motivo.

**Causa — a mecânica que esconde, e ela é do Git, não das pessoas.** Três
coisas verdadeiras ao mesmo tempo:

1. **`main` vermelha convoca mais de um socorrista.** É desenho, não acidente:
   com a `main` vermelha o portão de deploy é fail-closed e **nenhum merge chega
   ao site**, então todo robô que topa com isso tem motivo para consertar.
2. **O conserto certo quase sempre é ADITIVO** — uma fixture nova, um passo
   novo, um hook novo. Não se edita uma linha existente; acrescenta-se um bloco.
3. **Git não conflita blocos adicionados em lugares diferentes do arquivo.** Uma
   sessão acrescentou no meio, a outra no fim. O merge foi limpo nos dois PRs, e
   os dois ficaram verdes — corretamente, porque cada conserto, sozinho, está
   certo.

É o **inverso exato** da `armadilhas/200` e da `156`. Lá, duas sessões colidiam
sem ter escrito uma linha em comum, e o conflito era barulhento — irritante, mas
**auto-denunciante**. Aqui elas escrevem coisas diferentes com o mesmo efeito, e
o silêncio é o problema: um conflito você conserta na hora, uma duplicata você
descobre por acaso.

**Por que importa, já que nada quebrou.** O custo é a prazo, e tem nome — é a
LEI ANTI-DUPLICAÇÃO do `CLAUDE.md` (*nenhum fato do projeto mora em dois
lugares*) quebrada dentro do próprio conserto. Quem mexer numa das duas peças
— trocar a raiz, acrescentar uma condição, apontar para outro gerador — **deixa
a outra para trás**, e a divergência só aparece no dia em que a `main` ficar
vermelha de novo, agora com duas versões da cura discordando. Enquanto isso,
todo leitor do arquivo paga o pedágio de decidir qual das duas é a de verdade.

**Solução — a regra é para o SEGUNDO socorrista, e ela é barata:**

> **Antes de acrescentar um conserto a uma `main` vermelha, procure o conserto
> que já chegou.** `git log --oneline -5 -- <o arquivo que você vai tocar>` e
> `gh pr list --search "<o sintoma>" --state all` custam dez segundos. A `main`
> vermelha é justamente o estado que garante que você **não é o único** olhando
> para ela.

E, quando você for o segundo a chegar e o primeiro conserto já estiver lá:
**melhore o dele em vez de acrescentar o seu ao lado.** Um arquivo com um
conserto bom é melhor que um arquivo com dois consertos corretos.

**Ao unificar duas peças que já duplicaram, escolha cada metade por mérito
separado** — foi assim que a TAR-028 fechou esta:

| metade | de qual das duas veio | por quê |
|---|---|---|
| o **corpo** | da chamada em processo | mais rápida, não esconde a falha do gerador atrás de um subprocesso |
| o **nome** | da que foi removida | era a convenção da casa (`painel_materializado`) **e** o nome que o docstring de outro teste já citava — manter fez o PR caber em um arquivo em vez de dois |
| o **texto** | dos dois, mesclado | cada docstring sabia algo que o outro não sabia (a issue #587 num, os três chamadores no outro) |

Nome e implementação são escolhas **independentes**: o reflexo de "fico com uma
inteira e jogo a outra fora" perde contexto de graça, e às vezes cria trabalho
onde não havia — aqui, renomear teria obrigado a tocar um segundo arquivo quente.

**E deixe o aviso onde o próximo vai ler.** A peça que sobrou ganhou um
parágrafo dizendo que é **uma de propósito**, com os dois SHAs que a fizeram
nascer duas vezes, e a frase que fecha o laço: *se você veio consertar a
materialização, conserte AQUI — não acrescente uma segunda.* Não é mecanismo
(nenhum CI lê comentário), mas é o único aviso que fica no caminho exato de quem
repetiria a falha.

**A categoria, maior que o caso:** é "sessões paralelas" da
`RETROSPECTIVA-FASE-D` mostrando a face silenciosa dela. O catálogo aprendeu
que trabalho paralelo se manifesta como **conflito**; esta entrada é a lembrança
de que ele também se manifesta como **concordância redundante** — e que a segunda
é pior de achar exatamente porque não dói.
