---
schema_version: 2
armadilha: 508
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: ci/pr.py aceita qualquer string em --detalhe, inclusive uma que pareca um caminho de arquivo; nao ha como o script distinguir "texto de julgamento" de "caminho que o autor esqueceu de apontar para --detalhe-arquivo" sem heuristica fragil sobre o conteudo da string.
sinal:
  - "o .detalhe. do registro tem \\d+ caracteres"
gatilho:
  - ci/pr.py
licao: "--detalhe de ci/pr.py recebe o TEXTO do julgamento, nao um caminho. Quem le arquivo e --detalhe-arquivo <arquivo> (ou DETALHE= do make pr, que ja grava em arquivo). Passar um caminho para --detalhe grava o caminho literal no recibo do livro, no lugar do julgamento, e o rito passa verde porque a string tem caracteres suficientes."
---

# 508: `--detalhe` de `ci/pr.py` recebe texto, não caminho

## Sintoma

No PR #1853 ("contracts: o cartão ganha titular e porta"), a entrada Python
de `ci/pr.py` recebeu um caminho de arquivo em `--detalhe` em vez do texto
do julgamento. O recibo embarcado no livro saiu com o caminho literal (ex.:
`/tmp/detalhe.txt`) no campo que deveria conter a explicação da entrega.
Nenhum comando falhou: a checagem de tamanho mínimo (`ci/pr.py` linha 322,
`len(pedido.detalhe.strip()) < MINIMO_DO_DETALHE`) passa porque o caminho
tem caracteres suficientes para parecer texto válido. O julgamento de fato
teve que ir para um registro separado em `painel/registros/`.

## Causa

`ci/pr.py` tem dois parâmetros distintos: `--detalhe` (o texto em si,
usado diretamente) e `--detalhe-arquivo <arquivo>` (que lê o conteúdo do
arquivo e o usa como texto). Só `make pr` com `DETALHE=` grava o texto num
arquivo temporário e passa por `--detalhe-arquivo` por baixo dos panos.
Quem chama `ci/pr.py` direto, achando que `--detalhe` também aceita
caminho (por analogia com `--corpo-arquivo`, `--mensagem-arquivo` e o
próprio `--detalhe-arquivo` vizinho), grava o caminho cru como se fosse o
julgamento. Não há checagem que rejeite uma string parecida com caminho
em `--detalhe`.

## Solução

Para passar texto direto: `--detalhe "o julgamento aqui, mínimo 80
caracteres"`. Para ler de um arquivo: `--detalhe-arquivo caminho/arquivo`
(nunca `--detalhe caminho/arquivo`). Depois de rodar `ci/pr.py` fora do
`make pr`, confira o campo `detalhe` do recibo antes de considerar o rito
fechado: se começar com `/` ou `.` seguido de extensão, é caminho vazando
para o campo errado.

## Evidência

PR #1853 ("contracts: o cartão ganha titular e porta"), recibo do livro
com o caminho literal no campo `detalhe`. `ci/pr.py` linhas 887-909
(`--detalhe` vs `--detalhe-arquivo`) e 322-328 (checagem de tamanho mínimo
que não distingue caminho de texto), conferidas em 21/09/2026.
