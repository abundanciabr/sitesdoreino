# `test_stdin_com_bom_utf8_nao_vira_recusa` reprova local no Windows, mesmo sem nenhuma mudança sua

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

**Se você é uma sessão Windows e viu isto: não é o seu diff.** Antes de
investigar mais, confirme rodando o mesmo teste isolado contra um worktree
limpo de `origin/main`:

```bash
git worktree add ../wt-verificacao-baseline origin/main
cd ../wt-verificacao-baseline
python -m pytest ci/tests/test_muralha_pasta_compartilhada.py::test_stdin_com_bom_utf8_nao_vira_recusa -v
```

Se reproduzir igual sem o seu código, o baseline já estava assim — reporte,
não tente consertar como parte de uma tarefa não relacionada.

**Correção definitiva:** fora do escopo de quem só encontrou isto de
passagem — `ci/muralha_pasta_compartilhada.py` é caminho CODEOWNERS
(`/ci/`), exige mandato de despacho próprio. Caminho provável de conserto,
para quem pegar esse despacho: `_ler_json_do_stdin()` ler
`sys.stdin.buffer.read().decode("utf-8-sig")` em vez de
`sys.stdin.read().lstrip(...)` — o codec `utf-8-sig` descarta o BOM na
própria decodificação, em vez de depender de já ter sido decodificado certo
antes.

**Origem:** encontrado verificando a limpeza da suíte "testador" antes de
abrir o PR de `painel/ia/` (o mapa técnico do projeto para IA), 27/08/2026 —
sem relação com o conteúdo daquele PR.
