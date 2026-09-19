---
schema_version: 2
armadilha: 484
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/padrao_de_trabalho.py
  - ci/pr.py
  - ci/mergear.py
  - painel/LEIA-ME.md
sinal:
  - "teto de CLAUDE.md"
  - "recibo excede 1 KB"
  - "Mova história para docs/decisoes"
  - "falta mandato do dono"
guarda:
  tipo: sino
  dono: ci/consultar_armadilhas.py
  detector: gatilho por caminho (CLAUDE.md, AGENTS.md, ci/pr.py)
licao: Arquivo guardado por portão tem ORÇAMENTO, e ele se mede ANTES de escrever. python ci/padrao_de_trabalho.py diz quantos bytes sobram no CLAUDE.md (eram 6 em 17/09/2026), painel/LEIA-ME.md diz que o recibo cabe em 1 KB, ci/mergear.py exige o Mandato-do-mantenedor com pedido e caminhos exatos numa LINHA SÓ. Medir depois custou cinco reescritas e três recusas do make pr.
---

# Meça o portão antes de escrever no arquivo que ele guarda

Medido em 17/09/2026, na entrega do portão do voo (PR #1703). A lei nova tinha
1.346 bytes. O `CLAUDE.md` de `origin/main` tinha 11.994 de um teto de 12.000:
**6 bytes livres.** Descobri isso depois de escrever, e não antes. O conserto
foi reescrever a mesma seção cinco vezes até a lei nova caber sem apagar
obrigação alheia (a versão final entregou a regra com o arquivo no MESMO
tamanho de antes).

Os três orçamentos desta casa, e o comando que diz cada um ANTES:

```bash
python ci/padrao_de_trabalho.py     # teto de CLAUDE.md e de AGENTS.md, em bytes
grep -n "1 KB" painel/LEIA-ME.md    # o recibo do make pr: título + detalhe curtos
sed -n '884,935p' ci/mergear.py     # o mandato: uma linha, com os caminhos exatos
```

O mandato mordeu do mesmo jeito: `ci/mergear.py` procura
`^Mandato-do-mantenedor: (.{20,})$` e exige que os caminhos apareçam como
palavras DAQUELA linha. O pedido do mantenedor espalhado em três linhas bonitas
reprova; a linha única, feia e completa, passa.

E um detalhe que só morde no Windows: o teto mede bytes do arquivo no disco,
sem normalizar quebra de linha. Com CRLF, o `CLAUDE.md` intocado de
`origin/main` já dá FAIL (12.230 de 12.000). Antes de acreditar num vermelho
de teto, meça o mesmo arquivo com LF.
