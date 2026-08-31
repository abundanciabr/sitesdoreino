# 259 — A régua que se recalcula sozinha comendo a espera errada

**Sintoma.** `ci/medir_tempos.py --escrever` roda limpo, sem aviso e sem erro,
e grava na régua das esperas que **o Docker Desktop acorda frio em 2 segundos**.
O número anterior, medido à mão, era 90 s. Nada no processo reclama: o script
mediu com precisão, o JSON é válido, os testes passam.

**Causa.** O recálculo separava as esperas do log
(`~/.sitesdoreino/esperas.jsonl`) **pelo prefixo do alvo**, e o mapa era:

```python
DO_LOG = {"pouso": "pouso:", "docker-frio": "sonda:", "sonda": "sonda:"}
```

`pouso:` só é escrito pelo `--pouso`, então ali o prefixo identifica sozinho.
Mas **`sonda:` é genérico**: é o alvo de qualquer `ci/esperar.py --sonda CMD`.
Em 31/08/2026 as 6 sondas do log eram um `gh pr view --json mergeable`, um
`pg_isready`, um `git fetch && git grep`, dois `gh pr view --json state` e
nenhuma, nenhuma mesmo, era o Docker acordando. O `docker-frio` estava comendo
a duração de coisas sem parentesco com ele, e a mediana de 2 s vinha de esperas
que terminam no primeiro piscar.

O `ci/esperar.py` **já tinha** a peça que resolvia: a opção `--regua`, que deixa
uma sonda declarar a qual chave da régua ela pertence (o próprio cabeçalho do
script traz o exemplo `--sonda "docker info" --regua docker-frio`). Só que
`registrar_espera` **não gravava essa chave no log** — a declaração morria na
memória do processo, e quem media depois só tinha o prefixo.

**Por que passa despercebido.** Esta é a `RETROSPECTIVA-FASE-D` §1 (falso-verde)
na sua forma mais educada: não há vermelho para ver. Uma régua errada não
quebra nada na hora, ela só faz a voz da espera mentir baixinho durante semanas,
e mentir com autoridade, porque o número diz "medido". É o mesmo perigo que o
`CLAUDE.md` descreve para o portão do travessão: **medir a coisa errada com
precisão é como um portão morre.**

**Solução.** Duas linhas de desenho, nas duas pontas:

1. `registrar_espera` passou a gravar o campo `regua` em cada linha do log — a
   chave efetiva (`args.regua or chave`), decidida por quem esperou.
2. `medir_do_log` passou a receber, junto do prefixo, se aquela chave **exige a
   declaração**. `pouso` não exige (o prefixo basta); `docker-frio` exige. Sem
   nenhuma espera declarada, a fonte devolve "sem amostra" e a régua **mantém o
   número antigo**, com o aviso na tela: `docker-frio: sem amostra nova —
   mantive o antigo`.

O desfecho honesto de uma fonte que não sabe é ficar quieta, não chutar. Isso já
estava escrito no cabeçalho do `medir_tempos.py` ("fonte que falhar NÃO derruba
a medição inteira") — o furo era que a fonte não sabia que não sabia.

**A regra que fica.** Quando uma medição automática separa amostras por um
identificador, pergunte se esse identificador é **exclusivo daquilo que você
quer medir**. Se ele for genérico (um comando livre, um nome de arquivo, um
prefixo que qualquer um pode escrever), a amostra vai encher de vizinhos e a
média não vai avisar. Ou o produtor declara a que grandeza pertence, ou aquela
chave não se mede sozinha.

**O primo desta armadilha:** duas chaves da mesma régua podem parecer a mesma
grandeza e não ser. A chave `pouso` mede *a pista mergear um PR que já está
verde na fila* (p50 109 s); o número que se colhe com
`gh pr list --json createdAt,mergedAt` é *o PR aberto até o merge* (p50 ~8 min),
e embute a volta de checks inteira. Trocar um pelo outro faria a voz dizer
"normalmente isso leva 8 min" para uma espera de 2 min. O rótulo de cada chave
existe para essa pergunta: leia o rótulo antes de escrever o número.

**Ver também:** `armadilhas/161` (a espera que fala e morre no teto),
`armadilhas/258` (a espera do pouso, que não devia existir).
