# Célula nova deixa o `deploy-celula` VERMELHO em todo merge, até o compose da VPS conhecê-la

**Sintoma:** a célula nasceu, o `make ci` dela é verde, o `muralhas` é verde, o PR
mergeia — e o `deploy-celula` fica **vermelho no merge, e em todos os merges
seguintes daquela célula**. O log do job diz, sem ambiguidade:

```
ERRO: 'sugestoes' não tem serviço algum em /opt/plataforma/docker-compose.yml.
Abortado de propósito: 'up -d' sem argumento subiria a plataforma inteira.
Process exited with status 1
```

Medido em 24/08/2026 na `sugestoes`: **cinco** runs vermelhos seguidos (PRs #108,
#113, #116, #122, #126) — um por despacho da célula, todos pela mesma linha.

**Causa:** o `deploy-celula` descobre o que subir **lendo o compose que está na
VPS** (`docker compose config --services | grep -E "^${CELULA}(-|$)"`), de propósito:
é assim que uma célula que ganha um auxiliar amanhã entra sozinha, sem lista fixa
que envelhece em silêncio. Enquanto `infra/docker-compose.yml` não declarar a
célula **e esse compose não tiver sido sincronizado pelo `deploy-infra`**, a busca
volta vazia e o job aborta fail-closed — corretamente: `up -d` sem argumento
subiria a plataforma inteira.

Duas consequências que confundem quem lê o run:

- O **build e o push da imagem funcionaram**. O passo que falha é o seguinte
  (`Ativar na VPS`), então `ghcr.io/<owner>/plataforma-<celula>:main` **já existe**
  no registry desde o primeiro merge. Não é problema de imagem.
- É **ERROR de ambiente, não FAIL de código**. Não saia corrigindo a célula: não há
  nada errado nela.

**Solução — e a ordem importa, porque ela é circular se você não a quebrar:**

1. Um PR de `infra/` declara o serviço da célula (e os auxiliares) no
   `infra/docker-compose.yml`.
2. **Antes de mergear esse PR**, o que o compose novo pressupõe precisa existir na
   VPS: o `env/<celula>.env` (escrito à mão pelo mantenedor — INV-P8) e o par
   banco+role do `infra/provisionamento-postgres.sql`. `DATABASE_URL` é fail-hard:
   sem banco, o container entra em crashloop.
3. Só então o merge. O `deploy-infra` sincroniza o compose e, no passo de
   verificação, **exige TODOS os serviços declarados em estado `running`** — se a
   célula nova não subir, o run reprova e derruba a verificação da plataforma
   inteira, não só a da célula nova.
4. Se a célula tem processo auxiliar cujo `command:` ainda não existe na imagem
   (ex.: `run_huey` antes de o Huey entrar na célula), o merge de `services/`
   que cria o comando vem **antes** do merge de `infra/`. Auxiliar declarado com
   comando inexistente sai do ar como `Unknown command`, e o `deploy-infra`
   reprova pelo mesmo passo de verificação.

Depois que o compose da VPS conhecer a célula, os merges dela voltam a ficar
verdes sozinhos — inclusive os que ficaram vermelhos antes: `gh run rerun <id>
--failed` no run do merge mais recente já entrega a imagem.

**Origem:** despacho EVO-22 (infra/sugestoes-na-vps), 24/08/2026, ao levantar por
que todo despacho da Caixa de Sugestões terminava com o `deploy-celula` vermelho.
Parente do `armadilhas/076` (célula nova e a lista fixa do `rollback.yml`): as
duas são a mesma família — **célula nova exige registro em lugares que o despacho
da célula não pode tocar**, e o sintoma aparece longe de quem o causou.
