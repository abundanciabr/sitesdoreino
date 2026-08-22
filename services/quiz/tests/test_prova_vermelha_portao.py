"""PROVA VERMELHA DO PORTÃO DE DEPLOY — arquivo DELIBERADAMENTE quebrado.

Nível B de docs/decisoes/PROJETO-PORTAO-DEPLOY.md, autorizado pelo mantenedor
em 22/08/2026: este teste falso deixa o ci-celula VERMELHO de propósito; o PR
será mergeado mesmo assim, e o portão de deploy tem de recusar o deploy
(portao-de-deploy: failure, deploy: skipped). O revert vem no PR seguinte.
NÃO é um bug real. Se você encontrou este arquivo na main, o revert falhou —
apague-o num PR normal.
"""


def test_prova_vermelha_do_portao() -> None:
    assert False, "vermelho de propósito — o portão de deploy deve barrar este commit"
