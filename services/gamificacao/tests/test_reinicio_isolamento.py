"""O corte preserva comprovantes, isola fatos antigos e exige avaliação nova."""

import gzip
import hashlib
from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.core.perfil import perfil_de
from apps.gamificacao.faixas import ao_item_criado, ao_rendimento_real_confirmado, total_real_cents
from apps.gamificacao.handlers import ao_sandbox_trabalho_concluido
from apps.gamificacao.jornada import salvar, situacao
from apps.gamificacao.models import (
    AvaliacaoDaJornada, BackupDoReinicioDasFaixas, FaixaDoAluno, JornadaPessoal,
    LancamentoDeXP, Pessoa,
    RecebimentoDeclarado, RegistroDaJornada, RendimentoRealLivro,
)
from apps.gamificacao.prints_recebimentos import processar, rodada


pytestmark = pytest.mark.django_db
SITE, P = "site-reinicio-isolamento", "aluno-reinicio-isolamento"


def _corte():
    agora = timezone.now()
    conteudo = gzip.compress(b"[]", mtime=0)
    BackupDoReinicioDasFaixas.objects.create(
        site_id=SITE, chave="reinicio-autorizado-20261011", conteudo=conteudo,
        sha256=hashlib.sha256(conteudo).hexdigest(), contagens={},
        criado_em=agora, aplicado_em=agora,
    )
    return agora


def _envelope(evento, ocorrido, **dados):
    return {
        "event": evento, "version": 1, "event_id": str(uuid4()),
        "occurred_at": ocorrido.isoformat(),
        "data": {"site_id": SITE, "pessoa_id": P, "ocorrido_em": ocorrido.isoformat(), **dados},
    }


def test_financeiro_arquivado_permanece_no_banco_sem_contar_na_jornada():
    perfil_de(P, SITE)
    JornadaPessoal.objects.create(pessoa_id=P, site_id=SITE)
    antigo = RecebimentoDeclarado.objects.create(
        pessoa_id=P, site_id=SITE, chave=uuid4(), valor_cents=7000,
        valor_original_cents=7000, origem="fora", estado="confirmado",
        recebido_em=date.today(), print_bytes=b"print-privado",
        leitura={"anterior_cents": 7000}, fora_da_progressao=True,
    )
    RendimentoRealLivro.objects.create(
        pessoa_id=P, site_id=SITE, event_id=str(uuid4()), rendimento_id="antigo",
        valor_cents=7000, ocorrido_em=timezone.now(), fora_da_progressao=True,
    )
    assert situacao(P, SITE)["total_cents"] == 0
    assert list(situacao(P, SITE)["recebimentos"]) == []
    assert total_real_cents(P, SITE) == 0
    assert bytes(RecebimentoDeclarado.objects.get(pk=antigo.pk).print_bytes) == b"print-privado"
    # Reenvio de aba antiga conserva a chave idempotente e não cria duplicata.
    salvar(P, SITE, {
        "acao": "recebimento", "revisao": "0", "chave": str(antigo.chave),
    })
    assert RecebimentoDeclarado.objects.count() == 1
    with pytest.raises(ValueError, match="não encontrado"):
        salvar(P, SITE, {
            "acao": "correcao", "revisao": "0", "recebimento": antigo.pk,
            "valor": "0", "recebido_em": date.today().isoformat(),
        })


def test_comprovante_pendente_arquivado_nao_entra_na_fila_nem_conclui_leitura():
    perfil_de(P, SITE)
    JornadaPessoal.objects.create(pessoa_id=P, site_id=SITE)
    antigo = RecebimentoDeclarado.objects.create(
        pessoa_id=P, site_id=SITE, chave=uuid4(), valor_cents=5000,
        valor_original_cents=5000, origem="fora", estado="pendente",
        recebido_em=date.today(), print_bytes=b"print-privado", fora_da_progressao=True,
    )
    with patch("apps.gamificacao.prints_recebimentos.ler_modelo") as leitor:
        rodada()
        assert processar(antigo.pk) is False
        leitor.assert_not_called()

    # A marca de arquivo também pode surgir enquanto o leitor está executando.
    RecebimentoDeclarado.objects.filter(pk=antigo.pk).update(fora_da_progressao=False)

    def arquivar_durante_leitura(_):
        RecebimentoDeclarado.objects.filter(pk=antigo.pk).update(fora_da_progressao=True)
        return {"status": "recebido", "valor_cents": 5000, "moeda": "BRL",
                "data": date.today().isoformat()}

    with patch("apps.gamificacao.prints_recebimentos.ler_modelo", side_effect=arquivar_durante_leitura):
        assert processar(antigo.pk) is False
    antigo.refresh_from_db()
    assert antigo.fora_da_progressao and antigo.estado == "analisando"
    assert situacao(P, SITE)["total_cents"] == 0
    assert not RegistroDaJornada.objects.filter(pessoa_id=P, site_id=SITE).exists()


def test_eventos_anteriores_ao_corte_nao_refazem_faixas_mas_novos_contam():
    corte = _corte()
    antigo, novo = corte - timedelta(seconds=1), timezone.now()
    ao_item_criado(_envelope("cursos.item-criado", antigo, item_id="antigo"))
    ao_sandbox_trabalho_concluido(_envelope("encomendas.sandbox-trabalho-concluido", antigo))
    ao_rendimento_real_confirmado(_envelope(
        "encomendas.rendimento-real-confirmado", antigo,
        rendimento_id="antigo", valor_cents=7000,
    ))
    assert not FaixaDoAluno.objects.filter(pessoa_id=P, site_id=SITE).exists()
    assert not JornadaPessoal.objects.filter(pessoa_id=P, site_id=SITE).exists()
    antigo_livro = RendimentoRealLivro.objects.get(rendimento_id="antigo")
    assert antigo_livro.fora_da_progressao and total_real_cents(P, SITE) == 0

    ao_item_criado(_envelope("cursos.item-criado", novo, item_id="novo"))
    # Os fatos novos permanecem no livro, sem fabricar faixas legadas.
    perfil_de(P, SITE)
    JornadaPessoal.objects.create(pessoa_id=P, site_id=SITE, inicio={"motivo": "freelancer"})
    ao_sandbox_trabalho_concluido(_envelope(
        "encomendas.sandbox-trabalho-concluido", novo,
        resultado="reconhecida", feedback="O modelo foi examinado conforme o briefing.",
        evidencia={"trabalho_id": "trabalho-novo", "entrega_id": "entrega-nova",
                   "analise_id": "analise-nova", "avaliacao": "atende"},
    ))
    ao_rendimento_real_confirmado(_envelope(
        "encomendas.rendimento-real-confirmado", novo,
        rendimento_id="novo", valor_cents=3000,
    ))
    assert not FaixaDoAluno.objects.filter(pessoa_id=P, site_id=SITE).exists()
    assert AvaliacaoDaJornada.objects.filter(pessoa_id=P, site_id=SITE,
                                             ordem=5, resultado="reconhecida").exists()
    assert not JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE).declaracoes.get("3")
    assert situacao(P, SITE)["atual"]["ordem"] == 1  # Aguarda as ordens 2–4.
    assert total_real_cents(P, SITE) == 3000


def test_faixa_antiga_real_permanece_e_linha_apos_corte_nao_finge_avaliacao():
    corte = _corte()
    perfil_de(P, SITE)
    pessoa = Pessoa.objects.get(id_da_plataforma=P)
    JornadaPessoal.objects.create(pessoa=pessoa, site_id=SITE, inicio={"motivo": "freelancer"})
    FaixaDoAluno.objects.create(pessoa=pessoa, site_id=SITE, ordem=2,
        estado="alcancada", origem="item", alcancada_em=corte - timedelta(seconds=1))
    FaixaDoAluno.objects.create(pessoa=pessoa, site_id=SITE, ordem=3,
        estado="alcancada", origem="sandbox", alcancada_em=corte + timedelta(seconds=1))
    estado = situacao(P, SITE)
    assert estado["atual"]["ordem"] == 2
    assert estado["lista"][1]["avaliacao_resultado"] == "historica"
    assert not estado["lista"][2]["alcancada"]
    assert not LancamentoDeXP.objects.filter(regra_slug__startswith="bonus-faixa-").exists()
