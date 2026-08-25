# Portão verde local e vermelho no CI porque o arquivo novo ainda não tinha `git add`

**Sintoma:** você roda o portão local antes de abrir o PR, e ele passa:

```
$ python ci/ci.py --apenas testador
  testar-o-testador  PASS   463 passed in 34.98s
RESULTADO  PASS
```

Abre o PR e o **mesmo comando** reprova no CI:

```
muralhas   Testar o testador (suíte adversarial dos portões)
  guardas/inverso  FAIL   1 guarda(s) em disco sem invariante declarado
```

E a pista que confirma o diagnóstico: depois de consertar, o portão local
segue devolvendo **exatamente o mesmo número de testes** de antes (463 nas
duas execuções). Ele nunca chegou a medir o arquivo novo.

**Causa:** os varredores da casa perguntam ao **git**, não ao disco —
`ci/guarda_dos_guardas.py::arquivos_versionados` roda
`git ls-files -z --cached`, e a docstring dele explica por quê: `Path.rglob`
entraria em `.claude/worktrees/`, onde o harness guarda worktrees de outras
sessões, e isso já produziu vermelho invisível uma vez (`armadilhas/106`).

A consequência é a que morde aqui, e está escrita na própria docstring:
**arquivo criado e ainda não adicionado ao índice é invisível para o
varredor.** Na CI tudo está commitado, então lá o arquivo aparece — a
assimetria é só na máquina de quem está trabalhando.

Não é falso-verde do portão: ele mediu certo o que enxergava. É falso-verde
do **procedimento** — a mesma família do padrão 1 da
`RETROSPECTIVA-FASE-D.md` (*ausência de evidência não é evidência de
sucesso*), na variante mais traiçoeira, porque o veredito verde é verdadeiro
para um conjunto de arquivos que não é o do PR.

**Solução:** `git add -A` **antes** de rodar qualquer portão local, sempre que
houver arquivo novo. Não é preciso commitar — o índice basta.

```bash
git add -A && python ci/ci.py --apenas testador
```

Regra de bolso: **portão que responde sobre "o repositório" enxerga o
repositório pelos olhos do git.** Se o seu trabalho ainda não passou por
`git add`, ele não faz parte do repositório para efeito de medição — e todo
veredito sobre ele é sobre o estado anterior.

**Como confirmar em 5 segundos que foi isto**, antes de sair procurando outra
causa: rode o portão, dê `git add -A`, rode de novo. Se o número de testes (ou
o veredito) mudar sem você ter tocado em código, era isto.

**Vale para qualquer arquivo novo, não só teste-guarda** — entrada nova em
`armadilhas/`, célula nova em `services/`, workflow novo. Todo portão que
inventaria o repositório tem o mesmo ponto cego enquanto o `git add` não
acontece.

**Origem:** gênese da célula `admin`, 25/08/2026. O teste-guarda
`services/admin/tests/test_inv_admin_nao_assina_sessao.py` foi criado, o
portão local rodou verde, e o `muralhas` do PR #181 reprovou por ele não estar
declarado em `INVARIANTES.md` — o portão local nunca o tinha visto. Custou um
ciclo de CI, e o único jeito de perceber foi notar que o número de testes não
mudou entre as duas execuções.
