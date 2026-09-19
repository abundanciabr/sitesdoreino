---
schema_version: 2
armadilha: 394
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: baixo
gatilho:
  - "services/*/apps/*/templates/**/*.html"
licao: a frase que um teste procura no HTML fica INTEIRA numa linha do template; quebrada em duas, ela some do `assert "..." in corpo` sem erro nenhum, e o teste que devia proteger a tela protege uma frase que ninguem le
guarda:
  tipo: nenhum
  motivo: nenhum portao sabe quais frases os testes procuram; a regra e de escrita do template e do teste, e vale quando os dois nascem juntos
sinal:
  - "assert '[^']*' in '<!doctype"
---

# A frase-chave quebrada em duas linhas do template some do `assert` e o teste fica verde pelo motivo errado

**Data:** 07/09/2026 · **Onde:** qualquer teste que confira texto no HTML
renderizado pelo `Client` do Django (a sala de aula, o admin, o fórum)
· **Custo evitado:** um teste verde que não protege a frase, ou vermelho
sem defeito nenhum na tela

## Sintoma

O template diz, quebrado para caber em 80 colunas:

```html
<p class="erro">Você entrou na escola, mas não encontramos uma matrícula
  ativa no seu nome.</p>
```

E o teste procura a frase inteira:

```
assert "não encontramos uma matrícula ativa no seu nome" in corpo
E   AssertionError: assert '...' in '<!doctype html>...'
```

Vermelho. O HTML tem a frase, mas com uma quebra de linha e dois espaços de
indentação no meio de "matrícula ativa". O contrário também acontece: o robô
"conserta" o teste procurando só "não encontramos uma matrícula", que também
está em outra tela, e o teste passa a ficar verde com a frase errada.

## Causa

O motor de templates não junta linhas: o que está no arquivo sai no HTML,
quebra e indentação inclusas. O navegador junta espaços na hora de mostrar,
e por isso a tela parece certa; o `assert` compara o texto cru.

## Solução

A frase que algum teste procura fica INTEIRA numa linha do template, mesmo que
a linha passe de 80 colunas. Quebre ANTES ou DEPOIS da frase, nunca dentro. No
teste, procure a frase inteira, distinta o bastante para não casar com outra
tela, e declare a constante no topo do arquivo de teste (`A_FRASE_SEM_SALA =
"..."`) para o template e o teste envelhecerem juntos.
