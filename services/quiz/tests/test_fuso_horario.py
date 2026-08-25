"""Guarda de fuso horário da célula quiz.

Por que existe: `USE_TZ = True` diz apenas "armazene em UTC". Quem decide o
horário que o usuário LÊ é `TIME_ZONE`, e sem essa linha vale o default de
fábrica do Django — `America/Chicago`. A falha é silenciosa até a primeira data
aparecer numa tela (a `sugestoes` foi pega assim, EVO-21/24-08-2026), e o quiz é
a célula com maior chance de mostrar data: o resultado do quiz.

Estes testes provam COMPORTAMENTO, não a existência da linha: se alguém apagar
`TIME_ZONE` do `config/settings.py`, o instante escolhido aqui muda de DIA, não
só de hora — que é exatamente o estrago que o usuário veria.
"""

from datetime import datetime, timedelta, timezone as tz_stdlib

from django.template import engines
from django.utils import timezone

# Instante escolhido a dedo: 04:00 UTC cai em dias DIFERENTES em São Paulo
# (25/08, 01:00, offset −03:00) e em Chicago (24/08, 23:00, offset −05:00).
# Qualquer regressão para o default de fábrica troca a data na tela, não só a hora.
INSTANTE_UTC = datetime(2026, 8, 25, 4, 0, tzinfo=tz_stdlib.utc)


def test_horario_local_da_celula_esta_tres_horas_atras_de_utc():
    local = timezone.localtime(INSTANTE_UTC)

    assert local.utcoffset() == timedelta(hours=-3), (
        "o horário local desta célula não é o de Brasília (−03:00): "
        f"offset={local.utcoffset()}. Faltou `TIME_ZONE` em config/settings.py?"
    )


def test_a_data_que_o_usuario_le_e_a_do_dia_no_brasil():
    local = timezone.localtime(INSTANTE_UTC)

    assert local.strftime("%d/%m/%Y %H:%M") == "25/08/2026 01:00", (
        "a data local mudou de dia — o usuário brasileiro veria o dia errado: "
        f"{local.strftime('%d/%m/%Y %H:%M')}"
    )


def test_template_renderiza_a_data_no_formato_brasileiro():
    """O caminho real: o motor de template converte datetime aware para o fuso
    corrente sozinho. Se `TIME_ZONE` estiver errado, a tela mente sem avisar."""
    template = engines["django"].from_string('{{ quando|date:"d/m/Y H:i" }}')

    renderizado = template.render({"quando": INSTANTE_UTC}).strip()

    assert (
        renderizado == "25/08/2026 01:00"
    ), f"o template renderizou {renderizado!r} em vez de '25/08/2026 01:00'"


def test_armazenamento_continua_em_utc():
    """Contraprova: o fuso de exibição não pode ter virado fuso de gravação."""
    from django.conf import settings

    assert settings.USE_TZ is True
    assert timezone.now().utcoffset() == timedelta(0)
