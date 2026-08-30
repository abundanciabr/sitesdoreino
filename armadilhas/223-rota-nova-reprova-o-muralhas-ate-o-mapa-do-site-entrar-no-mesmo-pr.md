---
schema_version: 2
armadilha: 223
estado: documentada
degrau: 5
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: CI
  motivo: o próprio `ci/mapa_do_site.py` reprova nos dois sentidos (rota sem entrada, entrada sem rota) e a recusa já ensina o conserto; o que faltava era a entrada dizer que o conserto cabe no MESMO PR, e não num segundo
---

# Rota nova reprova o `muralhas`, e o conserto (`painel/mapa-do-site.json`) parece ser de outra célula

**Sintoma.** Você acrescenta uma rota ao `urls.py` de uma célula qualquer, a
suíte da célula fica verde, e o `muralhas` reprova com uma mensagem que não fala
da sua célula:

```
  mapa-do-site  FAIL  painel/mapa-do-site.json discorda do roteamento
--- FAIL cobertura ---
  - FALTA no mapa: forum → 't/<int:topico_id>/moderar'   responde em /forum/t/<int:topico_id>/moderar
```

**Causa.** `ci/mapa_do_site.py` roda em todo PR e compara o mapa humano
(`painel/mapa-do-site.json`, a tela `/admin/mapa/`) com o roteamento medido de
três fontes. Rota que existe e não está no mapa é página que o dono não sabe que
tem; entrada sem rota é link quebrado na tela dele. Os dois sentidos reprovam.

**A dúvida que custa a rodada, e a resposta.** `painel/` é a célula `admin`
(`celulas.yml`), então bate o reflexo de tirar o mapa do PR e mandá-lo depois,
por causa da `armadilhas/151`. **Não faça isso, por dois motivos:**

1. **A regra de 151 caiu.** A cerca "1 PR = 1 célula" acabou em 29/08/2026
   (Onda 5 do `PLANO-MESTRE-ROBOS-SEM-COLISAO.md`): o `ci-celula` virou MATRIZ e
   roda a suíte de CADA célula tocada, em vez de recusar por largura. Dois PRs
   já não compram nada. Precedente medido: o PR #585 (30/08) levou
   `services/forum/**` e `painel/**` juntos e mergeou.
2. **Separar cria um impasse de ordem.** O mapa sozinho, num PR anterior,
   descreve rota que ainda não existe, e o mesmo portão reprova pelo outro lado
   ("entrada sem rota"). O PR do código sozinho reprova pelo primeiro. Só
   juntos os dois ficam verdes ao mesmo tempo.

**A regra que fica:** rota nova e a linha dela no `painel/mapa-do-site.json`
viajam no MESMO PR. Vale para `path()`, `re_path()` e rota de gesto (o endereço
que um botão dispara) — o varredor mede `urls.py`, não telas.

O que o portão **não** confere, e por isso é revisão de gente: se o `titulo` e a
`descricao` estão escritos em português de leigo, e se o campo `gesto` está
correto (`RETROSPECTIVA-FASE-D` §2, buraco declarado).

**Origem:** 30/08/2026, TAR-037 (as ferramentas do administrador no fórum, PR
#627). Quatro rotas novas, quatro linhas no mapa, um `muralhas` verde.
