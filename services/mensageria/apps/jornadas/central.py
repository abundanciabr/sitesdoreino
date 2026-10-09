"""Central de automações: versões editáveis e execução pelo motor de jornadas."""
from __future__ import annotations

import re
import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.conversas import enderecos, envio
from apps.conversas.models import Conversa, MensagemDaConversa

from . import condicoes, motor
from .models import Entrega, EstadoDoAluno, Inscricao, Jornada, JornadaVersao, Passo, TextoDoPasso

MODELOS = (
    ("boas-vindas", "Boas-vindas e primeiro acesso"),
    ("compra", "Compra, matrícula e acesso liberado"),
    ("recuperar-acesso", "Recuperação de acesso e senha"),
    ("inicio-estudos", "Início dos estudos"),
    ("dificuldade", "Dificuldade do aluno"),
    ("retorno", "Retorno após inatividade"),
    ("lembretes", "Atividades, entregas e encontros"),
    ("avaliacao", "Avaliação e devolução"),
    ("conquistas", "Faixas, conquistas e etapas"),
    ("forum", "Resposta no Fórum"),
    ("operacional", "Avisos operacionais"),
    ("pesquisa", "Pesquisa de satisfação"),
    ("campanha", "Campanhas, indicações e continuidade"),
)
MODELO_CORPOS = {
    "boas-vindas": "Olá! Que bom ter você por aqui. Se precisar de ajuda para começar, responda esta mensagem.",
    "compra": "Olá! Podemos ajudar com dúvidas sobre sua compra, matrícula ou acesso.",
    "recuperar-acesso": "Olá! Se está com dificuldade para entrar na sua conta, responda aqui para receber orientação da equipe.",
    "inicio-estudos": "Olá! Se quiser ajuda para começar os estudos, estamos por aqui.",
    "dificuldade": "Olá! Alguma dificuldade nas atividades? Conte-nos o que aconteceu.",
    "retorno": "Olá! Se quiser retomar seus estudos, podemos ajudar a encontrar o próximo passo.",
    "lembretes": "Olá! Passando para lembrar de suas atividades. Se precisar de orientação, responda aqui.",
    "avaliacao": "Olá! Sua atividade teve uma devolução. Confira os comentários quando puder.",
    "conquistas": "Olá! Há uma nova conquista no seu percurso de estudos. Confira quando puder.",
    "forum": "Olá! Há uma resposta para sua conversa no Fórum: {{link}}",
    "operacional": "Olá! Temos uma atualização importante sobre seu atendimento. Responda aqui se precisar de ajuda.",
    "pesquisa": "Olá! Como está sua experiência de estudo? Sua resposta nos ajuda a melhorar.",
    "campanha": "Olá! Se quiser conhecer outras opções de estudo, podemos orientar você.",
}
MODELO_GATILHOS = {
    "boas-vindas": "identidade.pessoa-cadastrada",
    "compra": "matricula.ativa",
    "recuperar-acesso": "manual",
    "inicio-estudos": "identidade.pessoa-cadastrada",
    "dificuldade": "manual",
    "retorno": "aluno.inatividade-detectada",
    "lembretes": "manual",
    "avaliacao": "checkpoint.devolvido",
    "conquistas": "gamificacao.conquista-concedida",
    "forum": "forum.resposta-criada",
    "operacional": "manual",
    "pesquisa": "manual",
    "campanha": "manual",
}
MODELO_ROTEIROS = {
    "recuperar-acesso": "Se a pessoa confirmar que perdeu o acesso, use a ferramenta "
        "solicitar_recuperacao_acesso. Só confirme o envio do link depois que a ferramenta "
        "retornar sucesso; não invente um link ou uma redefinição de senha.",
    "compra": "Só confirme compra, matrícula ou acesso quando o fato confirmado estiver "
        "no histórico. Se houver dúvida, consulte o estado real antes de responder.",
    "forum": "Use somente o link completo e real da resposta recebida no Fórum.",
}
GATILHOS_TRANSACIONAIS = frozenset({
    "matricula.ativa", "checkpoint.devolvido", "forum.resposta-criada",
    "gamificacao.nivel-alcancado", "gamificacao.conquista-concedida",
    "gamificacao.marco-validado",
})


def classe_do_gatilho(gatilho: str) -> str:
    return "transacional" if gatilho in GATILHOS_TRANSACIONAIS else "relacional"
PUBLICOS = {"todos", "alunos", "contatos", "turma"}
RESPOSTAS = {"pausar", "encerrar", "avancar", "continuar", "humano"}
INTERACOES = {"", "botoes", "lista", "links"}
CAMPOS = ("nome", "curso", "turma", "progresso", "aula", "link")
_CAMPO = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def configuracao(versao: JornadaVersao) -> dict:
    return versao.central_config if isinstance(versao.central_config, dict) else {}


def e_central(versao: JornadaVersao) -> bool:
    return configuracao(versao).get("central") is True


def preencher(corpo: str, contexto: dict) -> str:
    """Só dados verificados entram; campo ausente interrompe o envio."""
    def trocar(match):
        campo = match.group(1)
        if campo not in CAMPOS or not contexto.get(campo):
            raise ValueError(f"campo {campo} indisponível")
        valor = str(contexto[campo])[:500]
        if campo == "link" and not valor.startswith("https://"):
            raise ValueError("link não verificado")
        return valor
    return _CAMPO.sub(trocar, corpo)


def publico_permite(publico: str, contexto: dict) -> bool:
    if publico.startswith("curso:"):
        # A seleção no painel usa o ID público do produto no catálogo.
        # `curso_id` do evento é a PK interna e pode coincidir por acaso.
        return bool(publico[6:] and publico[6:] == str(contexto.get("produto_id") or ""))
    if publico.startswith("turma:"):
        return bool(publico[6:] and publico[6:] == str(contexto.get("turma_id") or ""))
    if publico == "todos":
        return True
    if publico == "alunos":
        return bool(contexto.get("aluno_id") or contexto.get("aluno") or contexto.get("matricula_id"))
    if publico == "contatos":
        return bool(contexto.get("contato_id") or contexto.get("lead_id"))
    if publico == "turma":
        return bool(contexto.get("turma_id"))
    return False


def _conversa(site_id: str, conversa) -> Conversa | None:
    if isinstance(conversa, Conversa):
        return conversa if conversa.site_id == site_id and conversa.canal == "whatsapp" else None
    try:
        return Conversa.objects.filter(pk=uuid.UUID(str(conversa)), site_id=site_id, canal="whatsapp").first()
    except (ValueError, TypeError):
        return None


def inscrever_evento(*, gatilho, site_id, destinatario_id, event_id, contexto=None,
                    conversa=None, momento=None, jornada_slug=None):
    """Inscreve nas automações ativas para um fato real, sem enviar no ato."""
    dados = dict(contexto) if isinstance(contexto, dict) else {}
    try:
        fato = uuid.UUID(str(event_id))
    except (ValueError, TypeError):
        return []
    candidatas = Jornada.objects.filter(site_id=site_id, gatilho=gatilho, ativa=True,
                                         central_entrada_aberta=True, central_pausada=False)
    if jornada_slug:
        candidatas = candidatas.filter(slug=jornada_slug)
    jornadas = list(candidatas)
    if not jornadas:
        return []
    conversa_real = _conversa(site_id, conversa or dados.get("conversa_id"))
    if conversa_real and str(destinatario_id).startswith("conversa:"):
        dados.setdefault("contato_id", str(conversa_real.id))
    if conversa_real is None:
        # Fatos de aluno não trazem a conversa; a identidade só é consultada no
        # instante do uso e não se copia telefone para a inscrição.
        from .despacho import _telefone_da_pessoa
        telefone, _, _ = _telefone_da_pessoa(pessoa_id=str(destinatario_id), site_id=site_id)
        telefone = enderecos.telefone(telefone or "")
        if telefone:
            conversa_real, _ = Conversa.objects.get_or_create(site_id=site_id, canal="whatsapp",
                                                               endereco=telefone)
    if conversa_real is None:
        return []
    inscritas = []
    for jornada in jornadas:
        versao = motor._versao_publicada(jornada)
        if versao is None or not e_central(versao):
            continue
        if not publico_permite(configuracao(versao).get("publico", "todos"), dados):
            continue
        publico = configuracao(versao).get("publico", "todos")
        contexto_id = str(dados.get("turma_id") or "")[:64] if publico.startswith("turma") else ""
        inscricao = motor.inscrever(jornada, destinatario_id=str(destinatario_id), site_id=site_id,
                                    contexto_id=contexto_id, origem_event_id=fato, momento=momento)
        if inscricao:
            alterados = Inscricao.objects.filter(pk=inscricao.pk, central_conversa_id__isnull=True).update(
                central_conversa_id=conversa_real.id if conversa_real else None,
                central_contexto={k: str(v)[:500] for k, v in dados.items() if k in CAMPOS},
            )
            if alterados:
                inscricao.refresh_from_db()
            inscritas.append(inscricao)
    return inscritas


def detectar_inatividade(*, momento=None, lote=200) -> int:
    """Gera o fato de cinco dias sem atividade a partir da projeção existente."""
    agora = momento or timezone.now()
    sites = Jornada.objects.filter(gatilho="aluno.inatividade-detectada", ativa=True,
                                    central_entrada_aberta=True, central_pausada=False).values_list("site_id", flat=True)
    total = 0
    for estado in EstadoDoAluno.objects.filter(site_id__in=sites,
            ultima_atividade_em__isnull=False,
            ultima_atividade_em__lte=agora - timedelta(days=5)).order_by("ultima_atividade_em")[:lote]:
        fato = uuid.uuid5(uuid.NAMESPACE_URL,
            f"inatividade:{estado.site_id}:{estado.destinatario_id}:{estado.ultima_atividade_em.isoformat()}")
        if Inscricao.objects.filter(site_id=estado.site_id, origem_event_id=fato).exists():
            continue
        total += len(inscrever_evento(gatilho="aluno.inatividade-detectada", site_id=estado.site_id,
            destinatario_id=estado.destinatario_id, event_id=fato,
            contexto={"aluno_id": estado.destinatario_id},
            momento=estado.ultima_atividade_em + timedelta(days=5)))
    return total


def ao_resposta(mensagem: MensagemDaConversa) -> int:
    """Aplica a escolha da versão ao responder, sem gerar resposta automática."""
    if mensagem.direcao != "entrada" or mensagem.conversa.canal != "whatsapp":
        return 0
    quantidade = 0
    recentes = timezone.now() - timedelta(days=30)
    vistas = set()
    inscricoes = Inscricao.objects.select_related("jornada_versao", "jornada").filter(
        site_id=mensagem.conversa.site_id, central_conversa_id=mensagem.conversa_id,
        central_suspensa=False, jornada__ativa=True,
    ).filter(Q(estado="andando") | Q(estado="concluida", criada_em__gte=recentes)).order_by("-criada_em")[:100]
    for inscricao in inscricoes:
        if inscricao.jornada_id in vistas or not e_central(inscricao.jornada_versao):
            continue
        with transaction.atomic():
            atual = Inscricao.objects.select_for_update().get(pk=inscricao.pk)
            escolha = configuracao(inscricao.jornada_versao).get("resposta", "pausar")
            if (atual.estado not in {"andando", "concluida"} or atual.central_suspensa
                    or (atual.estado == "concluida" and escolha != "humano")
                    or mensagem.ocorrida_em <= atual.ancora_em
                    or atual.central_contexto.get("_ultima_resposta_id") == str(mensagem.id)):
                continue
            vistas.add(inscricao.jornada_id)
            atual.central_contexto = {**atual.central_contexto, "_ultima_resposta_id": str(mensagem.id)}
            atual.save(update_fields=["central_contexto"])
            if mensagem.descadastro:
                if atual.estado == "andando":
                    atual.estado, atual.proximo_em, atual.motivo_de_saida = "cancelada", None, "descadastro"
                    atual.save(update_fields=["estado", "proximo_em", "motivo_de_saida"])
            else:
                if escolha == "humano":
                    Inscricao.objects.filter(site_id=mensagem.conversa.site_id,
                        central_conversa_id=mensagem.conversa_id,
                        estado__in=("andando", "concluida")).update(central_suspensa=True)
                    try:
                        confirmacao = envio.enviar(
                            conversa=mensagem.conversa,
                            texto="Recebemos sua mensagem. Uma pessoa da equipe vai acompanhar a conversa.",
                            chave_idempotencia=f"central-humano:{mensagem.id}",
                            autor="agente", autor_id=f"central:{inscricao.jornada.slug}",
                        )
                    except Exception:  # noqa: BLE001 - pedido humano suspende automação mesmo sem confirmação
                        confirmacao = None
                    if (confirmacao and confirmacao.mensagem and
                            confirmacao.mensagem.estado_envio in {"aceito", "enviado", "entregue", "lido"}):
                        Conversa.objects.filter(pk=mensagem.conversa_id, estado="agente").update(estado="pessoa")
                    quantidade += 1
                    continue
                if escolha == "encerrar":
                    atual.estado, atual.proximo_em, atual.motivo_de_saida = "cancelada", None, "pessoa respondeu"
                    atual.save(update_fields=["estado", "proximo_em", "motivo_de_saida"])
                elif escolha == "avancar":
                    passo = atual.jornada_versao.passos.filter(ordem__gt=atual.passo_atual).order_by("ordem").first()
                    if passo:
                        # A resposta antecipa o passo devido; não o marca como entregue.
                        atual.proximo_em = timezone.now()
                        atual.save(update_fields=["proximo_em"])
                elif escolha == "pausar":
                    atual.central_suspensa = True
                    atual.save(update_fields=["central_suspensa"])
            quantidade += 1
    return quantidade


def reconciliar_handoffs(lote: int = 200) -> int:
    """Confere a mesma confirmação incerta; nunca cria um segundo envio."""
    confirmados = 0
    inscricoes = Inscricao.objects.filter(
        estado__in=("andando", "concluida"), central_suspensa=True,
        central_contexto__has_key="_ultima_resposta_id",
        central_conversa_id__isnull=False,
    ).select_related("jornada_versao")[:lote]
    for inscricao in inscricoes:
        if configuracao(inscricao.jornada_versao).get("resposta") != "humano":
            continue
        conversa = _conversa(inscricao.site_id, inscricao.central_conversa_id)
        if conversa is None or conversa.estado != "agente":
            continue
        chave = f"central-humano:{inscricao.central_contexto['_ultima_resposta_id']}"
        confirmacao = conversa.mensagens.filter(chave_idempotencia=chave).first()
        if confirmacao is None:
            continue
        envio._sincronizar(confirmacao)
        if confirmacao.estado_envio in {"aceito", "enviado", "entregue", "lido"}:
            confirmados += Conversa.objects.filter(pk=conversa.pk, estado="agente").update(estado="pessoa")
    return confirmados


def processar_entrega(entrega: Entrega, *, permitir_falha: bool = False) -> None:
    """Sincroniza uma intenção; resultado incerto conserva o mesmo ID sem reenviar."""
    inscricao = entrega.inscricao
    versao = inscricao.jornada_versao
    if not e_central(versao):
        return
    chave = f"central:{inscricao.id}:{entrega.passo_id}"
    conversa = _conversa(inscricao.site_id, inscricao.central_conversa_id)
    if conversa is None:
        entrega.resultado, entrega.motivo = "falhou", "conversa WhatsApp existente não encontrada"
        entrega.save(update_fields=["resultado", "motivo"])
        return
    anterior = conversa.mensagens.filter(chave_idempotencia=chave).first()
    if anterior and not (permitir_falha and anterior.estado_envio == "falhou"):
        envio._sincronizar(anterior)
        mapa = {"aceito": "aceita_pelo_gateway", "enviado": "enviada", "entregue": "entregue",
                "lido": "lida", "falhou": "falhou", "desconhecido": "resultado_desconhecido",
                "pendente": "resultado_desconhecido"}
        entrega.resultado = mapa.get(anterior.estado_envio, "resultado_desconhecido")
        entrega.motivo = anterior.erro[:200]
        if entrega.resultado in {"enviada", "entregue", "lida"} and not entrega.enviado_em:
            entrega.enviado_em = timezone.now()
        entrega.save(update_fields=["resultado", "motivo", "enviado_em"])
        return
    if (inscricao.jornada.central_pausada or inscricao.central_suspensa
            or inscricao.estado in {"cancelada", "saiu"}):
        return
    estado = motor._projecao(inscricao)
    try:
        vale = condicoes.avaliar(entrega.passo.condicao_slug, estado, timezone.now())
    except condicoes.CondicaoDesconhecida:
        vale = False
    if not vale:
        entrega.resultado, entrega.motivo = "pulada", "condição não satisfeita no envio"
        entrega.save(update_fields=["resultado", "motivo"])
        return
    texto = entrega.passo.textos.filter(idioma="pt-br").first()
    if texto is None:
        entrega.resultado, entrega.motivo = "falhou", "texto ausente"
        entrega.save(update_fields=["resultado", "motivo"])
        return
    try:
        corpo = preencher(texto.corpo, inscricao.central_contexto)
    except ValueError as erro:
        entrega.resultado, entrega.motivo = "falhou", str(erro)[:200]
        entrega.save(update_fields=["resultado", "motivo"])
        return
    modelo = entrega.passo.central_modelo_whatsapp or None
    if modelo:
        try:
            from apps.whatsapp_modelos.modelos import escolher_modelo
            aprovado = escolher_modelo(str(modelo.get("nome") or ""), str(modelo.get("idioma") or ""))
        except Exception:  # noqa: BLE001 - integração indisponível não autoriza modelo
            aprovado = None
        if aprovado is None or not aprovado.suportado:
            entrega.resultado, entrega.motivo = "falhou", "modelo WhatsApp não aprovado ou indisponível"
            entrega.save(update_fields=["resultado", "motivo"])
            return
    resultado = envio.enviar(conversa=conversa, texto=corpo, chave_idempotencia=chave,
                             autor="agente", autor_id=f"central:{inscricao.jornada.slug}",
                             interacao=entrega.passo.central_interacao or None,
                             modelo=modelo)
    if resultado.mensagem:
        entrega.resultado = {"aceito": "aceita_pelo_gateway", "enviado": "enviada", "entregue": "entregue",
                             "lido": "lida", "falhou": "falhou"}.get(resultado.mensagem.estado_envio,
                                                                   "resultado_desconhecido")
        if entrega.resultado in {"enviada", "entregue", "lida"}:
            entrega.enviado_em = timezone.now()
    elif resultado.resultado in {"descadastrado", "sem_consentimento", "conversa_com_pessoa"}:
        entrega.resultado = "barrada_por_preferencia"
    else:
        entrega.resultado = "pendente"
    entrega.motivo = (resultado.detalhe or resultado.resultado)[:200]
    entrega.save(update_fields=["resultado", "motivo", "enviado_em"])


def testar(*, jornada: Jornada, conversa: Conversa, versao: JornadaVersao,
           chave_idempotencia: str) -> dict:
    """Teste consciente na conversa escolhida pelo admin, com chave estável."""
    if conversa.site_id != jornada.site_id or conversa.canal != "whatsapp":
        raise ValueError("conversa WhatsApp inexistente neste site")
    primeiro = versao.passos.order_by("ordem").first()
    if primeiro is None:
        raise ValueError("versão sem passos")
    texto = primeiro.textos.filter(idioma="pt-br").first()
    if texto is None:
        raise ValueError("passo sem texto")
    chave = "central-teste:" + str(uuid.uuid5(uuid.NAMESPACE_URL,
                                               f"{jornada.site_id}:{jornada.slug}:{chave_idempotencia}"))
    inscricao = Inscricao.objects.filter(jornada=jornada,
        central_conversa_id=conversa.id).order_by("-criada_em").first()
    contexto = inscricao.central_contexto if inscricao else {}
    try:
        corpo = preencher(texto.corpo, contexto)
    except ValueError as erro:
        raise ValueError(f"teste exige contexto real: {erro}") from erro
    modelo = primeiro.central_modelo_whatsapp or None
    if modelo:
        try:
            from apps.whatsapp_modelos.modelos import escolher_modelo
            aprovado = escolher_modelo(str(modelo.get("nome") or ""), str(modelo.get("idioma") or ""))
        except Exception as erro:  # noqa: BLE001 - não propagar detalhe de credencial
            raise ValueError("modelo WhatsApp indisponível") from erro
        if aprovado is None or not aprovado.suportado:
            raise ValueError("modelo WhatsApp não aprovado")
    resposta = envio.enviar(conversa=conversa, texto=corpo,
                            chave_idempotencia=chave, autor="agente",
                            autor_id=f"central:teste:{jornada.slug}",
                            interacao=primeiro.central_interacao or None,
                            modelo=modelo)
    return {"estado": resposta.mensagem.estado_envio if resposta.mensagem else resposta.resultado,
            "resultado": resposta.resultado,
            "mensagem_id": str(resposta.mensagem.id) if resposta.mensagem else None,
            "detalhe": resposta.detalhe}
