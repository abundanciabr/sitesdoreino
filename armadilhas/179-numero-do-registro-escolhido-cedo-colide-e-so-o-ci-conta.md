---
schema_version: 2
armadilha: 179
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: ci/tests/test_livro_manda_ao_almoxarife.py
sinal:
  - `n[úu]mero repetido no mesmo dia`
gatilho:
  - painel/registros/*
licao: o número do registro se PEDE, nunca se escolhe olhando a pasta: `python ci/reservar.py numero registro`. E o dia do nome sai em UTC (`date -u +%Y%m%d`), não no relógio daqui.
---

# Número do registro escolhido cedo colide — e quem conta é o CI, 15 minutos depois

**Sintoma.** O PR fica verde na sua máquina, você pede pouso, e ele volta com
**três** checks vermelhos que não têm nada a ver com o que você mudou:

```
muralhas             FAIL   o livro de ocorrências (painel/) inválido
ci-celula (admin)    FAIL   CalledProcessError: node painel/gerar_manifesto.js
ci-celula-gate       FAIL
```

O motivo real está enterrado no log da muralha:

```
- número repetido no mesmo dia: 20260829-093 foi usado por 2 registros
  (20260829-093-a-home-de-quem-nunca-pediu-..., 20260829-093-o-www-dava-tela-...)
```

`ci-celula (admin)` reprova junto porque `painel/` pertence à célula `admin` e o
`conftest.py` dela roda o gerador — um número repetido derruba a suíte inteira
de 250 testes que não têm relação nenhuma com o livro.

**Causa.** Você escolheu o número olhando `origin/main` **no começo** do
trabalho. Entre esse instante e o merge, outra sessão criou um registro e pegou
o mesmo número. Neste repositório isso não é raro: em 29/08/2026 houve dezenas
de merges por hora, e **três colisões seguidas** aconteceram numa única sessão
(093, 094 e, na terceira tentativa, quase o 096).

O gerador está certo em reprovar — dois registros com o mesmo `AAAAMMDD-NNN`
quebram a chave do livro. O problema é o momento em que você olha.

**Solução — PEÇA o número, não escolha.** O almoxarife existe desde 28/08/2026
(Onda 2 do plano mestre) e resolve isto por classe:

```bash
git fetch origin                                   # veja o mundo de agora
N=$(python ci/reservar.py numero registro)         # o SERVIDOR arbitra
DIA=$(python -c "import datetime;print(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d'))")
# arquivo: painel/registros/$DIA-$N-slug.js  (e o campo `arquivo:` idêntico)
```

O número sai de uma referência criada no servidor do GitHub — comparar-e-trocar,
a mesma trava que impede dois `push` simultâneos de se atropelarem. Duas sessões
no mesmo segundo: uma ganha, a outra é **recusada pelo servidor** e recebe o
próximo. Não há janela para as duas lerem "036 está livre".

O `DIA` sai em **UTC de propósito** — o almoxarife numera por dia UTC, e entre
21h e meia-noite em Brasília isso é o dia seguinte. Nomear com a data local ali
recria a colisão pelo outro lado: `armadilhas/158`.

> **Correção de 29/08/2026.** Esta entrada nasceu (PR #509) mandando escolher o
> número à mão "o mais tarde possível", conferindo a `main` com `git ls-tree`.
> **Aquilo não é solução — é a própria armadilha, mais rápida.** No mesmo dia,
> o registro escrito para contar ESTA lição colidiu seguindo ESTA receita: a
> `main` andou entre o `ls-tree` e o merge, e o `113` teve de virar `115`.
> Medido em 29/08: 82 números gastos no livro e só 39 reservas atômicas — mais
> da metade dos registros do dia foi adivinhada, e é daí que vêm as colisões.
> Conferir a `main` de agora não fecha a janela; só a encurta. O que fecha é o
> servidor arbitrar.

**Fallback honesto, quando o almoxarife não estiver disponível** (sem rede para
o `git ls-remote`, por exemplo): escolha à mão contra a `main` de agora, sabendo
que a janela continua aberta.

```bash
git fetch origin
git ls-tree -r origin/main --name-only painel/registros \
  | grep -o "$(date +%Y%m%d)-[0-9]*" | sort -u | tail -3
```

E se colidir, o conserto é mecânico e leva 30 segundos:

```bash
git mv painel/registros/AAAAMMDD-NNN-slug.js painel/registros/AAAAMMDD-MMM-slug.js
```

…e trocar o campo `arquivo:` **dentro** do arquivo (o gerador confere que os
dois batem), rodar `node painel/gerar_manifesto.js` de novo, commitar e
empurrar. **Não pule números "de propósito" para reservar espaço:** buraco na
sequência não reserva nada, e a próxima sessão vai preencher o buraco.

**Não confundir com** a pista de pouso ter atualizado a base: aquilo aparece
como `MOTIVO-DA-RECUSA: BASE-VELHA` e se resolve com `git pull` do próprio
ramo. Aqui a base está fresca e o livro é que tem dois donos para o mesmo
número.

**Quem faz valer.** A CURA: `ci/reservar.py` (a trava atômica no servidor) ·
`ci/tests/test_livro_manda_ao_almoxarife.py` (garante que a porta do livro e
esta entrada continuem mandando ao almoxarife — o furo real de 29/08 foi
mecanismo existente com a porta apontando para o outro lado) ·
`ci/tests/test_reservar.py` (inclui a corrida: segunda sessão recusada).
A REDE, para a colisão que ainda passar: `node painel/gerar_manifesto.js`
(fail-closed, não escreve nada quando acha a colisão) · `ci/muralha-do-painel.sh`
· e, de carona, `services/admin/tests/conftest.py`.
