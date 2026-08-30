---
schema_version: 2
armadilha: 224
estado: guardada
degrau: 5
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: CI
  dono: ci/mapa_de_celulas.py
sinal:
  - `declara consumir .* e n[ãa]o h[áa] sinal disso`
  - `o mapa e o c[óo]digo discordam sobre quem consome quem`
---

# Célula nova não pode declarar em `celulas.yml` o consumo que o PLANO prevê — o varredor reprova como declaração órfã

**Sintoma.** O despacho da gênese diz, com todas as letras, *"`celulas.yml` com
`consome: [identidade]`"* — e o plano da célula diz o mesmo. Você escreve
exatamente isso, e o `muralhas` reprova:

```
  mapa-de-celulas  FAIL  o mapa e o código discordam sobre quem consome quem
  - gamificacao declara consumir identidade e não há sinal disso
```

A leitura tentadora é *"o varredor não sabe que a célula vai consumir"*. Ele
sabe melhor: **ela ainda não consome.**

**Causa.** `ci/mapa_de_celulas.py::verificar()` mede o consumo nos **dois**
sentidos, e os dois são FAIL:

| sentido | o que significa |
|---|---|
| código lê `OUTRA_API_URL`, mapa não declara | dependência escondida — quebra a ordem de publicação |
| mapa declara, código não lê | **declaração órfã** — o mapa promete a mais |

A régua é literal: a expressão `\b([A-Z][A-Z0-9_]*)_API_URL\b` varrida sobre os
`caminhos` da célula, ignorando `tests/` e `migrations/`. Numa gênese não há
cliente, não há `settings` lendo endereço, não há nada — logo, não há sinal, e a
declaração fica órfã. **Nenhuma gênese de célula pode declarar consumo**, por
construção: o esqueleto não fala com ninguém.

E o motivo de o portão ser duro dos dois lados está escrito no próprio arquivo:
*"um mapa que promete a mais é tão mentiroso quanto um que promete a menos, e
envelhece exatamente assim: alguém remove o consumo e esquece a linha"*. Um mapa
que já nasce prometendo o futuro treina todo mundo a não confiar nele.

**Por que o despacho pede o contrário, e não é erro dele.** O plano de uma
célula descreve o **destino** — a `gamificacao` vai mesmo consumir a
`identidade` (§4 do plano dela), e a linha do consumo faz parte do desenho. O
que o plano não separa é *em qual PR da escada* essa linha entra. Ela entra no
mesmo PR do CLIENTE, e não antes — na escada da `gamificacao`, o PR 7
(`clients/sessao`), não o PR 1.

**Solução — `consome: []`, com o comentário que explica a lista vazia:**

```yaml
  gamificacao:
    caminhos: [services/gamificacao]
    # NASCE SEM CONSUMIR NINGUÉM, e a lista vazia é a declaração honesta —
    # não um esquecimento. O plano prevê `consome: [identidade]`, e essa
    # linha entra no PR 7 da escada, junto com o cliente que lê
    # `IDENTIDADE_API_URL`. Declará-la HOJE seria declaração órfã.
    consome: []
```

O comentário não é enfeite: `celulas.yml` já distingue *"não consome ninguém"*
(a lista vazia, uma declaração) de *"esquecemos"* (a chave ausente, que o
carregador trata como `[]` sem reclamar). Sem a frase, o próximo leitor não sabe
em qual dos dois casos está.

**E o esquecimento do outro lado não escapa:** quem escrever o cliente no PR 7 e
não voltar aqui é pego pelo primeiro sentido do varredor, com a mensagem
`gamificacao lê IDENTIDADE_API_URL e não declara`. A linha entra em algum
momento — a única pergunta é se ela entra junto com a verdade ou antes dela.

**Vale para todo campo do mapa que descreve comportamento**, não só `consome`:
`caminhos` também é medido contra o disco (caminho declarado que não existe é
FAIL). A regra que generaliza é a de sempre nesta casa: **declaração é medida
contra a realidade, então declare o presente, nunca o roadmap.**

**Origem:** TAR-034, a gênese da célula `gamificacao` (30/08/2026, PR #629). O
despacho e o `PLANO-CELULA-GAMIFICACAO.md` §6 pediam `consome: [identidade]` na
linha 1 da escada; o varredor recusou, e a recusa estava certa.
