# `+` em querystring vira ESPAÇO — e o vazio resultante parece uma resposta legítima

**Sintoma.** Uma tela que busca por e-mail (ou por qualquer texto que possa conter
`+`) mostra "não encontramos nada" para alguém que **existe**. Nenhum erro, nenhum
log, status 200 dos dois lados. Com `fulano@exemplo.com` funciona; com
`fulano+curso@exemplo.com`, não.

**Causa.** Numa querystring, `+` é a codificação histórica de espaço. O
`request.GET` do Django decodifica corretamente — e é justamente por isso que o
e-mail chega ao seu código já como `fulano curso@exemplo.com`. Daí em diante tudo
"funciona": você escapa direitinho o espaço (`%20`), a célula vizinha responde 200
com a lista vazia, e a tela mostra o vazio.

São **dois** pontos de falha independentes, e consertar um só não resolve:

1. **quem escreve o link** — `?email={{ pessoa.email }}` sem `|urlencode` manda o
   `+` cru;
2. **quem monta o caminho da chamada seguinte** — `f".../alunos/{email}/..."` sem
   `quote(email, safe="")` repete o problema no outro salto.

**Solução.** `{{ email|urlencode }}` no template e `quote(valor, safe="")` no
cliente HTTP. E, no teste, **meça o link que a tela gera**, não uma URL que você
montou à mão no próprio teste — um teste que monta `f"?email={email}"` reproduz o
bug dentro de si mesmo e reprova o código correto (foi o que aconteceu aqui, em
29/08/2026, PR #478).

**Por que isto merece entrada própria.** O modo de falha não é "quebrou": é
**vazio silencioso que se lê como resposta**. É o mesmo padrão do falso-verde da
`RETROSPECTIVA-FASE-D` §1 — "não achei" e "não perguntei direito" chegam na tela
como a mesma frase, e a mais inofensiva das duas é a que a pessoa acredita. No
prontuário de um aluno o custo é direto: o mantenedor lê "esta pessoa nunca esteve
aqui" sobre alguém que estudou lá um ano, e decide com base nisso.

**Onde já mordeu.** `services/admin` — tela do prontuário
(`DECISAO-a-ficha-nao-se-apaga.md` §5). Guardas:
`test_o_link_da_tela_escapa_o_email` e `test_o_email_com_mais_chega_inteiro_na_alunos`,
em `services/admin/tests/test_prontuario_na_tela.py`.
