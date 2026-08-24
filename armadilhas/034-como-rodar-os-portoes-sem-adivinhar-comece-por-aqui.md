<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.0  ·  referencias antigas "ARMADILHAS §5.0" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.0 Como rodar os portões sem adivinhar (comece por aqui)

Dois comandos, com perguntas **diferentes**:

```bash
python ci/doctor.py     # "este ambiente consegue executar o trabalho?"
python ci/ci.py         # "esta mudanca respeita as invariantes?"
```

`make doctor` / `make ci` na raiz fazem exatamente isso — o Makefile é fachada, a
implementação é o Python. Se `make` faltar numa máquina, os comandos acima continuam
sendo o caminho oficial.

**Leia o estado, não a cor.** Os portões falam quatro palavras ([INV-CI01]):

| Estado | Significa | Exit |
|---|---|---|
| `PASS` | mediu e está correto | 0 |
| `FAIL` | mediu e achou violação — **conserte o código** | 1 |
| `ERROR` | **não conseguiu medir** — conserte o ambiente | 2 |
| `SKIP` | declarado não aplicável, com motivo escrito | 0 |

`ERROR` nunca é "quase passou": é a CI dizendo que não sabe. Se aparecer
`ERROR contrato/<celula>` localmente, quase sempre falta variável de ambiente do §2 —
o detalhe do erro traz o comando, o exit code e o stderr crus.

`python ci/ci.py --apenas freeze,muralhas` roda um subconjunto;
`python ci/ci.py --listar` mostra o que existe.
