schema_version: 2
armadilha: 433
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/mergear.py
  - ci/tests/test_mergear.py
guarda:
  tipo: CI
  dono: ci/tests/test_mergear.py
  detector: test_o_main_abre_o_diff_uma_vez_para_as_duas_sombras
sinal: 'cada sombra parece correta isoladamente, mas o pouso abre o endpoint do diff mais de uma vez'
licao: 'Quando duas sombras compartilham um recurso, teste a coordenação pelo main e conte as chamadas externas. Um teste apenas na classe compartilhada não detecta a segunda sombra criando outro leitor.'
---

# 433: Sombra coordenada só se prova no `main()`

**Data:** 09/09/2026. **Onde:** `ci/mergear.py` e `ci/tests/test_mergear.py`.

## Sintoma e causa

O teste unitário de `DiffDoPR` provava que uma instância reutiliza sua leitura,
mas o `main()` podia entregar uma instância nova à segunda sombra sem que a
suíte percebesse. As duas sombras pareciam corretas e o mesmo endpoint era
consultado duas vezes.

## Solução e evidência

O teste passa pelo `main()`, simula o pouso completo e conta exatamente uma
chamada a `pulls/N/files`. Outra prova força a primeira leitura a falhar e
exige que a segunda tente novamente, em vez de aceitar um diff vazio guardado.
