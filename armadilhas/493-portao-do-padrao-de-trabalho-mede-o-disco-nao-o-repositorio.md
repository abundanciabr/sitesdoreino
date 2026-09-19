---
schema_version: 2
armadilha: 493
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/padrao_de_trabalho.py
  - ci/tests/test_padrao_de_trabalho.py
sinal:
  - "teto de CLAUDE\\.md FAIL"
guarda:
  tipo: CI
  dono: ci/tests/test_padrao_de_trabalho.py
  detector: test_o_padrao_esta_integro_no_repositorio_de_verdade
licao: "ci/padrao_de_trabalho.py le CLAUDE.md do disco com read_bytes() para o teto de 12000 bytes. No Windows o CRLF infla o arquivo (11994 no git, 12230 no disco) e o teste reprova so ali, sem nada errado no conteudo. Guarda do repositorio de verdade le via git show, nunca read_bytes() do disco."
---

# O portão do padrão de trabalho mede o disco, não o repositório

**Data:** 18/09/2026 · **Onde:** `ci/padrao_de_trabalho.py` ·
**Custo evitado:** perseguir um `CLAUDE.md` "inchado" que nunca cresceu

## Sintoma

`test_padrao_de_trabalho.py::test_o_padrao_esta_integro_no_repositorio_de_verdade`
reprova só no Windows local com `teto de CLAUDE.md FAIL`, e passa normal no
runner Linux do CI. Medido nesta sessão:

```
git show origin/main:CLAUDE.md | wc -c   →  11994 bytes (dentro do teto de 12000)
wc -c < CLAUDE.md (disco, checkout local) →  12230 bytes (acima do teto)
```

## Causa

`ci/padrao_de_trabalho.py`, linha 227, confere o teto de `CLAUDE.md` com
`read_bytes()` sobre o arquivo do disco. O nome do teste promete medir "o
repositório de verdade", mas `read_bytes()` lê o que o checkout local tem
nos bytes, e no Windows o Git normaliza `LF` para `CRLF` ao materializar o
arquivo. A diferença de 236 bytes entre as duas medições é exatamente essa
normalização de fim de linha, não conteúdo novo. O guarda mede a
configuração de fim de linha da máquina, não o objeto que o Git versiona.

## Solução

Um guarda que declara medir "o repositório de verdade" lê pelo Git, nunca
pelo disco: `git show origin/main:<caminho>` (ou `git show HEAD:<caminho>`
quando o alvo é o commit atual, não a origem). Isso devolve os bytes que o
Git de fato versiona, sem normalização de fim de linha da máquina local, e
o teto passa a medir o que ele promete medir em qualquer sistema
operacional.

## Família: instrumento medindo o ambiente, não o objeto

Esta é a quinta armadilha da mesma família nesta sessão: um instrumento
escolhido ou lido por conveniência do ambiente, em vez de pela fonte
correta, produz um sintoma que parece defeito no objeto medido e não é.

- armadilha 489: `ci/freeze-de-contrato.sh` escolhe o primeiro Python do
  PATH, não o da bancada.
- armadilha 490: um exportador que lê o próprio contrato congelado mede a
  si mesmo em vez de medir o código.
- armadilha 491: o atalho `.exe` do venv é bloqueado pela política do
  sistema; o mesmo pacote pelo módulo Python funciona.
- armadilha 493 (esta): o portão do padrão de trabalho lê o `CLAUDE.md` do
  disco (com o CRLF do Windows) em vez de pelo Git, e mede o fim de linha
  da máquina em vez do conteúdo versionado.

## O que NÃO é a causa

Não é `CLAUDE.md` ter crescido além do teto: o conteúdo versionado
(`git show origin/main:CLAUDE.md`) está em 11994 bytes, dentro do limite.
Não é bug na lógica de comparação do teste: ele compara corretamente o que
`read_bytes()` devolve contra o teto declarado. O defeito é a fonte da
leitura.
