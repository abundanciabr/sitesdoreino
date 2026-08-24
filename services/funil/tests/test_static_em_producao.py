"""O estático que a página PEDE tem de ser SERVIDO — na configuração de produção.

Medido ao vivo em 24/08/2026, antes deste arquivo existir:

    https://basileiatoutheou.org/static/funil/api.js  -> 404
    https://meshcraft.top/static/funil/api.js         -> 404
    https://basileiatoutheou.org/healthz              -> 200

As duas landings carregam exatamente esse `<script>` e a ilha Alpine chama
`api.post(...)` logo abaixo: sem o arquivo, `api` não existe e o formulário
"Quero receber novidades" morria no navegador — em silêncio para o visitante.
O `/healthz` a 200 no mesmo host é o que localiza a falha: os dois caminhos
saem pela MESMA isenção do CONV-SITE, e a diferença entre eles era só uma —
`/healthz` tinha rota no urlconf, `/static/` não tinha.

Por que a suíte não pegou isso antes, e o que mudou aqui: os testes que
existiam mediam o SETTING (`STATIC_URL`/`STATICFILES_DIRS`, que sempre
estiveram certos) ou a isenção do middleware com um espião no lugar da view
(`test_d6_roteamento`) — ou seja, tudo MENOS a única coisa que o visitante
sente, a resposta HTTP. Estes testes medem só isso, e pelo caminho de
produção: `DEBUG=0`, urlconf real, cadeia de middleware real.
"""

import mimetypes
import re
from pathlib import Path

import pytest
from django.conf import settings

from tests.conftest import HOST_A, HOST_MESH

# Só o que o BROWSER vai buscar sozinho: `src=`/`href=` apontando para
# /static/. É de propósito que o scanner leia o HTML servido em vez de uma
# lista fixa — página nova que carregar um estático novo entra nesta prova
# sem ninguém lembrar de atualizar o teste.
RE_ESTATICO_PEDIDO = re.compile(r'(?:src|href)="(/static/[^"]+)"')

ORIGEM = Path(settings.STATICFILES_DIRS[0])


def corpo(resposta) -> bytes:
    """`django.views.static.serve` devolve `FileResponse` (streaming) — não tem
    `.content`. Este helper aceita as duas formas para o teste não amarrar na
    implementação de quem serve."""
    if resposta.streaming:
        return b"".join(resposta.streaming_content)
    return resposta.content


def test_a_suite_roda_na_configuracao_de_producao():
    """Cadeado da premissa: sem isto, este arquivo poderia medir o modo DEBUG.

    Com `DEBUG=1` o `runserver` serve estáticos por conta própria e um 200
    aqui não diria NADA sobre produção (uvicorn, `DEBUG=0`) — foi exatamente
    essa a ilusão que deixou o bug passar. O Django força `DEBUG=False` na
    suíte; aqui isso vira asserção, não suposição.
    """
    assert settings.DEBUG is False


def test_o_api_js_da_landing_responde_200_com_o_conteudo_EXATO_do_arquivo(client):
    """O caso medido em produção, direto: 404 → 200, com os bytes certos.

    Sem `rede`: a isenção do CONV-SITE tira `/static/` antes de qualquer
    resolução de Host, então este caminho não fala com o catálogo — e o teste
    prova isso de graça (mock nenhum registrado, e mesmo assim passa).
    """
    resposta = client.get("/static/funil/api.js", HTTP_HOST=HOST_A)

    assert resposta.status_code == 200, (
        "/static/funil/api.js respondeu "
        f"{resposta.status_code} — as landings carregam este arquivo e a ilha "
        "Alpine chama api.post() logo abaixo: sem ele o formulário morre no "
        "navegador, sem erro visível para o visitante."
    )
    assert corpo(resposta) == (ORIGEM / "funil" / "api.js").read_bytes()
    # Tipo derivado do ARQUIVO, não um fallback genérico: `.js` servido como
    # text/html (a cara de uma página de erro) o browser não executa.
    assert resposta["Content-Type"] == mimetypes.guess_type("api.js")[0]


@pytest.mark.parametrize(
    "caminho,host",
    [
        ("/", HOST_A),  # landing de site monolíngue
        ("/pt-br/", HOST_MESH),  # landing i18n
    ],
)
def test_todo_estatico_que_a_pagina_PEDE_e_realmente_servido(
    client, rede, caminho, host
):
    """A prova que não envelhece: varre o HTML servido e busca cada estático.

    Um teste que citasse `api.js` pelo nome ficaria verde no dia em que uma
    página passasse a carregar um `.css` ou um segundo `.js` que ninguém serve
    — o mesmo buraco, com outro arquivo dentro.
    """
    html = client.get(caminho, HTTP_HOST=host).content.decode()
    pedidos = RE_ESTATICO_PEDIDO.findall(html)

    # Instrumentação (INV-CI01 na escala de um teste): scanner que não acha
    # nada passaria como "página limpa" e a prova viraria carimbo.
    assert pedidos, f"{caminho} não pediu nenhum estático — o scanner cegou"

    for url in pedidos:
        resposta = client.get(url, HTTP_HOST=host)
        assert resposta.status_code == 200, (
            f"{caminho} carrega {url}, e {url} respondeu "
            f"{resposta.status_code} em produção (DEBUG=0)."
        )
        relativo = url[len(settings.STATIC_URL) :]
        assert corpo(resposta) == (ORIGEM / relativo).read_bytes()


def test_servir_estatico_NAO_depende_do_collectstatic_ter_rodado():
    """Declaração viva de qual diretório é a fonte da verdade.

    O `RUN python manage.py collectstatic --noinput || true` do Dockerfile
    FALHA em todo build (não há `DJANGO_SECRET_KEY` em tempo de build, e o
    `settings.py` é fail-hard) — o `|| true` engole o erro e a imagem sobe com
    `STATIC_ROOT` vazio. Qualquer solução que servisse de `STATIC_ROOT`
    continuaria devolvendo 404 em produção, com todos os testes verdes. Servir
    do diretório-FONTE (que o `COPY . .` põe na imagem) é o que fecha o bug de
    verdade; se um dia esta linha inverter, é aqui que a inversão para.
    """
    assert not (settings.STATIC_ROOT).exists() or not any(
        Path(settings.STATIC_ROOT).iterdir()
    ), (
        "STATIC_ROOT existe e tem conteúdo NESTA máquina — o teste acima está "
        "medindo o diretório-fonte por sorte. Confirme o document_root da rota."
    )
    assert (ORIGEM / "funil" / "api.js").is_file()


def test_estatico_inexistente_e_404_nunca_200_com_corpo_errado(client):
    assert (
        client.get("/static/funil/nao-existe.js", HTTP_HOST=HOST_A).status_code == 404
    )


def test_a_rota_de_estatico_nao_serve_arquivo_de_fora_do_diretorio(client):
    """Travessia de diretório: `/static/../config/settings.py` não pode vazar.

    A rota é pública e o padrão da URL é `.*` — sem esta prova, "serve o
    diretório-fonte" seria "serve o código-fonte".

    A resposta é **400**, não 404: o `safe_join` do Django levanta
    `SuspiciousFileOperation` (logado em `django.security`) antes de olhar o
    disco. É mais forte que um 404 — recusa explícita e auditável, em vez de
    "não achei" — e está congelado aqui com o número certo justamente para
    ninguém "consertar" o teste afrouxando a asserção para `!= 200`.
    """
    resposta = client.get("/static/funil/../../config/settings.py", HTTP_HOST=HOST_A)
    assert resposta.status_code == 400
    assert b"SECRET_KEY" not in corpo(resposta)


def test_estatico_continua_sendo_rota_de_MAQUINA_e_nunca_se_localiza(client, rede):
    """D6/guarda 2: `/pt-br/static/...` é 404, e continua sendo depois do fix.

    O resolver de idioma decapa o prefixo em `path_info` ANTES da resolução de
    URL — quer dizer que uma rota de estático ingênua nasceria alcançável por
    `/{idioma}/static/...`, publicando uma URL de máquina por idioma (conteúdo
    duplicado para robô, superfície nova para ninguém). É o mesmo cuidado que
    o `sitemap.xml` já tinha; `test_d6_roteamento` cobre o caso pela lista, e
    aqui ele fica ao lado do 200 que ele contrasta.
    """
    assert (
        client.get("/pt-br/static/funil/api.js", HTTP_HOST=HOST_MESH).status_code == 404
    )
    # E o caminho nu do MESMO host multilíngue segue servindo — a matriz D1
    # não redireciona rota de máquina para /{idioma}/.
    assert client.get("/static/funil/api.js", HTTP_HOST=HOST_MESH).status_code == 200
