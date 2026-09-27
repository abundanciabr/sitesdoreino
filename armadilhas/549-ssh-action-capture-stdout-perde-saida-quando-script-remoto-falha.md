---
schema_version: 2
armadilha: 549
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - .github/workflows/
sinal:
  - "Matching delimiter not found 'EOF'"
guarda:
  tipo: nenhum
  motivo: "ci/operacoes_vps.py::preparar so gera o script deste workflow especifico; nao existe portao que varra todo .github/workflows/ e reprove um appleboy/ssh-action com capture_stdout sem o padrao || true + JSON, e criar esse varredor e mudanca de codigo, fora do alcance de uma entrada de licao (a tarefa 893 cobre os 14 workflows restantes)"
licao: "appleboy/ssh-action com capture_stdout: true delimita a saida com heredoc EOF; sob bash -e -o pipefail, se o script remoto sai != 0, o 'echo EOF' final nao roda e o GitHub descarta a saida com 'Matching delimiter not found'. Faça o script sempre sair 0 (|| true + JSON de veredito) e leia o resultado num passo com if: always()."
---

# 549: `appleboy/ssh-action` com `capture_stdout: true` descarta a saída quando o script remoto falha

**Data:** 27/09/2026 · **Onde:** `.github/workflows/`, PRs #2249 e #2264,
obra Appmax · **Custo evitado:** perder toda a evidência de uma operação da
VPS bem no caso em que ela mais importa — quando algo deu errado — e
diagnosticar às cegas.

## Sintoma

Um passo `appleboy/ssh-action@v1` com `capture_stdout: true` cujo script
remoto termina com código diferente de zero produz, no log da Action:

```
Error: Matching delimiter not found 'EOF'
```

e `steps.<id>.outputs.stdout` fica vazio, mesmo o script remoto tendo
impresso a saída esperada antes de falhar.

## Causa

`capture_stdout: true` funciona escrevendo a saída do comando remoto entre
marcadores (`... <<'EOF' ... EOF`) que a Action depois recorta. O runner
GitHub Actions executa o `script_path` sob `bash -e -o pipefail` por
padrão: se qualquer comando do script sai com código não-zero, o `bash`
aborta imediatamente, e o `echo 'EOF'` de fechamento — que viria DEPOIS do
comando que falhou — nunca chega a rodar. Sem o delimitador de fechamento,
a Action não consegue recortar a saída e a descarta, reportando o erro de
delimitador em vez do conteúdo real.

## Solução

Nunca deixe o script remoto sair diferente de zero quando o objetivo é
capturar e interpretar a saída depois:

1. Encerre o script remoto sempre com sucesso (`|| true` na última etapa
   que poderia falhar), e imprima um JSON de veredito como última linha
   (sucesso, falha e motivo ficam **dentro** do JSON, não no código de
   saída do processo).
2. Leia esse JSON num passo separado do workflow, com `if: always() &&
   steps.<id-do-ssh-action>.outcome != 'skipped'`, nunca decidindo pelo
   `outcome` do próprio passo `ssh-action` (que também pode falhar por
   timeout de rede, não só pelo script).

O padrão já corrigido está em `.github/workflows/operacoes-vps.yml`
(`ci/operacoes_vps.py`, que gera o script terminando em `|| true` e cujo
passo de leitura roda com `if: always() && steps.remoto.outcome !=
'skipped'`). Os 14 workflows fora da obra Appmax que ainda usam
`appleboy/ssh-action` com `capture_stdout: true` sem esse padrão estão na
tarefa 893 — não console-los aqui.

## Origem

PRs #2249 e #2264, obra Appmax, sessões de coordenação de 27/09/2026;
`.github/workflows/operacoes-vps.yml`, `ci/operacoes_vps.py`.
