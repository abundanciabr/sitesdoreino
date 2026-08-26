# tests/test_fuso_horario.py
# Guarda do fuso desta célula — e ele nasce fechando um falso-verde, não um vazio.
#
# Esta é a célula onde o defeito do fuso FOI DESCOBERTO (EVO-21, 24/08/2026), e a
# `ARMADILHAS-OPERACAO.md` §9 a listava entre as "corrigidas COM GUARDA QUE MORDE".
# O guarda existia — `test_a_data_do_aviso_sai_no_fuso_e_no_formato_de_quem_le`, em
# `tests/test_inv_aviso_e_so_do_dono.py` — e ele NÃO mordia para o fuso. Medido em
# 26/08/2026, com Postgres de verdade: apagando `TIME_ZONE` do `config/settings.py`,
# aquele teste continua VERDE (`1 passed`).
#
# A razão é sutil e vale aprender: ele compara a página com
# `timezone.localtime(aviso.criado_em)` — a MESMA conversão que o template faz. Apague
# a linha e os dois lados vão juntos para Chicago; a igualdade se mantém. Ele prova o
# FORMATO (`d/m/Y H:i` em vez de `Aug. 24, 2026, 9 a.m.`) e prova que o template
# respeita o fuso configurado — mas não prova QUAL é o fuso configurado. Aquele teste
# não está errado no que faz; só cobre menos do que o nome dele promete, e a §9
# acreditou na promessa.
#
# A cura é a que a armadilha/099 já prescrevia e que este arquivo aplica: comparar com
# um valor ANCORADO (`-03:00` e uma data escrita), nunca com o resultado da própria
# conversão que se quer testar. Guarda que usa o objeto medido como régua não mede
# nada — é a mesma família do `@if [ -f .importlinter ]`.
#
# O guarda não mede a linha (isso seria conferir o próprio texto) — mede o
# COMPORTAMENTO que ela compra: um instante gravado em UTC tem de voltar em horário
# de Brasília na hora de exibi-lo. Sem `TIME_ZONE` vale o default de fábrica do
# Django, `America/Chicago`: cinco horas atrás, capaz de trocar até o DIA perto da
# virada, sem erro nenhum — CI verde, deploy verde, `/healthz` 200 e a data errada
# na tela. Foi assim que a `sugestoes` foi pega em 24/08/2026 (EVO-21).
# Receita completa: armadilhas/099.
#
# O instante é escolhido para trocar de DIA entre os dois fusos: 04:00 UTC é 01:00
# do dia 25 em São Paulo (−03:00) e 23:00 do dia 24 em Chicago (−05:00). Assim o
# guarda não acusa um número torto — acusa a data errada, que é o estrago real.
from datetime import datetime, timedelta, timezone as fuso_padrao

from django.utils import timezone

INSTANTE_UTC = datetime(2026, 8, 25, 4, 0, tzinfo=fuso_padrao.utc)


def test_a_data_que_se_le_e_a_do_dia_no_brasil():
    local = timezone.localtime(INSTANTE_UTC)

    assert local.utcoffset() == timedelta(hours=-3), (
        f"o fuso de exibição não é o de Brasília: offset {local.utcoffset()}. "
        'Falta `TIME_ZONE = "America/Sao_Paulo"` em config/settings.py?'
    )
    assert (
        local.strftime("%d/%m/%Y %H:%M") == "25/08/2026 01:00"
    ), f"04:00 UTC é 25/08 01:00 no Brasil, saiu {local:%d/%m/%Y %H:%M}"


def test_o_armazenamento_continua_em_utc(settings):
    """O fuso é só de EXIBIÇÃO. Se `USE_TZ` cair, o banco passa a guardar naive e a
    conversão acima vira mentira — a dupla anda junta."""
    assert settings.USE_TZ is True
    assert timezone.now().utcoffset() == timedelta(
        0
    ), "timezone.now() deixou de ser UTC — o armazenamento saiu do lugar"
