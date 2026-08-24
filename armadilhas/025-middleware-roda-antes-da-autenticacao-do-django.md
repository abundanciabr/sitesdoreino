<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.6  ·  referencias antigas "ARMADILHAS §4.6" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.6 Middleware roda ANTES da autenticação do django-ninja

**Sintoma:** teste que espera 401 (sem token) recebe 404, ou tenta uma conexão HTTP
real e estoura.
**Causa:** ordem real da pilha: middleware → view/auth. O CONV-SITE resolve o site
(e chama o catálogo) **antes** de o Bearer ser conferido.
**Solução:** todo teste que bate na API precisa de Host válido **e** do mock de rede
ativo — inclusive os testes de "sem token".
**Origem:** Prompt 4 (checkout).
