<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §6 — Testes
     ID historico: §6.4  ·  referencias antigas "ARMADILHAS §6.4" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 6.4 Teste-guarda é intocável

Proibido deletar, desativar, comentar ou afrouxar teste para passar (RITOS.md §2.3).
Se o teste parece errado: **pare e reporte**, não ajuste o assert. Duas tentativas
consecutivas de correção falharam ⇒ `git reset --hard <último-verde>` e reporte —
a terceira tentativa é onde nascem labirintos.
