---
schema_version: 2
armadilha: 225
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: quem recusa já é o portão certo (`ci/divida_do_livro.py`), e a recusa dele até nomeia a isenção ("PR que só toca painel/ é isento"); o que falta é a frase que liga a isenção ao MOTIVO dela (o checkout da pista é da main), e isso é texto, não medição -- um portão que exigisse "registro de dívida em PR próprio" teria de adivinhar a intenção de cada registro
sinal:
  - `tirei a etiqueta .?pousar.? para n[ãa]o travar a fila`
---

# O registro que paga a dívida do livro não pode viajar DENTRO do PR barrado — a pista faz checkout da `main`

**Sintoma.** Você pede pouso, o portão reprova em **"dívida do livro"** por
merges de OUTRAS sessões (`armadilhas/185`), você escreve o registro que quita a
conta, commita **no mesmo ramo**, e:

```
python ci/mergear.py <N> --conferir
  dívida do livro   PASS   livro em dia      ← na sua máquina
```

```
🛬 pista de pouso — não pousei, e tirei a etiqueta `pousar`
  dívida do livro   FAIL   2 merge(s) sem registro   ← na pista, no mesmo PR
```

As duas leituras discordam sobre o mesmo fato, e a sua é a que engana: local, o
`--conferir` lê `painel/registros/` do SEU checkout, onde o registro novo já
está. Repetir o pedido de pouso não muda nada — é laço.

**Causa.** A pista (`.github/workflows/pouso.yml`) **nunca faz checkout do
código do PR**: ela roda `actions/checkout` com `ref: main`. É decisão de
segurança, não descuido — um PR não pode alterar o juiz que vai julgá-lo
(`pull_request_target` com checkout do PR é a receita clássica de execução de
código não revisado com o token do repositório). Consequência direta:
`ci/divida_do_livro.py::numeros_citados()` lê `painel/registros/` **da `main`**,
onde o seu registro ainda não existe. Um registro que viaja dentro do PR barrado
não existe para o portão que o barra.

**Solução — PR próprio, só de `painel/`, mergeado ANTES.** A isenção que faz
isso funcionar já está escrita na própria recusa e é `so_toca_o_livro`: um PR
cujo diff inteiro está sob `painel/` é isento da conferência de dívida (senão o
pagamento seria impossível — ele também nasceria devendo).

```bash
# 1. tire o registro do ramo barrado
cp painel/registros/<o-registro>.js /tmp/           # guarde ANTES do reset
git reset --hard HEAD~1 && git push --force-with-lease

# 2. PR só do livro, a partir de origin/main
git switch -c agent/livro/divida-<numeros> origin/main
cp /tmp/<o-registro>.js painel/registros/ && git add painel/registros
# commit, push, PR, --pousar

# 3. com ele na main, o PR original pousa
python ci/mergear.py <N> --pousar
```

**A regra que fica, em uma frase:** dívida do livro se paga **na `main`**, nunca
dentro do PR que ela está barrando. Vale para a dívida de outras sessões
(`armadilhas/185`) e para a sua própria.

E o corolário que economiza a volta inteira: **antes de pedir pouso, rode
`python ci/mergear.py <N> --conferir`.** Se a dívida aparecer ali, você a paga
em PR próprio enquanto os checks do seu ainda rodam, e as duas coisas caminham
juntas em vez de uma esperar a outra.

**Origem.** 30/08/2026, TAR-039 (o professor também modera, PR #633). O
pagamento tinha sido commitado dentro do próprio PR: local o portão dizia
"livro em dia", a pista devolveu o PR com a mesma conta aberta. Custou uma
volta; a segunda tentativa, com o PR #634 só de `painel/`, entrou.
