# Arquivo gerado que sai do Git quebra, em silêncio, tudo que o lia do checkout

**Sintoma:** você tira um artefato gerado do versionamento (o certo a fazer — ele
era colisão diária entre sessões), a muralha do painel fica verde, e o CI da
célula explode com dezenas de falhas que não parecem ter relação com o que você
mexeu:

```
FAILED tests/test_painel_vivo.py::test_a_pasta_do_painel_foi_encontrada
   AssertionError: sem a pasta do painel os testes abaixo não provariam nada
FAILED tests/test_painel_vivo.py::test_o_csp_libera_exatamente_o_script_embutido
   FileNotFoundError: '/home/runner/work/.../painel/painel.html'
FAILED tests/test_mapa_ia_publico.py::... assert 404 == 200
16 failed, 202 passed
```

Medido em 28/08/2026, no PR da Onda 3 (escritor único do painel): a muralha
passou porque ela **constrói** o painel antes de conferir; a suíte da célula
`admin` reprovou porque ela **lê** o arquivo pronto e ninguém o tinha construído
naquele checkout.

**Causa:** um arquivo versionado é lido por quem quiser, sem cerimônia — e por
isso ganha leitores que ninguém cadastrou. Quando ele passa a ser construído,
todo leitor precisa de alguém que construa antes dele. `grep` pelo nome do
arquivo encontra os leitores óbvios (`painel/painel.html`); não encontra quem o
alcança por uma função (`diretorio_do_painel()`), por uma rota, ou por uma
varredura de pasta.

**Solução — antes de tirar um gerado do Git, faça a lista de quem materializa:**

1. Levante os leitores por CAMINHO e por FUNÇÃO:
   `grep -rn "painel.html\|diretorio_do_painel" --include=*.py --include=*.js --include=*.yml .`
2. Para cada leitor, decida quem constrói para ele — e escreva isso onde ele
   mora, não num documento:
   - a muralha do CI → constrói ela mesma (primeiro passo do script);
   - o deploy → constrói antes de montar a imagem, fail-closed;
   - a suíte de uma célula → *fixture* de sessão que materializa o que falta;
   - o mantenedor na máquina dele → um atalho de dois cliques
     (`painel/abrir-o-painel.cmd`), porque ele não abre terminal.
3. **Nenhum desses caminhos pode montar em silêncio quando não consegue.** O
   fixture da célula, sem Node, volta sem montar de propósito: o teste-guarda
   `test_a_pasta_do_painel_foi_encontrada` reprova alto, e a mensagem diz a
   verdade. Montar "o que der" seria verde sem medição.
4. Rode o CI da célula tocada ANTES de abrir o PR — a muralha verde não fala
   pelas células, e foi exatamente essa a leitura errada que custou a rodada.

**Prova de que a trava existe:** `ci/verificar_painel.py` reprova se o gerado
voltar ao índice do Git, e `ci/tests/test_painel_vivo_no_deploy.py` mede que o
deploy **monta antes de copiar** (a ordem, não só a linha).

**Origem:** PR #435 (Onda 3 do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`).
Parente de `armadilhas/156`, que descreve a doença que esta mudança curou.
