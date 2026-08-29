# `git diff --name-only` mostra só o DESTINO de um rename — e o portão que lê o diff fica cego

**Sintoma:** não há erro nenhum, e é esse o problema. Um portão que deriva o
escopo do diff (a catraca de testes, a cerca de célula, o detector de células
tocadas, o orçamento de arquivos) anuncia com toda a confiança que nada
aconteceu — sobre um PR que mexeu no que ele existe para vigiar:

```
TESTES nos arquivos tocados: 0 antes · 0 depois
CATRACA DE TESTES — teste não some em silêncio

  testes  PASS   nenhum teste apagado, reduzido ou desligado neste PR
```

O PR que produziu isso tinha **uma linha**:

```bash
git mv ci/tests/test_reversao.py ci/tests/reversao_helpers.py
```

**17 testes coletados pelo pytest viraram 0.** A suíte inteira continuou verde
(o pytest não coleta o que não se chama `test_*`), e a catraca — o portão criado
na Onda 6 exatamente para que "nenhum teste some em silêncio" — imprimiu PASS.

**Causa:** com a detecção de rename ligada (o padrão do `git diff`),
`--name-only` devolve **um caminho por mudança**, e para um rename esse caminho
é o **destino**. A origem não aparece em lugar nenhum:

```
$ git diff --name-only origin/main...HEAD
ci/tests/reversao_helpers.py
```

O portão então faz o raciocínio certo sobre a informação errada: "este arquivo
não existia na base ⇒ é arquivo novo ⇒ só soma". O arquivo antigo, com os testes
dentro, nunca entra na conta — nem como apagado, nem como reduzido.

É a mesma família da `armadilhas/104` (inventário de nomes lido como guarda de
comportamento), mas pior: aqui o guarda nem chega a olhar o objeto. E a
autorização que existia (`remove-teste`) não é contornada — ela simplesmente
nunca é acionada.

**Solução:** peça as **duas pontas** ao git, com `--name-status -M`:

```
$ git diff --name-status -M origin/main...HEAD
R100    ci/tests/test_reversao.py    ci/tests/reversao_helpers.py
```

E julgue o PAR, não o caminho solto. Para a catraca ficou assim:

| origem → destino | veredito |
|---|---|
| teste → teste | conta antes e depois; cair é perda |
| teste → não-teste | o arquivo inteiro saiu da suíte = perda |
| (nada) → teste | arquivo novo, só soma |
| teste → (nada) | apagado — o único caso que `--name-only` já pegava |

Duas armadilhas dentro desta:

1. **`-M` também muda o `D`.** Sem ele, um "apagar aqui e criar ali" pode chegar
   como `D` + `A`; com ele, como `R`. Trate os dois — o teste-guarda do conserto
   precisou aceitar as duas redações porque o git decide pela semelhança do
   conteúdo, e essa decisão muda quando o arquivo muda junto.
2. **Não caia no alarme falso.** Renomear `test_x.py` para `test_y.py` é
   legítimo e frequente; se o portão passar a cobrar autorização por isso, ele
   vira um guarda que grita à toa — e guarda que grita à toa é guarda que se
   aprende a ignorar. O par `teste → teste` tem de continuar passando, e isso
   merece um teste próprio.

**Onde mais isto mora:** todo lugar que lê `git diff --name-only` para decidir
escopo. Neste repositório, quando esta entrada foi escrita:
`ci/catraca_de_testes.py` (consertado), `ci/cerca-de-celula.sh`,
`ci/ci.py::celulas_tocadas`, `ci/orcamento-de-mudanca.sh`. Nos três últimos o
efeito é diferente e menos grave — um rename de arquivo de célula ainda aponta
para uma célula —, mas a leitura é a mesma e vale conferir antes de confiar.

**Como foi achado:** auditoria interna das Ondas 3 a 6 (29/08/2026), procurando
um terceiro jeito de reduzir a proteção dos testes sem a catraca reprovar. A
própria catraca declarava dois furos na cara; este era o terceiro, e não estava
declarado porque ninguém sabia dele. Conserto e prova: PR #465.
