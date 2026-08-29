# Job que vira matriz muda de nome, e cega todo mundo que o procura pelo nome

**Sintoma:** você transforma um job em matriz (`strategy: matrix`), tudo fica
verde no PR — e o que depende daquele job pelo NOME começa a reprovar em
lugares distantes, um de cada vez:

```
--- ERROR ci-celula ---------------------------------------------------
Jobs vistos: ['ci-celula (admin)', 'ci-celula-gate', 'detectar']
Job renomeado/removido tira a evidência do lugar onde o portão a procura.
```

Medido em 29/08/2026 (Onda 5, degrau 2). O nome do job passou de `ci-celula`
para **`ci-celula (admin)`** — o GitHub anexa o valor da matriz entre
parênteses — e três consumidores diferentes ficaram cegos, cada um numa etapa:

| quem procurava | quando doeu | o que fez |
|---|---|---|
| `ci-celula-gate` (o próprio workflow) | no mesmo PR | reprovou: lista vazia contra contagem 1 |
| `ci/mergear.py` (skips permitidos) | ao mergear | reprovaria "pulo não declarado" |
| `ci/portao_de_deploy.py` | **depois do merge**, no deploy | ERROR, deploy pulado, produção intacta |

**Causa:** nome de job é uma interface, e a matriz a renomeia. Nada avisa: o
YAML continua válido, o job roda, e quem procura `nome == "ci-celula"` não acha
mais nada. Cada consumidor descobre sozinho, no momento em que ele roda — o
terceiro só apareceu **em produção**, porque o portão de deploy só existe depois
do merge.

**Solução — casar por prefixo, e exigir TODAS as instâncias:**

```python
instancias = [job for nome, job in sorted(por_nome.items())
              if nome == nome_job or nome.startswith(nome_job + " (")]
```

O detalhe que importa: **um `success` numa célula não fala pelas outras.** Se o
código aceitasse a primeira instância verde e parasse, um deploy sairia com uma
célula reprovada — justamente o que o `fail-fast: false` da matriz existe para
tornar visível. Guarda: `test_uma_celula_verde_nao_fala_pelas_outras`.

**A lição de método, que vale mais que o caso:** antes de transformar um job em
matriz, faça a lista de quem o procura pelo nome —

```bash
grep -rn "ci-celula" --include=*.py --include=*.yml --include=*.sh . | grep -v tests/
```

— e conserte os três de uma vez. Três rodadas de CI foram gastas descobrindo os
consumidores um a um, e o último custou um deploy vermelho.

**O que funcionou bem, e deve continuar assim:** os três reprovaram alto. O
portão disse ERROR ("não consegui medir") e **pulou o deploy** em vez de
publicar sem evidência — a produção seguiu servindo a imagem anterior o tempo
todo. Fail-closed é o que transformou um erro de nome num atraso, e não num
incidente.

**Origem:** PRs #443 e #444, Onda 5 do `PLANO-MESTRE-ROBOS-SEM-COLISAO.md`.
