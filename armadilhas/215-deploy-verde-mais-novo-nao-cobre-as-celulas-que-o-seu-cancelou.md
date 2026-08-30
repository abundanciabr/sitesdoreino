---
schema_version: 2
armadilha: 215
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: nada compara a lista de células do run cancelado com a dos runs seguintes; exigiria um vigia que soubesse quais células cada merge ainda deve ao site
sinal:
  - `deploy \([a-z]+\): cancelled`
---

# Um deploy verde MAIS NOVO não cobre as células que o seu run cancelou

**Sintoma:** o `deploy-celula` do seu merge fica vermelho. Você olha a lista de
runs, vê um mais novo já `success`, e conclui o razoável: *a esteira publica
sempre a `main` mais recente, então o run novo levou a minha mudança junto*.

Fecha a tarefa. **Metade do seu merge não está no ar.**

**Causa — duas regras verdadeiras que, juntas, abrem um buraco:**

1. **A matriz do deploy tem `fail-fast`.** Uma célula que falha **cancela as
   irmãs**. No caso medido, `forum` caiu por blip de SSH (`armadilhas/127`) e
   levou `funil`, `quiz`, `admin` e `sugestoes` junto — `checkout` já tinha
   passado e sobreviveu.
2. **Cada run só publica as células que o SEU push tocou.** O run seguinte
   nasceu de outro merge, com outro conjunto de caminhos. Ele publicou `admin`,
   `forum` e `sugestoes` — e nunca ouviu falar de `funil` e `quiz`.

Resultado: as duas células ficaram com a imagem antiga, **sem nada vermelho em
lugar nenhum**. O run do seu merge está vermelho e "já foi resolvido pelo
seguinte"; o seguinte está verde e não deve nada a ninguém.

É a mesma família da [188](188-deploy-de-push-cancelado-pela-cadeira-musical-fica-fora-do-ar.md)
— merge órfão que ninguém alarma — mas por outra porta: lá o run inteiro é
cancelado pela concorrência; aqui o run roda, uma célula decide o destino das
irmãs, e o silêncio vem da PARIDADE DE CAMINHOS entre merges diferentes.

**Como conferir, e é rápido:** compare as duas listas com os olhos.

```bash
gh run view <run-do-seu-merge> --json jobs --jq '.jobs[] | "\(.name): \(.conclusion)"'
gh run view <run-verde-mais-novo> --json jobs --jq '.jobs[] | "\(.name): \(.conclusion)"'
```

Toda célula que aparece `cancelled` na primeira e **não aparece** na segunda
continua devendo. `success` na primeira está publicada; não precisa de nada.

**Solução:** rode a vacina **no run do SEU merge**, não no verde mais novo —
`python ci/rerun_de_deploy.py --run <id>` (a mesma da 127 e da 188). Se você já
tem um trabalho seguinte que toca as células devedoras, ele também paga a dívida
ao mergear; foi o que aconteceu no caso medido, por sorte e não por desenho.

**A regra de bolso:** *verde mais novo não é quitação.* A pergunta certa nunca é
"a esteira já rodou depois de mim?", e sim **"quais células o meu merge tocou, e
qual run publicou CADA uma delas?"**.

**Contexto:** 30/08/2026, no deploy do PR #603 (a limpeza dos travessões). Eu
mesmo conclui, olhando a lista de runs, que o verde seguinte cobria tudo — e só
achei o buraco ao abrir os jobs um a um. `funil` e `quiz` teriam ficado com o
título antigo no ar por tempo indeterminado.
