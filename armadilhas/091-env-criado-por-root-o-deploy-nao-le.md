# Env criado como `root` ⇒ `deploy-infra` reprova com "permission denied"

**Sintoma:** o deploy da infraestrutura falha na **validação**, antes de trocar
qualquer coisa:

```
open /opt/plataforma/env/<celula>.env: permission denied
ERRO: o compose novo reprovou na validação — NADA foi trocado.
```

A plataforma continua inteira (o portão é fail-closed e recusa antes do swap), mas o
deploy não anda, e a mensagem não diz quem não conseguiu ler.

**Causa:** o arquivo de env foi criado por um script rodado como **root**, com
`umask 077` — resultado: `root:root`, modo `600`. O pipeline entra na VPS como o
usuário **`deploy`**, e é ele quem roda `docker compose config`. `deploy` não lê um
600 de root, então o compose não resolve o `env_file` e a validação reprova.

O detalhe que engana: **os outros `env/*.env` funcionam**, porque nasceram pela mão do
mantenedor na sessão do `deploy`. Só o arquivo novo diverge — e ele diverge em
*metadado*, não em conteúdo. Um `cat` do arquivo (como root) mostra tudo certo.

**Solução — copie dono e modo de um env que JÁ funciona**, em vez de escolhê-los:

```bash
chown --reference=env/alunos.env env/<nova>.env
chmod --reference=env/alunos.env env/<nova>.env
```

`--reference` é melhor que fixar `deploy:deploy 640` no script: não exige que o script
adivinhe o usuário nem o modo corretos daquela máquina, e continua certo se a
convenção mudar. **A definição de "certo" é o arquivo que já está em produção.**

**Conferência que fecha o assunto** (imprima no fim do provisionamento):

```bash
stat -c '%U:%G %a' env/nova.env env/alunos.env    # os dois têm de sair iguais
```

**A regra que generaliza:** todo arquivo que o pipeline vai LER precisa nascer com o
dono e o modo do usuário do pipeline — e a forma barata de garantir isso é derivar de
um vizinho que funciona, nunca declarar um valor no script. Vale para env, chave,
socket, e qualquer coisa que um script de mantenedor crie em caminho compartilhado.

**Origem:** Lote 2 da Caixa de Sugestões, 24/08/2026 — primeiro `deploy-infra` da
célula `sugestoes`. Corrigido no mesmo dia em `infra/provisionar-sugestoes.sh`.
