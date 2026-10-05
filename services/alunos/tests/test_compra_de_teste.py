import pytest

from apps.matriculas.handlers import ao_pagamento_aprovado
from apps.matriculas.models import Matricula
from apps.matriculas.services import como_o_painel_ve


@pytest.mark.django_db
@pytest.mark.parametrize("ambiente,origem", [("sandbox", "teste"), ("producao", "comprou")])
def test_ambiente_do_pagamento_chega_ao_placar(ambiente, origem):
    dados = {
        "platform_site_id": "escola", "order_id": "pedido",
        "product_id": "curso", "provider": "appmax",
        "provider_reference_id": "pagamento",
        "customer": {"email": "aluno@example.test", "name": "Aluno"},
        "ambiente": ambiente,
    }
    ao_pagamento_aprovado(dados)
    ao_pagamento_aprovado(dados)
    matricula = Matricula.objects.get(order_id="pedido")
    assert matricula.status == "ativa"
    assert matricula.em_teste is (ambiente == "sandbox")
    assert como_o_painel_ve(matricula)["origem"] == origem

