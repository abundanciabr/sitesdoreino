# `--conferir` de arquivo gerado reprova com tudo em dia — `manifesto.js está DESATUALIZADO` num checkout que acabou de dar `git pull`

**Sintoma:** `node painel/gerar_manifesto.js --conferir` (ou qualquer verificador
do padrão "gera em memória e compara com o arquivo commitado") falha com
"DESATUALIZADO" logo depois de um `git pull` limpo, sem nenhuma mudança em
`registros/`. No CI (Linux) o mesmo comando passa verde. Rodar o gerador de novo
"conserta" — e o git não mostra diff nenhum.

**Causa:** fins de linha. O repositório converte LF→CRLF no checkout do Windows
(warnings `LF will be replaced by CRLF` no add). O arquivo gerado em memória tem
`\n`; o mesmo arquivo lido do disco após um checkout tem `\r\n`. A comparação
byte a byte (`atual !== conteudo`) enxerga um "desatualizado" que é só fim de
linha. Pior: o comportamento depende de QUAL checkout você está — um worktree
recém-criado pode vir LF e o clone principal CRLF, então "funciona no meu
worktree" não prova nada.

**Solução:** no comparador do `--conferir`, normalizar `\r\n → \n` nos DOIS
lados antes de comparar (fim de linha não é conteúdo). Corrigido em
`painel/gerar_manifesto.js` (26/08/2026), com teste-guarda: manifesto convertido
a CRLF de propósito continua PASS; registro novo sem regenerar continua FAIL.
Regra geral para qualquer verificador futuro do tipo "gerado vs. commitado"
neste repositório: compare conteúdo normalizado, nunca bytes crus — ou o
verificador será um em cada sistema operacional.

**Origem:** obra da reforma dos painéis, 26/08/2026 — o `--conferir` passou no
worktree e no CI, e reprovou no clone principal do mantenedor no primeiro
`git pull`, com o livro perfeitamente em dia.
