---
schema_version: 2
armadilha: 389
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: baixo
gatilho:
  - "contracts/*.openapi.yaml"
licao: o congelado se monta do export, e o serializador se PROVA reconstruindo o congelado atual byte a byte antes de escrever o novo. `yaml.safe_dump(doc, sort_keys=False)`, com os dois padroes do PyYAML intactos.
guarda:
  tipo: nenhum
  motivo: e conhecimento de como executar um rito manual raro (o Rito de Contrato), nao regra que uma maquina possa vigiar sozinha; o que evita a queda e a prova de ida e volta, e ela mora no proprio gesto
sinal:
  - "METODO NAO BATE"
  - "title: Cursos . API interna"
---

# Montar o congelado a partir do export exige PROVAR o serializador antes, e o PyYAML tem dois padrões que ninguém lembra

**Data:** 07/09/2026 · **Onde:** todo Rito de Contrato (RITOS.md §3) de célula que
já tem contrato congelado · **Custo evitado:** um PR de contrato com diferença
falsa de centenas de linhas, ou pior, um congelado que passa no freeze e não é
o arquivo que a casa vinha guardando

## Sintoma

A `armadilhas/243` manda montar o contrato do Rito **a partir do documento
exportado**, nunca de cabeça. Você obedece: roda `manage.py export_openapi`,
converte o JSON para YAML, preserva o cabeçalho de comentários e escreve o
arquivo. O `contract_freeze` até passa, porque as duas pontas saem do mesmo
lugar.

Mas o `git diff` do seu PR de contrato mostra **o arquivo inteiro reescrito**,
não a operação nova. E lendo de perto:

```diff
-  title: "Cursos — API interna"
+  title: Cursos — API interna
-      description: 'A lista que o editor usa para escolher o instrumento cabivel de
-        uma
+      description: 'A lista que o editor usa para escolher o instrumento cabivel de uma
```

Nada disso é decisão de ninguém. É o serializador com outros padrões.

## Causa

`yaml.safe_dump` tem dois padrões que mudam o arquivo inteiro e que a mão
costuma "melhorar" sem pensar:

1. **`allow_unicode=False`** (o padrão). O congelado guarda `—` como
   `—`, escapado. Ligar `allow_unicode=True` parece uma gentileza e
   reescreve toda linha com acento ou travessão.
2. **`width=80`** (o padrão). É essa largura que quebra as descrições longas em
   várias linhas. Passar `width=10**9` junta cada descrição numa linha só e
   reescreve todo bloco de prosa do contrato.

`sort_keys=False` é a única que precisa ser dita, porque o padrão é `True` e
ordenaria `components` antes de `info`, embaralhando o documento.

O freeze não pega nada disso: ele normaliza os dois lados pelo MESMO
normalizador antes de comparar, então um arquivo com a serialização "errada"
passa igual. Quem paga é a leitura humana do diff, e a próxima pessoa que tentar
comparar duas versões do contrato.

## Solução

**Prove o serializador antes de usá-lo, com uma volta completa: o congelado
ATUAL, lido e reescrito, tem de sair byte a byte igual a ele mesmo.** Se não
sair, o método está errado e o resto do Rito não vale.

```bash
cd <bancada> && python -c "import yaml; t=open('contracts/<celula>.openapi.yaml',encoding='utf-8').read(); c=''.join(t.splitlines(True)[:N]); b=t[len(c):]; print('reconstroi identico?', yaml.safe_dump(yaml.safe_load(b), sort_keys=False)==b)"
```

`N` é a contagem de linhas do cabeçalho de comentários, que se mede assim:

```bash
git show origin/main:contracts/<celula>.openapi.yaml | awk '/^[^#]/{print NR-1; exit}'
```

Com `reconstroi identico? True` na mão, e só então, troque o corpo pelo export
do código e **preserve o cabeçalho de comentários byte a byte** — ele é escrito
para gente e não sai de exportador nenhum.

Confira o que mudou em OPERAÇÕES, não em linhas: o diff de linhas engana, o
conjunto de `operationId` não.

```
NASCERAM: ['checkLesson']
SUMIRAM : []
```

## O que NÃO fazer

Escrever o congelado a partir do diff que o freeze imprime. O freeze mostra o
documento NORMALIZADO, que não é o formato do arquivo: colar aquilo produz um
arquivo que passa no freeze e não se parece com nenhum outro contrato da casa.

## Origem

Rito de Contrato do `checkLesson` (degrau 3.1 da sala de aula, TAR-245,
PR do contrato #1324 e PR do código #1276). A primeira tentativa usou
`allow_unicode=True` e `width=10**9`, e a prova de ida e volta reprovou antes de
qualquer arquivo ser tocado: `METODO NAO BATE`, com as primeiras 40 linhas da
diferença na tela. Relacionadas: `armadilhas/243` (a ordem dos dois PRs) e
`armadilhas/324` (a prosa da porta também vira pedra).
