---
schema_version: 2
armadilha: 330
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: o cartógrafo (`ci/mapa_do_site.py`) mede o ENDEREÇO de cada rota e é fail-closed nos dois sentidos, mas nunca olha o campo `gesto` — `armadilhas/223` já declara esse buraco. A implicação sã ("rota `@require_POST` exige `gesto: true`") é derivável e foi medida aqui; construí-la é a TAR-144, e depende de mandato porque `ci/` é CODEOWNERS
sinal:
  - "require_POST"
  - "mapa-do-site.json"
  - "405 Method Not Allowed"
---

# Rota `@require_POST` sem `"gesto": true` vira link clicável na tela do dono, e todo teste fica verde

**Sintoma.** Não há nenhum. É esse o problema.

`/admin/mapa/` abre, as três contas da capa somam, os 963 testes da célula
`admin` passam, o `ci/mapa_do_site.py` diz **PASS** com 172 rotas medidas e 172
declaradas. E o mantenedor clica num nome da lista — "Ligar ou desligar uma
medalha ou marco" — e recebe **405 Method Not Allowed**.

Medido em 04/09/2026: cinco endereços assim, renderizados como link de verdade.

```
LINKS CLICAVEIS OFERECIDOS AO DONO PARA ROTAS SO-POST: 5
    /admin/economia/mudar-conquista
    /admin/economia/mudar-degrau
    /conquistas/forja/registrar
    /conquistas/interno/decidir
    /conquistas/marcos/enviar
```

**Causa.** Quem decide se a linha vira link é `_preparar`, em
`services/admin/apps/core/mapa_do_site.py`, e a regra dele está certa: link só
para endereço concreto, público **e que não seja gesto**. O que ele não tem é
como saber o que é gesto. Ele lê o campo `"gesto": true` do
`painel/mapa-do-site.json` — um campo que **uma pessoa escreve à mão** e que
**nenhum portão confere** (`armadilhas/223`, buraco declarado).

Então o modo de falha é o mais barato que existe: quem acrescenta a rota copia
a entrada da irmã, escreve a descrição, e esquece uma linha de JSON. As cinco
entradas do dia 04/09 **diziam no próprio texto** "Não é uma página: quem clica
volta para a tela com a resposta" — a prosa estava certa, o campo estava
ausente, e é o campo que a tela obedece.

É a Classe 8 (mapa velho) na sua forma mais discreta: o mapa não está errado
sobre onde as coisas ficam, e sim sobre **o que elas são**. E é o padrão 2 da
`RETROSPECTIVA-FASE-D` outra vez (garantia sem mecanismo apodrece), no mesmo
formato do `armadilhas/222`: existe portão, o portão é verde, e por isso
ninguém abre o arquivo para conferir.

**Solução — as duas medições, e elas concordam.**

1. **O decorador, no código.** Percorra `urls.py` por AST, siga o import até o
   arquivo da view, e olhe os decoradores da `def`. `@require_POST` (ou
   `require_http_methods` só com POST) é prova de que a rota **não é página**.
   Achou as cinco.

2. **A prosa da própria entrada.** Procure `não é (uma) página`, `o que
   acontece ao`, `o gesto de` na `titulo`+`descricao` de quem está sem
   `"gesto": true`. Achou **as mesmas cinco**, sem ler uma linha de Python.

Duas medições independentes que apontam o mesmo conjunto é o que transforma
"achei um problema" em "medi um problema". A segunda cabe em cinco linhas e
serve de conferência rápida em qualquer sessão.

**A implicação vale num sentido só, e escrever a volta quebraria o portão.**
POST-only ⇒ gesto é verdade sempre. Gesto ⇒ POST-only é **falso**:
`/entrar/google` e `/entrar/google/retorno` são GET, estão marcadas como gesto,
e estão certas — abrir esse endereço não mostra página nenhuma, dispara o
vaivém do Google. Um portão que exigisse a recíproca reprovaria quatro entradas
corretas no primeiro dia.

**O que NÃO fazer.** Não conserte tirando o link de quem responde 405 na hora
da renderização: isso mediria a rota pelo comportamento dela em produção, e a
tela do dono passaria a depender de uma chamada HTTP para desenhar uma lista.
O fato mora no mapa; o lugar de proteger o fato é o portão que já lê o mapa.

**Contexto:** despacho do mantenedor em 04/09/2026 ("atualize o mapa do site"),
PR #1036 — que também corrigiu 19 entradas escritas sem acento nenhum na tela
que ele lê, duas entradas da `metricas` que ainda falavam no futuro de uma parte
no ar desde 04/09, e um `~97 endereços e ~35 telas` no `_doc` do arquivo quando
já eram 172. O portão do campo `gesto` ficou como **TAR-144**, esperando
mandato: `ci/` é caminho CODEOWNERS.
