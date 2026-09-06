---
schema_version: 2
armadilha: 372
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  detector: ci/tests/test_padrao_de_trabalho.py
  motivo: o teto de caracteres do CLAUDE.md reprova o arquivo engordado; o que ele não mede é se um texto dentro do teto é lei ou história, e isso é julgamento de quem escreve
sinal:
  - FAIL cabe no teto de contexto
  - Subir o teto é decisão do mantenedor
---

# O CLAUDE.md engordou de história e era relido em toda chamada de todo robô

**Data:** 06/09/2026 · **Onde:** `CLAUDE.md` da raiz, medido pelo mantenedor no painel de uso · **Custo medido:** 421 milhões de tokens em 4 dias só para reler o arquivo.

## Sintoma

A cota semanal some sem que o trabalho pareça maior. O `CLAUDE.md` tem 60 mil caracteres e quase metade é história: a data em que cada lei nasceu, o número do PR, "medido no dia", "custou". Nada disso muda o que o robô faz na chamada seguinte, e tudo isso é reenviado em cada chamada, de cada sessão, de cada robô.

## Causa

Cada lei nova entrava no arquivo com o próprio porquê, porque a doença-mãe desta casa é lei que depende de lembrança, e contar o dia em que a regra custou caro parecia a forma de ninguém repeti-lo. O arquivo certo para a regra é o arquivo errado para a memória: o único que entra sozinho no contexto de toda sessão é também o mais caro de encher.

## Solução

Lei e história em lugares diferentes. O `CLAUDE.md` carrega só a regra, o comando e a linha `Quem faz valer`; o porquê de cada lei mora em `docs/decisoes/DECISAO-claude-md-so-lei.md`. A régua, em uma pergunta: "isto muda o que o robô faz na próxima chamada?" Se não muda, é história, e vai para a memória.

O teto de 20.000 caracteres (`TETO_DE_CARACTERES` em `ci/padrao_de_trabalho.py`) reprova o arquivo que reengordar, e a recusa diz para onde a história vai. Subir o teto é decisão do mantenedor. Lei nova: regra no `CLAUDE.md`, história na memória, no mesmo PR.
