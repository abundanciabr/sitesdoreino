---
schema_version: 2
armadilha: 233
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: ci/tests/test_guarda_declarada_e_sino.py
---

# A assinatura de falha era o PREFIXO da configuração CERTA — o sino tocava em cima da própria cura

**Sintoma.** O sino das armadilhas badala num dia perfeitamente saudável, e
badala justamente sobre a lição que ensina o conserto que você acabou de
aplicar. Você inspeciona um cabeçalho de segurança em produção — tudo certo, a
cura no lugar — e leva a badalada assim mesmo:

```
$ curl -I https://meshcraft.top/admin/
HTTP/1.1 302 Found
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; …

🔔 SINO DAS ARMADILHAS: … armadilhas/199 …
   Casou: "style-src 'self'"
```

**Causa.** A assinatura foi copiada de um pedaço de **configuração**, e não de
uma mensagem de falha. Configuração certa e configuração errada **compartilham
prefixo** — a diferença mora no que vem DEPOIS:

```
style-src 'self'                          ← doente (nada libera o embutido)
style-src 'self' 'sha256-FcQqt3aNlV7…'    ← a CURA que a armadilhas/199 ensina
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com
                                          ← saudável, a política do painel
```

Ancorar em `style-src 'self'` casa as três. É a `armadilhas/229` numa segunda
forma: lá o texto compartilhado era o **rótulo** de uma linha de relatório, dito
igual no PASS e no FAIL; aqui é o **começo de uma diretiva**, dito igual na
configuração doente e na curada. A família é a mesma — assinatura ancorada em
texto que os dois estados dizem.

**A parte que morde de verdade: a "correção óbvia" também está errada.** O
reflexo é apertar a assinatura para a forma SEM o pedaço que cura — o
`style-src` sem `sha256-`, isto é, `style-src 'self';` nu. Não faça, e a razão
só aparece medindo: **uma resposta sem corpo não tem `<style>` para hashear**.
`porta.py::_hashes_de_estilo` devolve vazio DE PROPÓSITO num 302 ou num 404, e a
política sai nua. Medido no ar em 30/08/2026: um `curl -I` no `/admin/` — que
redireciona para o login — devolve exatamente `style-src 'self';` num dia sem
defeito nenhum.

Ou seja: **a ausência do pedaço que cura não é sintoma, porque a ausência também
é legítima.** Quando o que distingue são bytes que às vezes faltam por um motivo
saudável, não há assinatura possível dentro da configuração — nem a larga nem a
estreita.

**Solução.** Saia da configuração e ancore no **evento**: a mensagem que só
existe quando a falha acontece de fato. Para a `199` isso é a violação que o
navegador imprime — `Applying inline style violates` —, que cala em cima dos
três cabeçalhos acima e só aparece quando o estilo é MESMO bloqueado. A segunda
assinatura foi apagada, e o motivo ficou escrito como comentário dentro do
próprio bloco `sinal:`, para que ninguém a recoloque por parecer óbvia.

E não pare na entrada consertada: **ponha as saídas saudáveis no
`CORPUS_FELIZ`** de `ci/indice_de_armadilhas.py`. Enquanto elas não estiverem
lá, o gerador aceita a próxima assinatura ruim do mesmo jeito — o guarda só
enxerga o que o corpus tem. Entraram as três formas de cabeçalho, e a do 302 nu
é a mais importante das três: é ela que reprova mecanicamente a tal "correção
óbvia" acima.

**A pergunta de triagem, para qualquer assinatura nova:**

> Esta frase é uma MENSAGEM que a falha produz, ou é um pedaço da CONFIGURAÇÃO
> que eu estou julgando?

Se for configuração, quase certamente o estado saudável também a contém — e a
assinatura só sabe errar.

**Origem.** 30/08/2026, TAR-043, na sequência da TAR-038 (que curou a
`armadilhas/185`, mesma classe, e pediu no item 3 a varredura das outras
entradas). O `CORPUS_FELIZ` não tinha cabeçalho CSP nenhum, então o guarda
`test_nenhum_sinal_do_catalogo_real_casa_saida_feliz` passava com o defeito
dentro de casa. Varridas as 210 entradas contra o corpus ampliado, a `199` era a
única infratora.
