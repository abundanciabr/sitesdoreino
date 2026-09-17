---
schema_version: 2
armadilha: 482
estado: documentada
degrau: 2
confianca: estrutural
custo_por_queda: alto
gatilho:
  - ci/mergear.py
  - ci/vigia_do_pouso.py
  - .github/workflows/pouso.yml
guarda:
  tipo: nenhum
  motivo: O silêncio está dentro de `ci/`, caminho CODEOWNERS, e consertá-lo é decisão do mantenedor. Enquanto isso, a cura é o comando `--conferir` na mão de quem abre o PR.
licao: PR verde reprovado no mandato some do log do `pouso.yml`: a varredura dá `continue` sem imprimir nada, e silêncio parece fila andando. Antes de dizer pronto, rode `python ci/mergear.py <N> --conferir`, que é somente leitura e imprime a tabela com o motivo. É a única coisa que separa esperar a vez de já ter sido pulado.
---

# A varredura do pouso pula em silêncio, e silêncio parece fila andando

A varredura que integra os PRs prontos tem esta linha em `integrar_abertos`,
em `ci/mergear.py`:

```python
if checar_mandato(raiz, pr).estado is not Estado.PASS:
    continue
```

O `continue` não imprime nada. Um PR verde que reprova no mandato desaparece
do log do `pouso.yml` como se nunca tivesse sido lido. Quem abre o log vê os
outros PRs sendo julgados, um por um, e conclui a coisa mais razoável do
mundo: que a vez do seu ainda não chegou.

Não chegou e não vai chegar. A varredura roda de novo, pula de novo, e cada
volta produz exatamente a mesma evidência de nada. A espera é indistinguível
do progresso, e é por isso que ela custa horas em vez de minutos: ninguém
interrompe uma fila que parece andar.

O único jeito de saber:

```bash
python ci/mergear.py <N> --conferir
```

Ele é somente leitura (não integra nada) e imprime a tabela inteira do
julgamento, com o motivo escrito na linha que reprovou. Rode antes de dizer
que o PR está pronto, não depois de estranhar a demora.

O que fez o PR #1684 ser pulado por 19 minutos foi um mandato escrito em
parágrafo, com vírgula entre os caminhos (armadilhas/481). Mas a causa pode
ser qualquer reprovação de `checar_mandato`, e todas somem do mesmo jeito.
