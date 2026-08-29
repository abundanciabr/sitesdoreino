# Clone raso faz o portão dizer "não existe" quando a verdade é "não medi"

**Sintoma:** um portão que anda no histórico do Git afirma, com toda a
confiança, que não há nada lá — sobre uma coisa que tem dezenas de entregas:

```
REVERSÃO — para qual imagem esta célula volta
  celula  PASS   'admin' está no manifesto
  atual   PASS   28032028083b (a entrega que falhou)
  alvo    FAIL   não há entrega anterior de 'admin' no histórico
```

Medido em produção em 29/08/2026, no run 33226662838 — a PRIMEIRA vez que a
reversão automática entrou em cena de verdade.

**Causa:** `actions/checkout@v4` traz, por padrão, **um commit só**
(`fetch-depth: 1`). Todo `git log`, `git rev-list`, `git merge-base` ou
`git describe` que rode nesse checkout mede um histórico de um item. O código
está certo, o comando está certo, e a resposta está vazia — porque não havia o
que ler.

**Por que é pior do que parece:** o erro não é o número, é a **categoria**. O
portão disse FAIL ("medi, e não há para onde voltar") quando a verdade era ERROR
("não consegui medir"). Quem lê o log sai investigando o registry — que está
são. É a inversão exata que a `RETROSPECTIVA-FASE-D` §1 proíbe: *ERROR nunca
vira FAIL, e FAIL nunca vira PASS*.

**Solução — as duas metades, e guardar só uma deixa a porta aberta:**

1. **A causa**, no workflow: o job que usa histórico faz o checkout completo.
   ```yaml
   - uses: actions/checkout@v4
     with:
       fetch-depth: 0
   ```
   Guarda: `ci/tests/test_reversao.py::test_o_deploy_baixa_o_historico_inteiro`.

2. **A mensagem**, no portão: ele passa a perguntar se pode medir antes de
   medir, e a recusar quando não pode.
   ```python
   raso = executar([*git, "rev-parse", "--is-shallow-repository"], ...).stdout.strip()
   if raso == "true":
       raise ErroDeInstrumentacao("este checkout é RASO — não dá para procurar…")
   ```
   Guarda: `ci/tests/test_reversao.py::test_clone_raso_e_ERROR_e_nunca_um_FAIL_de_conteudo`,
   que clona o cenário com `--depth 1` e exige exit 2.

**Onde mais isto morde:** qualquer portão que ande no histórico. O
`rollback.yml` já fazia `fetch-depth: 0` com um comentário explicando o porquê —
foi o único que nasceu certo, porque quem o escreveu tinha acabado de pagar por
isso. `ci/boletim.py` e `ci/divida_do_livro.py` rodam no PC (clone completo) e
não sofrem; se um dia forem para o CI, vão sofrer.

**Detalhe que custa uma rodada de teste:** ao montar um cenário Git de mentira,
lembre que **o Git não versiona diretório vazio**. Um `contracts/` vazio some no
clone, e o portão reprova por "raiz declarada não é a raiz do repositório" — o
motivo errado, de novo. Ponha um arquivo dentro.

**Origem:** PR #440, Onda 4 fatia 2 do `PLANO-MESTRE-ROBOS-SEM-COLISAO.md`.
Parente de `armadilhas/127` (a VPS que recusa a conexão), que foi o que fez a
entrega falhar e deu à reversão a chance de mostrar o próprio defeito.
