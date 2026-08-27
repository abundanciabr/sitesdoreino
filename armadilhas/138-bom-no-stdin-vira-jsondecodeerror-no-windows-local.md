# `test_stdin_com_bom_utf8_nao_vira_recusa` reprova local no Windows, mesmo sem nenhuma mudança sua — RESOLVIDO em 27/08/2026

**Sintoma:** rodando `python ci/ci.py --apenas testador` (ou `pytest
ci/tests/test_muralha_pasta_compartilhada.py`) numa máquina Windows, o teste
`test_stdin_com_bom_utf8_nao_vira_recusa` reprova com:

```
AssertionError: 🧱 PAROU POR SEGURANÇA: a muralha da pasta compartilhada não
conseguiu medir (JSONDecodeError: Expecting value: line 1 column 1 (char 0))
```

— **inclusive num checkout limpo de `origin/main`, sem nenhuma mudança sua.**
Confirmado nesta sessão: mesmo teste, isolado, rodado num worktree novo
direto da `main`, reproduz idêntico.

**Causa:** `ci/muralha_pasta_compartilhada.py::_ler_json_do_stdin()` lê
`sys.stdin.read()` e descarta o BOM com `.lstrip(chr(0xFEFF))` — isso só
funciona se o Python já tiver decodificado os 3 bytes do BOM UTF-8
(`EF BB BF`) como o único caractere `chr(0xFEFF)`. Em algumas configurações
locais de Windows, `sys.stdin` decodifica pela codepage do console (não
UTF-8) por padrão, e os 3 bytes do BOM viram caracteres de lixo em vez de 1
— o `.lstrip` não bate com nada, o lixo fica colado antes do `{`, e
`json.loads` reprova. Mesma família da armadilha 003 (acento virando lixo em
cp1252), só que na LEITURA do stdin em vez da escrita do stdout.

**Isto não bloqueia PR nenhum:** o required check `muralhas` do GitHub roda
em `ubuntu-latest`, não Windows — este teste exercita um caminho de
decodificação sensível à codepage do console, então é plausível (não
confirmado nesta sessão, que não tem acesso a rodar a CI real) que ele passe
limpo no Linux da CI mesmo falhando aqui.

**Se você viu isto ANTES de 27/08/2026 (ou depois, numa árvore que não tem a
correção abaixo): não é o seu diff.** Confirme rodando o mesmo teste isolado
contra um worktree limpo de `origin/main`:

```bash
git worktree add ../wt-verificacao-baseline origin/main
cd ../wt-verificacao-baseline
python -m pytest ci/tests/test_muralha_pasta_compartilhada.py::test_stdin_com_bom_utf8_nao_vira_recusa -v
```

Se reproduzir igual sem o seu código, o baseline já estava assim — reporte,
não tente consertar como parte de uma tarefa não relacionada.

**Resolvido:** `_ler_json_do_stdin()` trocou `sys.stdin.read().lstrip(chr(0xFEFF))`
por `sys.stdin.buffer.read().decode("utf-8-sig")` — lê os bytes crus do stdin
(sem passar pelo modo texto, que é quem decodificava pela codepage do console)
e descarta o BOM na própria decodificação, com um codec que não depende de o
BOM já ter virado 1 único caractere antes. Mesma correção nos dois pontos que
chamam `_ler_json_do_stdin()` (`_hook_pre_tool_use` e `_hook_aviso_de_sessao`,
que só captura a exceção e cai para `dados = {}`). Suíte inteira de
`test_muralha_pasta_compartilhada.py` (36 testes) e `python ci/ci.py --apenas
muralhas` verdes depois da troca.
**Se você AINDA vir este sintoma numa árvore com a correção acima: não é mais
este defeito** — é uma regressão ou um caso novo (por exemplo, um encoding em
que nem `utf-8-sig` dá conta); investigue do zero em vez de assumir que é
"conhecido e não bloqueia".

**Origem:** encontrado verificando a limpeza da suíte "testador" antes de
abrir o PR de `painel/ia/` (o mapa técnico do projeto para IA), 27/08/2026 —
sem relação com o conteúdo daquele PR. Corrigido na sessão seguinte, mesmo
dia, despacho dedicado (`ci/` é caminho CODEOWNERS, mandato próprio).
