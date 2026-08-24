<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.14  ·  referencias antigas "ARMADILHAS §3.14" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.14 Portão roda com o Python ERRADO porque o PATH estava em formato Windows

**Sintoma:** `bash ci/cross-smoke.sh` fica **verde**, mas o traceback/warning na
saída mostra `C:\Users\...\Programs\Python\Python312\Lib\site-packages\...` —
o Python **global** da máquina, não o venv da célula com as versões pinadas.
**Causa:** `export PATH="C:/Users/.../venv/Scripts:$PATH"` **não funciona** no Git
Bash. A busca de executáveis do Bash espera caminhos POSIX; `C:/...` entra no PATH
como uma entrada inválida, é ignorada em silêncio, e o `python` do script resolve
para o primeiro do PATH herdado — o global. Nada falha, nada avisa.
**Solução:** no PATH, use a forma `/c/Users/...`:
`export PATH="/c/Users/davia/AppData/Local/Temp/claude/<venv>/Scripts:$PATH"`.
Confira antes de confiar no portão: `which python` tem de apontar para o venv.
(Isto é o oposto do §3.7 — *dentro* de código Python o caminho precisa ser
`C:/Users/...`; no PATH do Bash precisa ser `/c/Users/...`. Os dois formatos são
necessários, em lugares diferentes.)
**Por que importa mais aqui:** é um primo do §5.6 — portão verde que não mediu o
que você acha que mediu. Passou verde com o interpretador errado, e um `make ci`
que "passa" contra pacotes de outra versão não prova nada sobre o CI real.
**Origem:** despacho 03 (pagamentos, fail-closed do Mercado Pago).
