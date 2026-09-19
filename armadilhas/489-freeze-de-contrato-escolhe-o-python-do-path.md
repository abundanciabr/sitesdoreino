---
schema_version: 2
armadilha: 489
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/freeze-de-contrato.sh
sinal:
  - "ModuleNotFoundError: No module named 'django'"
guarda:
  tipo: CI
  dono: ci/contract_freeze.py
  detector: exportar_vivo
licao: "ci/freeze-de-contrato.sh varre o PATH (python antes de python3) e usa o primeiro interpretador >= 3.10 que achar, sem checar se tem Django instalado. Em maquina com dois Pythons no PATH, o ERROR e do instrumento, nao do contrato: chame o Python da bancada (venv/services/<celula>) direto por ci/contract_freeze.py <celula>, nunca mexa no contrato so por causa deste ERROR."
---

# `freeze-de-contrato.sh` escolhe o Python do PATH, não o da bancada

**Data:** 18/09/2026 · **Onde:** `ci/freeze-de-contrato.sh`, célula `alunos` ·
**Custo evitado:** investigar um defeito de contrato que não existe

## Sintoma

`bash ci/freeze-de-contrato.sh alunos` devolve ERROR nesta máquina Windows:

```
FREEZE DE CONTRATO

  contrato/alunos  ERROR  exportar contrato vivo de 'alunos': exit code 1

--- ERROR contrato/alunos ---------------------------------------------
Comando:
  C:\Users\davia\AppData\Local\Programs\Python\Python314\python.exe manage.py export_openapi
...
stderr (869 bytes):
  Traceback (most recent call last):
    File "...\services\alunos\manage.py", line 9, in main
      from django.core.management import execute_from_command_line
  ModuleNotFoundError: No module named 'django'
```

## Causa

O wrapper procura `python` antes de `python3` no PATH e aceita o primeiro que
responda `sys.version_info >= (3, 10)`. Nesta máquina o PATH resolve `python`
para o Python 3.14.7 instalado globalmente, que não tem Django nem as
dependências da célula. O Python 3.12 da bancada (o que tem o ambiente da
célula instalado) fica atrás no PATH e nunca é escolhido. O script não erra:
ele acha um Python válido pela definição dele (versão), só que é o
interpretador errado para este repositório.

## Solução

Confirmado nesta sessão: chamando `ci/contract_freeze.py` direto pelo
Python 3.12 da bancada, com as variáveis de ambiente do CI (ver armadilha 483),
o mesmo contrato passa:

```
FREEZE DE CONTRATO

  contrato/alunos   PASS   idêntico ao congelado (1201 linhas comparadas)
  seguranca/alunos  PASS   11 operação(ões) com autenticação conferida na fonte

RESULTADO  PASS
```

Quando `freeze-de-contrato.sh` der `ModuleNotFoundError: No module named
'django'`, não mexa no contrato nem no código da célula: é ERROR de
instrumento. Rode `python ci/contract_freeze.py <celula>` apontando
explicitamente para o Python que tem o ambiente da célula instalado (o da
bancada, não o primeiro do PATH), com as variáveis de ambiente do CI
exportadas.

## O que NÃO é a causa

Não é o contrato ter divergido, não é a célula `alunos` estar quebrada, e não
é o `ci/contract_freeze.py` estar com bug: a lógica de comparação passou
100% quando alimentada com o interpretador certo. O defeito é só a seleção de
interpretador em máquina com mais de um Python no PATH.
