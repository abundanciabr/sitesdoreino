"""Quantos dias faltam, para uma pessoa. A ESPERA que substitui a posição.

Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §5.4. O número que o aluno
quer não é "7o da fila", é "em cerca de 3 dias". Posição é uma medida de dentro
da máquina; espera é a única resposta que muda o que a pessoa faz hoje.

**E ela vem NULA quando não há ritmo para medir, nunca inventada.** Este é o
ponto inteiro deste arquivo. Uma estimativa chutada num Mural recém-aberto é
pior que nenhuma: o aluno organiza a semana em cima dela, e a plataforma não
tinha como saber. Nos primeiros meses o normal é `null`, e a tela diz "ainda não
dá para estimar" em vez de um número bonito.

A conta tem duas metades, e as duas são medidas, não arbitradas:

1. **A posição** sai da MESMA ordenação que o motor usa para escolher quem
   recebe (`motor.CHAVE_DA_ORDEM`, a lei §6.2: menos entregas primeiro, empate
   pela data de entrada). Reescrever a ordem aqui seria uma segunda régua, e
   duas réguas divergem no primeiro parâmetro que mudar.
2. **O ritmo** é quantas encomendas foram OFERECIDAS na janela do parâmetro `janela_do_ritmo_da_espera`, nos
   níveis que o título desta pessoa alcança. Encomenda de nível que ela não pode
   pegar não anda a fila dela, e contá-la prometeria uma vez rápida que não
   existe.

Guarda: `tests/test_espera_estimada.py`.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from apps.encomendas import motor
from apps.encomendas.models import (
    Encomenda,
    MudancaDeStatus,
    Parametro,
    PerfilProfissional,
)

# A chave da janela, no vocabulario fechado da lei 3.8. O NUMERO nao mora aqui,
# e a ausencia dele e a regra: `tests/test_parametros_sao_dado.py` reprova
# qualquer numero solto no codigo desta celula, e reprova com razao. Janela curta
# demais devolve nulo na primeira semana morna; longa demais promete o ritmo do
# mes passado para a fila de hoje, e quem decide isso e o dono, por tela.
CHAVE_DA_JANELA = "janela_do_ritmo_da_espera"


def niveis_ao_alcance(titulo_banca: str) -> tuple[str, ...]:
    """Os níveis de encomenda que este título alcança, pela régua do motor.

    Sai de `motor.TITULO_MINIMO_DO_NIVEL` e `motor.ORDEM_DOS_TITULOS`, que são as
    mesmas tabelas que decidem elegibilidade de verdade. Título vazio (quem ainda
    não passou pelo plantão) não alcança nível nenhum.
    """
    meu = motor.ORDEM_DOS_TITULOS.get(titulo_banca, 0)
    return tuple(
        nivel
        for nivel, minimo in motor.TITULO_MINIMO_DO_NIVEL.items()
        if meu >= motor.ORDEM_DOS_TITULOS[minimo]
    )


def posicao_na_fila(perfil: PerfilProfissional, *, site_id: str) -> int | None:
    """Em que lugar da fila esta pessoa está, contando a partir de 1.

    `None` para quem NUNCA ativou a fila. Não é um caso de borda: `data_entrada_fila`
    nulo significa ausência, não atraso (a docstring de `motor.Candidato` diz
    isso com todas as letras), e `motor.CHAVE_DA_ORDEM` recusa ordenar quem não
    tem data. Inventar um lugar para quem não entrou seria prometer uma vez a
    quem não está esperando por nenhuma.

    Quem se pausou ou está trabalhando CONTINUA tendo lugar: a data de entrada é
    dela e só o abandono a altera (lei §6.2, [INV-ENC-J4]). Por isso a conta
    ordena por posse de data, e não por disponibilidade.
    """
    na_fila = [
        candidato
        for candidato in motor.candidatos_do_banco(site_id)
        if candidato.data_entrada_fila is not None
    ]
    for lugar, candidato in enumerate(sorted(na_fila, key=motor.CHAVE_DA_ORDEM), 1):
        if candidato.perfil_id == perfil.id:
            return lugar
    return None


def encomendas_por_dia(
    perfil: PerfilProfissional, agora: datetime, *, site_id: str
) -> float | None:
    """O ritmo recente de encomendas nos níveis que esta pessoa alcança.

    Mede as TRANSIÇÕES para `oferecida` registradas na janela, e não as
    encomendas criadas: o que anda a fila é uma vez chegando a alguém, e uma
    encomenda criada que nunca foi oferecida não andou a fila de ninguém.

    `None` quando nada foi oferecido na janela. Zero seria uma divisão por zero
    disfarçada de resposta.
    """
    niveis = niveis_ao_alcance(perfil.titulo_banca)
    if not niveis:
        return None
    janela = Parametro.inteiro_vigente(CHAVE_DA_JANELA, agora, site_id=site_id)
    quantas = MudancaDeStatus.objects.filter(
        encomenda__site_id=site_id,
        encomenda__nivel__in=niveis,
        para=Encomenda.Status.OFERECIDA,
        em__gte=agora - timedelta(days=janela),
    ).count()
    if quantas == 0:
        return None
    return quantas / janela


def estimar_dias(
    perfil: PerfilProfissional, agora: datetime, *, site_id: str
) -> int | None:
    """Quantos dias, em números redondos, ou `None` quando não dá para medir.

    Arredonda para CIMA: prometer menos do que se sabe é a única direção em que
    o erro machuca de verdade, porque o aluno programa a semana em cima disso.
    """
    ritmo = encomendas_por_dia(perfil, agora, site_id=site_id)
    lugar = posicao_na_fila(perfil, site_id=site_id)
    if ritmo is None or lugar is None:
        return None
    return math.ceil(lugar / ritmo)
