# Célula que vira `freeze: required` em PR de `contracts/` só quebra no PRÓXIMO PR dela: `contrato/<celula> ERROR — No module named 'yaml'`

**Sintoma:** um PR normal da célula — testes verdes no runner, `214 passed` —
morre no último degrau do `make ci` com um erro que o local não reproduz:

```
  contrato/sugestoes  ERROR  PyYAML indisponível
--- ERROR contrato/sugestoes ------------------------------------------
No module named 'yaml'
make: *** [Makefile:28: contrato-check] Error 2
```

Local fica **verde**: a máquina de quem desenvolve tem PyYAML global, e o
freeze o encontra por acidente. Medido no PR #146 (25/08/2026) — o primeiro PR
da `sugestoes` depois de o contrato dela congelar.

**Causa:** o Rito de Contrato (RITOS §3) introduz o freeze num PR que toca só
`contracts/` + `ci/` — **nenhum arquivo de `services/`** — então o `ci-celula`
daquele PR nem roda (não há célula detectada). O manifesto passa a exigir o
freeze, mas o `requirements.txt` da célula nunca foi cobrado: a primeira vez
que o runner instala as dependências DELA e roda `make contrato-check` é o
primeiro PR seguinte que toque a célula — dias depois, num despacho que não
tem nada a ver com contrato. O portão está certo em reprovar (dependência
ausente NÃO é validação bem-sucedida, INV-CI01); o que está atrasado é a
dependência.

**Solução:** `PyYAML==6.0.2` (a versão pinada nas outras células `required`)
no `requirements.txt` da célula — **no mesmo dia em que o manifesto dela vira
`required`**, mesmo que o PR de contrato não possa tocar `services/`: é um PR
de célula de uma linha, imediatamente atrás do PR de contrato. A `identidade`
recebeu o dela assim (PR #147), antes de o sintoma aparecer.

**Como conferir se alguma célula está nesse limbo agora:**

```bash
python - <<'EOF'
import json, pathlib
m = json.load(open("ci/manifesto-de-contratos.json", encoding="utf-8"))
for celula, cfg in m["celulas"].items():
    if cfg.get("freeze") == "required":
        req = pathlib.Path(f"services/{celula}/requirements.txt").read_text(encoding="utf-8")
        if "PyYAML" not in req and "pyyaml" not in req:
            print("SEM PyYAML:", celula)
EOF
```

**Origem:** PR #146 (`sugestoes/usar-login-do-site`), 25/08/2026.
