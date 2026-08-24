# O patch de prova leva junto o que ainda não foi commitado — e o `-R` apaga

**Sintoma:** você segue o protocolo vermelho→verde por patch (`armadilhas/084`), a
suíte fica verde no fim, tudo parece certo — e **uma correção sua desapareceu**. O
único sinal foi a contagem de testes cair: `217 passed` virou `216 passed`. Nenhum
erro, nenhum conflito, nenhum aviso.

**Causa:** `git diff` captura **todo o trabalho não commitado**, não só a mudança que
você quer falsificar. Se você já tinha uma correção pronta e ainda não commitada na
árvore, ela entra no patch junto. Aí o `git apply -R` (o passo que produz o vermelho)
desfaz **as duas** — a que você queria quebrar e a que você queria guardar. Se o
vermelho aparecer como esperado, você aplica o patch de volta e segue; mas se algum
passo intermediário reescrever a árvore, a correção some sem deixar rastro.

**Solução — a catraca: commite o verde ANTES de gerar o patch.**

```bash
git add -A && git commit -m "wip: verde antes da prova"   # a catraca
git diff > /scratch/fix.patch     # agora só o que veio DEPOIS entra
```

Com o verde commitado, o pior caso do `apply -R` é voltar ao commit — nunca perder
trabalho. E `git diff` passa a significar exatamente "o que estou falsificando agora".

**Alternativas que também fecham o buraco**, quando commitar no meio não serve:

- `git diff -- caminho/do/arquivo.py` — restringe o patch ao arquivo em questão, em vez
  de levar a árvore inteira.
- `git status --short` **antes** de gerar o patch: se aparecer alguma coisa que você
  não pretende falsificar, pare e commite primeiro. Dois segundos que evitam a caça.

**O sinal que denuncia, e vale memorizar:** contagem de testes que **cai** entre duas
execuções verdes. Verde não é o mesmo que "nada se perdeu" — um teste que sumiu junto
com o código dele não reprova nada, e é por isso que este modo de falha é silencioso.
Compare a contagem com a do começo do despacho, sempre.

**Origem:** despacho EVO-21 (`sugestoes`, o sininho), 24/08/2026 — a correção de fuso
horário e o teste dela sumiram exatamente assim, e só a contagem 217→216 acusou.
