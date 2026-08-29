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

**Solução.** Escolha o número **o mais tarde possível**, e confira contra a
`main` de agora, não contra a do começo:

```bash
git fetch origin
git ls-tree -r origin/main --name-only painel/registros \
  | grep -o "$(date +%Y%m%d)-[0-9]*" | sort -u | tail -3
```

Na prática, o que funciona:

1. Faça o PR de código primeiro, sem registro.
2. **Depois de abrir o PR** (você já tem o número dele para citar na
   `evidencia`), rode o `git fetch` acima, escolha o próximo número livre,
   escreva o registro, `node painel/gerar_manifesto.js`, commite e faça push.
3. Se ainda assim colidir, o conserto é mecânico e leva 30 segundos:

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

**Quem faz valer.** `node painel/gerar_manifesto.js` (fail-closed, não escreve
nada quando acha a colisão) · `ci/muralha-do-painel.sh` · e, de carona,
`services/admin/tests/conftest.py`.
