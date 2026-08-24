<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §7 — Coordenação (humano, painéis, outros agentes)
     ID historico: §7.6  ·  referencias antigas "ARMADILHAS §7.6" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 7.6 Fase E (red-team): golpes paralelos colidem na MESMA linha da tabela

**Sintoma:** `git push origin main` (ou merge de um PR de docs) recusa com
"non-fast-forward", e o `git merge`/`rebase` seguinte estoura `CONFLICT (content)`
bem na tabela de `02-RED-TEAM.md` — mesmo as duas sessões tendo editado **linhas
diferentes** da tabela (uma marca o golpe 2, outra marca o golpe 3, por exemplo).
**Causa:** durante a Fase E é normal ter mais de uma sessão rodando golpes
diferentes ao mesmo tempo (§7.1) — cada uma parte do MESMO commit de
`origin/main` no início, edita sua própria linha da tabela de resultados, e a
segunda a empurrar sempre encontra a primeira já mergeada. Git resolve isso como
merge de texto puro; se as linhas tocadas forem realmente diferentes, o conflito é
só de proximidade (blocos de diff adjacentes), não de conteúdo — resolve-se
mantendo as DUAS marcações lado a lado, nunca escolhendo uma em vez da outra.
**Solução:** antes de tentar `push`/merge de uma marcação de golpe,
`git fetch origin && git rebase origin/main` (ou `git merge origin/main`) no branch
de docs; se aparecer conflito só na tabela, é quase sempre "as duas linhas devem
sobreviver" — edite o bloco de conflito juntando as duas marcações, nunca descarte
a alheia. Depois disso, o push volta a ser fast-forward.
**Origem:** golpe 2, PR #41 — colidiu com a marcação do golpe 3 (PR #34) feita por
outra sessão entre o commit local e o push.
