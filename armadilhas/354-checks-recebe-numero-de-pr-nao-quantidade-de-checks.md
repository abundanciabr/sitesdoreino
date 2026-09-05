# `--checks` recebe o número do PR, não a quantidade de checks que ele tem

**Sintoma:** `python ci/esperar.py --checks <N> --teto 20 --e-pousar` repete
"não consegui medir" a cada tentativa, até estourar as 20 tentativas de 20
segundos sem nunca ver um check. Nada quebrou (o instrumento é fail-closed e
não pousa o que não consegue medir), mas o ciclo inteiro de espera foi
queimado à toa.

Medido em 05/09/2026: **dois robôs diferentes, sem saber um do outro, caíram
nisso no mesmo dia.** Um passou `--checks 6` porque era a quantidade de checks
que via na lista do PR, e o portão foi medir o **PR #6**, mesclado desde os
primeiros dias do repositório e alheio à tarefa. O outro passou `--checks 13`
pelo mesmo motivo, e o portão foi medir o **PR #13**, também mesclado desde
agosto. O segundo só percebeu porque estranhou o "não consegui medir" se
repetir tentativa após tentativa.

**Causa:** o parâmetro é `--checks PR` (a ajuda do próprio programa diz isso),
mas o NOME sugere uma contagem, e um número pequeno é plausível nas duas
leituras. O robô acabou de olhar `gh pr checks` ou a lista de checks do PR, e
essa contagem está fresca na cabeça no exato momento de montar o comando de
espera, então nada na tela chama atenção para a troca.

**Solução:** o argumento de `--checks` é o **número do PR**, o mesmo que
aparece em `gh pr view <N>`, na URL do PR e no que o `gh pr create` devolveu
ao abri-lo. Nunca a contagem de quantos checks existem. Neste repositório, que
já passa de mil PRs, um número de dois dígitos ou menos em `--checks` é quase
certeza de erro: confira contra o número que o `gh pr create` devolveu antes
de montar o comando.

```bash
# ERRADO — 6 e 13 eram QUANTIDADES de checks, não números de PR
python ci/esperar.py --checks 6 --teto 20 --e-pousar
python ci/esperar.py --checks 13 --teto 20 --e-pousar

# CERTO — o número que "gh pr create" devolveu para O SEU PR
python ci/esperar.py --checks 1131 --teto 20 --e-pousar
```

O conserto de fundo não é memória, é o instrumento recusar na cara: `ci/esperar.py`
pode conferir, antes de esperar, que o número recebido é um PR ABERTO deste
repositório, e recusar com uma frase que ensine em vez de gastar o teto
inteiro tentando medir um PR que já fechou há semanas. Isso ficou registrado
como tarefa de conserto no balcão (`ci/`, caminho CODEOWNERS, sem mandato para
tocar no dia desta entrada) em vez de ser construído aqui.

**Origem:** dois robôs independentes, 05/09/2026. **Categoria**
(`RETROSPECTIVA-FASE-D`): garantia sem mecanismo (a régua morava só na leitura
atenta da ajuda) · falso-verde por omissão (o instrumento fica repetindo um
erro genérico em vez de apontar a causa).
