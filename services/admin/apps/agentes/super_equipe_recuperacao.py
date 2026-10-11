"""Conferência local de chamadas já feitas, sem reenviar pedidos ao modelo."""
import hashlib
import json
from decimal import Decimal

from django.utils import timezone

from .models import Consumo
from .super_equipe_automatica import evento


def conferir(item):
    rodadas = item.desenvolvimento.get("rodadas", {})
    consumos = list(Consumo.objects.filter(execucao_id=item.trabalho_id,
        origem="super_equipe_codigo").order_by("criado_em")) if item.trabalho_id else []
    ligados = {r.get("consumo_id") for r in rodadas.values()}
    dados = {
        "melhoria_id": item.pk, "trabalho_id": item.trabalho_id,
        "episodio": item.evidencia.get("episodio"),
        "rodadas": [{"chave": chave, "iniciada_em": r.get("iniciada_em"),
            "base": r.get("base"), "resposta_salva": bool(r.get("resposta")),
            "acao": (r.get("resposta") or {}).get("acao"),
            "consumo_id": r.get("consumo_id"), "custo_usd": r.get("custo_usd")}
            for chave, r in rodadas.items()],
        # A origem e o trabalho delimitam a consulta. Um consumo sem vínculo
        # explícito não é atribuído a uma rodada por aproximação de horário.
        "consumos_do_trabalho": [{"id": c.pk, "criado_em": c.criado_em.isoformat(),
            "resposta_id": c.resposta_id, "modelo": c.modelo,
            "desconhecido": c.desconhecido, "vinculado_a_rodada": c.pk in ligados,
            "tokens_entrada": c.tokens_entrada, "tokens_saida": c.tokens_saida,
            "tokens_cache": c.tokens_entrada_em_cache,
            "valor_usd": str(c.custo_estimado_usd)} for c in consumos],
        "custo_calculado_do_uso_usd": str(sum((c.custo_estimado_usd for c in consumos
            if not c.desconhecido), Decimal("0"))),
        "reserva_sem_confirmacao_usd": str(sum((c.custo_estimado_usd for c in consumos
            if c.desconhecido), Decimal("0"))),
        "chamadas_adicionais": 0,
    }
    dados["assinatura"] = hashlib.sha256(json.dumps(dados, sort_keys=True).encode()).hexdigest()
    return dados


def registrar_conferencia(item, dados):
    """Acrescenta evidência ao histórico; nunca libera uma chamada desconhecida."""
    anteriores = item.desenvolvimento.get("conferencias", [])
    if any(c.get("assinatura") == dados["assinatura"] for c in anteriores):
        return
    salvas = sum(r["resposta_salva"] for r in dados["rodadas"])
    sem_resposta = len(dados["rodadas"]) - salvas
    texto = (f"Recuperação conferida: {salvas} respostas salvas e {sem_resposta} rodadas sem resultado salvo. "
        f"Desenvolvimento do trabalho {item.trabalho_id}: US$ {dados['custo_calculado_do_uso_usd']} "
        "calculados a partir do uso recebido; "
        f"US$ {dados['reserva_sem_confirmacao_usd']} reservados sem confirmação. "
        "Reserva não é cobrança confirmada. Rodadas, consumos e histórico preservados; "
        "nenhuma chamada de IA reenviada. Retomada não liberada por esta conferência. "
        "Custo externo desta conferência: não informado.")
    registro = {**dados, "conferida_em": timezone.now().isoformat(),
        "resultado_anterior": item.resultado}
    item.desenvolvimento = {**item.desenvolvimento, "conferencias": [*anteriores, registro]}
    item.resultado = texto
    item.save(update_fields=["desenvolvimento", "resultado"])
    evento(item, texto)
