"""Recuperação conservadora de avaliações reais anteriores, sem refazer envios."""

from django.apps import apps


def _sandbox_valido(fato):
    if fato.get("origem") != "sandbox":
        return False
    resultado = fato.get("resultado") or {}
    if not isinstance(resultado, dict):
        return False
    avaliacao = resultado.get("avaliacao") or {}
    medidas = resultado.get("medidas_programas") or []
    requisitos = resultado.get("requisitos") or []
    if (fato.get("origem") != "sandbox" or fato.get("estado") != "concluida"
        or fato.get("teste_mantenedor") or resultado.get("tem_falhas")
        or avaliacao.get("resultado") != "atende"
        or not str(avaliacao.get("justificativa") or "").strip()
        or not all(fato.get(c) for c in ("trabalho_id", "entrega_id", "analise_id"))
        or not isinstance(medidas, list) or not isinstance(requisitos, list) or not requisitos):
        return False
    arquivos_lidos = [str(item.get("arquivo")) for item in medidas
                      if isinstance(item, dict) and item.get("estado") == "concluida"
                      and (item.get("conteudo") or {}).get("arquivos")]
    if not arquivos_lidos:
        return False
    for requisito in requisitos:
        if not isinstance(requisito, dict):
            return False
        provas = requisito.get("evidencias")
        if (not requisito.get("encontrado") or requisito.get("nao_encontrado")
            or requisito.get("inconclusivo") or not isinstance(provas, list)
            or not provas or not any(nome in str(prova) for prova in provas
                                      for nome in arquivos_lidos)):
            return False
    return True


def _fila_valida(fato):
    evidencia = fato.get("evidencia") or {}
    return (fato.get("origem") == "fila" and fato.get("resultado") == "reconhecida"
            and isinstance(evidencia, dict) and evidencia.get("avaliador_papel") == "cliente"
            and all(evidencia.get(c) for c in ("pedido_id", "entrega_id", "versao", "aprovada_em"))
            and bool(str(fato.get("feedback") or "").strip()))


def _fatos_locais(pessoa_id, site_id):
    """Só lê Encomendas quando os modelos estão instalados no mesmo runtime."""
    config = next((c for c in apps.get_app_configs()
                   if c.name.endswith(".apps.encomendas") and
                   c.label.startswith("encomendas")), None)
    if config is None:
        return []
    try:
        Analise = apps.get_model(config.label, "AnaliseEntregaSandbox")
        Outbox = apps.get_model(config.label, "OutboxMarketplace")
    except LookupError:
        return []
    # A aplicação unificada usa configurações por célula, inclusive nas leituras.
    from contextlib import nullcontext
    try:
        from config.runtime import serving
    except ImportError:
        try:
            from modules.aplicacao.config.runtime import serving
        except ImportError:
            serving = None
    fatos = []
    with serving("encomendas") if serving else nullcontext():
        for analise in Analise.objects.filter(
            site_id=site_id, estado="concluida",
            entrega__participacao__pessoa_id=pessoa_id,
            entrega__teste_mantenedor=False,
        ).select_related("entrega__participacao"):
            fatos.append({
                "origem": "sandbox", "pessoa_id": pessoa_id, "site_id": site_id,
                "estado": analise.estado, "teste_mantenedor": analise.entrega.teste_mantenedor,
                "trabalho_id": str(analise.entrega.participacao_id),
                "entrega_id": str(analise.entrega_id), "analise_id": str(analise.pk),
                "resultado": analise.resultado,
            })
        for payload in Outbox.objects.filter(
            site_id=site_id, event="encomendas.fila-trabalho-concluido",
        ).values_list("payload", flat=True):
            if isinstance(payload, dict) and payload.get("pessoa_id") == pessoa_id:
                fatos.append({"origem": "fila", **payload})
    return fatos


def recuperar_avaliacoes_anteriores(pessoa_id, site_id, fatos=None):
    """Registra somente realizações antigas examinadas e devolve a quantidade nova.

    ``fatos`` permite à camada integradora fornecer fatos do serviço Encomendas
    quando as células Django rodam separadas. Nenhuma consulta remota é feita aqui.
    """
    from .jornada import registrar_avaliacao, situacao
    if situacao(pessoa_id, site_id).get("caminho") != "freelancer":
        return 0
    fatos = _fatos_locais(pessoa_id, site_id) if fatos is None else fatos
    novos = 0
    for fato in fatos:
        if not isinstance(fato, dict) or (fato.get("pessoa_id"), fato.get("site_id")) != (pessoa_id, site_id):
            continue
        if _sandbox_valido(fato):
            resultado = fato["resultado"]
            evidencia = {
                "trabalho_id": fato["trabalho_id"], "entrega_id": fato["entrega_id"],
                "analise_id": fato["analise_id"], "avaliacao": "atende",
                "requisitos_verificados": len(resultado["requisitos"]),
                "chave": "historico:sandbox:" + str(fato["analise_id"]),
                "conquista_equivalente_original": {"ordem": 3, "origem": "sandbox"},
            }
            ordem = 5
            feedback = resultado["avaliacao"]["justificativa"].strip()
        elif _fila_valida(fato):
            fonte = fato["evidencia"]
            evidencia = {campo: fonte[campo] for campo in
                         ("pedido_id", "entrega_id", "versao", "aprovada_em", "avaliador_papel")}
            evidencia.update({
                "chave": "historico:fila:" + str(fonte["pedido_id"]) + ":" + str(fonte["entrega_id"]),
                "conquista_equivalente_original": {"ordem": 4, "origem": "fila"},
            })
            ordem, feedback = 6, fato["feedback"].strip()
        else:
            continue
        from .models import AvaliacaoDaJornada
        antes = AvaliacaoDaJornada.objects.filter(
            pessoa_id=pessoa_id, site_id=site_id, ordem=ordem,
            evidencia__chave=evidencia["chave"],
        ).exists()
        registrar_avaliacao(pessoa_id, site_id, ordem, "reconhecida", feedback, evidencia)
        novos += int(not antes)
    return novos
