"""Projeção factual dos trabalhos no checklist privado autorizado."""
from django.db import transaction
from django.db.models import Q, Sum
from decimal import Decimal
import logging
from apps.core.models import Documento, VersaoDoDocumento
from .models import Execucao, RotinaSuperEquipe

NOME = "checklist-super-equipe-cinco-especialistas-20261012"
INICIO = "<!-- super-equipe-estado-inicio -->"
FIM = "<!-- super-equipe-estado-fim -->"


def sincronizar():
    rotina = RotinaSuperEquipe.objects.filter(host="meshcraft.top").first()
    linhas = [INICIO, "## Estado dos trabalhos sincronizado pelo servidor", "",
        "Fotografias e estados persistidos. Conclusão de um trabalho não aprova automaticamente um teste ou item do plano.", "",
        "Rotina antiga: " + ("ativa" if rotina and rotina.ativa else "pausada"), "",
        "| Trabalho | Estado | Respostas salvas | Uso registrado (US$) | Reserva incerta (US$) |",
        "|---|---|---|---|---|"]
    for e in Execucao.objects.filter(tipo=Execucao.Tipo.SUPER_EQUIPE,
            estado__host="meshcraft.top").order_by("-pk")[:8]:
        resultados = e.estado.get("resultados") or {}
        total = len(e.estado.get("especialidades") or [])
        custos = e.consumos.aggregate(uso=Sum("custo_estimado_usd", filter=Q(desconhecido=False)),
            incerto=Sum("custo_estimado_usd", filter=Q(desconhecido=True)))
        linhas.append(f"| `https://meshcraft.top/admin/super-equipe/{e.pk}/` | {e.get_situacao_display()} | {len(resultados)}/{total} | {custos['uso'] or Decimal('0')} | {custos['incerto'] or Decimal('0')} |")
    linhas += ["", "Valores são registros da aplicação; reservas incertas continuam no consumo. Custo externo não informado não é zero.", FIM]
    bloco = "\n".join(linhas)
    with transaction.atomic():
        doc = Documento.objects.select_for_update().filter(nome=NOME,
            publico=False, arquivado=False).first()
        if doc is None:
            return False
        corpo = doc.corpo
        if INICIO in corpo and FIM in corpo:
            a, b = corpo.index(INICIO), corpo.index(FIM) + len(FIM)
            novo = corpo[:a] + bloco + corpo[b:]
        else:
            novo = bloco + "\n\n---\n\n" + corpo
        if novo == corpo:
            return False
        if not doc.versoes.exists():
            VersaoDoDocumento.objects.create(documento=doc, titulo=doc.titulo,
                publico=False, ordem=doc.ordem, corpo=corpo,
                gesto="Texto anterior à sincronização")
        doc.corpo = novo
        doc.save(update_fields=["corpo", "atualizado_em"])
        VersaoDoDocumento.objects.create(documento=doc, titulo=doc.titulo,
            publico=False, ordem=doc.ordem, corpo=novo,
            gesto="Sincronização dos estados da Super Equipe")
    return True


def acompanhar(execucao):
    if execucao.tipo == Execucao.Tipo.SUPER_EQUIPE and execucao.estado.get("host") == "meshcraft.top":
        try:
            sincronizar()
        except Exception:
            logging.getLogger(__name__).exception("Checklist privado: sincronização não concluída")
