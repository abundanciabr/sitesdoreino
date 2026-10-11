"""Leitura local da análise do Sandbox e reconhecimento da terceira etapa."""

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import AvaliacaoSandboxProjetada, JornadaPessoal, LancamentoDeXP, RegistroDaJornada


ESTADOS = {"pendente", "em_analise", "falha", "concluida"}
RESULTADOS = {"", "atende", "precisa_ajustes", "inconclusiva"}


def _data(valor):
    data = parse_datetime(valor) if isinstance(valor, str) else None
    if data is None:
        raise ValueError("Avaliação do Sandbox sem data válida")
    return timezone.make_aware(data) if timezone.is_naive(data) else data


def _texto(valor, limite):
    return valor.strip()[:limite] if isinstance(valor, str) else ""


def _url_local(valor):
    caminho = _texto(valor, 500)
    return caminho if caminho.startswith("/") and not caminho.startswith("//") and "\\" not in caminho else ""


def registrar_evento(envelope):
    """Aceita só a revisão mais recente do trabalho; o consumer deduplica event_id."""
    if envelope.get("version") != 1:
        raise ValueError("Versão desconhecida da avaliação do Sandbox")
    data = envelope.get("data") or {}
    pessoa_id = _texto(data.get("pessoa_id"), 100)
    site_id = _texto(data.get("site_id"), 64)
    trabalho_id = _texto(data.get("trabalho_id"), 64)
    entrega_id = _texto(data.get("entrega_id"), 64)
    analise_id = _texto(data.get("analise_id"), 64)
    event_id = _texto(envelope.get("event_id"), 64)
    estado = data.get("estado")
    resultado = data.get("resultado") or ""
    versao = data.get("versao")
    entrega_criada_em = _data(data.get("entrega_criada_em"))
    quando = _data(data.get("atualizado_em"))
    ocorrido_em = _data(data.get("ocorrido_em"))
    atual = data.get("atual")
    if (not all((pessoa_id, site_id, trabalho_id, entrega_id, analise_id, event_id))
            or isinstance(versao, bool) or not isinstance(versao, int) or versao < 1
            or estado not in ESTADOS or resultado not in RESULTADOS
            or not isinstance(atual, bool)
            or (estado != "concluida" and resultado == "atende")
            or (estado == "concluida" and not resultado)):
        raise ValueError("Avaliação do Sandbox fora do contrato")
    # A criação da entrega na fonte define qual envio é mais recente, mesmo
    # após limpeza que reinicie a numeração; dentro dela vale a atualização.
    from .faixas import _pessoa
    from .reinicio import evento_anterior_ao_reinicio
    with transaction.atomic():
        pessoa = _pessoa(pessoa_id)
        JornadaPessoal.objects.get_or_create(pessoa=pessoa, site_id=site_id)
        jornada = JornadaPessoal.objects.select_for_update().get(pessoa=pessoa, site_id=site_id)
        outra = AvaliacaoSandboxProjetada.objects.filter(trabalho_id=trabalho_id).exclude(
            pessoa=pessoa, site_id=site_id,
        ).exists()
        if outra:
            raise ValueError("Trabalho do Sandbox associado a outra pessoa ou site")
        registro = AvaliacaoSandboxProjetada.objects.select_for_update().filter(
            pessoa=pessoa, site_id=site_id, trabalho_id=trabalho_id,
        ).first()
        if registro and (
            entrega_criada_em < registro.entrega_criada_em or
            (entrega_criada_em == registro.entrega_criada_em
             and entrega_id == registro.entrega_id
             and quando <= registro.origem_atualizada_em)
        ):
            return registro
        if registro and entrega_criada_em == registro.entrega_criada_em and registro.entrega_id != entrega_id:
            raise ValueError("Duas entregas do Sandbox têm o mesmo instante de criação")
        if registro and entrega_id == registro.entrega_id and entrega_criada_em != registro.entrega_criada_em:
            raise ValueError("Entrega do Sandbox mudou o instante de criação")
        if registro and entrega_id == registro.entrega_id and versao != registro.versao:
            raise ValueError("Entrega do Sandbox mudou de versão")
        campos = dict(
            entrega_id=entrega_id, analise_id=analise_id, event_id=event_id,
            versao=versao, entrega_criada_em=entrega_criada_em,
            origem_atualizada_em=quando, ocorrido_em=ocorrido_em,
            atual=atual, estado=estado,
            resultado=resultado, explicacao=_texto(data.get("explicacao"), 4000),
            justificativa=_texto(data.get("justificativa"), 4000),
            proxima_acao=_texto(data.get("proxima_acao"), 1000),
            url=_url_local(data.get("url")), historico=data.get("historico") is True,
            anterior_reinicio=evento_anterior_ao_reinicio(site_id, envelope),
        )
        if registro is None:
            registro = AvaliacaoSandboxProjetada.objects.create(
                pessoa=pessoa, site_id=site_id, trabalho_id=trabalho_id, **campos,
            )
        else:
            for chave, valor in campos.items():
                setattr(registro, chave, valor)
            registro.save(update_fields=[*campos, "atualizada_em"])
        _reconhecer(jornada, registro)
        return registro


def reconhecer_pendentes(jornada):
    """Usado depois da etapa 2: avaliação anterior continua valendo na sequência."""
    for registro in AvaliacaoSandboxProjetada.objects.select_for_update().filter(
        pessoa=jornada.pessoa, site_id=jornada.site_id, estado="concluida",
        resultado="atende", historico=False, anterior_reinicio=False,
        atual=True, reconhecida_em__isnull=True,
    ).order_by("origem_atualizada_em", "pk"):
        if _reconhecer(jornada, registro):
            break  # a terceira etapa e seu bônus são únicos


def _reconhecer(jornada, registro):
    if (registro.historico or registro.anterior_reinicio or not registro.atual or registro.estado != "concluida" or
            registro.resultado != "atende" or registro.reconhecida_em):
        return False
    from .jornada import situacao
    antes = situacao(jornada.pessoa_id, jornada.site_id)
    if not antes["lista"][1]["alcancada"]:
        return False
    if jornada.confirmacoes_sequenciais.get("3") and antes["lista"][2]["alcancada"]:
        return False
    from .bonus_faixas import conceder, configurar
    configurar(jornada.site_id)
    agora = timezone.now()
    jornada.declaracoes = {**jornada.declaracoes, "3": agora.isoformat()}
    jornada.confirmacoes_sequenciais = {
        **jornada.confirmacoes_sequenciais, "3": agora.isoformat(),
    }
    jornada.revisao += 1
    jornada.save(update_fields=["declaracoes", "confirmacoes_sequenciais", "revisao", "atualizada_em"])
    pontos = conceder(jornada.pessoa_id, jornada.site_id, [3])
    registro.reconhecida_em = agora
    registro.reconhecida_versao = registro.versao
    registro.reconhecida_entrega_id = registro.entrega_id
    registro.reconhecida_analise_id = registro.analise_id
    registro.save(update_fields=["reconhecida_em", "reconhecida_versao", "reconhecida_entrega_id", "reconhecida_analise_id", "atualizada_em"])
    RegistroDaJornada.objects.create(
        pessoa=jornada.pessoa, site_id=jornada.site_id, acao="avaliacao_sandbox",
        dados={
            "texto": "A análise reconheceu sua prática no Sandbox.",
            "passo": 3, "trabalho_id": registro.trabalho_id,
            "entrega_id": registro.entrega_id, "analise_id": registro.analise_id,
            "versao": registro.versao, "event_id": registro.event_id,
            "resultado": registro.resultado, "explicacao": registro.explicacao,
            "bonus_xp": pontos,
        },
    )
    return True


def resumo(pessoa_id, site_id):
    """O mesmo resumo privado para aluno e suporte, sem conceder nada na leitura."""
    linhas = list(AvaliacaoSandboxProjetada.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id,
    ).order_by("-entrega_criada_em", "-pk"))
    if not linhas:
        return {"fonte": "gamificacao", "site_id": site_id,
                "pessoa_id": pessoa_id, "avaliacoes": []}
    jornada = JornadaPessoal.objects.filter(pessoa_id=pessoa_id, site_id=site_id).first()
    sequencia = False
    if jornada and jornada.confirmacoes_sequenciais.get("2") and jornada.declaracoes.get("2"):
        from .inicio import etapas_inicio, requisitos_branca
        from .models import AnexoDaJornada
        tem_anexo = AnexoDaJornada.objects.filter(
            pessoa_id=pessoa_id, site_id=site_id, passo=2,
        ).exists()
        sequencia = bool(
            all(requisitos_branca(jornada, tem_anexo).values())
            and etapas_inicio(pessoa_id, site_id, jornada, tem_anexo)[3]["concluida"]
        )
    bonus_creditado = LancamentoDeXP.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id, regra_slug="bonus-faixa-azul",
        pontos__gt=0,
    ).exists()
    itens = []
    for linha in linhas:
        reconhecimento_da_versao = bool(
            linha.reconhecida_em and linha.reconhecida_versao == linha.versao
            and linha.reconhecida_entrega_id == linha.entrega_id
            and linha.reconhecida_analise_id == linha.analise_id
        )
        if linha.historico:
            estado, texto = "historico", "Registro histórico preservado; esta importação não concede novo bônus."
        elif linha.anterior_reinicio:
            estado, texto = "historico", "Avaliação anterior ao reinício preservada; ela não concede novo bônus."
        elif reconhecimento_da_versao:
            estado = "reconhecido"
            texto = "Prática reconhecida após a análise; bônus já concedido uma única vez." if bonus_creditado else "Prática reconhecida após a análise; bônus de XP não consta no histórico."
        elif linha.reconhecida_em:
            estado, texto = "nao_reconhecido", "Reconhecimento de uma entrega anterior preservado; esta avaliação ainda não o substitui."
        elif not linha.atual:
            estado, texto = "nao_reconhecido", "Esta análise não é da entrega atual."
        elif linha.estado != "concluida":
            estado, texto = "aguardando_analise", "A avaliação ainda não reconheceu a realização."
        elif linha.resultado != "atende":
            estado, texto = "nao_reconhecido", "A análise não reconheceu esta versão; confira o retorno."
        elif not sequencia:
            estado, texto = "aguardando_sequencia", "Avaliação concluída; falta alcançar a etapa anterior."
        elif jornada and jornada.confirmacoes_sequenciais.get("3"):
            estado, texto = "nao_reconhecido", "A etapa já estava registrada na jornada; esta avaliação não concede outro bônus."
        else:
            estado, texto = "aguardando_sequencia", "Avaliação registrada; reconhecimento em atualização."
        itens.append({
            "trabalho_id": linha.trabalho_id, "entrega_id": linha.entrega_id,
            "analise_id": linha.analise_id, "versao": linha.versao,
            "entrega_criada_em": linha.entrega_criada_em.isoformat(),
            "atualizado_em": linha.origem_atualizada_em.isoformat(),
            "ocorrido_em": linha.ocorrido_em.isoformat(), "atual": linha.atual,
            "estado": linha.estado, "resultado": linha.resultado,
            "explicacao": linha.explicacao, "justificativa": linha.justificativa,
            "proxima_acao": linha.proxima_acao, "url": linha.url,
            "historico": linha.historico,
            "anterior_reinicio": linha.anterior_reinicio,
            "reconhecimento": {"estado": estado, "texto": texto},
        })
    return {"fonte": "gamificacao", "site_id": site_id,
            "pessoa_id": pessoa_id, "avaliacoes": itens}
