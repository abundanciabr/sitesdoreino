---
schema_version: 2
armadilha: 380
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: mecanizar seria varrer a prosa das 355 entradas atras de caminhos citados e conferir que existem, e isso reprovaria em massa por causa das lapides, dos arquivos que so existem no historico e dos exemplos inventados; o que falta e o gesto de quem MOVE um arquivo, e esse gesto e conhecimento
---

# O endereço dentro da lição envelhece calado, e quem move o arquivo não sabe que existe uma lição apontando para ele

**Sintoma.** Você lê uma armadilha para não repetir um erro, ela cita o arquivo
que resolve o caso, você vai lá e o arquivo não está. Ou pior: o arquivo existe,
mas o que a lição promete sobre ele deixou de ser verdade.

Medido em 07/09/2026. A `armadilhas/328` dizia, com todas as letras:

```
Um job `windows-latest` no `muralhas.yml` roda a mesma suíte no sistema onde os
robôs de fato trabalham. (...) Ele bloqueia o pouso do mesmo jeito.
```

```bash
grep -rn "windows-latest" .github/workflows/
.github/workflows/rede-do-windows.yml:91:    runs-on: windows-latest
```

Duas afirmações, as duas falsas. O job não mora mais no `muralhas.yml`, e não
bloqueia pouso nenhum: roda na `main`, **depois** do merge.

**Causa.** As duas frases eram verdade quando foram escritas, e pararam de ser
**oito horas depois**, no mesmo dia. O commit `f684f1e0` criou o job dentro do
`muralhas.yml` às 16h46 de 04/09/2026; o `65cad846`, na mesma noite, mudou a
casa dele para `.github/workflows/rede-do-windows.yml` porque no Windows a
suíte levava 9min11s contra 2min15s dos outros jobs e empurrava a espera de um
PR de 1min36s para 14min17s.

Ninguém errou. Quem escreveu a lição descreveu o que existia; quem mudou o job
tinha um motivo medido e forte. O que falhou é que **nada liga as duas pontas**:
o autor da mudança não tinha como saber que uma armadilha citava aquele caminho,
e a armadilha não tem quem a releia. Um teste que estivesse errado ficaria
vermelho; uma frase que ficou errada não fica de cor nenhuma.

É a mesma família da `armadilhas/328`, um degrau acima: lá, a decisão de máquina
andava em prosa e morreu na travessia; aqui, a decisão de uma PESSOA (onde
procurar) anda em prosa e morre no `git mv`.

**Solução, e ela é um gesto, não um portão.** Ao mover, renomear ou mudar o
alcance de um arquivo que existe para proteger alguém, procure quem fala dele
**antes de fechar o PR**:

```bash
grep -rn "nome-do-arquivo" armadilhas/ docs/ CLAUDE.md
```

O que aparecer, corrija no MESMO PR, do mesmo jeito que se corrige um `import`
quebrado. Custa dez segundos e é a única hora em que a informação existe: depois
do merge, ninguém mais sabe que a frase envelheceu.

E do outro lado do balcão, quem LÊ uma armadilha: se o caminho citado não
estiver lá, o `grep` acima acha a casa nova em um comando. A lição continua
valendo, só o endereço mudou. Não descarte a entrada, conserte o endereço.
