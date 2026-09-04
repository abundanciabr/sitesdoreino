---
schema_version: 2
armadilha: 305
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: dizer que a main superou um PR é juízo sobre INTENÇÃO (dois arquivos iguais podem ser a mesma entrega ou duas diferentes), e nenhum portão o mede sem adivinhar; o que existe é o gesto de três comandos escrito abaixo, e ele cabe no primeiro minuto do resgate
sinal:
  - `is already used by worktree at`
---

# Resgatar um PR antigo começa medindo se a `main` já o superou, não rebaseando

**Sintoma.** Um lote de resgate recebe PRs devolvidos pela pista dias atrás, com
a hipótese "estavam verdes, basta atualizar e pedir pouso". Você rebaseia, roda
as muralhas, empurra, e só então descobre que o arquivo que o PR CRIA já existe
na `main` com outro conteúdo (o rebase colide arquivo com arquivo), ou que a
tela que ele entrega já está no ar por outro PR. O tempo de rebase, suíte e
checks foi gasto num PR morto.

Medido em 03/09/2026, no resgate dos três PRs de 31/08 (#740, #734, #761):
**dois dos três já tinham sido refeitos por outros PRs**. O #734 (rodapé da
Caixa) tinha sido reescrito pelos #871 e #873, e a `armadilhas/287` já contava
essa história pelo lado de quem refez. O #761 (comando para testar o aviso do
celular) tinha sido superado por um Rito de Contrato de cinco PRs (#907 a #911),
e o seu arquivo de testes já existia na `main` com o conteúdo da porta nova.
Só o #740 (uma armadilha) ainda fazia sentido.

**Causa.** PR devolvido pela pista some do campo de visão de todo mundo
(`armadilhas/287`), e o repositório recebe dezenas de merges por dia. Em 48h a
`main` anda centenas de commits (894, no caso medido) e a probabilidade de
alguém ter refeito o mesmo trabalho é alta. A hipótese do resgate ("só faltou
pousar") é a mais natural e a mais cara: ela pula a pergunta "isto ainda é
necessário?" e vai direto para "como faço isto pousar?".

**Solução: três medições antes de criar a bancada, uma por PR.**

```bash
# 1. os arquivos que o PR CRIA já existem na main? (colisão certa no rebase)
gh pr view <N> --json files --jq '.files[].path' | while read f; do
  git cat-file -e "origin/main:$f" 2>/dev/null && echo "JÁ NA MAIN: $f"; done

# 2. quem os trouxe, e quando? (o PR que superou o seu)
git log origin/main --format='%h %ad %s' --date=short -1 -- <arquivo>

# 3. a distância: quanto a main andou desde que o PR nasceu
git rev-list --count origin/<ramo>..origin/main
```

Se o passo 1 acusar arquivo que o PR cria já existindo na `main`, o PR está
superado até prova em contrário: leia o commit que o trouxe (passo 2) e, se for
a mesma entrega, **feche o PR com um comentário que nomeia o que o superou**, em
vez de pousar. Ramo fica no servidor; nada se apaga.

Dois detalhes que o resgate ensinou, e que a receita acima não cobre:

- **O ramo pode estar preso numa bancada antiga.** `git switch <ramo>` falha com
  `is already used by worktree at ../wt-...`, porque a sessão original deixou a
  bancada (e não se apaga bancada alheia: pedido do mantenedor em 29/08). Não é
  bloqueio: trabalhe em HEAD solto na bancada nova e empurre com
  `git push --force-with-lease origin HEAD:<ramo>`.
- **PR só de `armadilhas/` NÃO é escrituração isenta.** A isenção de
  `ci/divida_do_livro.py` é `painel/` e/ou `fila/`, e o portão recusa com
  "nenhum registro viaja neste PR" (`armadilhas/248`). O despacho do resgate
  chegou dizendo o contrário, e a recusa custou uma volta de checks. Armadilha
  precisa de recibo como qualquer entrega: um registro curto citando o número.

**Origem.** Resgate do lote de 03/09/2026: os PRs #734 e #761 fechados como
superados (comentários neles nomeiam os PRs que os substituíram), o #740
rebaseado e pousado. Registro `20260904-025`.
