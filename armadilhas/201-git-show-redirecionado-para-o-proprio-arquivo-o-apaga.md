---
schema_version: 2
armadilha: 201
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: `o erro acontece no shell do agente, sobre um arquivo NAO COMMITADO — nao ha diff para um portao medir, e no instante seguinte o repositorio esta consistente de novo. Um hook que recusasse redirecionamento para arquivo versionado pegaria a forma perigosa (Bash tem hook), mas tambem recusaria dezenas de usos legitimos; ficou registrado como ideia, nao improvisado aqui. A defesa e a receita de tres linhas abaixo.`
sinal:
  - `fatal: ambiguous argument '[^']*;[^']*'`
---

# `git show origin/main:arquivo > arquivo` APAGA o arquivo antes de o comando rodar — e a segunda tentativa come o seu backup

**Sintoma.** Você está provando o vermelho→verde do jeito certo: manter os
testes novos e trocar SÓ o arquivo consertado pelo do `origin/main`. Escreve o
que parece uma linha só, com backup e tudo:

```bash
cp .github/workflows/deploy-celula.yml "$SCRATCH/backup.yml" \
  && git show origin/main:.github/workflows/deploy-celula.yml > .github/workflows/deploy-celula.yml
```

O `git show` falha (aqui: `fatal: ambiguous argument
'origin\main;.github\workflows\deploy-celula.yml'` — o Git Bash do Windows
converteu o `:` e as barras). Você corrige a linha e **roda o comando de novo,
inteiro**. Dessa vez funciona. Você faz a medição do vermelho, restaura o
backup… e o arquivo volta com **0 bytes**. Uma hora de edição some.

**Causa — dois fatos verdadeiros que se somam, e nenhum deles é bug:**

1. **O shell abre o `>` ANTES de executar o comando.** O arquivo de destino é
   truncado para zero na hora em que a linha é montada. Se o comando falha
   depois disso, o destino já foi destruído — o `&&` protege o que vem
   *depois*, não o que o redirecionamento já fez. Na primeira tentativa, o
   workflow virou 0 byte enquanto o `git show` nem tinha rodado.
2. **A segunda tentativa refez o backup a partir do arquivo já destruído.** O
   `cp` está na MESMA linha, antes do `git show` — então ele copiou os 0 bytes
   por cima do backup bom. As duas cópias morreram, e a mensagem de erro da
   primeira tentativa não falava de nenhuma delas.

Nada acusa: `git status` mostra o arquivo como `M` (modificado), que é
exatamente o que se espera de quem está mexendo nele. O tamanho zero só
aparece se você o procurar.

**Por que isto é caro justamente aqui.** Esta receita — *trocar um arquivo pelo
do `origin/main` para ver o teste novo reprovar* — é o gesto padrão do protocolo
vermelho→verde desta casa (`RITOS.md` §2 peça 3, `armadilhas/195`). Ela é
executada em cima do arquivo que a sessão acabou de escrever e **ainda não
commitou** — ou seja, sobre o único estado do trabalho que não tem cópia no Git.

**Solução — três linhas, e a ordem é o remédio:**

```bash
git add <arquivo>                                   # 1. a catraca primeiro
git show origin/main:<arquivo> > /tmp/base.yml      # 2. redirecione para OUTRO nome
cp /tmp/base.yml <arquivo>                          # 3. só então sobrescreva
# ... rode os testes, veja o vermelho ...
git checkout <arquivo>                              # 4. o Git devolve o seu trabalho
```

Regra de bolso: **nunca redirecione (`>`) para um arquivo que o comando à
esquerda precisa ler, nem para um arquivo que você não pode reconstruir.**
Redirecione para um nome novo e mova depois — `mv` acontece *depois* de o
conteúdo existir; `>` acontece *antes*.

E, se o trabalho já estiver commitado (passo 1), o pior caso vira um
`git checkout` — que é o motivo de a catraca do §2 mandar commitar todo estado
verde IMEDIATAMENTE, e não "quando o PR estiver pronto".

**A pista secundária, para quem trabalha no Windows.** O Git Bash converte
argumentos que parecem caminho POSIX: `origin/main:.github/x` vira
`origin\main;.github\x`. O `:` do `git show` é a vítima mais comum. O antídoto é
`MSYS_NO_PATHCONV=1` na frente do comando — e ele é o que faz o `git show`
funcionar de primeira, evitando a falha que dispara toda esta cadeia.

**Origem.** 30/08/2026, TAR-013 (a vacina do deploy medindo a porta 22). O
`deploy-celula.yml` recém-editado — cinco blocos novos, ~120 linhas — foi
truncado a 0 byte por esta sequência e teve de ser reescrito a partir do
`origin/main`. As edições eram recuperáveis porque estavam no contexto da
sessão; um agente que tivesse fechado a janela teria perdido tudo. Custou uma
rodada inteira de reaplicação.
**Categoria** (`RETROSPECTIVA-FASE-D`): a prova vem de fora (§3) mordendo quem
a executa — o gesto que mede o mundo antigo não pode destruir o mundo novo.
