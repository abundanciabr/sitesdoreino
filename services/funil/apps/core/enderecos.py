# apps/core/enderecos.py
"""Os endereços de sessão que este site precisa conhecer — e só eles.

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

Não confundir com `IDENTIDADE_API_URL`/`NOTIFICACOES_API_URL` (em
`clients.py`): aqueles são a rede interna do Docker, por onde o SERVIDOR
pergunta. Estes são endereços públicos, por onde o NAVEGADOR da pessoa caminha.
"""

import os

# Onde a pessoa que já entrou vai ao clicar no próprio nome. Continua sendo a
# Caixa: é a única área logada do site até a escola nascer.
CAIXA_PADRAO = "/forms/sugestoes/"

# A tela de avisos da Caixa — destino do sino (Fase 5 do sininho,
# docs/notificacoes/PLANO-MESTRE.md). Mesma célula de CAIXA_PADRAO (o prefixo
# público sai da MESMA FORCE_SCRIPT_NAME, services/sugestoes/config/
# settings.py), rota nomeada `avisos` em services/sugestoes/config/urls.py —
# lida ali, nunca adivinhada, porque só ela sabe se um dia esse prefixo muda.
AVISOS_PADRAO = "/forms/sugestoes/avisos"

# O FÓRUM da escola — a área pública dele responde sem login desde 30/08/2026.
# Célula `forum`, monolíngue, prefixo próprio no gateway. Entra aqui (e não
# cravado no template) pela mesma razão dos de cima: no dia em que o fórum
# mudar de endereço, a mudança do lado do site é esta linha.
FORUM_PADRAO = "/forum/"

# A BIBLIOTECA PÚBLICA de documentos (`DECISAO-a-area-de-documentos.md`). Mora
# na célula `admin`, mas o caminho público NÃO leva o prefixo `/admin`: são
# dois prefixos de propósito, e só este é isento na porta.
DOCUMENTOS_PADRAO = "/docs/"

# A rota que manda direto ao Google — da célula `identidade`, dona do login do
# site inteiro: quem clica no botão do site já decidiu entrar, e uma segunda
# tela de "Entrar com Google" seria um clique a mais para dizer a mesma coisa.
ENTRADA_PADRAO = "/entrar/google"

# O segundo jeito de entrar (`DECISAO-login-por-senha.md`), também da célula
# `identidade` — o `action` do mini-formulário de senha em `funil/login.html`.
ENTRADA_SENHA_PADRAO = "/entrar/senha"

# A PRANCHETA do portfólio (degrau 18 do PLANO-PORTFOLIO-DO-ALUNO, célula
# `pages`). Único botão da home logada para lá: ele manda nas duas caras do
# endereço, a de quem foi reconhecido e as telas de recusa da porta fail-closed
# (`AGENTS.pages.md`, INV-P12 e AC-05) — a Prancheta se defende sozinha.
PRANCHETA_PADRAO = "/pages/"


def _ler(nome: str, padrao: str) -> str:
    return (os.environ.get(nome) or "").strip() or padrao


def url_da_caixa() -> str:
    return _ler("URL_DA_CAIXA", CAIXA_PADRAO)


def url_dos_avisos() -> str:
    return _ler("URL_DOS_AVISOS", AVISOS_PADRAO)


def url_de_entrada() -> str:
    return _ler("URL_DE_ENTRADA", ENTRADA_PADRAO)


def url_de_entrada_por_senha() -> str:
    return _ler("URL_DE_ENTRADA_SENHA", ENTRADA_SENHA_PADRAO)


def url_do_forum() -> str:
    return _ler("URL_DO_FORUM", FORUM_PADRAO)


def url_dos_documentos() -> str:
    return _ler("URL_DOS_DOCUMENTOS", DOCUMENTOS_PADRAO)


def url_da_prancheta() -> str:
    return _ler("URL_DA_PRANCHETA", PRANCHETA_PADRAO)
