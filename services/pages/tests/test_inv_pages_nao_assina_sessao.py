"""Teste-guarda [INV-P12]: a célula `pages` NUNCA assina o cookie de sessão.

Lei: `INVARIANTES.md` [INV-P12] e `DECISAO-celula-de-identidade.md` §6.4 —
*"nenhum código novo pode escrever `request.session`; quem grava o cookie
`meshcraft_sessao` é só a `identidade`"* — herdada por esta célula em
`docs/changespecs/CS-PAGES-0001.md` (contratos permitidos) e no degrau 06 da
escada do `PLANO-PORTFOLIO-DO-ALUNO.md` §5, que diz com todas as letras: a
célula repassa o cookie à `identidade` e nunca assina.

**Por que isso merece um guarda em vez de um combinado escrito:** duas células
assinando o MESMO cookie (`meshcraft_sessao`, `Path=/`) com chaves diferentes
produzem um cabo-de-guerra silencioso — abrir a Prancheta desloga do site,
entrar no site desloga daqui — **sem erro em lugar nenhum, sem log, sem
alarme** (`armadilhas/143`). Ninguém reporta "fui deslogado": as pessoas
reentram e seguem, e a plataforma perde sessão o dia inteiro sem nada acusar.

**E nesta célula a tentação tem nome: a PRANCHETA GUARDA PROGRESSO.** O
critério AC-06 do corredor exige que o aluno marque um item da lista de
conferência, feche o navegador, abra em OUTRO APARELHO e encontre a marcação no
lugar. Toda tela assim precisa responder "o que esta pessoa já marcou?" — e o
caminho de menor esforço para guardar essa lembrança é `request.session[...]`.
Ele funciona em dev, passa em teste de unidade, reprova o próprio AC-06 (sessão
não atravessa aparelho) e, em produção, desloga a plataforma inteira, porque lá
existe um segundo assinante do mesmo cookie. É por isso que o estado vai para o
MODELO, por aluno, do degrau 02 em diante.

O guarda mede a CONFIGURAÇÃO, não a intenção: sem `SessionMiddleware` e sem
`django.contrib.sessions`, `request.session` nem existe. Quem quiser
reintroduzir sessão nesta célula tem de apagar este arquivo — e aí é uma
decisão visível no diff, que é exatamente o ponto.
"""

from django.conf import settings


def test_sem_middleware_de_sessao():
    """`SessionMiddleware` ausente ⇒ `request.session` não existe."""
    assert not any("SessionMiddleware" in m for m in settings.MIDDLEWARE), (
        "a célula pages não pode ter SessionMiddleware — quem assina sessão "
        "é a identidade"
    )


def test_sem_app_de_sessao():
    """`django.contrib.sessions` ausente ⇒ nenhum backend de sessão instalado."""
    assert (
        "django.contrib.sessions" not in settings.INSTALLED_APPS
    ), "a célula pages não pode instalar django.contrib.sessions"


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
        "a célula pages não declara SESSION_ENGINE — quem assina sessão do "
        "site é a identidade (DECISAO-celula-de-identidade §6.4)"
    )


def test_o_cookie_de_csrf_tem_nome_proprio():
    """CSRF com nome de fábrica colide com as células vizinhas.

    Isto não é sessão, mas é o mesmo problema de vizinhança: `meshcraft.top`
    serve o `funil` na raiz, a Caixa em `/forms/sugestoes`, a área
    administrativa em `/admin`, o fórum em `/forum`, as conquistas em
    `/conquistas`, a sala de aula em `/cursos` e esta célula em `/pages` (mais
    a vitrine em `/estudio`). Duas células gravando `csrftoken` no mesmo host é
    uma invalidando o formulário da outra.
    """
    assert settings.CSRF_COOKIE_NAME == "pages_csrf"
    assert settings.CSRF_COOKIE_NAME != "csrftoken"
