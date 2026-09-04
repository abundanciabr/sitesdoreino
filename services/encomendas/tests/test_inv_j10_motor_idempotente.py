"""[INV-ENC-J10] Reexecutar o motor sem mudança de estado não cria oferta nova.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §5 (justiça).
Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §7.4 (*"o motor é função de
(estado atual, agora); rodar duas vezes seguidas não cria duas ofertas"*), §8.6
(*"nada agendado individualmente"*) e o **cenário 15 do anexo B**: *"processo cai
com ofertas pendentes → ao voltar, relógios corretos, nenhuma oferta
duplicada"*.

**Este invariante é o que torna a fila operável.** Os outros nove dizem quem
recebe; este diz que a máquina pode ser desligada, atualizada, reiniciada e
duplicada sem que ninguém perceba. É a diferença entre um sistema que só está
certo quando tudo corre bem e um que está certo no pior dia.

POR QUE NÃO EXISTE TIMER AGENDADO — E POR QUE ISSO SE MEDE AQUI
----------------------------------------------------------------
O caminho óbvio, ao criar uma oferta que vence em três horas úteis, é agendar
alguma coisa para daqui a três horas. Um timer agendado vive FORA do banco: na
fila do Redis, ou na memória de um processo. O deploy troca o container; o Redis
cai; a máquina reinicia. **Um timer que morre não deixa rastro** — a oferta fica
pendente para sempre, a encomenda nunca volta para a fila, e ninguém recebe erro
nenhum. Verde em todo lugar, fila parada.

A reavaliação periódica não tem esse estado: a verdade inteira está nas colunas
(`Oferta.expira_em`, `Encomenda.status`, o histórico). Este arquivo mede
exatamente isso, e o guarda mais forte dele é o das seis horas fora do ar: uma
passada só faz o que trezentas e sessenta fariam, porque ela não pergunta "o que
devia ter acontecido às 14h?", pergunta "o que está vencido AGORA?".

A CONTRAPROVA QUE FALTA EM MUITO GUARDA DE IDEMPOTÊNCIA
--------------------------------------------------------
"Rodar duas vezes não muda nada" é verdade trivial para um motor que não faz
nada. Por isso cada guarda daqui tem o par: a PRIMEIRA passada muda o estado (e
o teste afirma o que ela mudou), e só a segunda é inerte.
"""

from datetime import timedelta

from apps.encomendas import motor, tique
from apps.encomendas.models import Encomenda, Oferta

SITE = "escola-a"


def fotografia():
    """O estado inteiro que importa, num objeto comparável.

    Comparar a fotografia toda, e não "a contagem de ofertas", é o que faz este
    guarda continuar valendo quando o degrau 2.5 acrescentar gestos: uma pausa
    aplicada duas vezes, um status mexido de novo, uma data de resposta
    reescrita — tudo isso aparece aqui sem ninguém precisar lembrar de medir.
    """
    return (
        sorted(
            Encomenda.objects.values_list("id", "status", "atualizada_em"),
            key=lambda linha: str(linha[0]),
        ),
        sorted(
            Oferta.objects.values_list(
                "id", "encomenda_id", "aluno_id", "resultado", "expira_em", "rodada"
            ),
            key=lambda linha: str(linha[0]),
        ),
    )


# ---------------------------------------------------------------------------
# 1. A SEGUNDA PASSADA É INERTE — no motor e no tique
# ---------------------------------------------------------------------------


def test_rodar_o_motor_duas_vezes_nao_cria_oferta_nova(
    semeado, criar_perfil, criar_encomenda
):
    """A frase da lei, medida na letra: duas passadas, uma oferta.

    A trava real é do banco (o índice único parcial `uma_oferta_pendente_por_encomenda`),
    mas a primeira camada é mais simples: a encomenda sai de `na_fila` ao ser
    oferecida, e a segunda varredura nem a vê. As duas juntas são o desenho.
    """
    encomenda = criar_encomenda()
    agora = encomenda.criada_em
    criar_perfil("pes-1", entrada=agora - timedelta(days=5))

    primeira = motor.rodar(agora, site_id=SITE)
    depois_da_primeira = fotografia()
    segunda = motor.rodar(agora, site_id=SITE)

    assert primeira.quantas_ofertas == 1, "a primeira passada TEM de fazer algo"
    assert segunda.quantas_ofertas == 0
    assert fotografia() == depois_da_primeira
    assert Oferta.objects.count() == 1


def test_rodar_o_tique_duas_vezes_no_mesmo_minuto_nao_muda_nada(
    semeado, criar_perfil, criar_encomenda
):
    """Durante um deploy há dois workers de pé por alguns segundos. Isso acontece.

    A trava por encomenda (`select_for_update`) serializa os dois sem que nenhum
    precise saber do outro, e a fotografia inteira prova que a segunda passada
    não tocou em coluna nenhuma — nem no `atualizada_em`, que é o rastro mais
    fácil de deixar por acidente.
    """
    encomenda = criar_encomenda()
    nasceu = encomenda.criada_em
    criar_perfil("pes-1", entrada=nasceu - timedelta(days=5))

    primeiro = tique.rodar(nasceu, site_id=SITE)
    depois_do_primeiro = fotografia()
    segundo = tique.rodar(nasceu, site_id=SITE)

    assert primeiro.rodada.quantas_ofertas == 1
    assert segundo.ofertas_expiradas == ()
    assert segundo.encomendas_abertas == ()
    assert segundo.rodada.quantas_ofertas == 0
    assert fotografia() == depois_do_primeiro


def test_abrir_duas_vezes_nao_reabre_o_que_ja_abriu(semeado, criar_encomenda):
    """A virada do [INV-ENC-J9] também é idempotente.

    Sem isto, cada minuto de tique escreveria uma linha nova no histórico da
    mesma encomenda aberta — e a transição `aberta` → `aberta` nem existe na
    máquina de estado, então a segunda passada estouraria `TransicaoProibida` no
    worker, de minuto em minuto, para sempre.
    """
    encomenda = criar_encomenda()
    agora = encomenda.criada_em + timedelta(days=2)

    assert tique.abrir_o_que_esperou_demais(agora, site_id=SITE) == (encomenda.pk,)
    assert tique.abrir_o_que_esperou_demais(agora, site_id=SITE) == ()


# ---------------------------------------------------------------------------
# 2. O CENÁRIO 15 DO ANEXO B: o processo cai com ofertas pendentes
# ---------------------------------------------------------------------------


def test_o_reinicio_encontra_os_relogios_exatamente_onde_estavam(
    semeado, criar_perfil, criar_encomenda
):
    """Cenário 15, primeira metade: **relógios corretos**.

    O "reinício" é literal no desenho desta célula: nenhum estado vive no
    processo, então voltar é só chamar o tique de novo. O que se mede é que o
    `expira_em` gravado NÃO se mexe — um motor que recalculasse a expiração ao
    reencontrar uma oferta pendente daria três horas novas a cada deploy, e um
    aluno atento nunca mais perderia um prazo.
    """
    encomenda = criar_encomenda()
    nasceu = encomenda.criada_em
    criar_perfil("pes-1", entrada=nasceu - timedelta(days=5))
    tique.rodar(nasceu, site_id=SITE)
    prazo_original = Oferta.objects.get(encomenda=encomenda).expira_em

    # O processo volta uma hora depois e faz o que sabe fazer: uma passada.
    tique.rodar(nasceu + timedelta(hours=1), site_id=SITE)

    oferta = Oferta.objects.get(encomenda=encomenda)
    assert oferta.expira_em == prazo_original
    assert oferta.resultado == Oferta.Resultado.PENDENTE


def test_o_reinicio_nao_duplica_oferta_nenhuma(semeado, criar_perfil, criar_encomenda):
    """Cenário 15, segunda metade: **nenhuma oferta duplicada**.

    Três encomendas, três alunos, e o tique chamado quatro vezes seguidas como
    se o worker tivesse reiniciado três vezes. No fim, três ofertas — uma por
    encomenda, uma por aluno.
    """
    for i in range(3):
        criar_encomenda(cliente=f"cli-{i}")
    nasceu = Encomenda.objects.earliest("criada_em").criada_em
    for i in range(3):
        criar_perfil(f"pes-{i}", entrada=nasceu - timedelta(days=10 - i))

    for _ in range(4):
        tique.rodar(nasceu, site_id=SITE)

    assert Oferta.objects.count() == 3
    assert Oferta.objects.values("encomenda_id").distinct().count() == 3
    assert Oferta.objects.values("aluno_id").distinct().count() == 3


def test_seis_horas_fora_do_ar_se_resolvem_numa_passada_so(
    semeado, criar_perfil, criar_encomenda
):
    """O guarda mais forte deste arquivo, e o que só a reavaliação periódica passa.

    O worker some por seis horas — deploy travado, Redis fora, máquina
    reiniciada. Quando volta, ele NÃO tem uma fila de trezentos e sessenta
    tiques atrasados para processar: ele pergunta o que está vencido agora, e a
    resposta resolve tudo de uma vez. A oferta que venceu no meio da ausência é
    fechada, a encomenda volta para a fila e o próximo da vez recebe — numa
    passada.

    Com timer agendado, esta mesma cena termina com a oferta pendente para
    sempre e a encomenda parada, sem erro em lugar nenhum.
    """
    encomenda = criar_encomenda()
    nasceu = encomenda.criada_em
    ana = criar_perfil("pes-ana", entrada=nasceu - timedelta(days=30))
    bia = criar_perfil("pes-bia", entrada=nasceu - timedelta(days=20))

    tique.rodar(nasceu, site_id=SITE)
    primeira = Oferta.objects.get(encomenda=encomenda)
    assert primeira.aluno_id == ana.id

    resultado = tique.rodar(primeira.expira_em + timedelta(hours=6), site_id=SITE)

    primeira.refresh_from_db()
    assert resultado.ofertas_expiradas == (primeira.pk,)
    assert primeira.resultado == Oferta.Resultado.EXPIROU
    assert resultado.rodada.quantas_ofertas == 1
    assert (
        Oferta.objects.get(
            encomenda=encomenda, resultado=Oferta.Resultado.PENDENTE
        ).aluno_id
        == bia.id
    )


def test_a_passada_seguinte_a_uma_expiracao_e_inerte(
    semeado, criar_perfil, criar_encomenda
):
    """O tique volta a passar pelo mesmo minuto, e a oferta já fechada fica em paz.

    **É o caso mais comum de todos, e o mais fácil de deixar sem guarda.** O
    tique bate a cada minuto: no minuto em que uma oferta vence ele a fecha, e
    nos sessenta minutos seguintes ele volta a passar por um `expira_em` que
    continua no passado. Se o "só oferta pendente" sumisse, a segunda passada
    tentaria fechar de novo uma oferta `expirou` — e `Oferta.responder` recusa,
    porque oferta fechada é PEDRA. O worker morreria de minuto em minuto, para
    sempre, e nenhuma outra asserção deste arquivo perceberia: elas todas param
    na primeira passada depois do vencimento.

    A regra tem DUAS camadas (o filtro da consulta e a reconferência dentro da
    trava), e foi o arredor de mutação que mostrou por que este guarda precisava
    existir: derrubar as duas de uma vez deixava a suíte inteira verde.
    """
    encomenda = criar_encomenda()
    nasceu = encomenda.criada_em
    criar_perfil("pes-ana", entrada=nasceu - timedelta(days=30))
    criar_perfil("pes-bia", entrada=nasceu - timedelta(days=20))
    tique.rodar(nasceu, site_id=SITE)
    venceu = Oferta.objects.get(encomenda=encomenda).expira_em

    primeira = tique.rodar(venceu, site_id=SITE)
    depois_da_primeira = fotografia()
    segunda = tique.rodar(venceu, site_id=SITE)

    assert len(primeira.ofertas_expiradas) == 1, "a primeira passada TEM de fechar uma"
    assert segunda.ofertas_expiradas == ()
    assert fotografia() == depois_da_primeira


def test_depois_de_uma_passada_nada_fica_vencido_para_tras(
    semeado, criar_perfil, criar_encomenda
):
    """A afirmação universal do "relógios corretos": não sobra prazo vencido.

    Os guardas de cima medem casos; este afirma a propriedade que o cenário 15
    pede, e que continua valendo quando os prazos das Fases 3 e 5 se pendurarem
    no mesmo tique: depois de uma passada, nenhuma oferta pendente está com o
    relógio vencido.
    """
    for i in range(3):
        criar_encomenda(cliente=f"cli-{i}")
    nasceu = Encomenda.objects.earliest("criada_em").criada_em
    for i in range(3):
        criar_perfil(f"pes-{i}", entrada=nasceu - timedelta(days=10 - i))
    tique.rodar(nasceu, site_id=SITE)

    muito_depois = nasceu + timedelta(hours=12)
    tique.rodar(muito_depois, site_id=SITE)

    vencidas = Oferta.objects.filter(
        resultado=Oferta.Resultado.PENDENTE, expira_em__lte=muito_depois
    )
    assert list(vencidas) == []
