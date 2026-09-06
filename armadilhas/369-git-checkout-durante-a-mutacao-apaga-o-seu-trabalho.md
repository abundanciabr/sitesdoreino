---
schema_version: 2
armadilha: 369
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nao ha o que mecanizar sem proibir o proprio git; o que faltava era saber que a sabotagem acontece SOBRE trabalho nao commitado, e isso e conhecimento
sinal:
  - "git checkout -- services"
  - "git restore"
---

# `git checkout <arquivo>` durante a prova por mutação apaga o seu trabalho, não a sabotagem

**Sintoma.** Você está provando um guarda por mutação (`armadilhas/195`): sabota o
código, roda o teste, vê o vermelho, e desfaz. Para desfazer, o reflexo é

```bash
git checkout -- services/<celula>/apps/core/views.py
```

O teste volta ao verde e tudo parece certo. Só que a suíte agora tem MENOS
testes vermelhos do que devia, ou o comportamento novo sumiu da tela, e você
gasta a rodada seguinte procurando um defeito que não existe.

**Causa.** A prova por mutação acontece **antes do commit**, sobre a implementação
que você acabou de escrever. `git checkout -- <arquivo>` não desfaz a sua
sabotagem: ele devolve o arquivo ao ÚLTIMO COMMIT, e leva junto tudo o que você
escreveu naquele arquivo desde então. A sabotagem some, e o trabalho também.

**Solução, e ela cabe em duas linhas.** Copie o arquivo antes de sabotar, e
restaure da cópia:

```bash
cp services/<celula>/apps/core/views.py /tmp/views-bom.py
# …sabota, roda, vê o vermelho…
cp /tmp/views-bom.py services/<celula>/apps/core/views.py
```

Melhor ainda: sabote por script, com a restauração num `finally`, para que ela
aconteça mesmo quando o teste estoura no meio. O molde que esta casa usa está em
`ci/`-adjacente, nos scripts de mutação de sessão: leia o original UMA vez para
uma variável, aplique cada sabotagem sobre essa variável, e escreva o original de
volta no fim, aconteça o que acontecer.

**A irmã desta armadilha, do mesmo dia.** Sabotagem que quebra a SINTAXE do
arquivo derruba a suíte inteira e não prova nada: 11 vermelhos por `SyntaxError`
não dizem que um guarda funciona. Confira com `python -c "import ast, pathlib;
ast.parse(pathlib.Path('<arquivo>').read_text(encoding='utf-8'))"` antes de rodar
o teste. É a `armadilhas/195` vista do lado de quem sabota: o vermelho tem de cair
na asserção, e para isso a sabotagem precisa produzir um programa VÁLIDO que se
comporta errado.

**Origem.** 06/09/2026, dois casos independentes no mesmo dia: o despacho da
TAR-227 (a sala servindo só o curso da matrícula, PR #1201) perdeu o trabalho em
`views.py` para um `git checkout` e teve de reaplicá-lo; e a maestro, no PR #1198,
sabotou uma f-string de forma que não compilava e leu 11 vermelhos que não
provavam nada.
