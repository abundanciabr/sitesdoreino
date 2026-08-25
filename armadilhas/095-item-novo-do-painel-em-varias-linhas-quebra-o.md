# Item novo do painel escrito em várias linhas quebra o painel INTEIRO — `node --check` acusa `SyntaxError: Invalid or unexpected token` numa linha que só tem `"`

**Sintoma:** você acrescenta um item a `arquivos/painel-dados.js` (uma string na
lista `DADOS.precisaDeVoce` ou `DADOS.episodios`), roda o `node --check`
obrigatório do §7.2 e ele quebra apontando para uma linha que contém só a aspa
de abertura:

```
arquivos/painel-dados.js:17
  "
  ^
SyntaxError: Invalid or unexpected token
```

Sem o check, o efeito no navegador seria o clássico do §7.2: o painel abre só
com o cabeçalho — o JS inteiro morreu, TODOS os cards somem, não só o seu.

**Causa:** string de JavaScript entre aspas **não atravessa linha física**. No
painel, cada item das listas é UMA string por linha — longa, com `\r\n`
**literais** (a sequência de dois caracteres, barra e letra) fazendo as quebras
visuais. Quem escreve o item num script Python multilinha (para "ficar
legível") injeta quebras de linha REAIS dentro do literal JS, e a primeira
delas encerra o parse. Pior: escrevendo o script num heredoc do Bash, é fácil
misturar os dois regimes — `\r\n` que era para ser literal vira CRLF de
verdade no meio do caminho (parente direto de `armadilhas/093`), e aí até a
tentativa de conserto "juntar as linhas" erra, porque o que há no arquivo não
é o que o editor mostra.

**Solução:**

1. **Item novo = UMA linha física.** Monte a string inteira numa variável de
   linha única (as quebras visuais são os quatro caracteres `\`+`r`+`\`+`n`)
   e injete depois da âncora — nunca cole um bloco multilinha.
2. Valide com os DOIS degraus do §7.2 antes de considerar pronto:
   `node --check arquivos/painel-dados.js` **e** o render completo
   (dados + renderizador), que imprime `painel OK — …`.
3. Se já quebrou e o `replace` de desfazer "não encontra" o texto: pare de
   adivinhar e olhe os **bytes crus** (`io.open(..., newline="").read()` +
   `repr()`) — o modo universal-newlines do Python mente sobre o que está no
   disco, e foi ele que escondeu o CRLF real neste caso.

**Origem:** sessão da célula de identidade, 25/08/2026 — o item do bloco H20
entrou multilinha, o painel quebrou, e o conserto às cegas errou duas vezes até
a leitura em modo binário mostrar o CRLF real atrás da aspa.
