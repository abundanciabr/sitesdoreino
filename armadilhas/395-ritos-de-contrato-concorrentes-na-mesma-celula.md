---
schema_version: 2
armadilha: 395
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: baixo
gatilho:
  - "contracts/*.openapi.yaml"
licao: o serializador que reconstroi o congelado e o que REPRODUZ o arquivo de hoje (descubra por busca: allow_unicode e width), nao o dos padroes do PyYAML; e quando outro Rito da mesma celula pousou entre o export do robo e o seu PR, o congelado novo nasce por EMENDA sobre o congelado atual (a operacao e os esquemas vindos do export, a prosa fundida), nunca pela troca do arquivo inteiro pelo export.
guarda:
  tipo: nenhum
  motivo: e conhecimento de como conduzir um rito manual num dia de varias sessoes na mesma celula; o que evita a queda e a prova de ida e volta com busca de parametros e o diff por operacao, e os dois moram no proprio gesto
sinal:
  - "METODO NAO BATE"
  - "BATE: allow_unicode=True width="
  - "ops antigo: 13 . atual: 17 . export: 13"
---

# Ritos de Contrato concorrentes na mesma célula: o serializador do congelado é o que reproduz o arquivo de hoje, e o congelado novo nasce por emenda

**Data:** 07/09/2026 · **Onde:** todo Rito de Contrato (RITOS.md §3) numa
célula em que mais de uma sessão está trabalhando no mesmo dia · **Custo
evitado:** um PR de contrato que APAGA as operações do Rito anterior (o portão
aditivo reprova), ou um congelado com o arquivo inteiro reescrito

## Sintoma

Você segue a `armadilhas/389` à risca: prova o serializador reconstruindo o
congelado byte a byte, com `yaml.safe_dump(doc, sort_keys=False)` e os padrões
do PyYAML. De manhã a prova passa (`reconstroi identico? True`). À tarde, na
bancada nova, ela reprova:

```
AssertionError: METODO NAO BATE
-  title: Cursos — API interna
+  title: "Cursos — API interna"
```

E o export do robô, gerado do ramo dele, tem TREZE operações, enquanto o
congelado da `main` já tem DEZESSETE:

```
ops antigo: 13 · atual: 17 · export: 13
atual - antigo: ['createCourse', 'listCourses', 'putCourse', 'putCourseStructure']
```

Nada disso é defeito seu. Entre o export e o seu PR, OUTRA sessão fez um Rito na
mesma célula (aqui, o dos vários cursos, commit `782268cf`, e depois a emenda
`#1359`), e escreveu o congelado com outros padrões de serialização.

## Causa

Duas coisas, e as duas vêm de haver mais de uma sessão na mesma célula:

1. **O serializador do congelado não é fixo.** Quem escreveu o arquivo por
   último escolheu `allow_unicode=True` e uma largura maior. A `389` ensinou os
   padrões porque o arquivo de ontem foi escrito com eles; o de hoje não foi.
   O que a `389` manda de verdade é a PROVA de ida e volta, e a prova continua
   valendo: o que muda é que os parâmetros precisam ser DESCOBERTOS, não
   presumidos.
2. **O export do robô envelhece.** O ramo do robô nasceu da `main` de antes do
   outro Rito; o export dele não conhece as operações novas. Trocar o arquivo
   inteiro pelo export apagaria essas operações, e o portão `contrato_aditivo`
   reprovaria (com razão).

## Solução

**Descubra o serializador por busca, e só então use-o:**

```python
for au in (False, True):
    for w in (80, 88, 100, 120, 200, 10**9):
        if yaml.safe_dump(doc, sort_keys=False, allow_unicode=au, width=w) == corpo:
            print("BATE: allow_unicode=%s width=%s" % (au, w))
```

Se mais de uma largura bate, use a menor: é a que mais se parece com o que
quem escreveu quis.

**Monte o congelado novo por EMENDA sobre o congelado ATUAL da `main`:**

- a operação que o seu degrau muda vem inteira do export do robô
  (aqui, `checkLesson` com o parâmetro `modo`);
- os esquemas que só existem no export entram; esquema existente que o export
  mudou é sinal de que o robô mexeu onde não devia, e para;
- a prosa (`info.description`, `armadilhas/324`) é a da `main` COM as emendas do
  seu degrau aplicadas por cima, nunca a do export inteira. Guarde o texto
  fundido num arquivo: é ele que o `config/api.py` do PR do código precisa
  produzir, palavra por palavra.

**Confira por operação, não por linha:** `NASCERAM`, `SUMIRAM`, e os parâmetros
da operação tocada antes e depois. Depois, no PR do código, rebaseie sobre a
`main`, exporte de novo e compare as três partes com o congelado (a operação,
o esquema, a prosa). O que sobrar de diferença tem de ser SÓ o que pertence ao
outro Rito e ainda não pousou.

**A pista rebaseia o PR de contrato sozinha** quando o outro Rito toca regiões
diferentes do mesmo arquivo (foi o caso: `putCourseStructure` de um lado,
`checkLesson` do outro). Não peça pouso de novo nem force nada: leia o
comentário dela no PR.

## Origem

Rito de Contrato do Guardião de fidelidade (degrau 3.2 da sala de aula,
TAR-246, contrato PR #1360, código PR #1357), no mesmo dia em que outra sessão
conduziu o Rito dos vários cursos (#1349, contrato `782268cf`, emenda #1359) na
mesma célula. Relacionadas: `armadilhas/243` (a ordem dos dois PRs), `389` (a
prova do serializador), `324` (a prosa vira pedra), `365` (as duas diferenças
invisíveis do export).
