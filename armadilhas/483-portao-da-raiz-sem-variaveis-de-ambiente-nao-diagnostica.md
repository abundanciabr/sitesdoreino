---
schema_version: 2
armadilha: 483
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/ci.py
  - ci/contract_freeze.py
sinal:
  - "exportar contrato vivo de"
guarda:
  tipo: CI
  dono: ci/contract_freeze.py
  detector: exportar_vivo
licao: Portão da raiz sem as variáveis de ambiente não diagnostica o repositório: toda célula com contrato vira ERROR e as verificações de segurança nem chegam a aparecer na tabela. Exporte PYTHONUTF8, DJANGO_SECRET_KEY, DATABASE_URL, REDIS_STREAMS_URL e HUEY_REDIS_URL (os valores estão em .github/workflows/ci-celula.yml) antes de concluir qualquer coisa sobre a saúde da main.
---

# Portão da raiz sem as variáveis de ambiente mente sobre a saúde do repositório

As células têm fail-hard deliberado em `config/settings.py` (INV-P10): variável
obrigatória ausente derruba o `django.setup()`. O exportador de contrato roda
dentro da célula, então ele morre antes de exportar, e o portão devolve ERROR.
Um ERROR por célula.

Medido no worktree limpo, revisão 1848ec1d, com `python ci/ci.py --apenas freeze`:

- sem variável nenhuma: 16 ERROR e 2 SKIP, e nenhuma linha `seguranca/*`;
- com o bloco abaixo: 22 PASS, 4 FAIL, 3 ERROR e 2 SKIP.

```bash
PYTHONUTF8=1 \
DJANGO_SECRET_KEY=ci-apenas-nunca-em-producao \
DATABASE_URL=postgres://ci:ci@localhost:5432/ci_db \
REDIS_STREAMS_URL=redis://localhost:6379/0 \
HUEY_REDIS_URL=redis://localhost:6379/1 \
python ci/ci.py --apenas freeze
```

Repare no que muda além da contagem: sem as variáveis, as verificações de
`seguranca/*` não reprovam, elas somem da tabela, porque o portão nem chega a
medi-las. A tabela curta parece uma tabela inteira.

O ERROR do portão já diz o conserto no detalhe (`ci/contract_freeze.py`, no
`except ErroDeInstrumentacao` de `exportar_vivo`), e isso está certo. O
problema é que dezesseis ERROR de uma vez PARECEM dívida do repositório, e
nesta casa um agente já os classificou assim por escrito. Conclusão errada
sobre a saúde da main manda gente consertar o que não está quebrado.

Os valores acima não são invenção: são os que `.github/workflows/ci-celula.yml`
declara. A célula `pagamentos` pede ainda `MP_ACCESS_TOKEN` e
`MP_WEBHOOK_SECRET`, e o mesmo arquivo tem os falsos que o CI usa.
