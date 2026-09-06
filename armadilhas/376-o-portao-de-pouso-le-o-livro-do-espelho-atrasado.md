---
schema_version: 2
armadilha: 376
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/mergear.py
  - ci/esperar.py
guarda:
  tipo: nenhum
  motivo: o conserto e em ci/, caminho CODEOWNERS, e virou tarefa na fila; ate la o que existe e esta licao
sinal:
  - "merge\\(s\\) entraram na main e NINGU[EÉ]M contou ao dono"
licao: O portão de pouso lê `painel/registros/` do DIRETÓRIO ONDE ELE RODA; espera armada do clone principal lê um livro velho e cobra dívida já paga. Arme a espera de uma bancada em dia, e confira `git rev-list --count HEAD..origin/main` antes de acreditar na recusa.
---

# O portão de pouso lê o livro do espelho atrasado, e cobra dívida já paga

**Sintoma.** O mesmo PR é recusado três vezes seguidas, com os checks todos
verdes, por uma dívida que não existe:

```
✅ todos os 7 checks verdes
🔴 o portão RECUSOU o pouso do PR 1252

3 merge(s) entraram na main e NINGUÉM contou ao dono:
#1233  2026-09-06  cursos: o titulo da encomenda e o do Boss ganham por onde entrar
#1236  2026-09-06  A lista dos robôs passa a dizer o que é dele
#1235  2026-09-06  contrato: o titulo da encomenda e o bloco ganham por onde entrar
```

Você abre os registros, e os três estão lá, citando os números certos. Você roda
`python ci/mergear.py <N> --conferir` **na sua bancada** e recebe:

```
  registro a bordo    PASS   o registro viaja neste PR e cita #1252
  dívida do livro     PASS   livro em dia
RESULTADO  PASS
```

Duas medições, a mesma ferramenta, o mesmo PR, respostas opostas.

**Causa.** `ci/divida_do_livro.py` procura os números dos PRs dentro dos
arquivos de `painel/registros/` **do diretório onde o processo está rodando**.
Não do `origin/main`, não do ramo do PR: do disco local.

E a ferramenta `Monitor`, que é a única forma autorizada de esperar
(`RITOS.md` §2), roda com o diretório de trabalho no **clone principal**. O
clone principal é espelho, e a lei desta casa diz que ele envelhece calado
(`armadilhas/148`, e o CLAUDE.md manda trabalhar em bancada). Numa sessão longa
ele fica dezenas de commits atrás sem nenhum aviso.

Medido em 06/09/2026, no meio de uma sessão que mergeou sete PRs:

```
HEAD do clone principal: 9d74eea6
origin/main:             5e19a2a7
commits atrasado:        83
os tres registros existem no clone principal?
  094 -> 0
  095 -> 0
  096 -> 0
```

Os três registros que pagavam a dívida estavam na `main` havia horas. O portão
simplesmente não os enxergava, porque olhava para uma cópia de antes.

**Por que isso é pior do que parece.** A mensagem de recusa é boa e ensina o
caminho certo para o caso normal: "para pagar, um registro NOVO citando o número
do PR". Seguir essa instrução aqui **cria um segundo cobrador para a mesma
conta**, que é exatamente a corrida de 31/08/2026 (`armadilhas/248`, quatro PRs
pagando as mesmas duas dívidas e a fila inteira travada). O portão avisa contra
isso duas linhas abaixo, mas quem está com pressa lê a instrução e não o aviso.

**Solução, hoje: arme a espera de uma bancada em dia.**

```bash
cd ../wt-<sua-bancada> && python ci/esperar.py --checks <N> --teto 20 \
  --dizendo "os checks do PR <N>" --e-pousar
```

O `cd` é a correção inteira. A bancada nasceu de `origin/main` e você traz a
`main` para dentro dela sempre que um PR seu pousa, então o livro que ela carrega
é o de verdade.

**Como confirmar em dez segundos, antes de acreditar numa recusa por dívida:**

```bash
git -C <caminho-do-clone-principal> fetch origin
git -C <caminho-do-clone-principal> rev-list --count HEAD..origin/main
```

Número diferente de zero, e a recusa por dívida é suspeita. Confirme rodando
`python ci/mergear.py <N> --conferir` da bancada: se lá der PASS, não escreva
registro nenhum.

**O que NÃO fazer:** escrever um registro novo "para pagar" sem antes medir de
onde o portão está lendo. Você paga uma dívida que não existe, e a próxima
sessão herda dois registros para o mesmo acontecimento.

**O conserto de verdade** é `ci/divida_do_livro.py` ler os registros do
`origin/main` em vez do disco local, ou `ci/mergear.py` recusar-se a julgar o
livro quando a árvore está atrás do `origin/main` (fail-closed com a frase que
ensina). É caminho CODEOWNERS e virou tarefa na fila.
