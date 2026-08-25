# O log da ssh-action ecoa o `script:` inteiro — e você lê o eco como se fosse a saída da execução

**Sintoma:** um run do `deploy-celula` (ou `deploy-infra`) falha, você filtra o
log atrás do erro, e encontra **exatamente a mensagem que esperava**:

```bash
gh run view <id> --log-failed | grep -iE "ERRO|error"
```
```
deploy (admin)  Ativar na VPS ...  echo "ERRO: '$CELULA' não tem serviço algum em /opt/plataforma/docker-compose.yml."
deploy (admin)  Ativar na VPS ...  echo "Abortado de propósito: 'up -d' sem argumento subiria a plataforma inteira."
```

Diagnóstico fechado, causa conhecida, é só seguir a receita da armadilha
correspondente. **E está errado:** o run falhou por outro motivo, e o que você
leu nem chegou a ser executado.

Repare no que denuncia, e é sutil — a linha começa com `echo "`. Você leu o
**código-fonte do script**, não a saída dele.

**Causa:** a `appleboy/ssh-action` imprime todos os seus inputs no bloco de
setup do step, e o `script:` é um deles — o shell inteiro, linha por linha,
antes de qualquer coisa rodar. Um `grep` por "ERRO" acha as linhas de `echo`
que **produziriam** aquela mensagem, com o mesmo texto que a execução real
imprimiria.

As duas se distinguem por duas marcas:

| | Eco dos parâmetros (setup) | Saída de verdade |
|---|---|---|
| Prefixo | `  echo "ERRO: …` (indentado, com `echo`) | `2026-08-25T19:51:14.9145774Z ERRO: …` |
| Timestamp | **não tem** | tem, com data-hora ISO |
| Posição | antes de `##[endgroup]` / `Drone SSH version` | depois |

No caso real, a falha verdadeira estava **três linhas depois do fim do eco**,
e era outra coisa completamente:

```
2026/08/25 19:51:14 dial tcp ***:22: i/o timeout
```

— ou seja, `armadilhas/017` (rede/SSH), que se resolve com `gh run rerun`, e
não `armadilhas/088` (compose sem a célula), que exigiria um PR de infra. O
diagnóstico errado mandaria alguém investigar o compose de uma VPS onde o
serviço já estava declarado e no ar.

**Solução:**

1. **Filtre por linhas com timestamp**, não por texto solto. O timestamp ISO no
   começo é o que separa execução de eco:
   ```bash
   gh run view <id> --log-failed | grep -E "[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z" | grep -iE "erro|error"
   ```
2. **Leia o FIM do step, não o resultado do grep.** A causa real de um step que
   morre é quase sempre a última linha antes do `##[error]`:
   ```bash
   gh run view <id> --log-failed | tail -20
   ```
3. **Desconfie quando o erro encontrado casa perfeito demais** com a hipótese
   que você já tinha. Foi exatamente assim que este caso quase passou: a
   armadilha 088 estava fresca na cabeça, a mensagem bateu palavra por palavra,
   e a conclusão saiu pronta. **Confirmação boa demais merece um segundo olhar
   no log cru** — a mesma disciplina da `armadilhas/045` (veredito nunca vem de
   pipe) aplicada à leitura, não à execução.

**De quebra, o que este caso ensina sobre o próprio `--log-failed`:** ele
devolve o step inteiro, **incluindo o setup**. Não é um filtro de "o que deu
errado"; é "o step que terminou mal, do começo ao fim".

**Origem:** PR 2b da área administrativa, 25/08/2026. Depois do `deploy-infra`
verde e do `/admin/healthz` respondendo 200 em produção, o rerun do
`deploy-celula` falhou; o `grep` por "ERRO" devolveu a mensagem da
`armadilhas/088`, e a conclusão natural — "o compose ainda não conhece a
célula" — contradizia a medição de fora que acabara de provar o contrário. Foi
a contradição entre as duas evidências que forçou a leitura do log cru, onde o
`i/o timeout` estava. Um `rerun` resolveu.
