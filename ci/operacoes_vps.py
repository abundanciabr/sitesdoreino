"""Operações fechadas da VPS: saída por lista permitida, nunca logs de aplicação."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

OPERACOES_DA_PLATAFORMA = {"estado-infra", "espaco-disco", "versao-compose"}
ESTADOS = {"created", "running", "paused", "restarting", "removing", "exited", "dead"}
SAUDES = {"healthy", "unhealthy", "starting", "ausente"}
RAIZ_INFRA = Path("/opt/plataforma")
ARQUIVOS_ESTADO_INFRA = (
    "docker-compose.yml",
    "sites.json",
    "sincronizar_sites.py",
    "provisionar-usuario-ponte.sh",
    "instalar-provisionador-usuario-ponte.sh",
    "traefik/traefik.yml",
    "traefik/dynamic/plataforma.yml",
    "traefik/dynamic/entrada-privada.yml",
    "docker-compose.yml.new",
    "sites.json.new",
    "sincronizar_sites.py.new",
    "traefik.new/traefik.yml",
    "traefik.new/dynamic/plataforma.yml",
    "traefik.new/dynamic/entrada-privada.yml",
    "infra.new/docker-compose.yml",
    "infra.new/sites.json",
    "infra.new/sincronizar_sites.py",
    "infra.new/provisionar-usuario-ponte.sh",
    "infra.new/instalar-provisionador-usuario-ponte.sh",
    "infra.new/traefik/traefik.yml",
    "infra.new/traefik/dynamic/plataforma.yml",
    "infra.new/traefik/dynamic/entrada-privada.yml",
)
SERVICOS_ESTADO_INFRA_LEGADO = ("traefik", "catalogo", "admin")
SERVICOS_ESTADO_INFRA_APLICACAO = ("traefik", "aplicacao")
SERVICOS_INCORPORADOS = frozenset({
    "admin", "alunos", "catalogo", "checkout", "cursos", "encomendas",
    "forum", "funil", "gamificacao", "identidade", "leads", "mensageria",
    "metricas", "notificacoes", "pagamentos", "pages", "quiz", "sugestoes",
})
ESTADOS_TENTATIVA = {
    "sending",
    "reconciliation_required",
    "pending",
    "approved",
    "rejected",
    "failed",
}
ESTADOS_OPERACAO = {"sending", "reconciliation_required", "completed", "failed"}
ESTADOS_OPERACAO_SAIDA = ESTADOS_OPERACAO | {"not_started"}
# Referência que o comprador vê no erro do Pix Appmax: sha256 do id da
# sessão do checkout (dados.js `referenciaDiagnostico`). A intent guarda a
# sessão em `metadata.checkout_session_id`; a chave de idempotência já não é
# a sessão (é a compra inteira), e só as intents antigas sem o metadata caem
# na chave, que nelas era a própria sessão. Expressão avaliada na VPS com `t`
# sendo a PaymentAttempt.
REFERENCIA_DA_TENTATIVA = (
    "hashlib.sha256(str((t.intent.metadata or {}).get('checkout_session_id')"
    " or t.intent.idempotency_key).encode()).hexdigest()"
)
MOTIVOS_APPMAX_PIX = {
    "campo_expiration_date",
    "campo_document_number",
    "campo_customer_id",
    "campo_order_id",
    "campo_payment_data",
    "sem_json",
    "sem_campo_identificavel",
    "indisponivel",
}
CAMPOS_CANDIDATA_APPMAX_PIX = {
    "referencia",
    "criada_em",
    "tentativa",
    "intent",
    "motivo",
    "qr_presente",
    "operacoes",
}
# A leitura por referência não repete "referencia" nem "criada_em" na
# evidência (medir() já filtrou por elas); a forma da evidência é quem
# distingue candidata única de descoberta, não o parâmetro `referencia` do
# conferir() da esteira, que para appmax-pix nunca o repassa.
CAMPOS_RESUMO_APPMAX_PIX = {
    "tentativa",
    "intent",
    "motivo",
    "qr_presente",
    "operacoes",
}
SITE_MESHCRAFT = "cc06b8c3-043b-4c06-92c5-5ea624e00586"
DIAGNOSTICOS_APPMAX_PEDIDO = {
    "vazio",
    "diagnostico",
    "status_conciliado",
    "outro_codigo",
}
STATUS_APPMAX_PEDIDO = {
    "aprovado",
    "integrado",
    "pendente_integracao",
    "cancelado",
    "recusado_por_risco",
    "pendente",
    "autorizado",
}
# [MEDICAO-VPS:appmax-pendentes] mesmo critério de "em aberto" da
# appmax-observacao (ESTADOS_EM_ABERTO de pagamentos/core/models.py), mas linha
# a linha em vez de contagem: cada tentativa Pix ou cartão que não terminou.
# Cartão com order_id válido soma uma consulta GET somente-leitura à Appmax
# (mesma chamada de consultar_pedido usada em appmax-pix-pedido e
# appmax-estorno) para expor as conferências que _consultar_resultado faz
# antes de mapear o status; NUNCA POST/PUT/DELETE.
METODOS_APPMAX_PENDENTES = {"pix", "cartao"}
ESTADOS_TENTATIVA_APPMAX_PENDENTES = {"sending", "pending", "reconciliation_required"}
ESTADOS_INTENT_APPMAX_PENDENTES = {
    "created",
    "pending",
    "approved",
    "rejected",
    "expired",
    "refunded",
}
CAMPOS_TENTATIVA_APPMAX_PENDENTES = {
    "referencia",
    "metodo",
    "estado_tentativa",
    "estado_intent",
    "motivo",
    "operacoes",
    "idade_horas",
    "consulta_appmax",
}
CAMPOS_CONSULTA_APPMAX_PENDENTES = {
    "status_bruto",
    "total_paid_centavos",
    "valor_esperado_centavos",
    "conferencias",
}
CONFERENCIAS_APPMAX_PENDENTES = {
    "id",
    "cliente",
    "total",
    "sub_total",
    "taxa",
    "parcelas",
    "metodo",
    "status_e_texto",
}
MOTIVO_APPMAX_PENDENTES_OK = re.compile(r"[a-z_]{1,60}")
STATUS_BRUTO_APPMAX_PENDENTES_OK = re.compile(r"[a-z_]{1,40}")
LIMITE_TENTATIVAS_APPMAX_PENDENTES = 200
# Orçamento das consultas à Appmax dentro do docker exec de 30s (comando()):
# um cliente reutilizado (token não se autentica de novo por cartão) e um
# prazo total, não por cartão — na primeira falha de rede ou ao estourar,
# os cartões restantes saem como "nao_consultado" em vez de arriscar o
# comando inteiro (achado da revisão do PR #2228).
PRAZO_APPMAX_PENDENTES_SEGUNDOS = 20
APPMAX_AUTH_SANDBOX = "https://auth.sandboxappmax.com.br/oauth2/token"
APPMAX_API_SANDBOX = "https://api.sandboxappmax.com.br"
ESTADOS_AVISO_APPMAX = {"pendente", "processado", "falhou", "carta_morta", "nao_medido"}
ACOES_AVISO_APPMAX = {
    "candidata_ausente_ou_multipla",
    "instalacao_ausente",
    "instalacao_incompleta",
    "instalacao_multipla",
    "aviso_nao_preservado",
    "aviso_multiplo",
}
ACOES_INBOX_LATENCIA_APPMAX = {
    "candidata_ausente_ou_multipla",
    "pedido_ausente",
    "avisos_acima_do_limite",
}
CAMPOS_CANDIDATA_INBOX_LATENCIA = {
    "referencia",
    "criada_em",
    "metodo",
    "tentativa",
    "intent",
    "tentativas",
}
METODOS_INTENT = {"pix", "card"}
STATUS_INTENT = {"created", "pending", "approved", "rejected", "expired", "refunded"}
CAMPOS_AVISO_INBOX_LATENCIA = {
    "evento",
    "estado",
    "recebido_em",
    "processado_em",
    "latencia_ms",
    "reentregas",
}
LIMITE_AVISOS_INBOX_LATENCIA = 20
INSTANTE_ISO = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)
INSTALACOES_OBSERVADAS_POR_ACAO = {
    "instalacao_ausente": {0},
    "instalacao_incompleta": {1, 2},
    "instalacao_multipla": {2},
}
CAMPOS_VALOR_ESTORNO = {
    "amount",
    "value",
    "refunded_amount",
    "refund_amount",
    "refund_value",
    "refunded_value",
    "total",
    "total_refunded",
}
SITE_QUIZ_CAMPOS = {"id", "host", "active"}
QUIZ_CAMPOS = {"slug", "active", "versoes"}
VERSAO_QUIZ_CAMPOS = {
    "key",
    "peso",
    "active",
    "perguntas",
    "alternativas",
    "pontuacao_minima",
    "pontuacao_maxima",
    "faixas",
    "cobertura",
}
FAIXA_QUIZ_CAMPOS = {
    "key",
    "min_score",
    "max_score",
    "botao_destino",
    "botao_rotulo",
    "titulo",
}
COBERTURA_QUIZ_CAMPOS = {"sem_buraco", "sem_sobreposicao"}
SLUG_QUIZ = re.compile(r"[A-Za-z0-9_-]{1,100}")
MIGRACAO_QUIZ = re.compile(r"[0-9]{4}_[a-z0-9_]{1,200}")
# [MEDICAO-VPS:quiz-configuracao] script fechado, sem parâmetro: lê Site,
# Quiz, QuizVersion, Question, Option, ResultBand agregados e a contagem de
# Submission por result_key (nunca a linha, nunca e-mail/nome/telefone) e de
# OutboxEvent pendente. Migrações lidas do MigrationRecorder, filtradas ao
# app_label "quiz" (services/quiz não declara AppConfig; o label é o default
# do último componente de "apps.quiz").
QUIZ_CONFIGURACAO_CODIGO = (
    "import json\n"
    "from django.db import connection\n"
    "from django.db.migrations.recorder import MigrationRecorder\n"
    "from django.db.models import Count\n"
    "from apps.quiz.models import OutboxEvent, Quiz, Site, Submission\n"
    "def cobertura(bandas, minimo, maximo):\n"
    "    if not bandas:\n"
    "        return {'sem_buraco': False, 'sem_sobreposicao': True}\n"
    "    sobreposicao = any(bandas[i]['max_score'] >= bandas[i + 1]['min_score'] for i in range(len(bandas) - 1))\n"
    "    buraco = bandas[0]['min_score'] > minimo or bandas[-1]['max_score'] < maximo\n"
    "    if not buraco:\n"
    "        limite = bandas[0]['max_score']\n"
    "        for banda in bandas[1:]:\n"
    "            if banda['min_score'] > limite + 1:\n"
    "                buraco = True\n"
    "                break\n"
    "            limite = max(limite, banda['max_score'])\n"
    "    return {'sem_buraco': not buraco, 'sem_sobreposicao': not sobreposicao}\n"
    "sites = [{'id': s.id, 'host': s.host, 'active': s.active} for s in Site.objects.order_by('id')]\n"
    "quizzes = []\n"
    "for quiz in Quiz.objects.order_by('site_id', 'slug'):\n"
    "    versoes = []\n"
    "    for versao in quiz.versions.order_by('key').prefetch_related('questions__options', 'bands'):\n"
    "        perguntas = list(versao.questions.all())\n"
    "        alternativas = 0\n"
    "        minimo = 0\n"
    "        maximo = 0\n"
    "        for pergunta in perguntas:\n"
    "            pontos = [opcao.points for opcao in pergunta.options.all()]\n"
    "            alternativas += len(pontos)\n"
    "            if pontos:\n"
    "                minimo += min(pontos)\n"
    "                maximo += max(pontos)\n"
    "        bandas = [{'key': b.key, 'min_score': b.min_score, 'max_score': b.max_score, 'botao_destino': b.botao_destino, 'botao_rotulo': b.botao_rotulo, 'titulo': b.title} for b in versao.bands.all()]\n"
    "        versoes.append({'key': versao.key, 'peso': versao.weight, 'active': versao.active, 'perguntas': len(perguntas), 'alternativas': alternativas, 'pontuacao_minima': minimo, 'pontuacao_maxima': maximo, 'faixas': bandas, 'cobertura': cobertura(bandas, minimo, maximo)})\n"
    "    quizzes.append({'slug': quiz.slug, 'active': quiz.active, 'versoes': versoes})\n"
    "submissoes_por_resultado = {}\n"
    "for linha in Submission.objects.values('result_key').annotate(total=Count('id')):\n"
    "    submissoes_por_resultado[linha['result_key']] = linha['total']\n"
    "eventos_pendentes = OutboxEvent.objects.filter(published_at__isnull=True).count()\n"
    "migracoes = sorted(nome for app_label, nome in MigrationRecorder(connection).applied_migrations() if app_label == 'quiz')\n"
    "print(json.dumps({'sites': sites, 'quizzes': quizzes, 'submissoes_por_resultado': submissoes_por_resultado, 'eventos_pendentes': eventos_pendentes, 'migracoes': migracoes}, sort_keys=True))\n"
)
CHAVES_OBSERVACAO_APPMAX = {
    "tentativas_ate_15_min",
    "tentativas_15_a_60_min",
    "tentativas_60_min_a_um_dia_util",
    "tentativas_acima_de_um_dia_util",
    "pre_autorizacao_de_teste_sandbox",
    "inbox_sem_processamento",
    "outbox_pendente",
    "fila_morta",
    "pedidos_com_tentativas_abertas_duplicadas",
    "pedidos_com_efeito_duplicado",
}
# [MEDICAO-VPS:appmax-observacao] janelas da G12B, só contagens. Não chama a
# Appmax nem escreve; por isso não exige sandbox e serve à observação de
# produção. As definições de inbox, outbox e fila morta são as de
# pagamentos/supervisao.py:medir_pendencias. O dia útil pula sábado e domingo
# em America/Sao_Paulo; feriado conta como dia útil.
# Só no sandbox da Appmax (settings.APPMAX_AUTH_URL/APPMAX_API_URL apontando
# para sandboxappmax.com.br): uma tentativa de cartão não terminal cujo
# card_reason_code gravado é "autorizado" (motivo que
# card/service.py:_consultar_resultado grava quando o status Appmax é
# "autorizado", pré-autorização de teste do cartão 0028, sem captura) sai da
# faixa vermelha acima de um dia útil e entra em pre_autorizacao_de_teste_sandbox
# (aviso, não alarme). Em produção o card_reason_code "autorizado" é dinheiro
# reservado de verdade: a tentativa continua em tentativas_acima_de_um_dia_util.
APPMAX_OBSERVACAO_CODIGO = (
    "import json\n"
    "from collections import Counter\n"
    "from datetime import timedelta\n"
    "from zoneinfo import ZoneInfo\n"
    "from django.conf import settings\n"
    "from django.utils import timezone\n"
    "from pagamentos.core.models import ESTADOS_EM_ABERTO, AppmaxWebhookInbox, OutboxEvent, PaymentAttempt\n"
    "agora = timezone.now()\n"
    "fuso = ZoneInfo('America/Sao_Paulo')\n"
    f"appmax_auth_sandbox = {APPMAX_AUTH_SANDBOX!r}\n"
    f"appmax_api_sandbox = {APPMAX_API_SANDBOX!r}\n"
    "sandbox = settings.APPMAX_AUTH_URL == appmax_auth_sandbox and settings.APPMAX_API_URL == appmax_api_sandbox\n"
    "def um_dia_util_depois(instante):\n"
    "    dia = instante.astimezone(fuso)\n"
    "    if dia.weekday() >= 5:\n"
    "        dia = (dia + timedelta(days=7 - dia.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)\n"
    "    dia += timedelta(days=1)\n"
    "    while dia.weekday() >= 5:\n"
    "        dia += timedelta(days=1)\n"
    "    return dia\n"
    "def faixa(criada_em, metodo, motivo):\n"
    "    idade = agora - criada_em\n"
    "    if idade <= timedelta(minutes=15):\n"
    "        return 'tentativas_ate_15_min'\n"
    "    if idade <= timedelta(minutes=60):\n"
    "        return 'tentativas_15_a_60_min'\n"
    "    if agora <= um_dia_util_depois(criada_em):\n"
    "        return 'tentativas_60_min_a_um_dia_util'\n"
    "    if sandbox and metodo == 'card' and motivo == 'autorizado':\n"
    "        return 'pre_autorizacao_de_teste_sandbox'\n"
    "    return 'tentativas_acima_de_um_dia_util'\n"
    "faixas = Counter()\n"
    "pedidos = Counter()\n"
    "for criada_em, site, pedido, metodo, motivo in PaymentAttempt.objects.filter(provider='appmax', state__in=ESTADOS_EM_ABERTO).values_list('created_at', 'platform_site_id', 'intent__order_id', 'intent__method', 'intent__card_reason_code'):\n"
    "    faixas[faixa(criada_em, metodo, motivo)] += 1\n"
    "    pedidos[(site, pedido)] += 1\n"
    "efeitos = Counter()\n"
    "for evento, payload in OutboxEvent.objects.filter(payload__provider='appmax').values_list('event', 'payload'):\n"
    "    if isinstance(payload, dict) and payload.get('provider_reference_id'):\n"
    "        efeitos[(evento, payload.get('platform_site_id'), payload['provider_reference_id'])] += 1\n"
    "print(json.dumps({\n"
    "    'tentativas_ate_15_min': faixas['tentativas_ate_15_min'],\n"
    "    'tentativas_15_a_60_min': faixas['tentativas_15_a_60_min'],\n"
    "    'tentativas_60_min_a_um_dia_util': faixas['tentativas_60_min_a_um_dia_util'],\n"
    "    'tentativas_acima_de_um_dia_util': faixas['tentativas_acima_de_um_dia_util'],\n"
    "    'pre_autorizacao_de_teste_sandbox': faixas['pre_autorizacao_de_teste_sandbox'],\n"
    "    'inbox_sem_processamento': AppmaxWebhookInbox.objects.filter(processed_at__isnull=True, dead_lettered_at__isnull=True).count(),\n"
    "    'outbox_pendente': OutboxEvent.objects.filter(published_at__isnull=True).count(),\n"
    "    'fila_morta': AppmaxWebhookInbox.objects.filter(dead_lettered_at__isnull=False).count(),\n"
    "    'pedidos_com_tentativas_abertas_duplicadas': sum(1 for total in pedidos.values() if total > 1),\n"
    "    'pedidos_com_efeito_duplicado': len({chave[1:] for chave, total in efeitos.items() if total > 1}),\n"
    "}, sort_keys=True))\n"
)
CODIGOS_FECHADOS = {
    "quiz-configuracao": QUIZ_CONFIGURACAO_CODIGO,
    "appmax-observacao": APPMAX_OBSERVACAO_CODIGO,
}
FORMATO = (
    '{"estado":{{json .State.Status}},'
    '"saude":{{if .State.Health}}{{json .State.Health.Status}}{{else}}"ausente"{{end}},'
    '"reinicios":{{.RestartCount}},"imagem":{{json .Image}}}'
)
FORMATO_IMAGEM_ADMIN = '{"id":{{json .Id}},"repo_digests":{{json .RepoDigests}}}'
ACOES = {
    "entrada": "Escolha uma operação e um serviço do catálogo na main.",
    "instrumento": "Confira Docker e a disponibilidade da VPS e rode a operação de novo.",
    "sandbox": "A leitura foi bloqueada porque o serviço não está apontado ao sandbox. Corrija APPMAX_AUTH_URL e APPMAX_API_URL na configuração do sandbox e repita.",
    "ausente": "Confira o deploy desse serviço e publique de novo (push na main).",
    "infra": "Arquivo da infraestrutura inacessível ou inesperado; preserve a VPS e confira a publicação antes de repetir.",
    "borda": "A borda local não respondeu; confira o Traefik e a rota pública antes de repetir.",
    "formato": "A medição não corresponde ao protocolo; corrija o coletor e publique de novo.",
}


class Falha(Exception):
    pass


def validar(operacao, servico, permitidos, referencia=""):
    if servico not in permitidos:
        raise Falha("entrada")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", servico):
        raise Falha("entrada")
    if (operacao in OPERACOES_DA_PLATAFORMA) != (servico == "plataforma"):
        raise Falha("entrada")
    if (
        operacao
        in {
            "appmax-pix",
            "appmax-pix-pedido",
            "appmax-pix-aviso",
            "appmax-inbox-latencia",
            "appmax-observacao",
            "appmax-estorno",
            "appmax-pendentes",
        }
        and servico != "pagamentos"
    ):
        raise Falha("entrada")
    if operacao == "quiz-configuracao" and servico != "quiz":
        raise Falha("entrada")
    if operacao in {"appmax-pix", "appmax-inbox-latencia"}:
        if referencia and not re.fullmatch(r"[0-9a-f]{64}", referencia):
            raise Falha("entrada")
    elif operacao in {
        "appmax-pix-pedido",
        "appmax-pix-aviso",
    }:
        if not re.fullmatch(r"[0-9a-f]{64}", referencia):
            raise Falha("entrada")
    elif operacao == "appmax-estorno":
        if referencia and not re.fullmatch(r"[0-9a-f]{64}", referencia):
            raise Falha("entrada")
    elif referencia:
        raise Falha("entrada")


def comando(argumentos, prazo_segundos=30):
    try:
        resultado = subprocess.run(
            argumentos,
            cwd="/opt/plataforma",
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=prazo_segundos,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        raise Falha("instrumento") from None
    if resultado.returncode:
        if resultado.stdout.strip() == "APPMAX_SANDBOX_REQUIRED":
            raise Falha("sandbox")
        raise Falha("instrumento")
    return resultado.stdout


def nome_container(servico):
    """Na publicação unificada, as células compartilham um contêiner."""
    return "aplicacao" if aplicacao_ativa() and servico in SERVICOS_INCORPORADOS else servico


def aplicacao_ativa():
    """O rollback move o diário da aplicação e reativa os contêineres antigos."""
    return (RAIZ_INFRA / "publicacoes" / "aplicacao.json").is_file()


def comando_shell(servico, identificador, codigo):
    executor = (["-m", "config.comando", servico] if aplicacao_ativa()
                else ["manage.py"])
    return comando(["docker", "exec", identificador, "python", *executor,
                    "shell", "-c", codigo])


def hash_arquivo_infra(relativo):
    partes = Path(relativo).parts
    if os.name != "posix":
        atual = RAIZ_INFRA
        try:
            if not stat.S_ISDIR(atual.lstat().st_mode):
                raise Falha("infra")
            for indice, parte in enumerate(partes):
                atual = atual / parte
                try:
                    metadados = atual.lstat()
                except FileNotFoundError:
                    return None
                if indice < len(partes) - 1:
                    if not stat.S_ISDIR(metadados.st_mode):
                        raise Falha("infra")
                elif (
                    not stat.S_ISREG(metadados.st_mode)
                    or metadados.st_size > 4 * 1024 * 1024
                ):
                    raise Falha("infra")
            with atual.open("rb") as arquivo:
                return hashlib.file_digest(arquivo, "sha256").hexdigest()
        except OSError:
            raise Falha("infra") from None

    descritor = None
    try:
        descritor = os.open(RAIZ_INFRA, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        if not stat.S_ISDIR(os.fstat(descritor).st_mode):
            raise Falha("infra")
        for indice, parte in enumerate(partes):
            flags = os.O_RDONLY | os.O_NOFOLLOW
            if indice < len(partes) - 1:
                flags |= os.O_DIRECTORY
            try:
                proximo = os.open(parte, flags, dir_fd=descritor)
            except FileNotFoundError:
                return None
            os.close(descritor)
            descritor = proximo
            metadados = os.fstat(descritor)
            if indice < len(partes) - 1:
                if not stat.S_ISDIR(metadados.st_mode):
                    raise Falha("infra")
            elif (
                not stat.S_ISREG(metadados.st_mode)
                or metadados.st_size > 4 * 1024 * 1024
            ):
                raise Falha("infra")
        with os.fdopen(descritor, "rb", closefd=False) as arquivo:
            return hashlib.file_digest(arquivo, "sha256").hexdigest()
    except OSError:
        raise Falha("infra") from None
    finally:
        if descritor is not None:
            os.close(descritor)


def conferir_medicao(operacao, dados, referencia=""):
    if not isinstance(dados, dict):
        raise Falha("formato")
    if operacao == "estado-servico":
        if set(dados) != {"estado", "saude", "reinicios", "imagem"}:
            raise Falha("formato")
        if dados["estado"] not in ESTADOS or dados["saude"] not in SAUDES:
            raise Falha("formato")
        if (
            type(dados["reinicios"]) is not int
            or not 0 <= dados["reinicios"] <= 1000000000
        ):
            raise Falha("formato")
        if not isinstance(dados["imagem"], str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", dados["imagem"]
        ):
            raise Falha("formato")
    elif operacao == "estado-infra":
        if set(dados) not in (
            {"arquivos", "servicos", "imagem_admin", "borda_http"},
            {"arquivos", "servicos", "imagem_aplicacao", "borda_http"},
        ):
            raise Falha("formato")
        arquivos, servicos = dados["arquivos"], dados["servicos"]
        if not isinstance(arquivos, dict) or set(arquivos) != set(
            ARQUIVOS_ESTADO_INFRA
        ):
            raise Falha("formato")
        if any(
            valor is not None
            and (not isinstance(valor, str) or not re.fullmatch(r"[0-9a-f]{64}", valor))
            for valor in arquivos.values()
        ):
            raise Falha("formato")
        modo_aplicacao = "imagem_aplicacao" in dados
        esperados = (SERVICOS_ESTADO_INFRA_APLICACAO if modo_aplicacao
                     else SERVICOS_ESTADO_INFRA_LEGADO)
        if not isinstance(servicos, dict) or set(servicos) != set(esperados):
            raise Falha("formato")
        for valor in servicos.values():
            if valor is not None:
                conferir_medicao("estado-servico", valor)
        chave_imagem = "imagem_aplicacao" if modo_aplicacao else "imagem_admin"
        servico_imagem = "aplicacao" if modo_aplicacao else "admin"
        imagem = dados[chave_imagem]
        if servicos[servico_imagem] is None:
            if imagem is not None:
                raise Falha("formato")
        else:
            if not isinstance(imagem, dict) or set(imagem) != {
                "container_image",
                "id",
                "repo_digests",
            }:
                raise Falha("formato")
            if imagem["container_image"] != servicos[servico_imagem]["imagem"]:
                raise Falha("formato")
            if not isinstance(imagem["id"], str) or not re.fullmatch(
                r"sha256:[0-9a-f]{64}", imagem["id"]
            ):
                raise Falha("formato")
            digests = imagem["repo_digests"]
            if (
                not isinstance(digests, list)
                or len(digests) > 8
                or any(
                    not isinstance(digest, str)
                    or not re.fullmatch(
                        (r"(?:ghcr\.io/abundanciabr/)?plataforma-aplicacao@sha256:[0-9a-f]{64}"
                         if modo_aplicacao else
                         r"(?:ghcr\.io/abundanciabr/)?plataforma-admin@sha256:[0-9a-f]{64}"),
                        digest,
                    )
                    for digest in digests
                )
                or len(digests) != len(set(digests))
            ):
                raise Falha("formato")
        if (
            type(dados["borda_http"]) is not int
            or not 100 <= dados["borda_http"] <= 599
        ):
            raise Falha("formato")
    elif operacao == "espaco-disco":
        if set(dados) != {"total_bytes", "livres_bytes"}:
            raise Falha("formato")
        if any(type(v) is not int or v < 0 for v in dados.values()):
            raise Falha("formato")
        if not 0 < dados["total_bytes"] or dados["livres_bytes"] > dados["total_bytes"]:
            raise Falha("formato")
    elif operacao == "appmax-pix":
        if set(dados) != CAMPOS_RESUMO_APPMAX_PIX:
            if referencia:
                raise Falha("formato")
            if set(dados) != {"modo", "classificacao", "candidatas"}:
                raise Falha("formato")
            if dados["modo"] != "descoberta":
                raise Falha("formato")
            if dados["classificacao"] not in {"ausente", "unica", "multipla"}:
                raise Falha("formato")
            candidatas = dados["candidatas"]
            if not isinstance(candidatas, list) or len(candidatas) > 100:
                raise Falha("formato")
            if dados["classificacao"] == "ausente" and candidatas:
                raise Falha("formato")
            if dados["classificacao"] == "unica" and len(candidatas) != 1:
                raise Falha("formato")
            if dados["classificacao"] == "multipla" and len(candidatas) < 2:
                raise Falha("formato")
            referencias = []
            for candidata in candidatas:
                if set(candidata) != CAMPOS_CANDIDATA_APPMAX_PIX:
                    raise Falha("formato")
                if not re.fullmatch(r"[0-9a-f]{64}", candidata["referencia"]):
                    raise Falha("formato")
                if not re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$",
                    candidata["criada_em"],
                ):
                    raise Falha("formato")
                if candidata["tentativa"] not in ESTADOS_TENTATIVA:
                    raise Falha("formato")
                if candidata["intent"] not in {
                    "created",
                    "pending",
                    "approved",
                    "rejected",
                    "expired",
                }:
                    raise Falha("formato")
                if type(candidata["qr_presente"]) is not bool:
                    raise Falha("formato")
                if candidata["motivo"] not in MOTIVOS_APPMAX_PIX:
                    raise Falha("formato")
                if not isinstance(candidata["operacoes"], dict) or set(
                    candidata["operacoes"]
                ) != {"customer", "order", "payment"}:
                    raise Falha("formato")
                if any(
                    valor not in ESTADOS_OPERACAO_SAIDA
                    for valor in candidata["operacoes"].values()
                ):
                    raise Falha("formato")
                referencias.append(candidata["referencia"])
            if len(referencias) != len(set(referencias)):
                raise Falha("formato")
        else:
            if dados["tentativa"] not in ESTADOS_TENTATIVA:
                raise Falha("formato")
            if dados["intent"] not in {
                "created",
                "pending",
                "approved",
                "rejected",
                "expired",
            }:
                raise Falha("formato")
            if type(dados["qr_presente"]) is not bool:
                raise Falha("formato")
            if dados["motivo"] not in MOTIVOS_APPMAX_PIX:
                raise Falha("formato")
            if not isinstance(dados["operacoes"], dict) or set(dados["operacoes"]) != {
                "customer",
                "order",
                "payment",
            }:
                raise Falha("formato")
            if any(
                valor not in ESTADOS_OPERACAO_SAIDA
                for valor in dados["operacoes"].values()
            ):
                raise Falha("formato")
    elif operacao == "appmax-pix-aviso":
        campos_comuns = {
            "resultado",
            "referencia",
            "registros_encontrados",
            "pix_emv_preservado",
            "pix_qrcode_preservado",
            "pix_expiration_date_preservado",
            "estado_processamento",
            "recebido_em",
            "processado_em",
            "inbox_consultada",
            "instalacoes_observadas",
        }
        if dados.get("resultado") == "nao_medido":
            if set(dados) != campos_comuns | {"acao"}:
                raise Falha("formato")
            if dados["acao"] not in ACOES_AVISO_APPMAX:
                raise Falha("formato")
            encontrados = dados["registros_encontrados"]
            if type(dados["inbox_consultada"]) is not bool:
                raise Falha("formato")
            observadas = dados["instalacoes_observadas"]
            if observadas is not None and (
                type(observadas) is not int or observadas not in {0, 1, 2}
            ):
                raise Falha("formato")
            if dados["inbox_consultada"]:
                if type(encontrados) is not int or encontrados not in {0, 1, 2}:
                    raise Falha("formato")
                if observadas != 1:
                    raise Falha("formato")
            elif encontrados is not None:
                raise Falha("formato")
            if (
                dados["acao"] == "candidata_ausente_ou_multipla"
                and (dados["inbox_consultada"] or observadas is not None)
            ) or (
                dados["acao"] == "aviso_multiplo"
                and (not dados["inbox_consultada"] or encontrados != 2)
            ) or (
                dados["acao"] == "aviso_nao_preservado"
                and (
                    not dados["inbox_consultada"]
                    or encontrados not in {0, 1}
                )
            ) or (
                dados["acao"] in INSTALACOES_OBSERVADAS_POR_ACAO
                and (
                    dados["inbox_consultada"]
                    or observadas not in INSTALACOES_OBSERVADAS_POR_ACAO[dados["acao"]]
                )
            ):
                raise Falha("formato")
            if (
                not re.fullmatch(r"[0-9a-f]{64}", dados["referencia"])
                or dados["referencia"] != referencia
                or any(
                    dados[campo] is not False
                    for campo in (
                        "pix_emv_preservado",
                        "pix_qrcode_preservado",
                        "pix_expiration_date_preservado",
                    )
                )
                or dados["estado_processamento"] != "nao_medido"
                or dados["recebido_em"] is not None
                or dados["processado_em"] is not None
            ):
                raise Falha("formato")
        else:
            if set(dados) != campos_comuns or dados["resultado"] != "medido":
                raise Falha("formato")
            if (
                dados["referencia"] != referencia
                or not re.fullmatch(r"[0-9a-f]{64}", dados["referencia"])
                or dados["registros_encontrados"] != 1
                or dados["inbox_consultada"] is not True
                or dados["instalacoes_observadas"] != 1
                or type(dados["pix_emv_preservado"]) is not bool
                or type(dados["pix_qrcode_preservado"]) is not bool
                or type(dados["pix_expiration_date_preservado"]) is not bool
                or dados["estado_processamento"] not in ESTADOS_AVISO_APPMAX - {"nao_medido"}
                or not isinstance(dados["recebido_em"], str)
                or not re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$",
                    dados["recebido_em"],
                )
                or (
                    dados["processado_em"] is not None
                    and (
                        not isinstance(dados["processado_em"], str)
                        or not re.fullmatch(
                            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$",
                            dados["processado_em"],
                        )
                    )
                )
            ):
                raise Falha("formato")
    elif operacao == "appmax-inbox-latencia":
        if dados.get("modo") == "descoberta":
            if referencia:
                raise Falha("formato")
            if set(dados) != {"modo", "classificacao", "candidatas"}:
                raise Falha("formato")
            if dados["classificacao"] not in {
                "ausente",
                "unica",
                "multipla",
                "acima_do_limite",
            }:
                raise Falha("formato")
            candidatas = dados["candidatas"]
            if not isinstance(candidatas, list) or len(candidatas) > 100:
                raise Falha("formato")
            if dados["classificacao"] in {"ausente", "acima_do_limite"} and candidatas:
                raise Falha("formato")
            if dados["classificacao"] == "unica" and len(candidatas) != 1:
                raise Falha("formato")
            if dados["classificacao"] == "multipla" and len(candidatas) < 2:
                raise Falha("formato")
            referencias = []
            for candidata in candidatas:
                if set(candidata) != CAMPOS_CANDIDATA_INBOX_LATENCIA:
                    raise Falha("formato")
                if not re.fullmatch(r"[0-9a-f]{64}", candidata["referencia"]):
                    raise Falha("formato")
                if not INSTANTE_ISO.fullmatch(candidata["criada_em"]):
                    raise Falha("formato")
                if candidata["metodo"] not in METODOS_INTENT:
                    raise Falha("formato")
                if candidata["tentativa"] not in ESTADOS_TENTATIVA:
                    raise Falha("formato")
                if candidata["intent"] not in STATUS_INTENT:
                    raise Falha("formato")
                if type(candidata["tentativas"]) is not int or not 1 <= candidata["tentativas"] <= 100:
                    raise Falha("formato")
                referencias.append(candidata["referencia"])
            if len(referencias) != len(set(referencias)):
                raise Falha("formato")
        else:
            if not isinstance(dados.get("referencia"), str) or not re.fullmatch(
                r"[0-9a-f]{64}", dados["referencia"]
            ):
                raise Falha("formato")
            if dados["referencia"] != referencia:
                raise Falha("formato")
            if dados.get("resultado") == "nao_medido":
                if set(dados) != {"resultado", "referencia", "acao"}:
                    raise Falha("formato")
                if dados["acao"] not in ACOES_INBOX_LATENCIA_APPMAX:
                    raise Falha("formato")
            else:
                if set(dados) != {"resultado", "referencia", "avisos", "efeitos"}:
                    raise Falha("formato")
                if dados["resultado"] != "medido":
                    raise Falha("formato")
                if type(dados["efeitos"]) is not int or not 0 <= dados["efeitos"] <= 1000000:
                    raise Falha("formato")
                avisos = dados["avisos"]
                if not isinstance(avisos, list) or len(avisos) > LIMITE_AVISOS_INBOX_LATENCIA:
                    raise Falha("formato")
                for aviso in avisos:
                    if not isinstance(aviso, dict) or set(aviso) != CAMPOS_AVISO_INBOX_LATENCIA:
                        raise Falha("formato")
                    if (
                        not isinstance(aviso["evento"], str)
                        or len(aviso["evento"]) > 100
                        or not re.fullmatch(r"[a-z]+(?:_[a-z]+)*", aviso["evento"])
                    ):
                        raise Falha("formato")
                    if aviso["estado"] not in ESTADOS_AVISO_APPMAX - {"nao_medido"}:
                        raise Falha("formato")
                    reentregas = aviso["reentregas"]
                    if type(reentregas) is not int or not 0 <= reentregas <= 1000000:
                        raise Falha("formato")
                    if not isinstance(aviso["recebido_em"], str) or not INSTANTE_ISO.fullmatch(
                        aviso["recebido_em"]
                    ):
                        raise Falha("formato")
                    if aviso["processado_em"] is None:
                        if aviso["latencia_ms"] is not None or aviso["estado"] == "processado":
                            raise Falha("formato")
                        continue
                    if not isinstance(aviso["processado_em"], str) or not INSTANTE_ISO.fullmatch(
                        aviso["processado_em"]
                    ):
                        raise Falha("formato")
                    try:
                        recebido = datetime.fromisoformat(aviso["recebido_em"].replace("Z", "+00:00"))
                        processado = datetime.fromisoformat(
                            aviso["processado_em"].replace("Z", "+00:00")
                        )
                    except ValueError:
                        raise Falha("formato") from None
                    latencia = (processado - recebido) // timedelta(milliseconds=1)
                    if latencia < 0:
                        raise Falha("formato")
                    if type(aviso["latencia_ms"]) is not int or aviso["latencia_ms"] != latencia:
                        raise Falha("formato")
    elif operacao == "appmax-observacao":
        if set(dados) != CHAVES_OBSERVACAO_APPMAX:
            raise Falha("formato")
        if any(type(v) is not int or not 0 <= v <= 1000000000 for v in dados.values()):
            raise Falha("formato")
    elif operacao == "appmax-pix-pedido":
        if dados.get("resultado") == "nao_medido":
            if set(dados) != {"resultado", "referencia", "acao"}:
                raise Falha("formato")
            if dados["referencia"] != referencia:
                raise Falha("formato")
            if not re.fullmatch(r"[0-9a-f]{64}", dados["referencia"]):
                raise Falha("formato")
            if dados["acao"] not in {
                "candidata_ausente_ou_multipla",
                "identidade_nao_comprovada",
                "metodo_nao_comprovado",
                "valor_nao_comprovado",
                "qr_nao_comprovado",
                "verificar_formato_resposta_sandbox",
            }:
                raise Falha("formato")
        else:
            campos = {
                "resultado",
                "referencia",
                "identidade_confere",
                "metodo",
                "metodo_confere",
                "valor_centavos",
                "valor_confere",
                "status",
                "qr_presente",
                "qr_formato_aceito",
                "qr_vencido",
                "diagnostico",
            }
            if set(dados) != campos or dados["resultado"] != "medido":
                raise Falha("formato")
            if dados["referencia"] != referencia:
                raise Falha("formato")
            if not re.fullmatch(r"[0-9a-f]{64}", dados["referencia"]):
                raise Falha("formato")
            if (
                dados["identidade_confere"] is not True
                or dados["metodo"] != "pix"
                or dados["metodo_confere"] is not True
                or type(dados["valor_centavos"]) is not int
                or dados["valor_centavos"] <= 0
                or dados["valor_confere"] is not True
                or dados["status"] not in STATUS_APPMAX_PEDIDO
                or type(dados["qr_presente"]) is not bool
                or type(dados["qr_formato_aceito"]) is not bool
                or type(dados["qr_vencido"]) is not bool
                or dados["diagnostico"] not in DIAGNOSTICOS_APPMAX_PEDIDO
            ):
                raise Falha("formato")
            if not dados["qr_presente"] and (
                dados["qr_formato_aceito"] or dados["qr_vencido"]
            ):
                raise Falha("formato")
    elif operacao == "appmax-pendentes":
        if set(dados) != {"tentativas"}:
            raise Falha("formato")
        tentativas = dados["tentativas"]
        if not isinstance(tentativas, list) or len(
            tentativas
        ) > LIMITE_TENTATIVAS_APPMAX_PENDENTES:
            raise Falha("formato")
        referencias = []
        for item in tentativas:
            if not isinstance(item, dict) or set(item) != CAMPOS_TENTATIVA_APPMAX_PENDENTES:
                raise Falha("formato")
            if not isinstance(item["referencia"], str) or not re.fullmatch(
                r"[0-9a-f]{64}", item["referencia"]
            ):
                raise Falha("formato")
            referencias.append(item["referencia"])
            if item["metodo"] not in METODOS_APPMAX_PENDENTES:
                raise Falha("formato")
            if item["estado_tentativa"] not in ESTADOS_TENTATIVA_APPMAX_PENDENTES:
                raise Falha("formato")
            if item["estado_intent"] not in ESTADOS_INTENT_APPMAX_PENDENTES:
                raise Falha("formato")
            motivo = item["motivo"]
            if not isinstance(motivo, str) or (
                motivo != "vazio"
                and motivo != "fora_do_padrao"
                and not MOTIVO_APPMAX_PENDENTES_OK.fullmatch(motivo)
            ):
                raise Falha("formato")
            operacoes = item["operacoes"]
            if not isinstance(operacoes, dict) or set(operacoes) != {
                "customer",
                "order",
                "payment",
            }:
                raise Falha("formato")
            if any(valor not in ESTADOS_OPERACAO_SAIDA for valor in operacoes.values()):
                raise Falha("formato")
            idade = item["idade_horas"]
            if type(idade) is not int or not 0 <= idade <= 1000000:
                raise Falha("formato")
            consulta = item["consulta_appmax"]
            if consulta is None:
                continue
            if item["metodo"] != "cartao":
                raise Falha("formato")
            if not isinstance(consulta, dict) or set(
                consulta
            ) != CAMPOS_CONSULTA_APPMAX_PENDENTES:
                raise Falha("formato")
            status_bruto = consulta["status_bruto"]
            if not isinstance(status_bruto, str) or (
                status_bruto != "fora_do_padrao"
                and not STATUS_BRUTO_APPMAX_PENDENTES_OK.fullmatch(status_bruto)
            ):
                raise Falha("formato")
            total_paid = consulta["total_paid_centavos"]
            if total_paid is not None and (
                type(total_paid) is not int or total_paid < 0
            ):
                raise Falha("formato")
            valor_esperado = consulta["valor_esperado_centavos"]
            if type(valor_esperado) is not int or valor_esperado < 0:
                raise Falha("formato")
            conferencias = consulta["conferencias"]
            if not isinstance(conferencias, dict) or set(
                conferencias
            ) != CONFERENCIAS_APPMAX_PENDENTES:
                raise Falha("formato")
            if any(type(v) is not bool for v in conferencias.values()):
                raise Falha("formato")
        if len(referencias) != len(set(referencias)):
            raise Falha("formato")
    elif operacao == "appmax-estorno":
        if set(dados) != {
            "pedido",
            "referencia",
            "status",
            "pedido_confere",
            "refunded_at",
            "campos_observados",
            "campo_valor",
            "valor_no_refund_centavos",
        }:
            raise Falha("formato")
        if dados["pedido"] == "ausente":
            if (
                any(
                    dados[campo] is not None
                    for campo in (
                        "referencia",
                        "status",
                        "campo_valor",
                        "valor_no_refund_centavos",
                    )
                )
                or dados["pedido_confere"] is not False
                or dados["refunded_at"] is not False
                or dados["campos_observados"] != []
            ):
                raise Falha("formato")
        elif dados["pedido"] == "encontrado":
            if not isinstance(dados["referencia"], str) or not re.fullmatch(
                r"[0-9a-f]{64}", dados["referencia"]
            ):
                raise Falha("formato")
            if dados["status"] not in {
                "aprovado",
                "integrado",
                "estornado",
                "pendente",
                "outro",
            }:
                raise Falha("formato")
            if (
                dados["pedido_confere"] is not True
                or type(dados["refunded_at"]) is not bool
            ):
                raise Falha("formato")
            campos = dados["campos_observados"]
            if (
                not isinstance(campos, list)
                or len(campos) != len(set(campos))
                or any(campo not in CAMPOS_VALOR_ESTORNO for campo in campos)
            ):
                raise Falha("formato")
            if dados["campo_valor"] is None:
                if dados["valor_no_refund_centavos"] is not None:
                    raise Falha("formato")
            elif (
                dados["campo_valor"] not in campos
                or type(dados["valor_no_refund_centavos"]) is not int
                or dados["valor_no_refund_centavos"] <= 0
            ):
                raise Falha("formato")
        else:
            raise Falha("formato")
    elif operacao == "versao-compose":
        if set(dados) != {"versao"} or not isinstance(dados["versao"], str):
            raise Falha("formato")
        if not re.fullmatch(r"v?[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}", dados["versao"]):
            raise Falha("formato")
    elif operacao == "quiz-configuracao":
        if set(dados) != {
            "sites",
            "quizzes",
            "submissoes_por_resultado",
            "eventos_pendentes",
            "migracoes",
        }:
            raise Falha("formato")
        sites = dados["sites"]
        if not isinstance(sites, list) or len(sites) > 1000:
            raise Falha("formato")
        for site in sites:
            if set(site) != SITE_QUIZ_CAMPOS:
                raise Falha("formato")
            if (
                not isinstance(site["id"], str)
                or not 0 < len(site["id"]) <= 64
                or not isinstance(site["host"], str)
                or not 0 < len(site["host"]) <= 255
                or type(site["active"]) is not bool
            ):
                raise Falha("formato")
        quizzes = dados["quizzes"]
        if not isinstance(quizzes, list) or len(quizzes) > 1000:
            raise Falha("formato")
        for quiz in quizzes:
            if set(quiz) != QUIZ_CAMPOS:
                raise Falha("formato")
            if not SLUG_QUIZ.fullmatch(quiz["slug"]) or type(quiz["active"]) is not bool:
                raise Falha("formato")
            versoes = quiz["versoes"]
            if not isinstance(versoes, list) or len(versoes) > 1000:
                raise Falha("formato")
            for versao in versoes:
                if set(versao) != VERSAO_QUIZ_CAMPOS:
                    raise Falha("formato")
                if not SLUG_QUIZ.fullmatch(versao["key"]):
                    raise Falha("formato")
                if type(versao["peso"]) is not int or not 0 <= versao["peso"] <= 32767:
                    raise Falha("formato")
                if type(versao["active"]) is not bool:
                    raise Falha("formato")
                if (
                    type(versao["perguntas"]) is not int
                    or not 0 <= versao["perguntas"] <= 100000
                    or type(versao["alternativas"]) is not int
                    or not 0 <= versao["alternativas"] <= 100000
                ):
                    raise Falha("formato")
                if (
                    type(versao["pontuacao_minima"]) is not int
                    or type(versao["pontuacao_maxima"]) is not int
                    or not -1000000
                    <= versao["pontuacao_minima"]
                    <= versao["pontuacao_maxima"]
                    <= 1000000
                ):
                    raise Falha("formato")
                faixas = versao["faixas"]
                if not isinstance(faixas, list) or len(faixas) > 1000:
                    raise Falha("formato")
                for faixa in faixas:
                    if set(faixa) != FAIXA_QUIZ_CAMPOS:
                        raise Falha("formato")
                    if not SLUG_QUIZ.fullmatch(faixa["key"]):
                        raise Falha("formato")
                    if (
                        type(faixa["min_score"]) is not int
                        or type(faixa["max_score"]) is not int
                        or not -1000000
                        <= faixa["min_score"]
                        <= faixa["max_score"]
                        <= 1000000
                    ):
                        raise Falha("formato")
                    if (
                        not isinstance(faixa["botao_destino"], str)
                        or len(faixa["botao_destino"]) > 500
                        or not isinstance(faixa["botao_rotulo"], str)
                        or len(faixa["botao_rotulo"]) > 80
                        or bool(faixa["botao_destino"]) != bool(faixa["botao_rotulo"])
                    ):
                        raise Falha("formato")
                    if (
                        not isinstance(faixa["titulo"], str)
                        or not 0 < len(faixa["titulo"]) <= 200
                    ):
                        raise Falha("formato")
                cobertura = versao["cobertura"]
                if set(cobertura) != COBERTURA_QUIZ_CAMPOS or any(
                    type(valor) is not bool for valor in cobertura.values()
                ):
                    raise Falha("formato")
        submissoes = dados["submissoes_por_resultado"]
        if not isinstance(submissoes, dict) or len(submissoes) > 1000:
            raise Falha("formato")
        for chave, total in submissoes.items():
            if not SLUG_QUIZ.fullmatch(chave):
                raise Falha("formato")
            if type(total) is not int or not 0 <= total <= 1000000000:
                raise Falha("formato")
        if (
            type(dados["eventos_pendentes"]) is not int
            or not 0 <= dados["eventos_pendentes"] <= 1000000000
        ):
            raise Falha("formato")
        migracoes = dados["migracoes"]
        if (
            not isinstance(migracoes, list)
            or len(migracoes) > 1000
            or len(migracoes) != len(set(migracoes))
            or any(not MIGRACAO_QUIZ.fullmatch(nome) for nome in migracoes)
        ):
            raise Falha("formato")
    else:
        raise Falha("formato")
    return dados


def medir_servico_estado_infra(nome):
    identificador = comando(
        [
            "docker",
            "ps",
            "--all",
            "--quiet",
            "--no-trunc",
            "--filter",
            "label=com.docker.compose.project=plataforma",
            "--filter",
            "label=com.docker.compose.service=" + nome_container(nome),
        ],
        prazo_segundos=10,
    ).strip()
    if not identificador:
        return None
    if not re.fullmatch(r"[0-9a-f]{12,64}", identificador):
        raise Falha("formato")
    try:
        dados = json.loads(
            comando(
                ["docker", "inspect", "--format", FORMATO, identificador],
                prazo_segundos=10,
            )
        )
    except (ValueError, TypeError):
        raise Falha("formato") from None
    return conferir_medicao("estado-servico", dados)


def medir(operacao, servico, referencia=""):
    if operacao == "estado-infra":
        arquivos = {nome: hash_arquivo_infra(nome) for nome in ARQUIVOS_ESTADO_INFRA}
        servicos = {}
        modo_aplicacao = aplicacao_ativa()
        for nome in (SERVICOS_ESTADO_INFRA_APLICACAO if modo_aplicacao
                     else SERVICOS_ESTADO_INFRA_LEGADO):
            servicos[nome] = medir_servico_estado_infra(nome)
        servico_imagem = "aplicacao" if modo_aplicacao else "admin"
        chave_imagem = "imagem_aplicacao" if modo_aplicacao else "imagem_admin"
        imagem = None
        if servicos[servico_imagem] is not None:
            container_image = servicos[servico_imagem]["imagem"]
            try:
                inspeccionada = json.loads(
                    comando(
                        [
                            "docker",
                            "image",
                            "inspect",
                            "--format",
                            FORMATO_IMAGEM_ADMIN,
                            container_image,
                        ],
                        prazo_segundos=10,
                    )
                )
            except (ValueError, TypeError):
                raise Falha("formato") from None
            if not isinstance(inspeccionada, dict):
                raise Falha("formato")
            if inspeccionada.get("repo_digests") is None:
                inspeccionada["repo_digests"] = []
            imagem = {
                "container_image": container_image,
                **inspeccionada,
            }
        try:
            codigo = comando(
                [
                    "curl",
                    "-skS",
                    "--connect-timeout",
                    "3",
                    "--max-time",
                    "12",
                    "--resolve",
                    "meshcraft.top:443:127.0.0.1",
                    "--resolve",
                    "meshcraft.top:80:127.0.0.1",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    "https://meshcraft.top/",
                ],
                prazo_segundos=15,
            ).strip()
        except Falha:
            raise Falha("borda") from None
        if not re.fullmatch(r"[1-5][0-9]{2}", codigo):
            raise Falha("borda")
        return conferir_medicao(
            operacao,
            {
                "arquivos": arquivos,
                "servicos": servicos,
                chave_imagem: imagem,
                "borda_http": int(codigo),
            },
        )
    if operacao == "espaco-disco":
        try:
            disco = shutil.disk_usage("/opt/plataforma")
        except OSError:
            raise Falha("instrumento") from None
        return conferir_medicao(
            operacao, {"total_bytes": disco.total, "livres_bytes": disco.free}
        )
    if operacao == "versao-compose":
        versao = comando(["docker", "compose", "version", "--short"]).strip()
        return conferir_medicao(operacao, {"versao": versao})
    identificador = comando(
        [
            "docker",
            "ps",
            "--all",
            "--quiet",
            "--no-trunc",
            "--filter",
            "label=com.docker.compose.project=plataforma",
            "--filter",
            "label=com.docker.compose.service=" + nome_container(servico),
        ]
    ).strip()
    if not identificador:
        raise Falha("ausente")
    if not re.fullmatch(r"[0-9a-f]{12,64}", identificador):
        raise Falha("formato")
    if operacao == "appmax-pix":
        sandbox_urls = (APPMAX_AUTH_SANDBOX, APPMAX_API_SANDBOX)
        codigo = (
            "import hashlib,json\n"
            "from datetime import timedelta\n"
            "from django.utils import timezone\n"
            "from django.conf import settings\n"
            "from pagamentos.core.models import PaymentAttempt\n"
            f"referencia = {referencia!r}\n"
            f"appmax_auth_sandbox = {sandbox_urls[0]!r}\n"
            f"appmax_api_sandbox = {sandbox_urls[1]!r}\n"
            "if not (settings.APPMAX_AUTH_URL == appmax_auth_sandbox and settings.APPMAX_API_URL == appmax_api_sandbox):\n"
            "    print('APPMAX_SANDBOX_REQUIRED')\n"
            "    raise SystemExit(23)\n"
            f"tentativas = list(PaymentAttempt.objects.filter(provider='appmax', platform_site_id='{SITE_MESHCRAFT}', intent__method='pix', created_at__gte=timezone.now()-timedelta(days=7)).select_related('intent').prefetch_related('operacoes').order_by('-created_at')[:100])\n"
            "tentativas = [t for t in tentativas if not referencia or " + REFERENCIA_DA_TENTATIVA + " == referencia]\n"
            "codigos = ('campo_expiration_date','campo_document_number','campo_customer_id','campo_order_id','campo_payment_data','sem_json','sem_campo_identificavel')\n"
            "def candidato(t):\n"
            "    bruto = t.reason or ''\n"
            "    motivo = next((c for c in codigos if bruto.endswith('diagnostico_' + c)), 'indisponivel')\n"
            "    operacoes = {x: 'not_started' for x in ('customer', 'order', 'payment')}\n"
            "    for operacao in t.operacoes.all():\n"
            "        operacoes[operacao.operation_type] = operacao.state\n"
            "    return {'referencia': " + REFERENCIA_DA_TENTATIVA + ", 'criada_em': t.created_at.isoformat(), 'tentativa': t.state, 'intent': t.intent.status, 'motivo': motivo, 'qr_presente': bool(t.intent.pix_qr_code and t.intent.pix_qr_code_base64), 'operacoes': operacoes}\n"
            "if referencia:\n"
            "    assert len(tentativas) == 1\n"
            "    resumo = candidato(tentativas[0])\n"
            "    print(json.dumps({x: resumo[x] for x in ('tentativa', 'intent', 'motivo', 'qr_presente', 'operacoes')}, sort_keys=True))\n"
            "else:\n"
            "    candidatas = [candidato(t) for t in tentativas]\n"
            "    classificacao = 'ausente' if not candidatas else 'unica' if len(candidatas) == 1 else 'multipla'\n"
            "    print(json.dumps({'modo': 'descoberta', 'classificacao': classificacao, 'candidatas': candidatas}, sort_keys=True))\n"
        )
        try:
            dados = json.loads(
                comando_shell(servico, identificador, codigo)
            )
        except (ValueError, TypeError):
            raise Falha("formato") from None
        return conferir_medicao(operacao, dados, referencia)
    if operacao == "appmax-pix-aviso":
        sandbox_urls = (APPMAX_AUTH_SANDBOX, APPMAX_API_SANDBOX)
        codigo = (
            "import hashlib,json\n"
            "from datetime import timedelta\n"
            "from django.conf import settings\n"
            f"referencia = {referencia!r}\n"
            f"appmax_auth_sandbox = {sandbox_urls[0]!r}\n"
            f"appmax_api_sandbox = {sandbox_urls[1]!r}\n"
            "if not (settings.APPMAX_AUTH_URL == appmax_auth_sandbox and settings.APPMAX_API_URL == appmax_api_sandbox):\n"
            "    print('APPMAX_SANDBOX_REQUIRED')\n"
            "    raise SystemExit(23)\n"
            "from django.utils import timezone\n"
            "from pagamentos.core.models import AppmaxWebhookInbox, InstalacaoAppmax, PaymentAttempt\n"
            f"tentativas = list(PaymentAttempt.objects.filter(provider='appmax', platform_site_id='{SITE_MESHCRAFT}', intent__method='pix', created_at__gte=timezone.now()-timedelta(days=7)).select_related('intent').order_by('-created_at')[:100])\n"
            "tentativas = [t for t in tentativas if " + REFERENCIA_DA_TENTATIVA + " == referencia]\n"
            "def nao_medido(acao, encontrados=None, instalacoes_observadas=None, inbox_consultada=False):\n"
            "    return {'resultado':'nao_medido','referencia':referencia,'registros_encontrados':encontrados,'inbox_consultada':inbox_consultada,'instalacoes_observadas':instalacoes_observadas,'pix_emv_preservado':False,'pix_qrcode_preservado':False,'pix_expiration_date_preservado':False,'estado_processamento':'nao_medido','recebido_em':None,'processado_em':None,'acao':acao}\n"
            "if len(tentativas) != 1:\n"
            "    print(json.dumps(nao_medido('candidata_ausente_ou_multipla'), sort_keys=True))\n"
            "else:\n"
            "    tentativa = tentativas[0]\n"
            f"    instalacoes_brutas = list(InstalacaoAppmax.objects.filter(platform_site_ids__contains=['{SITE_MESHCRAFT}'])[:2])\n"
            "    instalacoes = [i for i in instalacoes_brutas if isinstance(i.platform_site_ids, list) and tentativa.platform_site_id in i.platform_site_ids and isinstance(i.app_id, str) and i.app_id.strip() and isinstance(i.appmax_site_id, str) and i.appmax_site_id.strip()]\n"
            "    if not instalacoes_brutas:\n"
            "        print(json.dumps(nao_medido('instalacao_ausente', instalacoes_observadas=0), sort_keys=True))\n"
            "    elif len(instalacoes) != len(instalacoes_brutas):\n"
            "        print(json.dumps(nao_medido('instalacao_incompleta', instalacoes_observadas=len(instalacoes_brutas)), sort_keys=True))\n"
            "    elif len(instalacoes) > 1:\n"
            "        print(json.dumps(nao_medido('instalacao_multipla', instalacoes_observadas=len(instalacoes)), sort_keys=True))\n"
            "    else:\n"
            "        instalacao = instalacoes[0]\n"
            "        avisos = list(AppmaxWebhookInbox.objects.filter(app_id=instalacao.app_id, appmax_site_id=instalacao.appmax_site_id, platform_site_id=tentativa.platform_site_id, event='order_pix_created', event_type='order', external_order_id=str(tentativa.external_order_id)).order_by('-received_at')[:2])\n"
            "        if len(avisos) != 1:\n"
            "            acao = 'aviso_nao_preservado' if not avisos else 'aviso_multiplo'\n"
            "            print(json.dumps(nao_medido(acao, len(avisos), 1, True), sort_keys=True))\n"
            "        else:\n"
            "            aviso = avisos[0]\n"
            "            payload = aviso.payload if isinstance(aviso.payload, dict) else {}\n"
            "            dados = payload.get('data') if isinstance(payload.get('data'), dict) else {}\n"
            "            if str(dados.get('order_id', '')).strip() != str(tentativa.external_order_id).strip():\n"
            "                print(json.dumps(nao_medido('aviso_nao_preservado', 1, 1, True), sort_keys=True))\n"
            "                raise SystemExit(0)\n"
            "            payment_info = dados.get('payment_info') if isinstance(dados.get('payment_info'), dict) else {}\n"
            "            pix = payment_info.get('pix') if isinstance(payment_info.get('pix'), dict) else {}\n"
            "            def presente(nome):\n"
            "                valor = pix.get(nome)\n"
            "                return isinstance(valor, str) and bool(valor.strip())\n"
            "            if aviso.dead_lettered_at is not None:\n"
            "                estado = 'carta_morta'\n"
            "            elif aviso.processed_at is not None:\n"
            "                estado = 'processado'\n"
            "            elif type(aviso.failed_attempts) is int and aviso.failed_attempts > 0:\n"
            "                estado = 'falhou'\n"
            "            else:\n"
            "                estado = 'pendente'\n"
            "            recebido_em = aviso.received_at.isoformat() if hasattr(aviso.received_at, 'isoformat') else None\n"
            "            processado_em = aviso.processed_at.isoformat() if aviso.processed_at is not None and hasattr(aviso.processed_at, 'isoformat') else None\n"
            "            if recebido_em is None:\n"
            "                print(json.dumps(nao_medido('aviso_nao_preservado', 1, 1, True), sort_keys=True))\n"
            "            else:\n"
            "                print(json.dumps({'resultado':'medido','referencia':referencia,'registros_encontrados':1,'inbox_consultada':True,'instalacoes_observadas':1,'pix_emv_preservado':presente('pix_emv'),'pix_qrcode_preservado':presente('pix_qrcode'),'pix_expiration_date_preservado':presente('pix_expiration_date'),'estado_processamento':estado,'recebido_em':recebido_em,'processado_em':processado_em}, sort_keys=True))\n"
        )
        try:
            dados = json.loads(
                comando_shell(servico, identificador, codigo)
            )
        except (ValueError, TypeError):
            raise Falha("formato") from None
        return conferir_medicao(operacao, dados, referencia)
    if operacao == "appmax-inbox-latencia":
        sandbox_urls = (APPMAX_AUTH_SANDBOX, APPMAX_API_SANDBOX)
        if not referencia:
            codigo = (
                "import hashlib,json\n"
                "from datetime import timedelta\n"
                "from django.conf import settings\n"
                f"appmax_auth_sandbox = {sandbox_urls[0]!r}\n"
                f"appmax_api_sandbox = {sandbox_urls[1]!r}\n"
                "if not (settings.APPMAX_AUTH_URL == appmax_auth_sandbox and settings.APPMAX_API_URL == appmax_api_sandbox):\n"
                "    print('APPMAX_SANDBOX_REQUIRED')\n"
                "    raise SystemExit(23)\n"
                "from django.db import connection\n"
                "from django.utils import timezone\n"
                "from pagamentos.core.models import PaymentAttempt\n"
                "with connection.cursor() as cursor:\n"
                "    cursor.execute('SET statement_timeout = 10000')\n"
                f"tentativas = list(PaymentAttempt.objects.filter(provider='appmax', platform_site_id='{SITE_MESHCRAFT}', intent__method='card', created_at__gte=timezone.now()-timedelta(days=7)).select_related('intent').order_by('-created_at')[:101])\n"
                "if len(tentativas) > 100:\n"
                "    print(json.dumps({'modo': 'descoberta', 'classificacao': 'acima_do_limite', 'candidatas': []}, sort_keys=True))\n"
                "    raise SystemExit(0)\n"
                "grupos = {}\n"
                "for t in tentativas:\n"
                "    referencia_t = " + REFERENCIA_DA_TENTATIVA + "\n"
                "    grupo = grupos.get(referencia_t)\n"
                "    if grupo is None:\n"
                "        grupos[referencia_t] = {'referencia': referencia_t, 'criada_em': t.created_at.isoformat(), 'metodo': t.intent.method, 'tentativa': t.state, 'intent': t.intent.status, 'tentativas': 1}\n"
                "    else:\n"
                "        grupo['tentativas'] += 1\n"
                "candidatas = list(grupos.values())\n"
                "classificacao = 'ausente' if not candidatas else 'unica' if len(candidatas) == 1 else 'multipla'\n"
                "print(json.dumps({'modo': 'descoberta', 'classificacao': classificacao, 'candidatas': candidatas}, sort_keys=True))\n"
            )
        else:
            codigo = (
                "import hashlib,json\n"
                "from datetime import timedelta\n"
                "from django.conf import settings\n"
                f"referencia = {referencia!r}\n"
                f"appmax_auth_sandbox = {sandbox_urls[0]!r}\n"
                f"appmax_api_sandbox = {sandbox_urls[1]!r}\n"
                "if not (settings.APPMAX_AUTH_URL == appmax_auth_sandbox and settings.APPMAX_API_URL == appmax_api_sandbox):\n"
                "    print('APPMAX_SANDBOX_REQUIRED')\n"
                "    raise SystemExit(23)\n"
                "from django.utils import timezone\n"
                "from pagamentos.core.models import AppmaxWebhookInbox, OutboxEvent, PaymentAttempt\n"
                f"tentativas = list(PaymentAttempt.objects.filter(provider='appmax', platform_site_id='{SITE_MESHCRAFT}', created_at__gte=timezone.now()-timedelta(days=7)).select_related('intent').order_by('-created_at')[:100])\n"
                "tentativas = [t for t in tentativas if " + REFERENCIA_DA_TENTATIVA + " == referencia]\n"
                "def nao_medido(acao):\n"
                "    print(json.dumps({'resultado': 'nao_medido', 'referencia': referencia, 'acao': acao}, sort_keys=True))\n"
                "    raise SystemExit(0)\n"
                "if len(tentativas) != 1:\n"
                "    nao_medido('candidata_ausente_ou_multipla')\n"
                "tentativa = tentativas[0]\n"
                "pedido = str(tentativa.external_order_id or '').strip()\n"
                "if not pedido:\n"
                "    nao_medido('pedido_ausente')\n"
                f"avisos = list(AppmaxWebhookInbox.objects.filter(platform_site_id=tentativa.platform_site_id, external_order_id=pedido).order_by('received_at', 'id')[:{LIMITE_AVISOS_INBOX_LATENCIA + 1}])\n"
                f"if len(avisos) > {LIMITE_AVISOS_INBOX_LATENCIA}:\n"
                "    nao_medido('avisos_acima_do_limite')\n"
                "def estado(aviso):\n"
                "    if aviso.dead_lettered_at is not None:\n"
                "        return 'carta_morta'\n"
                "    if aviso.processed_at is not None:\n"
                "        return 'processado'\n"
                "    return 'falhou' if aviso.failed_attempts > 0 else 'pendente'\n"
                "def resumo(aviso):\n"
                "    processado = aviso.processed_at\n"
                "    return {'evento': aviso.event, 'estado': estado(aviso), 'recebido_em': aviso.received_at.isoformat(), 'processado_em': processado.isoformat() if processado is not None else None, 'latencia_ms': (processado - aviso.received_at) // timedelta(milliseconds=1) if processado is not None else None, 'reentregas': aviso.redeliveries}\n"
                "efeitos = OutboxEvent.objects.filter(event__in=['pagamento.aprovado', 'pagamento.recusado'], payload__provider='appmax', payload__platform_site_id=tentativa.platform_site_id, payload__provider_reference_id=pedido).count()\n"
                "print(json.dumps({'resultado': 'medido', 'referencia': referencia, 'avisos': [resumo(aviso) for aviso in avisos], 'efeitos': efeitos}, sort_keys=True))\n"
            )
        try:
            dados = json.loads(
                comando_shell(servico, identificador, codigo)
            )
        except (ValueError, TypeError):
            raise Falha("formato") from None
        return conferir_medicao(operacao, dados, referencia)
    if operacao == "appmax-pix-pedido":
        sandbox_urls = (APPMAX_AUTH_SANDBOX, APPMAX_API_SANDBOX)
        codigo = (
            "import hashlib,json,re\n"
            "from datetime import datetime,timedelta,timezone as dt_timezone\n"
            "from zoneinfo import ZoneInfo\n"
            "from django.conf import settings\n"
            "from django.utils import timezone\n"
            f"referencia = {referencia!r}\n"
            f"appmax_auth_sandbox = {sandbox_urls[0]!r}\n"
            f"appmax_api_sandbox = {sandbox_urls[1]!r}\n"
            "if not (settings.APPMAX_AUTH_URL == appmax_auth_sandbox and settings.APPMAX_API_URL == appmax_api_sandbox):\n"
            "    print('APPMAX_SANDBOX_REQUIRED')\n"
            "    raise SystemExit(23)\n"
            "from pagamentos.core.models import PaymentAttempt\n"
            "from pagamentos.providers.appmax.client import AppmaxClient\n"
            f"tentativas = list(PaymentAttempt.objects.filter(provider='appmax', platform_site_id='{SITE_MESHCRAFT}', intent__method='pix', created_at__gte=timezone.now()-timedelta(days=7)).select_related('intent').order_by('-created_at')[:100])\n"
            "tentativas = [t for t in tentativas if " + REFERENCIA_DA_TENTATIVA + " == referencia]\n"
            "def nao_medido(acao):\n"
            "    return {'resultado': 'nao_medido', 'referencia': referencia, 'acao': acao}\n"
            "if len(tentativas) != 1:\n"
            "    print(json.dumps(nao_medido('candidata_ausente_ou_multipla'), sort_keys=True))\n"
            "else:\n"
            "    tentativa = tentativas[0]\n"
            "    order_id = str(tentativa.external_order_id or '')\n"
            "    customer_id = str(tentativa.customer_id or '')\n"
            "    if not re.fullmatch(r'[1-9][0-9]*', order_id) or not customer_id:\n"
            "        print(json.dumps(nao_medido('identidade_nao_comprovada'), sort_keys=True))\n"
            "    else:\n"
            "        try:\n"
            "            pedido = AppmaxClient().consultar_pedido(int(order_id))\n"
            "        except Exception:\n"
            "            print(json.dumps(nao_medido('verificar_formato_resposta_sandbox'), sort_keys=True))\n"
            "        else:\n"
            "            cliente = pedido.get('customer') if isinstance(pedido, dict) else None\n"
            "            pagamento = pedido.get('payment') if isinstance(pedido, dict) else None\n"
            "            valores = pedido.get('amounts') if isinstance(pedido, dict) else None\n"
            "            if not isinstance(cliente, dict) or str(cliente.get('id')) != customer_id:\n"
            "                print(json.dumps(nao_medido('identidade_nao_comprovada'), sort_keys=True))\n"
            "            elif not isinstance(pagamento, dict) or pagamento.get('method') != 'pix':\n"
            "                print(json.dumps(nao_medido('metodo_nao_comprovado'), sort_keys=True))\n"
            "            elif not isinstance(valores, dict) or type(valores.get('sub_total')) is not int or valores['sub_total'] <= 0 or type(tentativa.amount_cents) is not int or tentativa.amount_cents <= 0 or valores['sub_total'] != tentativa.amount_cents:\n"
            "                print(json.dumps(nao_medido('valor_nao_comprovado'), sort_keys=True))\n"
            "            else:\n"
            "                status = pedido.get('status')\n"
            "                if status not in ('aprovado','integrado','pendente_integracao','cancelado','recusado_por_risco','pendente','autorizado'):\n"
            "                    print(json.dumps(nao_medido('verificar_formato_resposta_sandbox'), sort_keys=True))\n"
            "                    raise SystemExit(0)\n"
            "                def campo(obj, nomes):\n"
            "                    for nome in nomes:\n"
            "                        if nome in obj:\n"
            "                            return obj[nome], True\n"
            "                    return None, False\n"
            "                qr_base64, tem_base64 = campo(pagamento, ('pix_qrcode','qr_code_base64'))\n"
            "                qr_emv, tem_emv = campo(pagamento, ('pix_emv','qr_code'))\n"
            "                vencimento, tem_vencimento = campo(pagamento, ('pix_expiration_date','expires_at'))\n"
            "                if not (tem_base64 and tem_emv):\n"
            "                    print(json.dumps(nao_medido('qr_nao_comprovado'), sort_keys=True))\n"
            "                    raise SystemExit(0)\n"
            "                if not isinstance(qr_base64, str) or not isinstance(qr_emv, str) or bool(qr_base64) != bool(qr_emv):\n"
            "                    print(json.dumps(nao_medido('qr_nao_comprovado'), sort_keys=True))\n"
            "                    raise SystemExit(0)\n"
            "                prefixo_qr = 'data:image/png;base64,'\n"
            "                if qr_base64.startswith(prefixo_qr):\n"
            "                    qr_base64 = qr_base64[len(prefixo_qr):]\n"
            "                if bool(qr_base64) != bool(qr_emv):\n"
            "                    print(json.dumps(nao_medido('qr_nao_comprovado'), sort_keys=True))\n"
            "                    raise SystemExit(0)\n"
            "                qr_presente = bool(qr_base64 and qr_emv)\n"
            "                qr_formato_aceito = False\n"
            "                qr_vencido = False\n"
            "                if qr_presente:\n"
            "                    if (\n"
            "                        not re.fullmatch(r'[A-Za-z0-9+/]+={0,2}', qr_base64)\n"
            "                        or not qr_emv.strip()\n"
            "                        or not isinstance(vencimento, str)\n"
            "                        or not tem_vencimento\n"
            "                    ):\n"
            "                        print(json.dumps(nao_medido('qr_nao_comprovado'), sort_keys=True))\n"
            "                        raise SystemExit(0)\n"
            "                    try:\n"
            "                        vencimento_data = datetime.fromisoformat(vencimento.replace(' ', 'T'))\n"
            "                    except (TypeError, ValueError):\n"
            "                        print(json.dumps(nao_medido('qr_nao_comprovado'), sort_keys=True))\n"
            "                        raise SystemExit(0)\n"
            "                    if vencimento_data.tzinfo is None:\n"
            "                        vencimento_data = vencimento_data.replace(tzinfo=ZoneInfo('America/Sao_Paulo'))\n"
            "                    qr_formato_aceito = True\n"
            "                    qr_vencido = datetime.now(dt_timezone.utc) >= vencimento_data.astimezone(dt_timezone.utc)\n"
            "                bruto = tentativa.reason or ''\n"
            "                if not isinstance(bruto, str) or not bruto.strip():\n"
            "                    diagnostico = 'vazio'\n"
            "                elif bruto == 'status_conciliado':\n"
            "                    diagnostico = 'status_conciliado'\n"
            "                elif bruto.startswith('appmax_pix_diagnostico_'):\n"
            "                    diagnostico = 'diagnostico'\n"
            "                else:\n"
            "                    diagnostico = 'outro_codigo'\n"
            "                print(json.dumps({'resultado':'medido','referencia':referencia,'identidade_confere':True,'metodo':'pix','metodo_confere':True,'valor_centavos':valores['sub_total'],'valor_confere':True,'status':status,'qr_presente':qr_presente,'qr_formato_aceito':qr_formato_aceito,'qr_vencido':qr_vencido,'diagnostico':diagnostico}, sort_keys=True))\n"
        )
        try:
            dados = json.loads(
                comando_shell(servico, identificador, codigo)
            )
        except (ValueError, TypeError):
            raise Falha("formato") from None
        return conferir_medicao(operacao, dados, referencia)
    if operacao == "appmax-pendentes":
        sandbox_urls = (APPMAX_AUTH_SANDBOX, APPMAX_API_SANDBOX)
        codigo = (
            "import hashlib,json,re,time\n"
            "from django.conf import settings\n"
            "from django.utils import timezone\n"
            f"appmax_auth_sandbox = {sandbox_urls[0]!r}\n"
            f"appmax_api_sandbox = {sandbox_urls[1]!r}\n"
            "if not (settings.APPMAX_AUTH_URL == appmax_auth_sandbox and settings.APPMAX_API_URL == appmax_api_sandbox):\n"
            "    print('APPMAX_SANDBOX_REQUIRED')\n"
            "    raise SystemExit(23)\n"
            "from pagamentos.core.models import ESTADOS_EM_ABERTO, PaymentAttempt\n"
            "from pagamentos.providers.appmax.client import AppmaxClient\n"
            "motivo_ok = re.compile(r'[a-z_]{1,60}')\n"
            "status_ok = re.compile(r'[a-z_]{1,40}')\n"
            "order_id_ok = re.compile(r'[1-9][0-9]*')\n"
            "campos_conferencia = ('id','cliente','total','sub_total','taxa','parcelas','metodo','status_e_texto')\n"
            "agora = timezone.now()\n"
            f"prazo_final = time.monotonic() + {PRAZO_APPMAX_PENDENTES_SEGUNDOS}\n"
            "cliente_appmax = AppmaxClient()\n"
            "falhou_rede = False\n"
            "def sanitiza_motivo(bruto):\n"
            "    if not isinstance(bruto, str) or not bruto:\n"
            "        return 'vazio'\n"
            "    if motivo_ok.fullmatch(bruto):\n"
            "        return bruto\n"
            "    return 'fora_do_padrao'\n"
            "def sanitiza_status(bruto):\n"
            "    if isinstance(bruto, str):\n"
            "        normalizado = bruto.strip().lower()\n"
            "        if status_ok.fullmatch(normalizado):\n"
            "            return normalizado\n"
            "    return 'fora_do_padrao'\n"
            "def consulta_fechada(status_bruto, tentativa):\n"
            "    return {'status_bruto': status_bruto, 'total_paid_centavos': None, 'valor_esperado_centavos': tentativa.effective_amount_cents, 'conferencias': {c: False for c in campos_conferencia}}\n"
            "def consultar(tentativa):\n"
            "    global falhou_rede\n"
            "    order_id = str(tentativa.external_order_id or '')\n"
            "    if not order_id_ok.fullmatch(order_id):\n"
            "        return None\n"
            "    if falhou_rede or time.monotonic() >= prazo_final:\n"
            "        return consulta_fechada('nao_consultado', tentativa)\n"
            "    try:\n"
            "        pedido = cliente_appmax.consultar_pedido(int(order_id))\n"
            "    except Exception:\n"
            "        falhou_rede = True\n"
            "        return consulta_fechada('nao_consultado', tentativa)\n"
            "    if not isinstance(pedido, dict):\n"
            "        pedido = {}\n"
            "    status = pedido.get('status')\n"
            "    cliente_obj = pedido.get('customer')\n"
            "    cliente_id = cliente_obj.get('id') if isinstance(cliente_obj, dict) else None\n"
            "    total_paid = pedido.get('total_paid')\n"
            "    amounts = pedido.get('amounts')\n"
            "    base = amounts.get('sub_total') if isinstance(amounts, dict) else None\n"
            "    taxa = amounts.get('installment_fee', 0) if isinstance(amounts, dict) else None\n"
            "    payment = pedido.get('payment')\n"
            "    parcelas = payment.get('installments') if isinstance(payment, dict) else None\n"
            "    metodo_pedido = payment.get('method') if isinstance(payment, dict) else None\n"
            "    total_paid_ok = isinstance(total_paid, int) and not isinstance(total_paid, bool)\n"
            "    base_ok = isinstance(base, int) and not isinstance(base, bool)\n"
            "    taxa_ok = isinstance(taxa, int) and not isinstance(taxa, bool)\n"
            "    conferencias = {\n"
            "        'id': str(pedido.get('id')) == order_id,\n"
            "        'cliente': cliente_id is not None and str(cliente_id) == str(tentativa.customer_id),\n"
            "        'total': total_paid_ok and total_paid == tentativa.effective_amount_cents,\n"
            "        'sub_total': base_ok and base == tentativa.amount_cents,\n"
            "        'taxa': base_ok and taxa_ok and base + taxa == tentativa.effective_amount_cents,\n"
            "        'parcelas': not isinstance(parcelas, bool) and parcelas == tentativa.installments,\n"
            "        'metodo': metodo_pedido == 'creditcard',\n"
            "        'status_e_texto': isinstance(status, str),\n"
            "    }\n"
            "    return {'status_bruto': sanitiza_status(status), 'total_paid_centavos': total_paid if total_paid_ok else None, 'valor_esperado_centavos': tentativa.effective_amount_cents, 'conferencias': conferencias}\n"
            "nomes_operacao = ('customer', 'order', 'payment')\n"
            "saida = []\n"
            f"consulta_qs = PaymentAttempt.objects.filter(provider='appmax', platform_site_id={SITE_MESHCRAFT!r}, state__in=ESTADOS_EM_ABERTO).select_related('intent').prefetch_related('operacoes').order_by('created_at')[:{LIMITE_TENTATIVAS_APPMAX_PENDENTES}]\n"
            "for t in consulta_qs:\n"
            "    operacoes = {x: 'not_started' for x in nomes_operacao}\n"
            "    for operacao_registrada in t.operacoes.all():\n"
            "        operacoes[operacao_registrada.operation_type] = operacao_registrada.state\n"
            "    metodo = 'cartao' if t.intent.method == 'card' else 'pix'\n"
            "    idade_horas = int((agora - t.created_at).total_seconds() // 3600)\n"
            "    consulta = consultar(t) if metodo == 'cartao' else None\n"
            "    saida.append({\n"
            "        'referencia': " + REFERENCIA_DA_TENTATIVA + ",\n"
            "        'metodo': metodo,\n"
            "        'estado_tentativa': t.state,\n"
            "        'estado_intent': t.intent.status,\n"
            "        'motivo': sanitiza_motivo(t.reason),\n"
            "        'operacoes': operacoes,\n"
            "        'idade_horas': idade_horas,\n"
            "        'consulta_appmax': consulta,\n"
            "    })\n"
            "print(json.dumps({'tentativas': saida}, sort_keys=True))\n"
        )
        try:
            dados = json.loads(
                comando_shell(servico, identificador, codigo)
            )
        except (ValueError, TypeError):
            raise Falha("formato") from None
        return conferir_medicao(operacao, dados)
    if operacao == "appmax-estorno":
        codigo = (
            "import hashlib,json\n"
            "from datetime import timedelta\n"
            "from django.utils import timezone\n"
            "from pagamentos.core.models import PaymentAttempt\n"
            "from pagamentos.providers.appmax.client import AppmaxClient\n"
            f"referencia = {referencia!r}\n"
            f"tentativas = list(PaymentAttempt.objects.filter(provider='appmax',platform_site_id='{SITE_MESHCRAFT}',intent__method='card',created_at__gte=timezone.now()-timedelta(days=7)).select_related('intent').order_by('-created_at')[:100])\n"
            "tentativas = [t for t in tentativas if t.external_order_id.isdecimal() and int(t.external_order_id)>0]\n"
            "if referencia:\n"
            "    tentativas = [t for t in tentativas if hashlib.sha256(str(t.intent_id).encode()).hexdigest()==referencia]\n"
            "if not tentativas:\n"
            "    resultado = {'pedido':'ausente','referencia':None,'status':None,'pedido_confere':False,'refunded_at':False,'campos_observados':[],'campo_valor':None,'valor_no_refund_centavos':None}\n"
            "else:\n"
            "    tentativa = tentativas[0]\n"
            "    pedido = AppmaxClient().consultar_pedido(int(tentativa.external_order_id))\n"
            "    refund = pedido.get('refund') or {}\n"
            "    campos = ('amount','value','refunded_amount','refund_amount','refund_value','refunded_value','total','total_refunded')\n"
            "    observados = [campo for campo in campos if campo in refund]\n"
            "    numericos = [(campo,refund[campo]) for campo in observados if type(refund[campo]) is int and refund[campo]>0]\n"
            "    campo,valor = numericos[0] if len(numericos)==1 else (None,None)\n"
            "    status = pedido['status'] if pedido['status'] in ('aprovado','integrado','estornado','pendente') else 'outro'\n"
            "    resultado = {'pedido':'encontrado','referencia':hashlib.sha256(str(tentativa.intent_id).encode()).hexdigest(),'status':status,'pedido_confere':True,'refunded_at':bool(refund.get('refunded_at')),'campos_observados':observados,'campo_valor':campo,'valor_no_refund_centavos':valor}\n"
            "print(json.dumps(resultado,sort_keys=True))\n"
        )
        try:
            dados = json.loads(
                comando_shell(servico, identificador, codigo)
            )
        except (ValueError, TypeError):
            raise Falha("formato") from None
        return conferir_medicao(operacao, dados)
    if operacao in CODIGOS_FECHADOS:
        try:
            dados = json.loads(
                comando_shell(servico, identificador, CODIGOS_FECHADOS[operacao])
            )
        except (ValueError, TypeError):
            raise Falha("formato") from None
        return conferir_medicao(operacao, dados)
    try:
        dados = json.loads(
            comando(["docker", "inspect", "--format", FORMATO, identificador])
        )
    except (ValueError, TypeError):
        raise Falha("formato") from None
    return conferir_medicao(operacao, dados)


def executar(operacao, servico, permitidos, referencia=""):
    try:
        validar(operacao, servico, permitidos, referencia)
        dados = medir(operacao, servico, referencia)
    except (Falha, TypeError, ValueError) as erro:
        codigo = str(erro) if isinstance(erro, Falha) else "formato"
        print(
            json.dumps(
                {"resultado": "ERROR", "erro": codigo, "acao": ACOES[codigo]},
                ensure_ascii=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "resultado": "PASS",
                "operacao": operacao,
                "servico": servico,
                "medicao": dados,
            },
            sort_keys=True,
        )
    )
    return 0


def conferir():
    try:
        saida = os.environ.get("SAIDA", "").strip()
        rodape = (
            "\n"
            + "=" * 47
            + "\n✅ Successfully executed commands to all hosts.\n"
            + "=" * 47
        )
        if saida.endswith(rodape):
            saida = saida[: -len(rodape)]
        dados = json.loads(saida)
        if set(dados) != {"resultado", "operacao", "servico", "medicao"}:
            raise Falha("formato")
        if (
            dados["resultado"] != "PASS"
            or dados["operacao"] != os.environ["OPERACAO"]
            or dados["servico"] != os.environ["SERVICO"]
        ):
            raise Falha("formato")
        conferencia_referencia = (
            dados["medicao"].get("referencia", "")
            if dados["operacao"]
            in {
                "appmax-pix-pedido",
                "appmax-pix-aviso",
                "appmax-inbox-latencia",
            }
            else ""
        )
        conferir_medicao(dados["operacao"], dados["medicao"], conferencia_referencia)
    except (ValueError, TypeError, KeyError):
        raise Falha("formato") from None
    # Somente a saída já validada chega ao resumo público. PASS significa coleta,
    # não saúde: exited/unhealthy continuam visíveis como achado.
    texto = json.dumps(dados, sort_keys=True)
    print(texto)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as resumo:
        resumo.write("## Medição da VPS\n\n```json\n" + texto + "\n```\n")


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["conferir"]:
            conferir()
        else:
            raise Falha("entrada")
    except (Falha, OSError, ValueError, TypeError, KeyError) as erro:
        print("ERROR: operação ou evidência inválida. Confira o catálogo, o serviço e a saída acima.")
        sys.exit(2)
