# apps/core/enderecos.py
"""Os dois endereços de sessão que este site precisa conhecer — e só eles.

Leis do assunto: `docs/decisoes/DECISAO-onde-mora-a-sessao.md` e, desde
25/08/2026, `docs/decisoes/DECISAO-celula-de-identidade.md`. O dia previsto
aqui ("no dia em que a identidade mudar de casa, este arquivo é a mudança
inteira do lado do site") CHEGOU — e foi exatamente assim: os defaults abaixo
passaram a apontar para a célula `identidade`, sem tocar view, template ou
middleware.

**Lidos NO PONTO DE USO, com default, nunca `env()` fail-hard.** São destino de
link, não credencial: faltar a variável não pode derrubar a vitrine do site nem
fechar a página. O default é o endereço real de hoje, então em dev e no CI tudo
funciona sem env nenhum.

Não confundir com `IDENTIDADE_API_URL` (em `clients.py`): aquele é a rede interna
do Docker, por onde o SERVIDOR pergunta. Estes dois são endereços públicos, por
onde o NAVEGADOR da pessoa caminha.
"""

import os

# Onde a pessoa que já entrou vai ao clicar no próprio nome. Continua sendo a
# Caixa: é a única área logada do site até a escola nascer.
CAIXA_PADRAO = "/forms/sugestoes/"

# A rota que manda direto ao Google — da célula `identidade`, dona do login do
# site inteiro: quem clica no botão do site já decidiu entrar, e uma segunda
# tela de "Entrar com Google" seria um clique a mais para dizer a mesma coisa.
ENTRADA_PADRAO = "/entrar/google"


def _ler(nome: str, padrao: str) -> str:
    return (os.environ.get(nome) or "").strip() or padrao


def url_da_caixa() -> str:
    return _ler("URL_DA_CAIXA", CAIXA_PADRAO)


def url_de_entrada() -> str:
    return _ler("URL_DE_ENTRADA", ENTRADA_PADRAO)
