"""Teste-guarda: a célula `admin` NUNCA assina o cookie de sessão do site.

Lei: `DECISAO-celula-de-identidade.md` §6.4 — *"nenhum código novo pode
escrever `request.session`; quem grava o cookie `meshcraft_sessao` é só a
`identidade`"* — herdada por esta célula em `DECISAO-celula-admin.md` §3.

**Por que isso merece um guarda em vez de um combinado escrito:** duas células
assinando o MESMO cookie (`meshcraft_sessao`, `Path=/`) com chaves diferentes
produzem um cabo-de-guerra silencioso — entrar pela área admin desloga do
site, entrar pelo site desloga da área admin — **sem erro em lugar nenhum**. A
`DECISAO-celula-de-identidade` §5 descreve o episódio real em que isso quase
entrou em produção, e o preço de descobrir depois: ninguém reporta "fui
deslogado", as pessoas só reentram e seguem.

A tentação concreta que este guarda mata: quando a porta nascer (PR 3), o
caminho mais curto para guardar "esta pessoa já foi conferida" é
`request.session[...]`. Ele funciona em dev, passa em qualquer teste de
unidade, e só quebra em produção — onde há um segundo assinante do mesmo
cookie.

O guarda mede a CONFIGURAÇÃO, não a intenção: sem `SessionMiddleware` e sem
`django.contrib.sessions`, `request.session` nem existe. Quem quiser
reintroduzir sessão nesta célula tem de apagar este arquivo — e aí é uma
decisão visível no diff, que é exatamente o ponto.
"""

from django.conf import settings


def test_sem_middleware_de_sessao():
    """`SessionMiddleware` ausente ⇒ `request.session` não existe."""
    assert not any(
        "SessionMiddleware" in m for m in settings.MIDDLEWARE
    ), "a célula admin não pode ter SessionMiddleware — quem assina sessão é a identidade"


def test_sem_app_de_sessao():
    """`django.contrib.sessions` ausente ⇒ nenhum backend de sessão instalado."""
    assert (
        "django.contrib.sessions" not in settings.INSTALLED_APPS
    ), "a célula admin não pode instalar django.contrib.sessions"


def test_sem_backend_de_sessao_declarado_pela_celula():
    """Nem por `SESSION_ENGINE` — o caminho que dispensa o app instalado.

    `signed_cookies` (o backend que a `identidade` usa) não precisa de app nem
    de tabela: bastaria a linha de `SESSION_ENGINE` mais o middleware para esta
    célula começar a assinar cookie. O guarda cobre essa porta lateral.

    A conferência é no MÓDULO da célula, não em `django.conf.settings`: o
    Django sempre tem um `SESSION_ENGINE` (o default global de fábrica), então
    perguntar ao objeto de settings responderia "existe" mesmo numa célula que
    nunca o declarou. O que importa é o que ESTE `config/settings.py` escreve.
    """
    import config.settings as settings_da_celula

    assert not hasattr(settings_da_celula, "SESSION_ENGINE"), (
        "a célula admin não declara SESSION_ENGINE — quem assina sessão do "
        "site é a identidade (DECISAO-celula-de-identidade §6.4)"
    )
