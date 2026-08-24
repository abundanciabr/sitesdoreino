# Patch de prova se GERA com `git diff` — escrever à mão custa uma rodada

**Sintoma:** o protocolo de evidência vermelho→verde por patch (obrigatório em lote,
porque a pilha de `git stash` é única por repositório e vaza entre worktrees) devolve
`error: patch failed: <arquivo>:1` / `error: <arquivo>: patch does not apply`. O agente
relê o trecho, jura que está certo, e perde uma rodada procurando erro no arquivo que
o git nomeou.

**Causa:** cabeçalho de trecho escrito à mão com **contagem de linhas errada**.
`@@ -1,2 +1,2 @@` promete 2 linhas de contexto+remoção; se o trecho tem 3, o git
recusa. E ele nomeia o arquivo cujo **cabeçalho** está errado — que não é
necessariamente o arquivo cujo **conteúdo** você queria mudar. Daí a sensação de que
"o erro aponta para o arquivo errado": o git está certo, a contagem é que mentiu.

**Solução — não escreva o patch, gere:**

```bash
# 1. faça a mudança de verdade no editor
# 2. gere o patch a partir dela
git diff > /caminho/scratch/fix.patch
# 3. VERMELHO: desfaz o fix e roda o teste (tem de falhar)
git apply -R /caminho/scratch/fix.patch && pytest -q caminho/do/teste
# 4. VERDE: repõe o fix e roda de novo (tem de passar)
git apply /caminho/scratch/fix.patch && pytest -q caminho/do/teste
```

O patch gerado tem contagens corretas por construção, e o `-R` dá o vermelho sem
tocar na pilha de stash. Guarde o `.patch` no scratch da sessão, **nunca em `/tmp`**
(que não existe na máquina do mantenedor) e nunca dentro do repositório.

**O que NÃO é o problema** (medido em 24/08/2026, os dois casos reproduzidos num
repositório de teste):

- Patch com **dois arquivos e sem a linha `diff --git`** aplica normalmente. A
  ausência do cabeçalho `diff --git` **não** quebra nada e **não** causa falha
  silenciosa — `git apply` identifica os arquivos pelas linhas `---`/`+++`.
- Quando o contexto do segundo arquivo não casa, o git nomeia **o segundo arquivo**,
  corretamente.

Isto está escrito porque a versão original desta armadilha, relatada num handoff,
culpava a falta do `diff --git` e falava em "falha em silêncio". **Não reproduziu.**
Vale a regra geral: relato de agente é hipótese até alguém rodar o comando.

**Origem:** despacho EVO-12b (`sugestoes`), 24/08/2026 — relato investigado e
corrigido pela sessão-maestro antes de virar entrada.
