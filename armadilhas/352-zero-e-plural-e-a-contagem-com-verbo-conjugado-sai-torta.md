---
schema_version: 2
armadilha: 352
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum teste automatizado lê a frase inteira em português - o que existe para pegar isto é a prévia com dados reais, que é passo de rito e não guarda de CI.
sinal:
  - pluralize
  - "0 eventos"
  - "0 envelheceuram"
  - verbo antes do numero no template
---

# Zero é plural, e a contagem com verbo conjugado sai torta

**Sintoma.** Um template escreve uma contagem junto com um verbo, usando o
filtro `pluralize` do Django para o final do verbo, e a frase sai errada
justamente nos dois casos mais comuns: contagem zero, e verbo antes do
número. Nenhum teste acusa nada, porque a suíte confere o número certo
chegando ao contexto, não a frase inteira em português.

**Causa.** Dois defeitos distintos, achados juntos no PR #1115 (célula
`admin`), em 05/09/2026:

1. **`pluralize` trata zero como plural.** `{{ n }} envelheceu{{
   n|pluralize:"ram" }}` produz, para `n = 0`, **"0 envelheceuram"** — o
   filtro segue a regra gramatical (zero concorda no plural, "0 eventos"),
   mas o verbo já vinha escrito no singular na própria linha do template, e
   ninguém tinha testado o caso zero contra a frase renderizada.
2. **Verbo conjugado antes do número trava de vez.** `{{ n }} evento{{
   n|pluralize }} chegou` produz, para `n = 3`, **"3 eventos chegou"**: o
   `pluralize` corrigiu o substantivo, mas o verbo que vem depois do número
   foi escrito fixo no singular e não tem filtro nenhum aplicado a ele.

Os dois passam por qualquer suíte verde, porque a suíte lê `context["n"]`, não
o HTML renderizado por extenso. Os dois só foram pegos **ao renderizar a
prévia com dados reais e ler a frase em voz alta** — exatamente o passo que
`feedback_mudanca_visual_pede_previa` já cobra para mudança visual, e que
aqui pegou um defeito de texto, não de layout.

**Solução.** Duas saídas, e a primeira é sempre a melhor:

1. **Conte em substantivos, não em frases com verbo.** `Fora do prazo: 0` /
   `Fora do prazo: 3` nunca conjuga nada e nunca erra. É a forma padrão para
   qualquer rótulo com contagem nesta casa.
2. Quando a frase com verbo for mesmo necessária, o verbo TAMBÉM precisa de
   `pluralize`, e o caso zero precisa ser lido por extenso antes de subir:
   `{{ n }} evento{{ n|pluralize }} chegou{{ n|pluralize:",ram" }}` cobre os
   dois números, mas só a leitura humana da frase renderizada (não o teste)
   confirma que ela soa certa em português.

A régua que fica: **renderize a prévia com dados reais e leia o texto antes
de subir**, para qualquer tela nova ou tela mexida, em qualquer célula. Um
teste verde garante que o número chegou; só um olho humano garante que a
frase em português está certa.
