# apps/core/mudou_de_casa.py — os endereços que a gestão deixou para trás
"""As telas de gestão saíram desta célula; os endereços delas continuam vivos.

Lei: `docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md` (28/08/2026).
Decisão do mantenedor: *"não vamos espalhar painéis ou gestão por aí, tudo será
em /admin"*.

**Redirecionar, e não apagar.** Um 404 aqui puniria quem salvou o endereço, e
quem salvou foi justamente quem mais usava a tela. O redirecionamento é
permanente (301) porque a mudança é permanente — e é o que faz o navegador
parar de perguntar por aqui.

**O destino é um caminho ABSOLUTO cravado, e isso é deliberado.** Todo endereço
desta célula sai de `reverse()`, porque `FORCE_SCRIPT_NAME` é quem carrega o
prefixo público (`armadilhas/029` e `/081`). Este é a exceção que confirma a
regra: o destino não pertence a esta célula, e nenhum `reverse()` daqui saberia
montá-lo. As duas superfícies vivem sob o MESMO host (`meshcraft.top`, roteadas
pelo mesmo Traefik), então o caminho absoluto basta e nada de host precisa
viajar em env nenhum.
"""

from django.http import HttpResponse, HttpResponsePermanentRedirect

from .moderacao import exige_staff

# A casa nova. Caminho absoluto de propósito — ver o docstring do módulo.
A_GESTAO_AGORA = "/admin/caixa/"

# O que uma aba velha ainda aberta lê ao tentar salvar. `410 Gone` e não 405:
# o método não é o problema — o formulário é que não existe mais em lugar
# nenhum desta célula.
NADA_FOI_SALVO = (
    "Esta tela mudou de casa e não salva mais nada.\n\n"
    "O que você acabou de enviar NÃO foi guardado. A gestão da Caixa mora em "
    f"{A_GESTAO_AGORA} — abra a ideia por lá e refaça o que você ia fazer.\n\n"
    "Esta página provavelmente estava aberta desde antes da mudança; um F5 "
    "aqui não resolve."
)


@exige_staff
def mudou_de_casa(request, ator, sugestao_id: int | None = None):
    """Qualquer endereço antigo da gestão leva para a casa nova.

    Uma view só para todos eles: as três abas e as cinco telas de moderação
    viraram seções da MESMA página do Admin, então mandar cada uma para um
    lugar diferente prometeria uma correspondência que não existe mais.
    `sugestao_id` entra e é ignorado pelo mesmo motivo — o destino é a casa,
    não a sala.

    **Continua atrás do crachá**, e isso não é zelo: quem não é da equipe leva
    403 antes de saber para onde a gestão foi. O redirecionamento é cortesia
    para quem já tinha acesso, nunca um mapa para quem não tem. E o decorador é
    o que faz o guarda de crachá (tests/test_inv_so_staff_modera.py) continuar
    contando estas rotas sozinho, sem ninguém precisar cadastrá-las.

    **POST não redireciona, RECUSA — e essa diferença é o ponto.** Até
    30/08/2026 esta view era `@require_GET`, o que bastava enquanto os
    endereços aposentados eram só de leitura. As telas de moderação trouxeram
    três de ESCRITA (mudar fase, avaliar, assinar), e aí um 301 seria pior que
    um erro: o navegador converte POST em GET no destino, a pessoa cairia na
    página nova e leria aquilo como "salvou". Falso-verde de produto
    (`RETROSPECTIVA-FASE-D` §1) — a resposta de sucesso descrevendo um efeito
    que não aconteceu. Quem enviou precisa ler que nada foi salvo.
    """
    if request.method != "GET":
        return HttpResponse(NADA_FOI_SALVO, status=410, content_type="text/plain")
    return HttpResponsePermanentRedirect(A_GESTAO_AGORA)
