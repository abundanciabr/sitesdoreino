<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.15  ·  referencias antigas "ARMADILHAS §5.15" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.15 Portão que exige "revisão humana" vira carimbo perpétuo se não expirar no diff

**Sintoma:** um campo tipo `_revisado_humano: "Fulano 2026-08-23"` fica verde
para sempre — o texto é reescrito em dezembro e a declaração de agosto continua
respondendo por ele. O portão MEDE que alguém escreveu uma linha, não que
alguém leu o texto que está no ar.
**Causa:** declaração de revisão é um dado ao lado do conteúdo, não um hash
DELE. Nada no estado atual do arquivo revela que o conteúdo mudou depois.
**Solução:** o portão precisa de duas metades — a estática (a declaração existe,
está bem formada, cobre cada unidade que precisa de revisão) e a **do diff**
(`git show ${BASE_REF}:arquivo`): se o conteúdo revisado mudou e a declaração
NÃO mudou, reprova. É a mesma mecânica da regra anti-burla do `_fonte`
(PLANO-I18N D4), e pelo mesmo motivo: sem ela, "recarimbar" é mais barato que
cumprir. Corolário de granularidade: declaração por unidade que o revisor
realmente leu (no i18n, POR IDIOMA) — uma declaração agregada faz uma leitura
responder por textos que o revisor nunca viu.
**Origem:** despacho funil/i18n-juridico (23/08/2026) — implementação do D8.2
em `services/funil/apps/i18n/validador.py` (`_checar_juridico` + `_revisao_no_diff`).
