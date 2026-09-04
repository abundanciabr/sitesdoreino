# apps/encomendas/tasks.py
"""O batimento: de minuto em minuto, o tique reavalia a fila de cada site.

Plano §8.6: *"um tique por minuto reavalia: ofertas expiradas, encomendas para
abrir, prazos vencidos (abandono), aprovações tácitas, SLAs de revisão, pausas
vencidas. **Nada agendado individualmente.**"* Deste degrau nascem os dois
primeiros; os outros quatro se penduram aqui quando chegarem (Fases 3 e 5), e a
forma já está pronta para eles.

**Este arquivo é fino de propósito, e a finura é a garantia.** Toda a regra mora
em `tique.rodar(agora, site_id=...)`, que é função de (estado, `agora`) e não
sabe o que é Huey. O que este módulo acrescenta são as duas únicas coisas que
uma task precisa ter e uma função pura não pode ter: **quem lê o relógio** e
**para quais sites**. É a mesma separação do motor, e é ela que faz o simulador
de cem alunos (degrau 2.6) rodar cem dias de fila sem Redis, sem worker e sem
esperar cem minutos.

**Rodar duas vezes no mesmo minuto é seguro** ([INV-ENC-J10]): o tique filtra
pelo que ainda está pendente, e o que já foi fechado não aparece no filtro.
Importa porque acontece: durante um deploy há dois workers de pé por alguns
segundos, e a trava por encomenda (`select_for_update`) serializa os dois sem
que nenhum precise saber do outro.
"""

import logging

from django.utils import timezone
from huey import crontab

from config.huey import huey

from . import tique

logger = logging.getLogger(__name__)


def bater_o_tique() -> dict[str, tique.Tique]:
    """Uma passada do tique em cada site instalado. O gesto inteiro, sem Huey.

    Separada da task de propósito: é esta função que o teste chama, que o
    `manage.py` de um plantão futuro poderia chamar à mão, e que o simulador do
    degrau 2.6 vai chamar cem vezes seguidas com `agora` andando. A task abaixo
    só a agenda.

    **`agora` é lido UMA VEZ, aqui, e desce por argumento até o fim.** Se cada
    módulo lesse o próprio relógio, duas encomendas da mesma passada teriam
    prazos separados por milissegundos, e o motor deixaria de ser função de
    (estado, `agora`) — a propriedade que o plano §7.4 exige e que todos os
    guardas de justiça usam para medir.

    Um site que estoura (parâmetro faltando, banco fora) não derruba os outros:
    o erro é registrado e a varredura continua. A direção importa e é a mesma da
    célula vizinha — uma escola sem régua é uma escola parada, nunca a plataforma
    inteira parada.
    """
    agora = timezone.now()
    resultados: dict[str, tique.Tique] = {}
    for site_id in tique.sites_com_parametros():
        try:
            resultados[site_id] = tique.rodar(agora, site_id=site_id)
        except Exception:  # noqa: BLE001 - um site torto não para os outros
            logger.exception("o tique da fila falhou no site %s", site_id)
    return resultados


@huey.periodic_task(crontab(minute="*"))
def tique_periodico() -> dict[str, tique.Tique]:
    """De minuto em minuto, para sempre. O único agendamento desta célula.

    O worker é `python manage.py run_huey` — entrada canônica, e a única que faz
    `django.setup()` + autodiscover de `tasks.py` (`armadilhas/030`). O serviço
    dele no compose nasce no degrau 2.10 (TAR-128), com o resto da célula.

    **Um agendamento, e ele não conhece nenhuma oferta.** É a diferença entre
    este desenho e o que a lei proíbe: aqui existe UM `crontab` fixo, que
    pergunta ao banco o que está vencido. Um timer por oferta seria N
    agendamentos vivos fora do banco, e cada um deles some em silêncio num
    deploy, levando junto a única coisa que faria aquela encomenda voltar para a
    fila.
    """
    return bater_o_tique()
