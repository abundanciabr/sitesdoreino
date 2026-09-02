"""O modelo de dados das jornadas: os vocabulários fechados, as fronteiras e o
que este PR promete NÃO fazer.

Companheiro de `test_jornadas_travas.py`, que mede as travas do §5. Aqui ficam
as guardas que impedem o motor de nascer torto: assunto inventado, canal
inventado, passo sem canal nenhum, jornada que se liga sozinha no deploy, e o
acoplamento com `apps/eventos` que o §10.7 do plano lista como critério de morte.
"""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.apps import apps as django_apps
from django.db import DataError, IntegrityError, transaction
from django.utils import timezone

from apps.jornadas import models as jornadas
from apps.jornadas.models import (
    Entrega,
    EstadoDoAluno,
    Inscricao,
    Jornada,
    JornadaVersao,
    Passo,
    Preferencia,
)

pytestmark = pytest.mark.django_db

SITE = "site-abc"

CONTRATO = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "eventos"
    / "notificacao.devida.v1.json"
)


def uma_versao():
    jornada = Jornada.objects.create(
        site_id=SITE, slug="boas-vindas", gatilho="identidade.pessoa-cadastrada.v1"
    )
    return JornadaVersao.objects.create(jornada=jornada, numero=1)


def criar_passo(**campos):
    padrao = {
        "jornada_versao": campos.pop("jornada_versao", None) or uma_versao(),
        "ordem": 1,
        "classe": "relacional",
        "canais": ["sino"],
    }
    padrao.update(campos)
    return Passo.objects.create(**padrao)


# ---------------------------------------------------------------------------
# NADA QUE ESTE PR CRIA CONSEGUE MANDAR CARTA PARA NINGUÉM
# ---------------------------------------------------------------------------


def test_a_jornada_nasce_desligada():
    """Ligar uma sequência é decisão do mantenedor, nunca efeito de um deploy.

    Mesma escolha que a `gamificacao` fez com a economia. Sem ela, o PR que
    semeia uma jornada a põe no ar sozinho — e o §8.7.2 é explícito: NENHUM
    preenchimento retroativo, só quem se cadastrar daí em diante recebe.
    """
    jornada = Jornada.objects.create(
        site_id=SITE, slug="boas-vindas", gatilho="identidade.pessoa-cadastrada.v1"
    )
    assert jornada.ativa is False


def test_a_versao_nasce_rascunho():
    versao = uma_versao()
    assert versao.publicada_em is None
    assert versao.publicada is False


# ---------------------------------------------------------------------------
# A FRONTEIRA COM `apps/eventos` — critério de morte §10.7
# ---------------------------------------------------------------------------


def test_nenhum_modelo_de_jornadas_aponta_para_apps_eventos():
    """`apps/jornadas` pode CRIAR a linha de `EnvioRegistrado`, e nada mais.

    Foi o acoplamento que a separação em célula teria impedido por construção, e
    que aqui só é impedido por disciplina — então a disciplina ganha um teste.
    Quem não consegue apontar não consegue acoplar: nenhuma chave estrangeira
    deste app atravessa para lá.
    """
    apontamentos = []
    for modelo in django_apps.get_app_config("jornadas").get_models():
        for campo in modelo._meta.get_fields():
            alvo = getattr(campo, "related_model", None)
            if alvo is not None and alvo._meta.app_label == "eventos":
                apontamentos.append(f"{modelo.__name__}.{campo.name}")

    assert apontamentos == [], (
        "critério de morte §10.7 do PLANO-SEQUENCIAS-DE-MENSAGENS: "
        f"jornadas passou a apontar para apps/eventos em {apontamentos}"
    )


# ---------------------------------------------------------------------------
# OS VOCABULÁRIOS FECHADOS, E QUEM OS RECUSA
# ---------------------------------------------------------------------------


def test_o_vocabulario_de_assuntos_e_subconjunto_do_contrato():
    """A fonte da verdade é o contrato; esta tupla é a mesma lista no banco.

    SUBCONJUNTO, e não igualdade: assunto novo no contrato pode ser de outra
    célula e não obriga jornada nenhuma. Ao contrário, um assunto que só existe
    aqui é uma jornada inventando o que dizer — exatamente o que o vocabulário
    fechado existe para impedir (constituição da célula).
    """
    contrato = json.loads(CONTRATO.read_text(encoding="utf-8"))
    do_contrato = set(contrato["properties"]["data"]["properties"]["assunto"]["enum"])

    inventados = set(jornadas.ASSUNTOS) - do_contrato
    assert inventados == set(), f"assunto que não existe no contrato: {inventados}"
    assert "jornada.passo" in jornadas.ASSUNTOS


def test_o_banco_recusa_um_assunto_inventado():
    versao = uma_versao()
    with pytest.raises(IntegrityError, match="passo_com_assunto_do_contrato"):
        with transaction.atomic():
            criar_passo(jornada_versao=versao, assunto="jornada.cobranca")


def test_o_banco_recusa_uma_classe_inventada():
    versao = uma_versao()
    with pytest.raises(IntegrityError, match="passo_com_classe_conhecida"):
        with transaction.atomic():
            criar_passo(jornada_versao=versao, classe="promocional")


def test_o_banco_recusa_um_canal_inventado():
    versao = uma_versao()
    with pytest.raises(IntegrityError, match="passo_so_usa_canais_conhecidos"):
        with transaction.atomic():
            criar_passo(jornada_versao=versao, canais=["sino", "telegrama"])


def test_o_max_length_nao_rouba_o_vermelho_da_restricao():
    """`armadilhas/226`: coluna justa recusa com `DataError`, não com a lei.

    As palavras inventadas destes testes são de propósito MAIORES que as
    legítimas — é o caso natural, e é o que revela a coluna apertada. Se algum
    dia um `max_length` for encolhido para o tamanho do vocabulário, quem passa a
    recusar é o tamanho da coluna: a mensagem deixa de dizer qual lei foi
    violada, e no dia em que alguém acrescentar uma palavra maior a proibição
    EVAPORA junto com o alargamento, sem ninguém tocar numa restrição.
    """
    folgas = {
        "classe": (Passo, jornadas.CLASSES),
        "assunto": (Passo, jornadas.ASSUNTOS),
        "resultado": (Entrega, jornadas.RESULTADOS),
        "estado": (Inscricao, jornadas.ESTADOS_DA_INSCRICAO),
        "canal": (Entrega, jornadas.CANAIS),
    }
    for nome, (modelo, vocabulario) in folgas.items():
        largura = modelo._meta.get_field(nome).max_length
        maior = max(len(v) for v in vocabulario)
        assert largura > maior, (
            f"{modelo.__name__}.{nome}: coluna de {largura} para vocabulário de "
            f"{maior} — apertada demais, a CheckConstraint perde o vermelho"
        )


def test_o_passo_sem_canal_nenhum_e_recusado():
    """Passo sem canal nenhum é passo que nunca sai — e o banco o recusa.

    A explicação que este teste NÃO dá, porque foi medida e é falsa: não é que
    `canais__len__gt=0` deixaria o vazio passar. Pelo ORM as duas grafias
    funcionam, porque o Django gera `coalesce(array_length(...), 0) > 0` e o
    `coalesce` fecha o buraco. A armadilha do `array_length` é real só no SQL
    escrito à mão — e está anotada onde ela morde, no `models.py` e na migração,
    que tem `RunSQL` de verdade.
    """
    versao = uma_versao()
    with pytest.raises(IntegrityError, match="passo_sai_por_algum_canal"):
        with transaction.atomic():
            criar_passo(jornada_versao=versao, canais=[])


def test_o_passo_nao_espera_para_tras():
    versao = uma_versao()
    with pytest.raises(IntegrityError, match="passo_nao_espera_para_tras"):
        with transaction.atomic():
            criar_passo(jornada_versao=versao, atraso=timedelta(days=-1))


def test_a_ordem_do_passo_comeca_no_um():
    """O contrato diz `"ordem": {"minimum": 1}`; aqui é a mesma regra no banco."""
    versao = uma_versao()
    with pytest.raises(IntegrityError, match="passo_comeca_no_um"):
        with transaction.atomic():
            criar_passo(jornada_versao=versao, ordem=0)


def test_dois_passos_na_mesma_ordem_da_mesma_versao_sao_recusados():
    versao = uma_versao()
    criar_passo(jornada_versao=versao, ordem=1)
    with pytest.raises(IntegrityError, match="uniq_passo_por_versao_e_ordem"):
        with transaction.atomic():
            criar_passo(jornada_versao=versao, ordem=1)


def test_a_jornada_precisa_de_gatilho():
    with pytest.raises(IntegrityError, match="jornada_tem_gatilho"):
        with transaction.atomic():
            Jornada.objects.create(site_id=SITE, slug="sem-gatilho", gatilho="")


def test_duas_jornadas_com_o_mesmo_slug_no_mesmo_site_sao_recusadas():
    Jornada.objects.create(site_id=SITE, slug="boas-vindas", gatilho="x.y.v1")
    with pytest.raises(IntegrityError, match="uniq_jornada_por_site_e_slug"):
        with transaction.atomic():
            Jornada.objects.create(site_id=SITE, slug="boas-vindas", gatilho="z.w.v1")


# ---------------------------------------------------------------------------
# A PREFERÊNCIA É POR CLASSE, E A PROJEÇÃO É POR PESSOA E SITE
# ---------------------------------------------------------------------------


def test_a_preferencia_e_por_canal_E_por_classe():
    """Não um `receber_email` booleano (VEREDITO §1.4).

    O booleano funciona três meses e vira dívida no dia em que for preciso
    distinguir segurança de progresso de comunidade — e nesse dia já haverá gente
    com a preferência gravada, o que torna a migração uma adivinhação sobre o que
    cada um quis dizer.
    """
    Preferencia.objects.create(
        destinatario_id="p1",
        site_id=SITE,
        canal="email",
        classe="engajamento",
        aceita=False,
    )
    # A MESMA pessoa, o MESMO canal, outra classe: linha nova, e é o ponto.
    Preferencia.objects.create(
        destinatario_id="p1",
        site_id=SITE,
        canal="email",
        classe="transacional",
        aceita=True,
    )

    with pytest.raises(
        IntegrityError, match="uniq_preferencia_por_pessoa_canal_classe"
    ):
        with transaction.atomic():
            Preferencia.objects.create(
                destinatario_id="p1",
                site_id=SITE,
                canal="email",
                classe="engajamento",
                aceita=True,
            )


def test_a_projecao_do_aluno_e_uma_linha_por_pessoa_e_site():
    EstadoDoAluno.objects.create(
        destinatario_id="p1", site_id=SITE, ultima_atividade_em=timezone.now()
    )
    EstadoDoAluno.objects.create(destinatario_id="p1", site_id="outro-site")

    with pytest.raises(IntegrityError, match="uniq_estado_do_aluno_por_pessoa_e_site"):
        with transaction.atomic():
            EstadoDoAluno.objects.create(destinatario_id="p1", site_id=SITE)


# ---------------------------------------------------------------------------
# A FRONTEIRA DE SITE, COM AS EXCEÇÕES VISÍVEIS
# ---------------------------------------------------------------------------


def test_o_site_id_esta_em_toda_entidade_de_entrada_do_app():
    """Lei 9 / [INV-P11], e as exceções DECLARADAS.

    Quatro tabelas guardam `site_id` direto: são as que alguém consulta pelo id
    da pessoa ou pelo site. As outras cinco chegam ao site por uma corrente de
    chaves estrangeiras que não tem como se romper — `Passo` só existe dentro de
    uma `JornadaVersao`, que só existe dentro de uma `Jornada`, que tem
    `site_id`. Repetir a coluna lá seria um segundo lugar para o mesmo fato, e o
    dia em que os dois discordassem ninguém saberia qual vale.

    Este teste existe para que a lista continue sendo uma ESCOLHA visível: tabela
    nova sem `site_id` e sem corrente até uma que o tenha reprova aqui.
    """
    com_site_id_proprio = {"Jornada", "Inscricao", "Preferencia", "EstadoDoAluno"}
    pela_corrente = {"JornadaVersao", "Passo", "TextoDoPasso", "Entrega", "Efeito"}

    medido = set()
    for modelo in django_apps.get_app_config("jornadas").get_models():
        campos = {c.name for c in modelo._meta.get_fields()}
        if "site_id" in campos:
            medido.add(modelo.__name__)

    assert medido == com_site_id_proprio
    todos = {m.__name__ for m in django_apps.get_app_config("jornadas").get_models()}
    assert todos == com_site_id_proprio | pela_corrente


def test_nenhuma_tabela_guarda_e_mail_nome_ou_telefone():
    """`DECISAO-EVO-01` §3: o contato vive numa linha só, na `identidade`.

    Quem precisa falar com a pessoa PERGUNTA na hora do envio. Guardar aqui
    seria uma segunda casa do dado — e o idioma gravado na inscrição congelaria
    a língua de quem se inscreveu (constituição da célula).
    """
    proibidos = ("email", "e_mail", "nome", "name", "telefone", "whatsapp", "phone")
    achados = []
    for modelo in django_apps.get_app_config("jornadas").get_models():
        for campo in modelo._meta.get_fields():
            nome = campo.name.lower()
            # `canal`/`canais` guardam a PALAVRA "email", que é o nome do canal,
            # não o endereço de ninguém — e é por isso que a busca é por campo.
            if nome in proibidos:
                achados.append(f"{modelo.__name__}.{campo.name}")

    assert achados == [], f"contato de pessoa dentro da mensageria: {achados}"


def test_o_texto_maior_que_a_coluna_nao_e_o_caminho_normal():
    """Guarda de sanidade da folga: `assunto_visivel` cabe uma frase de verdade."""
    versao = uma_versao()
    passo = criar_passo(jornada_versao=versao)
    from apps.jornadas.models import TextoDoPasso

    TextoDoPasso.objects.create(
        passo=passo,
        idioma="pt-br",
        assunto_visivel="Bem-vindo à Meshcraft Academy, seus primeiros passos começam agora",
        corpo="corpo",
    )

    with pytest.raises(DataError):
        with transaction.atomic():
            TextoDoPasso.objects.create(
                passo=passo, idioma="en", assunto_visivel="x" * 201, corpo="c"
            )
