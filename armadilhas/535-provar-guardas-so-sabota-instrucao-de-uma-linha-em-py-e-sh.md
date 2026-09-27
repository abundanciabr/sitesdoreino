---
schema_version: 2
armadilha: 535
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: baixo
gatilho:
  - ci/provar_guardas.py
sinal:
  - "nenhuma guarda declarada"
guarda:
  tipo: nenhum
  motivo: "provar_guardas.py so sabota instrucao de uma linha porque DIALETOS declara um comentario por dialeto (pass # para .py, # para .sh); ensinar a mutar .js/.html exigiria um dialeto de comentario e de instrucao neutra por linguagem nova, mudanca de codigo fora do alcance de uma entrada de licao"
licao: "ci/provar_guardas.py so reconhece sufixo .py ou .sh (DIALETOS, linha 63) e so sabota UMA linha, comentando-a com o prefixo do dialeto. Guarda em .js ou .html nao tem sabotagem automatica: comente a linha protegida a mao, confirme o teste VERMELHO, desfaca a sabotagem e so entao commite."
---

# 535: `ci/provar_guardas.py` só sabota instrução de uma linha em `.py`/`.sh`

**Data:** 27/09/2026 · **Onde:** `ci/provar_guardas.py`, obra Appmax ·
**Custo evitado:** achar que o script recusou provar um guarda em `.js` ou
`.html` por erro, quando na verdade ele nunca alcançou essas linguagens.

## Sintoma

Rodar `python ci/provar_guardas.py ci/tests/test_exemplo.py` contra uma
guarda declarada num arquivo `.js` ou `.html` (por exemplo, uma validação de
formulário ou um guard-clause de template) não sabota nada e falha cedo,
tipicamente com

```
ProvaInvalida: nenhuma guarda declarada; adicione # guarda: caminho.py:linha ao teste
```

porque o marcador `# guarda: caminho:linha` só é reconhecido para arquivos
`.py` ou `.sh`.

## Causa

`ci/provar_guardas.py` define `DIALETOS = {".py": (b"pass  # ",
sintaxe_python), ".sh": (b"# ", sintaxe_shell)}` (linha 63): só existem dois
dialetos de comentário, um por sufixo. A função `mutar` (linha 120) usa esse
dicionário para escolher o prefixo que transforma a linha protegida numa
instrução neutra de uma linha só (`pass  # <linha original>` em Python, `#
<linha original>` em shell). Não há dialeto para `.js`/`.html`, então
qualquer arquivo com esses sufixos nunca entra no fluxo de sabotagem
automática — o script para antes, na leitura do marcador.

## Solução

Para provar um guarda que vive em `.js` ou `.html` (Lei 6, RITOS §4, regra 4
do Padrão de Trabalho): comente manualmente a linha que o guarda protege,
rode o teste correspondente e confirme que ele **reprova**, desfaça a
sabotagem manual e só então commite. O rito continua o mesmo (vermelho
sabotado → verde restaurado); só o instrumento automático não alcança essas
duas linguagens. Isto é adicional ao já documentado em `armadilhas/504`
(alcance restrito a `ci/tests/`, e "pass + comentário" compilando como
instrução simples): aqui o limite é o SUFIXO do arquivo protegido, não o
diretório do teste.

## Origem

Obra Appmax, sessão de coordenação de 27/09/2026, `ci/provar_guardas.py`
linhas 63 e 120; relacionado a `armadilhas/504`.
