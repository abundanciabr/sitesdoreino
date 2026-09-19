---
schema_version: 2
armadilha: 384
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: nenhum portão sabe que um formulário é a única entrada de uma tabela que outra regra consulta. O que existe é a pergunta de trinta segundos deste arquivo, feita antes de apagar qualquer formulário — `git grep` do endpoint que ele chama, e depois de quem lê o que ele escreve
sinal:
  - remover a seção
  - tirar da tela
  - não preciso dela por enquanto
---

# Apagar o formulário que é a única chave de uma trava não tira a trava: tranca a porta

**Data:** 06/09/2026 · **Onde:** `/admin/caixa/ideia/<id>`, seção "A assinatura que libera a obra" (PR #1286) · **Custo evitado:** uma fase do produto trancada para sempre, sem nenhum lugar no site para destrancar.

## Sintoma

O mantenedor manda um recorte da tela e pede, com todas as letras:

> Eu preciso remover essa parte de "A assinatura que libera a obra" (...)
> Quero apenas as FASES e essa outra parte eu não preciso dela, pelo menos por
> enquanto.

É um pedido de UI, claríssimo, com as bordas do bloco desenhadas no print. O
caminho óbvio é achar o `<h2>` no template, apagar até o `</form>`, rodar os
testes e entregar. O diff caberia em uma tela.

Só que **junto do pedido ele colou outra coisa**: a URL de um erro que tinha
acabado de levar, com `?erro=Esta+ideia+est%C3%A1+em+%E2%80%9CPlanejado%E2%80%9D+...`
— a recusa de mover a ideia para "Em desenvolvimento" por falta de ChangeSpec.

Os dois fatos na mesma mensagem descrevem uma armadilha: o formulário que ele
quer apagar é **a única coisa no site inteiro que destrava aquela recusa**.
Entregar o pedido ao pé da letra deixa o seletor de fases oferecendo "Em
desenvolvimento", o clique recusando com a mesma frase, e nenhuma porta para
sair disso. Fica pior do que estava.

## Causa

Uma tela que ESCREVE uma linha e uma regra que LÊ aquela linha moram longe uma
da outra, e nada as liga no código:

```
services/admin/.../caixa_ideia.html   → POST /gestao/ideias/<id>/changespec
                                      → grava ChangeSpecAprovado
services/sugestoes/.../moderacao.py   ← consulta sugestao.changespecs.exists()
services/sugestoes/.../models.py      ← consulta de novo, no save()
migrations/0004_changespec_aprovado   ← consulta de novo, num trigger do Postgres
```

Aqui eram três degraus, o último dentro do banco de dados — e nenhum deles
aparece quando se lê o template. O `git grep` do NOME da seção não acha nada
disso: o que liga as duas pontas é o endpoint que o formulário chama e a tabela
que ele alimenta, nunca o texto do título.

Quanto mais bem-feita a trava, mais fundo ela mora, e menos ela aparece para
quem está apagando a tela.

## Solução

**Antes de apagar qualquer formulário, pergunte de que trava ele é a chave.**
Trinta segundos, dois comandos:

```bash
# 1. o que este formulário escreve? (o endpoint do `action`, não o título)
git grep -n "gestao/ideias/{ideia_id}/changespec" -- services/

# 2. quem LÊ o que ele escreveu?
git grep -n "changespecs\|ChangeSpecAprovado" -- services/ | grep -v tests
```

Se a segunda busca devolve alguma regra que RECUSA, o pedido "tire isto da
tela" tem uma segunda metade que o pedido não diz, e ela é decisão do
mantenedor, não sua: **tirar a tela sozinha, e a fase fica trancada; tirar a
exigência junto, e ela anda.** Vai em `AskUserQuestion`, com as duas
consequências ditas em uma linha cada.

**Meça antes de perguntar, para a pergunta ter recomendação.** Aqui a medição
que decidiu foi uma busca só:

```bash
git grep -l "em_desenvolvimento" origin/main -- 'ci/*' '.github/*' 'fila/*'
# nada em ci/, nada em .github/, nada na fila
```

Ou seja: a trava protegia um rótulo de roadmap, não um gatilho de máquina —
nenhum robô jamais leu aquele status. Com esse número na mão a pergunta deixa
de ser "o que você prefere?" e vira "eu recomendo tirar as duas, e é por isto".
Ele escolheu tirar as duas.

## O que fazer com a lei que a trava impunha

Trava removida por decisão do dono não é trava esquecida. A lei escrita continua
lá, e a próxima sessão que ler `FORMATO-CHANGESPEC.md` §5 vai "consertar" a
ausência de boa-fé. Três coisas andam junto com o código, no mesmo PR:

1. o invariante em `INVARIANTES.md` reescrito para o que ele guarda AGORA, com
   a revogação datada — nunca apagado, porque a metade que sobrou continua valendo;
2. a lei de origem marcada como revogada, dizendo quem revogou e quando;
3. **o teste-guarda invertido**: o que media a trava passa a medir a ausência
   dela, pelo mesmo caminho por onde ela recusava. Uma lei revogada precisa de
   guarda tanto quanto a lei precisava
   (`services/sugestoes/tests/test_a_fase_anda_sem_assinatura.py`).

E deixe a volta barata: a tabela, o histórico e a operação do contrato ficam de
pé, e a migration que derruba o trigger carrega o `reverse_sql` que o recria.
