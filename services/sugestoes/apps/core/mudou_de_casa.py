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

from django.http import HttpResponsePermanentRedirect
from django.views.decorators.http import require_GET

from .moderacao import exige_staff

# A casa nova. Caminho absoluto de propósito — ver o docstring do módulo.
A_GESTAO_AGORA = "/admin/caixa/"


@require_GET
@exige_staff
def mudou_de_casa(request, ator):
    """Qualquer endereço antigo da gestão leva para a casa nova.

    Uma view só para todos eles: as três abas e as telas de moderação viraram
    seções da MESMA página do Admin, então mandar cada uma para um lugar
    diferente prometeria uma correspondência que não existe mais.

    **Continua atrás do crachá**, e isso não é zelo: quem não é da equipe leva
    403 antes de saber para onde a gestão foi. O redirecionamento é cortesia
    para quem já tinha acesso, nunca um mapa para quem não tem. E o decorador é
    o que faz o guarda de crachá (tests/test_inv_so_staff_modera.py) continuar
    contando estas rotas sozinho, sem ninguém precisar cadastrá-las.
    """
    return HttpResponsePermanentRedirect(A_GESTAO_AGORA)
