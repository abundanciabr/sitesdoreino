# `make ci` da raiz devolve ERROR com `ModuleNotFoundError: No module named 'huey'`

**Sintoma:** `python ci/ci.py` (ou `make ci`) na raiz devolve `RESULTADO ERROR` —
não FAIL — e o rodapé diz "O exportador não rodou, então a CI NÃO comparou os
contratos". No meio do traceback recortado aparece `KeyError: 'export_openapi'`,
que é uma pista falsa: o comando de management existe. A causa real só aparece
rodando o exportador na mão, dentro da célula:
`cd services/checkout && python manage.py export_openapi` →
`File "config/huey.py", line 9, in <module> from huey import RedisHuey` /
`ModuleNotFoundError: No module named 'huey'`.
**Causa:** o portão `freeze` roda o `export_openapi` de **cada uma das 8 células**
com o Python que invocou o `ci.py` — o global da máquina, não um venv por célula.
`checkout`, `mensageria` e `quiz` importam `config/huey.py` já no `settings.py`, então
para elas o freeze precisa do `huey` instalado onde o `ci.py` está rodando. O Django
engole o `ImportError` do settings e reporta `KeyError: 'export_openapi'` (não
encontrou o comando porque não conseguiu carregar `INSTALLED_APPS`) — é por isso que
o sintoma visível aponta para o lugar errado.
**Solução:** instale a versão **pinada** no `requirements.txt` das células, nunca a
mais nova:

```bash
python -m pip install "huey==2.5.1"   # a mesma de services/{checkout,mensageria,quiz}
```

Vale a regra geral: se o `make ci` da raiz devolver ERROR com um `ModuleNotFoundError`
de biblioteca de célula, o que falta é a dependência **no Python que roda o `ci.py`**
— e a correção é instalar a versão pinada, porque instalar a mais nova troca um ERROR
por uma divergência silenciosa entre o local e o CI (§3.5).
**Não confunda com FAIL:** ERROR aqui é ambiente, não código. Não saia mexendo em
`services/` por causa dele (§5.0).
**Origem:** despacho docs/armadilhas-particionado (23/08/2026) — o baseline do RITOS §1
reprovou assim numa máquina onde `make ci` nunca tinha sido rodado da raiz.
