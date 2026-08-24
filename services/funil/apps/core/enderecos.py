# apps/core/enderecos.py
"""Os dois endereços da Caixa que este site precisa conhecer — e só eles.

Lei do assunto: `docs/decisoes/DECISAO-onde-mora-a-sessao.md`.

Por que num módulo próprio, e não cravados no template: no dia em que a
identidade mudar de casa (a célula dedicada, quando a escola nascer), **este
arquivo é a mudança inteira do lado do site** — duas variáveis de ambiente, sem
tocar view, template ou middleware. Endereço cravado em `<a href>` transformaria
aquela mudança numa caça a strings espalhadas.

**Lidos NO PONTO DE USO, com default, nunca `env()` fail-hard.** São destino de
link, não credencial: faltar a variável não pode derrubar a vitrine do site nem
fechar a página. O default é o endereço real de hoje, então em dev e no CI tudo
funciona sem env nenhum.

Não confundir com `SUGESTOES_API_URL` (em `clients.py`): aquele é a rede interna
do Docker, por onde o SERVIDOR pergunta. Estes dois são endereços públicos, por
onde o NAVEGADOR da pessoa caminha.
"""

import os

# Onde a pessoa que já entrou vai ao clicar no próprio nome.
CAIXA_PADRAO = "/forms/sugestoes/"

# A rota que manda direto ao Google, sem passar pela porta da Caixa: quem clica
# no botão do site já decidiu entrar, e uma segunda tela de "Entrar com Google"
# seria um clique a mais para dizer a mesma coisa.
ENTRADA_PADRAO = "/forms/sugestoes/entrar/google"


def _ler(nome: str, padrao: str) -> str:
    return (os.environ.get(nome) or "").strip() or padrao


def url_da_caixa() -> str:
    return _ler("URL_DA_CAIXA", CAIXA_PADRAO)


def url_de_entrada() -> str:
    return _ler("URL_DE_ENTRADA", ENTRADA_PADRAO)
