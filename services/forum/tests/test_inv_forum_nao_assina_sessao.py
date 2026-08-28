"""Teste-guarda [INV-P12]: a célula `forum` NUNCA assina o cookie de sessão.

Lei: `INVARIANTES.md` [INV-P12] e `DECISAO-celula-de-identidade.md` §6.4 —
*"nenhum código novo pode escrever `request.session`; quem grava o cookie
`meshcraft_sessao` é só a `identidade`"* — herdada por esta célula em
`DECISAO-forum-da-escola.md` §3.

**Por que isso merece um guarda em vez de um combinado escrito:** duas células
assinando o MESMO cookie (`meshcraft_sessao`, `Path=/`) com chaves diferentes
produzem um cabo-de-guerra silencioso — entrar no fórum desloga do site, entrar
no site desloga do fórum — **sem erro em lugar nenhum, sem log, sem alarme**
(`armadilhas/143`). Ninguém reporta "fui deslogado": as pessoas reentram e
seguem, e a plataforma perde sessão o dia inteiro sem nada acusar.

**E neste fórum o risco é maior que o normal**, porque foi um requisito de
login que o criou: o mantenedor pediu explicitamente para estar logado uma vez
só e circular pelo site inteiro sem nunca mais ver tela de login
(`DECISAO-forum-da-escola.md` §2). Uma segunda assinatura de cookie aqui
quebraria exatamente a coisa que justificou construir esta célula em vez de
instalar um fórum pronto.

A tentação concreta que este guarda mata: quando as permissões por área
nascerem, o caminho mais curto para guardar "esta pessoa já foi conferida" é
`request.session[...]`. Funciona em dev, passa em qualquer teste de unidade, e
só quebra em produção — onde há um segundo assinante do mesmo cookie.

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
    ), "a célula forum não pode ter SessionMiddleware — quem assina sessão é a identidade"


def test_sem_app_de_sessao():
    """`django.contrib.sessions` ausente ⇒ nenhum backend de sessão instalado."""
    assert (
        "django.contrib.sessions" not in settings.INSTALLED_APPS
    ), "a célula forum não pode instalar django.contrib.sessions"


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
        "a célula forum não declara SESSION_ENGINE — quem assina sessão do "
        "site é a identidade (DECISAO-celula-de-identidade §6.4)"
    )


def test_o_cookie_de_csrf_tem_nome_proprio():
    """CSRF com nome de fábrica colide com as células vizinhas.

    Isto não é sessão, mas é o mesmo problema de vizinhança: `meshcraft.top`
    serve o `funil` na raiz, a Caixa em `/forms/sugestoes`, a área
    administrativa em `/admin` e o fórum em `/forum`. Duas células gravando
    `csrftoken` no mesmo host é uma invalidando o formulário da outra.
    """
    assert settings.CSRF_COOKIE_NAME == "forum_csrf"
    assert settings.CSRF_COOKIE_NAME != "csrftoken"
