---
schema_version: 2
armadilha: 522
estado: documentada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: o veredito de ci/esperar.py --deploy e do RUN inteiro, nao por job; distinguir "celula verde, SSH ruim" de uma falha real de deploy exige ler o log do job publicar-dados-admin, que e leitura, nao maquina.
sinal:
  - "publicar-dados-admin.*i/o timeout"
gatilho:
  - ci/esperar.py
licao: "ci/esperar.py --deploy reprova o commit inteiro quando o job publicar-dados-admin cai por timeout de SSH, mesmo que o deploy da propria celula (funil, admin) tenha saido verde. O veredito e do workflow deploy-celula como um todo; confira o job publicar-dados-admin em separado antes de tratar REJEITADO como falha da celula."
---

# 522: `ci/esperar.py --deploy` reprova por timeout de SSH em `publicar-dados-admin`, mesmo com a célula verde

## Sintoma

`python ci/esperar.py --deploy <SHA>` voltou REJEITADO num commit cujo
deploy da célula (funil, admin) havia saído verde nos logs do próprio job.
O log do job `publicar-dados-admin` mostrava algo como

```
dial tcp <host>:22: i/o timeout
```

## Causa

`ci/esperar.py --deploy` lê o veredito do workflow `deploy-celula` como um
todo, e esse workflow tem um job separado, `publicar-dados-admin`, que abre
uma conexão SSH para publicar dados administrativos. Quando essa conexão
expira (rede instável do runner, VPS momentaneamente inacessível), o job
falha e o run inteiro fica vermelho, ainda que os jobs de deploy da célula em
si (funil, admin) tenham terminado com sucesso.

## Solução

Um `REJEITADO` de `ci/esperar.py --deploy` não é automaticamente "a célula
não subiu". Antes de tratar como falha de deploy:

```bash
gh run view <run-id> --log-failed -R <repo> | grep -A5 publicar-dados-admin
```

Se o log mostrar timeout de SSH e os demais jobs (deploy da célula) estiverem
verdes, a causa é a conexão, não o código: reexecute o job
(`gh run rerun <run-id> --job <id>`) em vez de investigar a célula.

## Evidência

Sistema de experimentos, 26 e 27/09/2026: runs de `deploy-celula` com
`publicar-dados-admin` vermelho por timeout de SSH enquanto os demais jobs de
deploy da célula terminaram verdes, relatado pela sessão que fechou o
sistema de experimentos.
