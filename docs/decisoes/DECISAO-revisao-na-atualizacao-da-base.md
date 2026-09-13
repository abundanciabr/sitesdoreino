# Revisão preservada por composição Git comprovada

Uma atualização automática da base cria um novo commit, mesmo quando apenas
combina o trabalho revisado com a main. Exigir outro atestado nesse caso
interrompia o encaminhamento assíncrono depois de `update-branch`.

O atestado original permanece ligado ao SHA que o revisor examinou. A pista
primeiro valida o último atestado confiável, inclusive sua identidade,
veredito, evidência e eventual recuperação de publicação. Uma reprovação ou
malformação posterior continua soberana. Nenhuma aprovação é copiada para
outro SHA.

Se o head mudou, a pista busca os objetos da main e do head sem checkout.
Uma referência temporária exclusiva fixa a main recém-obtida para toda a
medição e é removida ao terminar. O código executado continua sendo o da
pista; nenhum arquivo do PR é materializado ou executado.

Cada commit do head até o SHA revisado, seguindo somente o primeiro pai,
precisa ter exatamente dois pais. O segundo deve ser ancestral da main
fixada, e a árvore do commit deve coincidir com `git merge-tree --write-tree`
dos seus pais, com exit zero. Toda a cadeia é conferida, inclusive commits
administrativos. Commit comum, base externa, conflito ou árvore alterada
exige nova revisão. Objeto ausente, prazo excedido ou falha do Git produz
ERROR e nunca aprova a composição.

O resultado informa o SHA revisado, o head composto e a main utilizada.
Checks continuam obrigatórios para o head atual, e a integração conserva
`--match-head-commit`. O modo de pedir pouso e os workflows permanecem sob
suas próprias regras.

Provas: `ci/tests/test_revisao_independente.py` usa repositórios Git reais e
atravessa `checar_revisao_independente` com o avaliador real. Cobre composição
limpa e cadeia, recibo intermediário, adulteração, conflito resolvido à mão,
base externa, atestado posterior inválido e falhas de instrumento. TAR-365.
