# Varredor que anda no disco entra em `.claude/worktrees/` — vermelho invisível na CI, barulhento na sua máquina

**Sintoma:** `python -m pytest ci/tests` no clone principal devolve `1 failed`
e a mensagem acusa arquivos que você nunca escreveu, dentro de pastas com
nomes que você não reconhece:

```
FAILED ci/tests/test_indice_de_armadilhas.py::test_toda_referencia_a_uma_armadilha_resolve
E   referência(s) a armadilha que não existe mais:
E       .claude/worktrees/fervent-chebyshev-fae8ba/ci/tests/test_indice_de_armadilhas.py:396 -> §99.99
E       .claude/worktrees/fervent-joliot-750780/ci/tests/test_indice_de_armadilhas.py:396 -> §99.99
E       .claude/worktrees/unruffled-khayyam-28935a/ci/tests/test_indice_de_armadilhas.py:396 -> §99.99
```

No GitHub Actions o mesmo teste passa. Você repete o comando, continua
vermelho, e como "na CI está verde" a conclusão natural é *é coisa da minha
máquina* — e o teste vira ruído que todo mundo aprende a pular.

**Causa:** o varredor era `RAIZ.rglob("*")` com uma lista de pastas a ignorar
(`.git`, `__pycache__`, `node_modules`, `.pytest_cache`). `rglob` anda no
DISCO, não no repositório. O harness do Claude Code guarda worktrees de outras
sessões em `.claude/worktrees/<nome>/`, que é um clone inteiro do projeto —
com `ci/`, `services/`, tudo. O varredor entrava lá e passava a medir o
repositório de outra sessão junto com o seu, inclusive a sentinela `§99.99`
que o próprio fixture escreve de propósito para provar que o guarda reprova.

O runner do GitHub não tem `.claude/` — por isso o furo era **mudo na CI e
barulhento em quem trabalha**, que é a pior combinação possível: o guarda
perde credibilidade exatamente com as pessoas que ele deveria proteger.

Duas agravantes que valem para qualquer varredor:

1. **A lista de pastas a pular cura o caso, não a classe.** Acrescentar
   `.claude` faria o vermelho sumir hoje; a próxima ferramenta inventa
   `.cursor/`, `.venv-2/`, `node_modules-old/` e o furo volta com outro nome.
2. **Um `.gitignore` não protege**: `.claude/` não está no `.gitignore` deste
   repositório. O que existe é `.git/info/exclude`, que é **local, não
   versionado** — ou seja, o comportamento muda de máquina para máquina.

**Solução:** pergunte ao git quais arquivos são rastreados, em vez de andar no
disco. O que o git rastreia é o repositório; o resto é lixo de máquina.

```python
execucao = executar(
    ["git", "ls-files", "-z", "--cached"],
    cwd=raiz,
    descricao="listar os arquivos versionados (git ls-files)",
    exigir_stdout=True,   # stdout vazio é ERROR, nunca "repositório vazio"
)
return sorted(p for p in execucao.stdout.split("\0") if p.strip())
```

Três detalhes que fazem a diferença:

- **`exigir_stdout=True`**: git que não responde tem de virar `ERROR`, nunca
  lista vazia. Lista vazia é indistinguível de "não há nada a verificar" —
  e aí o portão aprova sem medir (INV-CI01).
- **Um varredor só, importado por quem precisar.** Se cada portão escrever o
  seu, cada um terá um bug diferente. Aqui ele mora em
  `ci/guarda_dos_guardas.py::arquivos_versionados` e o
  `ci/tests/test_indice_de_armadilhas.py` o importa.
- **Consequência aceita, e documente-a:** arquivo criado e ainda não
  `git add`-ado é invisível para o varredor. Na CI tudo está commitado, e o
  rito da casa manda `git add` por arquivo — mas se você está rodando um
  portão local com arquivo novo, adicione ao índice antes de confiar no verde.

**Como saber se o seu varredor tem este bug:** crie uma pasta de mentira e veja
se ele a enxerga.

```bash
mkdir -p .claude/worktrees/fantasma/ci/tests
cp ci/tests/<o-arquivo-que-o-varredor-le>.py .claude/worktrees/fantasma/ci/tests/
python -m pytest ci/tests -q     # verde = varredor correto; vermelho = anda no disco
rm -rf .claude/worktrees/fantasma
```

**Bônus (aconteceu na mesma sessão):** consertado o varredor, ele passou a
enxergar arquivos novos que ANTES escapavam — e imediatamente pegou uma citação
pendurada de verdade num teste recém-escrito, que continha a sentinela literal.
Se o seu arquivo de teste precisa escrever uma citação inválida de propósito,
monte-a em tempo de execução (`f"... {secao}99.99"`) para que a string literal
não exista no fonte.

**Origem:** despacho `ci/guarda-dos-guardas` (peça B2 do PLANO-10X, lote de
25/08/2026).
