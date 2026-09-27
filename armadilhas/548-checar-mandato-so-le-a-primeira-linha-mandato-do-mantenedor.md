---
schema_version: 2
armadilha: 548
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/mergear.py
sinal:
  - "o mandato do dono não alcança"
guarda:
  tipo: nenhum
  motivo: "trocar re.search por um leitor que junta todas as linhas Mandato-do-mantenedor: do corpo e escolhe a que cobre cada caminho e mudanca de codigo em ci/mergear.py, fora do alcance de uma entrada de licao"
licao: "checar_mandato acha Mandato-do-mantenedor: com re.search, que devolve so a PRIMEIRA ocorrencia do corpo, e usa essa UNICA linha para validar TODOS os caminhos do PR. Corpo com duas linhas (uma para contracts/, outra para ci/) so tem a primeira lida; se a de contracts/ vier depois, reprova com 'o mandato nao alcanca'. Escreva a linha do caminho mais restrito PRIMEIRO."
---

# 548: `checar_mandato` só lê a primeira linha `Mandato-do-mantenedor:`, mesmo havendo mais de uma

**Data:** 27/09/2026 · **Onde:** `ci/mergear.py::checar_mandato`, PR #2242,
obra Appmax · **Custo evitado:** PR reprovado por "mandato não alcança" um
caminho, achando que falta pedir autorização, quando ela já está escrita
mais abaixo no mesmo corpo.

## Sintoma

```
FAIL mandato do mantenedor: o mandato do dono não alcança contracts/...
```

O PR #2242 tinha, no corpo, duas linhas `Mandato-do-mantenedor:` — uma
cobrindo caminhos de `ci/` e outra cobrindo `contracts/`. A linha de
`contracts/` vinha depois da linha de `ci/`. O portão reprovou como se
nenhuma autorização cobrisse `contracts/`, mesmo ela existindo no corpo.

## Causa

`ci/mergear.py::checar_mandato` lê o mandato assim:

```python
mandato = re.search(
    r"^Mandato-do-mantenedor: (.{20,})$", pr.get("body") or "", re.MULTILINE
)
```

`re.search` devolve só a **primeira** ocorrência do padrão no corpo inteiro,
não uma lista. Essa única variável `mandato` é reutilizada dentro do laço
`for arquivo in pr.get("files")`, para cada caminho tocado, testando se
`padrao` ou `caminho` está em `mandato.group(1).split()`. Se a autorização
para um caminho está numa SEGUNDA linha `Mandato-do-mantenedor:`, ela nunca
é lida: o portão sempre compara contra a primeira linha encontrada, seja
qual for o caminho em questão. Isto é distinto do `armadilhas/510` (que
documenta a mesma linha cortada em várias linhas físicas por falta de
`re.DOTALL`): aqui há DUAS linhas `Mandato-do-mantenedor:` válidas e
completas, e a ordem entre elas decide qual é lida.

## Solução

Quando o PR toca caminhos que exigem autorizações distintas (por exemplo,
`contracts/` e `ci/` com mandatos diferentes), escreva no corpo a linha que
cobre o caminho **mais restrito primeiro** — hoje o portão só enxerga uma
linha `Mandato-do-mantenedor:` por PR, a primeira do corpo. Confirme com

```bash
python ci/mandato_por_faixa.py --arquivos <arquivos do PR> --faixa <faixa> --corpo-arquivo <corpo>
```

antes de `gh pr edit`, e se o portão ainda recusar por "não alcança", reveja
a ORDEM das linhas antes de reescrever o conteúdo delas.

## Origem

PR #2242, obra Appmax, sessão de coordenação de 27/09/2026;
`ci/mergear.py::checar_mandato`; relacionado a `armadilhas/510`.
