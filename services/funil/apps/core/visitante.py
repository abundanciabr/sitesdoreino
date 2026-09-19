# apps/core/visitante.py
"""Quem é este navegador — um número opaco, e nada mais que isso.

O PROBLEMA QUE ISTO FECHA
-------------------------
Antes de `pedido.criado` a plataforma é cega. Ninguém sabe quantas pessoas
abriram a vitrine, e ninguém sabe que a pessoa que comprou hoje é a mesma que
leu a página três vezes na semana passada. Sem um identificador estável do
visitante anônimo não existe funil para medir nem venda para atribuir.

O QUE ELE É, E O QUE ELE DELIBERADAMENTE NÃO É
-----------------------------------------------
É um UUID4 sorteado por esta célula e devolvido num cookie de primeira parte.
Não há nada dentro dele: nem e-mail, nem IP, nem impressão digital do
navegador, nem qualquer coisa de que se possa voltar à pessoa. Ele serve para
CONTAR gente, nunca para DESCREVER gente, e a diferença é a razão de o valor
ser sorteado em vez de derivado.

`HttpOnly`, e essa é a parte que parece detalhe e não é. O JavaScript da página
não lê este cookie: quando a telemetria do navegador precisar do número, quem o
entrega é o servidor, no corpo da página, a partir de `request.id_do_visitante`.
Um cookie de identidade legível por script é um cookie roubável por script.

QUEM VOLTA É A MESMA PESSOA
---------------------------
Cookie válido recebido significa nenhum `Set-Cookie` na resposta. Reescrever o
cookie a cada visita apagaria exatamente aquilo que ele existe para medir, e o
defeito seria invisível: o site continuaria funcionando e todo visitante
recorrente viraria um visitante novo.

Valor que não é um UUID4 na forma canônica não é nosso e não vira identidade.
Ele é descartado em silêncio e um número novo é sorteado no lugar: adulterar o
cookie no navegador não derruba a página, e também não engana a contagem.

O QUE ELE NÃO ENCOSTA
---------------------
Não toca `meshcraft_sessao` (quem assina sessão é a célula `identidade`) nem o
cookie de `ver_como`. O visitante anônimo é ortogonal à pessoa logada: quem
entrou também tem um número de visitante, e os dois respondem a perguntas
diferentes.

Rota de máquina não ganha cookie. A lista vem de `middleware.ROTAS_DE_MAQUINA`
em vez de ser reescrita aqui, porque duas listas com o mesmo propósito divergem
(Lei 3): a rota de máquina que nascer amanhã já entra isenta. `Set-Cookie` numa
resposta de `/static/` é cache envenenado esperando acontecer, e num
`/sitemap.xml` é um número de visitante gasto com um robô.

CACHE: A DECISÃO JÁ ESTAVA TOMADA NESTA CÉLULA
-----------------------------------------------
Este middleware não mexe em `Cache-Control` nem em `Vary`, e a omissão é
deliberada. `tests/test_sessao_no_site.py::test_pagina_de_visitante_continua_
cacheavel` decidiu em 26/08/2026 que cookie de medição não pode custar o cache
da vitrine. Quem não pode ser guardado por proxy é a página que mostrou o NOME
de alguém, e essa continua saindo com `private, no-store` pelo
`_marcar_variacao_por_pessoa`. Um `no-store` aqui tiraria o cache da vitrine
inteira para ganhar nada: a borda não guarda resposta com `Set-Cookie`.
"""

import uuid

from django.conf import settings

from apps.core.middleware import ROTAS_DE_MAQUINA

#: O nome do cookie, na convenção da casa (`meshcraft_sessao`,
#: `meshcraft_ver_como`). Não é assinado, e não precisa ser: ele não carrega
#: autoridade nenhuma. Forjá-lo só embaralha a própria contagem de quem forjou.
COOKIE = "meshcraft_visitante"

#: Um ano. A pergunta que este número responde ("esta pessoa já esteve aqui?")
#: só tem valor em escala de meses; uma validade curta transformaria visitante
#: recorrente em visitante novo por decurso de prazo.
VALIDADE_EM_SEGUNDOS = 60 * 60 * 24 * 365


def id_valido(valor: str) -> str:
    """O número recebido, se ele for um dos nossos. Caso contrário `""`.

    Fail-closed na forma, como o `disfarce_valido` do `ver_como`: exige o UUID
    **4** na forma **canônica** em minúsculas, que é a única que esta célula
    emite. As outras formas que a biblioteca aceita (chaves, `urn:uuid:`, hex
    sem hífen, maiúsculas) são recusadas de propósito, porque nenhuma delas
    saiu daqui e aceitá-las faria o mesmo visitante ser contado duas vezes
    conforme a forma escrita no navegador.
    """
    try:
        lido = uuid.UUID(valor)
    except ValueError:
        return ""
    if lido.version != 4 or str(lido) != valor:
        return ""
    return valor


class IdentidadeDoVisitante:
    """Middleware. Ver a docstring do módulo para a regra e o porquê de cada
    restrição.

    Entra DEPOIS do `SiteResolutionMiddleware`, e a ordem é a regra, não
    estilo. Host não cadastrado morre em 404 lá em cima ([INV-P11]) e nunca
    chega aqui: nenhum número de visitante é gasto com um domínio que não é
    nosso. E o `path_info` que este middleware lê já veio sem o prefixo de
    idioma, que é a forma em que a isenção de rota de máquina casa
    (`armadilhas/086`: middleware que reescreve caminho tem DOIS caminhos na
    mesma requisição).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info.startswith(ROTAS_DE_MAQUINA):
            return self.get_response(request)

        recebido = id_valido(request.COOKIES.get(COOKIE, ""))
        # Antes da view: quem vier depois (a telemetria do funil) lê daqui.
        request.id_do_visitante = recebido or str(uuid.uuid4())

        resposta = self.get_response(request)
        if not recebido:
            resposta.set_cookie(
                COOKIE,
                request.id_do_visitante,
                max_age=VALIDADE_EM_SEGUNDOS,
                httponly=True,
                samesite="Lax",
                # `not DEBUG` e não `request.is_secure()`, e a escolha é
                # medida: esta célula não declara `SECURE_PROXY_SSL_HEADER`
                # (TAR-508), então `is_secure()` responde False em produção,
                # porque o TLS termina no Traefik. O cookie sairia sem
                # `Secure` justamente onde ele precisa sair com. `not DEBUG`
                # é determinístico e é a mesma régua do `CSRF_COOKIE_SECURE`
                # das outras células.
                secure=not settings.DEBUG,
            )
        return resposta
