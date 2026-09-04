"""Teste-guarda [INV-P12]: a célula `metricas` NUNCA assina o cookie de sessão.

Lei: `INVARIANTES.md` [INV-P12] e `DECISAO-celula-de-identidade.md` §6.4 —
*"nenhum código novo pode escrever `request.session`; quem grava o cookie
`meshcraft_sessao` é só a `identidade`"*.

**Por que isso merece um guarda em vez de um combinado escrito:** duas células
assinando o MESMO cookie (`meshcraft_sessao`, `Path=/`) com chaves diferentes
produzem um cabo-de-guerra silencioso — entrar aqui desloga do site, entrar no
site desloga daqui — **sem erro em lugar nenhum, sem log, sem alarme**
(`armadilhas/143`). Ninguém reporta "fui deslogado": as pessoas reentram e
seguem, e a plataforma perde sessão o dia inteiro sem nada acusar.

**A tentação, nesta célula, tem forma própria.** Ela vai guardar fatos SOBRE
pessoas: quem se cadastrou, quem completou o quiz, quem escreveu no fórum, quem
virou aluna. A pergunta "de quem é este evento?" aparece em toda linha de
código daqui, e o caminho de menor esforço para respondê-la seria ler a sessão
de quem fez a chamada. Não é assim que esta célula sabe de quem é um fato: **o
identificador da pessoa vem no CORPO do evento, pelo contrato** (o `id` opaco
que a `identidade` publica), e é só isso que a `metricas` conhece. Ela nunca
tem uma pessoa na frente — quem a chama é outra célula, com Bearer de par.

O guarda mede a CONFIGURAÇÃO, não a intenção: sem `SessionMiddleware` e sem
`django.contrib.sessions`, `request.session` nem existe. Quem quiser
reintroduzir sessão aqui tem de apagar este arquivo, e aí é uma decisão
visível no diff, que é exatamente o ponto.
"""

from django.conf import settings


def test_sem_middleware_de_sessao():
    """`SessionMiddleware` ausente ⇒ `request.session` não existe."""
    assert not any("SessionMiddleware" in m for m in settings.MIDDLEWARE), (
        "a célula metricas não pode ter SessionMiddleware — quem assina "
        "sessão é a identidade"
    )


def test_sem_app_de_sessao():
    """`django.contrib.sessions` ausente ⇒ nenhum backend de sessão instalado."""
    assert (
        "django.contrib.sessions" not in settings.INSTALLED_APPS
    ), "a célula metricas não pode instalar django.contrib.sessions"


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
        "a célula metricas não declara SESSION_ENGINE — quem assina sessão "
        "do site é a identidade (DECISAO-celula-de-identidade §6.4)"
    )


def test_nao_ha_autenticacao_de_pessoa_nesta_celula():
    """`django.contrib.auth` também fica de fora, e pela mesma razão.

    Esta célula nunca tem uma pessoa na frente: quem a chama é outra célula,
    com Bearer de par (degraus 7.3 e 7.4). Instalar `auth` aqui abriria a porta
    para um segundo cadastro de pessoas na plataforma, que é a duplicação que a
    célula de identidade existe para impedir.
    """
    assert "django.contrib.auth" not in settings.INSTALLED_APPS
    assert not any("AuthenticationMiddleware" in m for m in settings.MIDDLEWARE)


def test_o_cookie_de_csrf_tem_nome_proprio():
    """CSRF com nome de fábrica colide com as células vizinhas.

    Isto não é sessão, mas é o mesmo problema de vizinhança: `meshcraft.top`
    serve o `funil` na raiz, a Caixa em `/forms/sugestoes`, a área
    administrativa em `/admin`, o fórum em `/forum` e as conquistas em
    `/conquistas`. Duas células gravando `csrftoken` no mesmo host é uma
    invalidando o formulário da outra. Esta célula não tem formulário hoje, e
    o nome próprio entra junto com o resto do molde para não faltar depois.
    """
    assert settings.CSRF_COOKIE_NAME == "metricas_csrf"
    assert settings.CSRF_COOKIE_NAME != "csrftoken"
