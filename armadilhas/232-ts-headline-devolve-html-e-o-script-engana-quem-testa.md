---
schema_version: 2
armadilha: 232
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: services/forum/tests/test_busca.py
sinal:
  - `SearchHeadline`
  - `ts_headline`
---

# `ts_headline` devolve HTML sem escapar, e `<script>` é justamente a carga que NÃO prova nada

**Sintoma.** Uma tela de busca com destaque (`SearchHeadline`, o `ts_headline`
do PostgreSQL) precisa imprimir o trecho como HTML — os marcadores só viram
grifo se o navegador os interpretar. Você escreve o teste de segurança óbvio:

```python
falar(texto="<script>alert('roubei')</script> como faço a textura?")
assert "<script>alert" not in pagina      # ✅ passa
```

O teste passa **mesmo com `|safe` no trecho cru, sem escape nenhum**. E aí a
tela vai para produção parecendo provada.

**Causa, medida contra PostgreSQL 17 e não suposta:** o parser do `ts_headline`
reconhece `<script>...</script>` como *tag* e a **descarta** do resultado. Mas
ele não é um sanitizador, e não pretende ser — o que ele não reconhece como tag
válida passa inteiro:

| texto da mensagem | o que o `ts_headline` devolve |
|---|---|
| `<script>alert('x')</script> ... textura` | ` alert('x')  ... [[hl]]textura[[/hl]]` — **tag removida** |
| `textura <img src=x onerror=alert(1)> fim` | `[[hl]]textura[[/hl]] <img src=x onerror=alert(1)> fim` — **passa inteiro** |
| `na textura o valor 3 < 5 > 1` | `na [[hl]]textura[[/hl]] o valor 3 < 5 > 1` — passa |
| `textura & companhia` | `[[hl]]textura[[/hl]] & companhia` — passa |

Ou seja: `<img src=x onerror=...>` é XSS armazenado servido a **quem buscar a
palavra** — e o teste com `<script>` teria dito que estava tudo bem.

**Solução, e ela é uma ORDEM antes de ser um código:**

```python
ABRE, FECHA = "[[hl]]", "[[/hl]]"      # marcadores que NÃO são HTML

def _trecho_seguro(bruto: str) -> str:
    # 1º escapar: tudo que veio da mensagem deixa de ser HTML
    # 2º trocar: os marcadores, que são NOSSOS, viram as únicas tags da string
    return mark_safe(
        escape(bruto).replace(escape(ABRE), "<mark>").replace(escape(FECHA), "</mark>")
    )
```

Inverter as duas linhas publica o texto do aluno como HTML. E os marcadores
**não podem ser `<b>`/`<mark>`**: se forem, o escape os mata junto com o resto e
não sobra destaque nenhum — o que empurra quem estiver com pressa de volta para
o `|safe` no cru.

Quem escrever `[[hl]]` dentro da própria mensagem consegue, no máximo, um grifo
a mais: depois do escape, o único texto que ainda pode virar tag é o marcador, e
ele só sabe virar `<mark>`.

**A regra que fica, e vale além da busca:** ao testar escape, **escolha a carga
por medição, não por fama.** `<script>` é a carga mais conhecida e, aqui, a
única que o caminho já limpava sozinho — ela mede o PostgreSQL, não o seu
código. A prova boa é a que falha quando você tira o conserto.

**Origem.** 30/08/2026, TAR-046 (a tela de busca do fórum, PR #651). A primeira
versão do teste usava `<script>` e passava; a medição do que o `ts_headline`
realmente devolve mostrou que ela teria passado sem escape nenhum.
