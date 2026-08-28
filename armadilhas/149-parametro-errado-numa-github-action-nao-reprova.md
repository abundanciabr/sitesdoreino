# Parâmetro com nome errado numa GitHub Action não reprova — ela avisa e IGNORA

**Sintoma:** o deploy fecha **verde** e a imagem nova **não sobe**. O site
continua no ar servindo a versão anterior, sem erro em lugar nenhum: o workflow
verde, os testes verdes, o merge verde. Você só descobre quando repara que uma
mudança que "já entrou" não está em produção.

No log do passo, quase no topo e fácil de passar batido, existe isto:

```
##[warning]Unexpected input(s) 'script_file', valid inputs are ['host', 'port',
… 'script', 'script_path', 'envs', … ]
```

E logo abaixo, o passo seguinte anunciando sucesso.

**Causa:** GitHub Actions **não valida** os `with:` de uma ação de forma fatal.
Nome que a ação não conhece vira `##[warning]` e é descartado. Com
`appleboy/ssh-action`, o efeito é o pior possível: sem `script` nem
`script_path`, ela abre a conexão SSH, **não executa nada**, e sai com código 0.
Conectar passou por entregar.

O nome certo é `script_path`. `script_file` não existe — e é um chute plausível,
porque o dump de variáveis do próprio runner mostra `INPUT_SCRIPT_FILE:` (ele
imprime todo `INPUT_*` do ambiente, inclusive os inválidos). Ler aquele dump como
lista de parâmetros suportados é a armadilha dentro da armadilha.

**Por que nenhum teste pegava:** o YAML era válido, o arquivo apontado existia, o
caminho estava certo, o script estava correto. O defeito morava **só na conversa
entre o workflow e a ação** — e essa conversa não é testada por nada que rode
antes do merge.

**Solução, em duas metades. Uma só não basta:**

1. **Trave a lista de parâmetros válidos.** Um teste que compare os `with:` de
   cada passo contra o conjunto que a ação aceita. A lista está no próprio
   `##[warning]` da primeira vez que você erra — copie de lá.

2. **Exija PROVA de que o trabalho aconteceu, não de que o passo terminou.** O
   script termina imprimindo uma sentinela; o workflow captura a saída
   (`capture_stdout: true`) e um passo posterior **reprova se não a encontrar**:

   ```yaml
   - name: A entrega rodou mesmo?
     env:
       SAIDA: ${{ steps.subir.outputs.stdout }}
     run: |
       printf '%s' "$SAIDA" | grep -q 'ENTREGA-CONCLUIDA:' || {
         echo "PAROU: a conexão abriu e nada foi executado."; exit 1; }
   ```

   Sentinela em ASCII: acento nela é um jeito barato de o `grep` falhar por
   codificação e a trava virar decoração. E a saída entra por `env:`, nunca
   interpolada direto no `run:` — texto de fora dentro de shell é injeção
   esperando acontecer.

**A regra que generaliza, e que já é lei nesta casa:** *status 2xx não é
sucesso* (`RETROSPECTIVA-FASE-D` §4). Aqui ela reaparece como **exit 0 não é
trabalho feito**. Todo passo cujo sucesso importa precisa provar o que fez, e
não que terminou.

**Custo real:** 28/08/2026, PR #344. O deploy fechou verde, anunciou "✅ A VPS
atendeu de primeira" — e era verdade, ela atendeu; só não foi pedido nada a ela.
Descoberto por leitura do log ao conferir o veredito, não por nenhum guarda.
Ironia registrada: o PR era justamente o que tornava a entrega mais confiável, e
os testes que ele trouxe afirmavam `script_file` — **eles codificaram o mesmo
engano do código**, que é o defeito que o registro `20260826-032` já tinha
nomeado (*o valor esperado de um teste nunca pode sair da mesma engrenagem que o
teste existe para vigiar*).
