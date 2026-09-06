# apps/core/api.py  # [RECEITA:R1 v1]
# Superfície da API espelhando contracts/alunos.openapi.yaml (somente-leitura quanto
# à FORMA — make contrato-check verde). Schemas inline via openapi_extra: o contrato
# congelado desta célula não declara components.schemas (tudo inline nos paths), então
# os handlers não usam ninja.Schema tipado — isso criaria refs nomeadas que o contrato
# não tem. createEnrollment é o reprocesso manual (mesma idempotência do consumer,
# INV-P5); listEnrollments responde "quem é aluno" (e por isso filtra por status —
# ver matriculas_que_valem). As três portas de /pre-matriculas são a fila de
# liberação (docs/decisoes/DECISAO-fila-de-liberacao.md).
import json
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError

from apps.core.clients import IdentidadeClient
from apps.matriculas.models import Matricula
from apps.matriculas.services import (
    OrderIdReservado,
    apagar_recusado,
    decidir_na_fila,
    entrar_na_fila,
    CAMPOS_CORRIGIVEIS,
    alunos_do_painel,
    atualizar_matricula,
    como_o_painel_ve,
    matricular,
    matriculas_que_valem,
    passado_de_quem_espera,
    prontuario_de,
    situacao_de,
)

router = Router()

_CREATE_ENROLLMENT_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["site_id", "order_id", "product_id", "customer"],
                    "properties": {
                        "site_id": {"type": "string"},
                        "order_id": {"type": "string"},
                        "product_id": {"type": "string"},
                        "customer": {
                            "type": "object",
                            "required": ["email", "name"],
                            "properties": {
                                "email": {"type": "string", "format": "email"},
                                "name": {"type": "string"},
                            },
                        },
                    },
                }
            }
        },
    },
    "responses": {
        201: {"description": "Matrícula criada"},
        200: {
            "description": "Replay idempotente — matrícula deste order_id já existia"
        },
        422: {"description": "Payload inválido"},
    },
}


@router.post(
    "/matriculas",
    operation_id="createEnrollment",
    summary="Matrícula manual/reprocesso — idempotente por order_id (INV-P5)",
    openapi_extra=_CREATE_ENROLLMENT_OPENAPI,
)
def create_enrollment(request):
    try:
        payload = json.loads(request.body)
        site_id = payload["site_id"]
        order_id = payload["order_id"]
        product_id = payload["product_id"]
        email = payload["customer"]["email"]
        name = payload["customer"]["name"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return JsonResponse({"detail": "payload inválido"}, status=422)

    try:
        matricula, criada = matricular(
            site_id=site_id,
            order_id=order_id,
            product_id=product_id,
            email=email,
            name=name,
        )
    except OrderIdReservado as erro:
        # [FILA] `pre:` é prefixo reservado às linhas da fila. Pedido real com
        # esse formato é payload inválido, não matrícula (422 já é declarado).
        return JsonResponse({"detail": str(erro)}, status=422)
    corpo = {
        "site_id": matricula.site_id,
        "order_id": matricula.order_id,
        "product_id": matricula.product_id,
        "customer": {"email": matricula.email, "name": matricula.name},
    }
    return JsonResponse(corpo, status=201 if criada else 200)


_LIST_ENROLLMENTS_OPENAPI = {
    "parameters": [
        {
            "name": "email",
            "in": "path",
            "required": True,
            "schema": {"type": "string", "format": "email"},
        }
    ],
    "responses": {
        200: {
            "description": "Lista de matrículas",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "site_id",
                                "order_id",
                                "product_id",
                                "status",
                                "enrolled_at",
                            ],
                            "properties": {
                                "site_id": {"type": "string"},
                                "order_id": {"type": "string"},
                                "product_id": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": ["ativa"],
                                    "description": 'SO os status que VALEM como acesso, e hoje ha um so.\n`suspensa` saiu em 28/08/2026 (DECISAO-gestao-de-alunos §2):\npassou a significar "acesso pausado pelo mantenedor".\n`reembolsada` saiu em 31/08/2026\n(DECISAO-reembolso-tira-o-acesso), quando o mantenedor\nREVERTEU a decisao dele de 24/08 ("quem ja foi aluno mantem\na voz"): reembolso passou a significar a compra desfeita, e\nquem recebeu o dinheiro de volta nao entra mais em nada.\n\nA LISTA ENCOLHEU, e o encolhimento e o ponto: um consumidor\nque ja tratava `reembolsada` continua compilando e apenas\nnunca mais recebe esse valor. Nenhum consumidor precisa\nmudar por causa desta porta — mas quem DERIVAVA acesso dela\npassa a excluir o reembolsado automaticamente, que e o\nefeito desejado.\n\nStatus novo nasce FORA desta lista: ela e de PERMISSAO, e a\ncelula tem um guarda que reprova quem esquecer de decidir.\n',
                                },
                                "enrolled_at": {
                                    "type": "string",
                                    "format": "date-time",
                                },
                            },
                        },
                    }
                }
            },
        },
        404: {"description": "Aluno inexistente"},
    },
}


@router.get(
    "/alunos/{email}/matriculas",
    operation_id="listEnrollments",
    summary="Matrículas de um aluno (suporte/E2E)",
    openapi_extra=_LIST_ENROLLMENTS_OPENAPI,
)
def list_enrollments(request, email: str):
    # [FILA] `matriculas_que_valem` em vez de `.filter(email=email)`: esta porta
    # é o que a Caixa de Sugestões usa para decidir acesso (`bool(...)` de
    # qualquer linha), então uma linha `aguardando` aqui abriria a Caixa para
    # quem ainda espera liberação — o oposto exato da fila. 404 é a resposta
    # certa para quem só está na fila: o cliente da Caixa traduz 404 para lista
    # vazia, que é o caminho de quem ainda não é aluno.
    matriculas = matriculas_que_valem(email)
    if not matriculas.exists():
        raise HttpError(404, "aluno inexistente")
    corpo = [
        {
            "site_id": m.site_id,
            "order_id": m.order_id,
            "product_id": m.product_id,
            "status": m.status,
            "enrolled_at": m.enrolled_at.isoformat(),
        }
        for m in matriculas
    ]
    return JsonResponse(corpo, safe=False, status=200)


_CREATE_PRE_ENROLLMENT_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "site_id",
                        "email",
                        "nome_completo",
                        "whatsapp",
                    ],
                    "properties": {
                        "site_id": {
                            "type": "string",
                        },
                        "email": {
                            "type": "string",
                            "format": "email",
                        },
                        "nome_completo": {
                            "type": "string",
                            "minLength": 1,
                        },
                        "whatsapp": {
                            "type": "string",
                            "description": "Com DDD. PII: mora aqui e so a porta do admin o devolve —\nnunca `GET /alunos/{email}/matriculas`, nunca evento. Mesma\ndisciplina que DECISAO-EVO-01 §3 deu ao e-mail, decidida\nnominalmente pelo mantenedor em 27/08/2026.\n",
                        },
                        "comprou_em": {
                            "type": [
                                "string",
                                "null",
                            ],
                            "format": "date",
                            "description": "OPCIONAL — pista de conferencia, nao dado de cadastro.",
                        },
                        "turma": {
                            "type": [
                                "string",
                                "null",
                            ],
                            "description": "OPCIONAL — pista de conferencia, nao dado de cadastro.",
                        },
                    },
                },
            },
        },
    },
    "responses": {
        "201": {
            "description": "Entrou na fila",
        },
        "200": {
            "description": "Ja estava na fila — dados atualizados",
        },
        "409": {
            "description": 'Este e-mail nao entra na fila. DUAS razoes, e elas sao diferentes:\n\n1. JA TEM matricula que vale — quem ja entra nao precisa de fila.\n   A conferencia usa a MESMA consulta que decide acesso, para nao\n   existir gente recusada aqui por "voce ja tem" que a Caixa nao\n   deixa entrar.\n2. FOI REEMBOLSADO (31/08/2026, DECISAO-reembolso-tira-o-acesso).\n   O mantenedor decidiu que quem recebeu o dinheiro de volta nao\n   pede para voltar sozinho: quem quiser voltar compra de novo ou\n   fala com a escola, e ele religa com um clique. A recusa mora\n   AQUI, e nao so na tela que esconde o formulario — regra que so\n   existe em HTML e promessa sem mecanismo.\n\n`encerrada` (ex-aluno) NAO barra, de proposito: ele PODE pedir para\nvoltar desde 29/08 (DECISAO-a-ficha-nao-se-apaga §3). A diferenca\nentre os dois e a decisao, nao um descuido.\n',
        },
        "422": {
            "description": "Payload invalido",
        },
    },
}

_LIST_PRE_ENROLLMENTS_OPENAPI = {
    "parameters": [
        {
            "name": "site_id",
            "in": "query",
            "required": False,
            "description": "OPCIONAL desde 28/08/2026 "
            "(DECISAO-categorias-de-usuario). Ausente\n"
            "= a fila de TODAS as escolas, e cada linha "
            "diz de qual veio.\n"
            "A plataforma e uma, as lojas sao N (Lei 9): "
            "o painel do dono e\n"
            "plataforma-inteira, e exigir que ele "
            "soubesse o codigo interno de\n"
            "uma escola para ver quem espera seria pedir "
            "que ele guardasse um\n"
            "identificador opaco. Passando o parametro, "
            "filtra — o comportamento\n"
            "de quem ja chamava assim nao muda.\n",
            "schema": {"type": "string"},
        },
        {
            "name": "status",
            "in": "query",
            "required": False,
            "schema": {
                "type": "string",
                "enum": ["aguardando", "recusada"],
                "default": "aguardando",
            },
        },
    ],
    "responses": {
        "200": {
            "description": "Quem esta na fila",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "id",
                                "site_id",
                                "email",
                                "nome_completo",
                                "whatsapp",
                                "status",
                                "criada_em",
                                "esperando_ha_dias",
                                "ja_foi_aluno",
                                "passagens_anteriores",
                                "saiu_em",
                            ],
                            "properties": {
                                "id": {"type": "string"},
                                "site_id": {
                                    "type": "string",
                                    "description": "De "
                                    "qual "
                                    "escola "
                                    "veio "
                                    "este "
                                    "pedido. "
                                    "Passa "
                                    "a "
                                    "vir "
                                    "SEMPRE, "
                                    "e "
                                    "nao\n"
                                    "so "
                                    "quando "
                                    "a "
                                    "busca "
                                    "e "
                                    "de "
                                    "todas: "
                                    "uma "
                                    "resposta "
                                    "com "
                                    "forma\n"
                                    "diferente "
                                    "conforme "
                                    "o "
                                    "filtro "
                                    "obriga "
                                    "cada "
                                    "consumidor "
                                    "a\n"
                                    "tratar "
                                    "dois "
                                    "casos, "
                                    "e "
                                    "o "
                                    "que "
                                    "esquecer "
                                    "trata "
                                    "o "
                                    "campo "
                                    "como\n"
                                    "ausente "
                                    "em "
                                    "silencio.\n",
                                },
                                "email": {"type": "string", "format": "email"},
                                "nome_completo": {"type": "string"},
                                "whatsapp": {"type": "string"},
                                "comprou_em": {
                                    "type": ["string", "null"],
                                    "format": "date",
                                },
                                "turma": {"type": ["string", "null"]},
                                "status": {
                                    "type": "string",
                                    "enum": ["aguardando", "recusada"],
                                },
                                "criada_em": {"type": "string", "format": "date-time"},
                                "esperando_ha_dias": {"type": "integer", "minimum": 0},
                                "motivo_recusa": {"type": ["string", "null"]},
                                "ja_foi_aluno": {
                                    "type": "boolean",
                                    "description": "A "
                                    "pessoa "
                                    "JA "
                                    "TEVE "
                                    "ficha "
                                    "nesta "
                                    "plataforma "
                                    "antes "
                                    "deste "
                                    "pedido\n"
                                    "(`DECISAO-a-ficha-nao-se-apaga.md` "
                                    "§3). "
                                    "Nasce "
                                    "em "
                                    "29/08/2026,\n"
                                    "no "
                                    "dia "
                                    "em "
                                    "que "
                                    "ex-aluno "
                                    "voltou "
                                    "a "
                                    "poder "
                                    "pedir "
                                    "entrada.\n"
                                    "\n"
                                    "CALCULADO "
                                    "pela "
                                    "celula, "
                                    "e "
                                    "nunca "
                                    "gravado: "
                                    "e "
                                    "a "
                                    "existencia "
                                    "de\n"
                                    "outra "
                                    "ficha "
                                    "com "
                                    "o "
                                    "mesmo "
                                    "e-mail, "
                                    "olhada "
                                    "na "
                                    "hora. "
                                    "Um "
                                    "campo\n"
                                    "gravado "
                                    "seria "
                                    "um "
                                    "segundo "
                                    "lugar "
                                    "guardando "
                                    "o "
                                    "que "
                                    "as "
                                    "fichas "
                                    "ja\n"
                                    "dizem, "
                                    "e "
                                    "os "
                                    "dois "
                                    "discordariam "
                                    "no "
                                    "primeiro "
                                    "backfill.\n"
                                    "\n"
                                    "Para "
                                    "que "
                                    "serve, "
                                    "em "
                                    "uma "
                                    "frase: "
                                    "sem "
                                    "ele, "
                                    "o "
                                    "mantenedor "
                                    "decide\n"
                                    "sobre "
                                    "um "
                                    "ex-aluno "
                                    "achando "
                                    "que "
                                    "e "
                                    "gente "
                                    "nova "
                                    "— "
                                    "que "
                                    "e\n"
                                    "exatamente "
                                    "o "
                                    "erro "
                                    "que "
                                    "a "
                                    "fila "
                                    "existe "
                                    "para "
                                    "nao "
                                    "cometer.\n",
                                },
                                "passagens_anteriores": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "description": "Quantas "
                                    "fichas "
                                    "anteriores "
                                    "esta "
                                    "pessoa "
                                    "tem "
                                    "(0 "
                                    "quando "
                                    "e "
                                    "a\n"
                                    "primeira "
                                    "vez). "
                                    "Nao "
                                    "e "
                                    "o "
                                    "mesmo "
                                    "que "
                                    "`ja_foi_aluno`: "
                                    "alguem\n"
                                    "recusado "
                                    "tres "
                                    "vezes "
                                    "tem "
                                    "passagens "
                                    "e "
                                    "nunca "
                                    "foi "
                                    "aluno.\n",
                                },
                                "saiu_em": {
                                    "type": ["string", "null"],
                                    "format": "date-time",
                                    "description": "Quando "
                                    "a "
                                    "ficha "
                                    "anterior "
                                    "mais "
                                    "recente "
                                    "foi "
                                    "encerrada "
                                    "— "
                                    "`null`\n"
                                    "se "
                                    "nao "
                                    "ha "
                                    "ficha "
                                    "anterior, "
                                    "ou "
                                    "se "
                                    "nenhuma "
                                    "foi "
                                    "encerrada. "
                                    "E "
                                    "a\n"
                                    "pista "
                                    "que "
                                    "a "
                                    "tarja "
                                    "da "
                                    "tela "
                                    "mostra "
                                    '("saiu '
                                    "em "
                                    '..."), '
                                    "e "
                                    "ela "
                                    "vem\n"
                                    "pronta "
                                    "pelo "
                                    "mesmo "
                                    "motivo "
                                    "de "
                                    "`esperando_ha_dias`: "
                                    "quem "
                                    "tem "
                                    "o\n"
                                    "relogio "
                                    "e "
                                    "a "
                                    "linha "
                                    "e "
                                    "a "
                                    "celula.\n",
                                },
                            },
                        },
                    }
                }
            },
        }
    },
}

_DECIDE_PRE_ENROLLMENT_OPENAPI = {
    "parameters": [
        {
            "name": "id",
            "in": "path",
            "required": True,
            "schema": {
                "type": "string",
            },
        },
    ],
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "decisao",
                        "decidido_por",
                    ],
                    "properties": {
                        "decisao": {
                            "type": "string",
                            "enum": [
                                "liberar",
                                "recusar",
                            ],
                        },
                        "decidido_por": {
                            "type": "string",
                            "description": "Id de plataforma de quem decidiu — a auditoria de quem liberou quem.",
                        },
                        "motivo": {
                            "type": [
                                "string",
                                "null",
                            ],
                            "description": "OBRIGATORIO quando decisao=recusar (422 sem ele).",
                        },
                        "product_id": {
                            "type": [
                                "string",
                                "null",
                            ],
                            "description": "O curso em que esta pessoa esta matriculada. OBRIGATORIO quando decisao=liberar (422 sem ele), e ignorado na recusa. E o id do produto no catalogo, que e o dono da lista de cursos: esta celula guarda a referencia, nunca uma copia da lista. [INV-ALU-C1], DECISAO-cursos-matriculas-e-alunos.md.",
                        },
                    },
                },
            },
        },
    },
    "responses": {
        "200": {
            "description": "Decidido",
        },
        "404": {
            "description": "Nao ha linha na fila com este id",
        },
        "409": {
            "description": "Esta linha ja foi decidida — decisao nao se refaz",
        },
        "422": {
            "description": "Payload invalido, recusa sem motivo, ou liberacao sem curso",
        },
    },
}

DESCRICAO_CRIAR_PRE_MATRICULA = 'A fila de liberacao (DECISAO-fila-de-liberacao.md). Cria uma Matricula\ncom status `aguardando` — que NAO da acesso a nada ate alguem liberar.\n\nPorta SEPARADA de `POST /matriculas` de proposito: aquela significa\n"alguem pagou" e e chamada pelo fluxo de pagamento. Misturar deixaria o\ncaminho do dinheiro capaz de criar linha em espera, e a fila capaz de\ncriar matricula paga. Duas intencoes, duas portas.\n\nIdempotente por (site_id, email): reenviar atualiza os dados e devolve\n200. A pessoa que erra o telefone e reenvia nao vira duas linhas na fila.\n'

DESCRICAO_LISTAR_PRE_MATRICULAS = "A UNICA porta que devolve o `whatsapp` (§5 da lei). `esperando_ha_dias`\nvem calculado: uma enxurrada de spam nao pode esconder o aluno de\nverdade que espera ha uma semana.\n"

DESCRICAO_DECIDIR_PRE_MATRICULA = '`liberar` muda o status para `ativa` — e a partir daí a pessoa entra na\nCaixa SEM nenhuma outra mudanca, porque a Caixa ja pergunta "tem\nmatricula que vale?".\n\n`liberar` exige `product_id`, e essa e a mudanca de 06/09/2026\n(DECISAO-cursos-matriculas-e-alunos.md, [INV-ALU-C1]): ninguem e aluno\ndo site, todo mundo e aluno de UM curso, e a matricula e o que diz qual.\nSem o curso a resposta e 422, e nada muda. NAO existe valor padrao: um\npadrao faria a escolha errada parecer escolha, e o erro so apareceria\nquando o aluno abrisse a sala e encontrasse o curso errado.\n\nA lista de cursos e do `catalogo`, e esta celula guarda a REFERENCIA e\nnunca a copia. Duas listas de cursos divergiriam no primeiro curso novo.\n\n`recusar` exige `motivo`: sem ele a pessoa espera para sempre e o\nmantenedor nao consegue distinguir "ninguem olhou" de "foi negado". E nao\npede curso: ninguem vira aluno de nada ao ser recusado.\n'


def _payload_valido(corpo, obrigatorias, opcionais):
    """[FILA] Traduz o `additionalProperties: false` do contrato em recusa real.

    Devolve `(payload, None)` ou `(None, resposta 422)`. Chave desconhecida é
    recusada de propósito: um cliente que erra o nome de um campo opcional
    (`whatsap`) receberia, no silêncio, uma linha na fila sem telefone — e o
    mantenedor descobriria só na hora de ligar para a pessoa.
    """
    try:
        payload = json.loads(corpo)
    except json.JSONDecodeError:
        return None, JsonResponse({"detail": "payload inválido"}, status=422)
    if not isinstance(payload, dict):
        return None, JsonResponse({"detail": "payload inválido"}, status=422)
    faltando = obrigatorias - set(payload)
    estranhas = set(payload) - obrigatorias - opcionais
    if faltando or estranhas:
        return None, JsonResponse(
            {
                "detail": "payload inválido",
                "faltando": sorted(faltando),
                "desconhecidas": sorted(estranhas),
            },
            status=422,
        )
    return payload, None


@router.post(
    "/pre-matriculas",
    operation_id="createPreEnrollment",
    summary="Alguem pede entrada e fica AGUARDANDO decisao humana",
    description=DESCRICAO_CRIAR_PRE_MATRICULA,
    openapi_extra=_CREATE_PRE_ENROLLMENT_OPENAPI,
)
def create_pre_enrollment(request):
    payload, erro = _payload_valido(
        request.body,
        obrigatorias={"site_id", "email", "nome_completo", "whatsapp"},
        opcionais={"comprou_em", "turma"},
    )
    if erro is not None:
        return erro

    nome_completo = str(payload["nome_completo"]).strip()
    whatsapp = str(payload["whatsapp"]).strip()
    if not nome_completo or not whatsapp:
        return JsonResponse(
            {"detail": "nome_completo e whatsapp são obrigatórios"}, status=422
        )

    comprou_em = payload.get("comprou_em")
    if comprou_em is not None:
        try:
            comprou_em = date.fromisoformat(str(comprou_em))
        except ValueError:
            return JsonResponse(
                {"detail": "comprou_em deve ser uma data AAAA-MM-DD"}, status=422
            )

    linha, criada = entrar_na_fila(
        site_id=str(payload["site_id"]),
        email=str(payload["email"]),
        nome_completo=nome_completo,
        whatsapp=whatsapp,
        comprou_em=comprou_em,
        turma=str(payload.get("turma") or "").strip(),
    )
    if linha is None:
        return JsonResponse(
            {"detail": "este e-mail já tem matrícula que vale"}, status=409
        )
    return JsonResponse(
        {"id": str(linha.pk), "status": linha.status}, status=201 if criada else 200
    )


@router.get(
    "/pre-matriculas",
    operation_id="listPreEnrollments",
    summary="A fila — porta do painel administrativo",
    description=DESCRICAO_LISTAR_PRE_MATRICULAS,
    openapi_extra=_LIST_PRE_ENROLLMENTS_OPENAPI,
)
def list_pre_enrollments(request, site_id: str = None, status: str = None):
    # Status fora do enum do contrato cai no padrão em vez de virar erro ou
    # lista vazia — e a direção importa: esconder a fila faria o painel dizer
    # "ninguém esperando" para um mantenedor que tem gente esperando há uma
    # semana. Mostrar demais para quem já está autenticado no admin não custa
    # nada; mostrar de menos custa a pessoa que desistiu de esperar.
    if status not in Matricula.STATUS_DA_FILA:
        status = Matricula.STATUS_AGUARDANDO

    agora = timezone.now()
    # `order_id__startswith` é redundante hoje (só a fila usa estes status) e
    # está aqui como cinto: esta porta devolve WhatsApp, e nenhuma linha que
    # não nasceu na fila deve poder aparecer nela.
    fila = Matricula.objects.filter(
        status=status,
        order_id__startswith=Matricula.PREFIXO_DA_FILA,
    ).order_by("enrolled_at")
    # [CATEGORIAS] `site_id` ausente = TODAS as escolas
    # (`DECISAO-categorias-de-usuario`, 28/08/2026). O painel do dono é
    # plataforma-inteira (Lei 9), e exigir dele o código interno de uma escola
    # para ver quem espera seria pedir que ele guardasse um identificador opaco.
    #
    # O filtro é aplicado DEPOIS, e só quando veio: escrever
    # `.filter(site_id=site_id)` com `None` casaria com `site_id IS NULL` e
    # devolveria lista vazia — "ninguém esperando" para um mantenedor que tem
    # gente esperando há uma semana, que é exatamente a direção de erro que o
    # comentário acima recusa.
    if site_id:
        fila = fila.filter(site_id=site_id)

    # UMA consulta para a fila inteira, antes do laço: perguntar o passado
    # dentro do `for` seria um N+1 que só aparece quando a fila cresce — ou
    # seja, exatamente quando ela importa.
    fila = list(fila)
    passado = passado_de_quem_espera(fila)

    corpo = [
        {
            "id": str(m.pk),
            # Vem SEMPRE, e não só quando a busca é de todas: resposta com forma
            # diferente conforme o filtro obriga cada consumidor a tratar dois
            # casos, e o que esquecer trata o campo como ausente em silêncio.
            "site_id": m.site_id,
            "email": m.email,
            "nome_completo": m.name,
            "whatsapp": m.whatsapp,
            "comprou_em": m.comprou_em.isoformat() if m.comprou_em else None,
            "turma": m.turma or None,
            "status": m.status,
            # `criada_em` é o `enrolled_at` que já existia: um segundo carimbo
            # de "quando esta linha nasceu" seriam dois lugares para o mesmo
            # fato, e eles discordariam no primeiro backfill.
            "criada_em": m.enrolled_at.isoformat(),
            "esperando_ha_dias": max((agora - m.enrolled_at).days, 0),
            "motivo_recusa": m.motivo_recusa or None,
            # [VOLTAR] O passado desta pessoa nesta plataforma, calculado na hora
            # (`DECISAO-a-ficha-nao-se-apaga.md`, 29/08/2026). Sem isto o
            # mantenedor decide sobre um ex-aluno achando que e gente nova — e
            # desde essa lei quem saiu PODE pedir para voltar, entao o caso
            # deixou de ser hipotetico.
            **passado[m.pk],
        }
        for m in fila
    ]
    return JsonResponse(corpo, safe=False, status=200)


def _para_quem_avisar(id_da_linha: str) -> str:
    """[AVISO] O id de plataforma de quem vai receber a carta, ou `""`.

    **Resolvido ANTES da transação, de propósito.** Isto é um salto de rede, e
    um salto de rede dentro de `transaction.atomic()` segura um lock de linha
    pelo tempo da resposta do vizinho. A leitura aqui é sem lock; quem decide o
    que acontece de verdade continua sendo a transação lá dentro, que reconfere
    o estado.

    Custa uma consulta a mais no caminho de um gesto humano (alguém clicou em
    "Liberar"), e a compensação é que a carta nasce DENTRO da transação do fato
    — que é a única forma de nunca existir aviso para algo que não aconteceu.

    Devolve `""` em todos os casos de "não sei": linha inexistente, pessoa que
    nunca entrou com o Google, `identidade` fora do ar, par não provisionado.
    Quem chama trata isso como "não há carta a enviar" — nunca como motivo para
    a decisão falhar.
    """
    email = (
        Matricula.objects.filter(pk=id_da_linha).values_list("email", flat=True).first()
        if str(id_da_linha).isdigit()
        else None
    )
    if not email:
        return ""
    return IdentidadeClient().id_por_email(email) or ""


@router.post(
    "/pre-matriculas/{id}/decisao",
    operation_id="decidePreEnrollment",
    summary="Liberar ou recusar quem esta na fila",
    description=DESCRICAO_DECIDIR_PRE_MATRICULA,
    openapi_extra=_DECIDE_PRE_ENROLLMENT_OPENAPI,
)
def decide_pre_enrollment(request, id: str):  # `id` sombreia o builtin: é o nome
    # do parâmetro no contrato, e o django-ninja casa a rota pelo nome.
    payload, erro = _payload_valido(
        request.body,
        obrigatorias={"decisao", "decidido_por"},
        opcionais={"motivo", "product_id"},
    )
    if erro is not None:
        return erro

    decisao = payload["decisao"]
    decidido_por = str(payload["decidido_por"]).strip()
    motivo = str(payload.get("motivo") or "").strip()
    product_id = str(payload.get("product_id") or "").strip()

    if decisao not in ("liberar", "recusar"):
        return JsonResponse(
            {"detail": "decisao deve ser liberar ou recusar"}, status=422
        )
    if not decidido_por:
        return JsonResponse({"detail": "decidido_por é obrigatório"}, status=422)
    if decisao == "recusar" and not motivo:
        # Sem motivo, a pessoa espera para sempre e o mantenedor não consegue
        # distinguir "ninguém olhou" de "foi negado" (contrato).
        return JsonResponse({"detail": "recusar exige motivo"}, status=422)

    linha, resultado = decidir_na_fila(
        id_da_linha=id,
        decisao=decisao,
        decidido_por=decidido_por,
        motivo=motivo,
        product_id=product_id,
        destinatario_id=_para_quem_avisar(id),
    )
    if resultado == "sem-curso":
        # [INV-ALU-C1] A frase diz o que faltou E o que fazer: quem lê este 422
        # é a tela de liberar do painel, e o mantenedor precisa entender o que
        # aconteceu sem abrir código. Quem recusa é `decidir_na_fila`, não esta
        # porta — aqui só se traduz a recusa em HTTP.
        return JsonResponse(
            {
                "detail": (
                    "liberar exige dizer o curso: escolha em qual curso esta "
                    "pessoa está matriculada e envie o campo product_id"
                )
            },
            status=422,
        )
    if resultado == "nao-encontrada":
        return JsonResponse({"detail": "não há linha na fila com este id"}, status=404)
    if resultado == "ja-decidida":
        return JsonResponse({"detail": "esta linha já foi decidida"}, status=409)
    return JsonResponse({"id": str(linha.pk), "status": linha.status}, status=200)


_DELETE_REJECTED_PRE_ENROLLMENT_OPENAPI = {
    "parameters": [
        {
            "name": "id",
            "in": "path",
            "required": True,
            "schema": {
                "type": "string",
            },
        },
    ],
    "responses": {
        "200": {
            "description": "Apagada. A linha nao existe mais.",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["apagada"],
                        "properties": {
                            "apagada": {"type": "boolean", "enum": [True]},
                        },
                    }
                }
            },
        },
        "404": {
            "description": "Nao ha linha RECUSADA na fila com este id",
        },
        "409": {
            "description": "Esta linha esta na fila mas ainda nao foi recusada — decida por POST /pre-matriculas/{id}/decisao antes de apagar",
        },
    },
}

DESCRICAO_APAGAR_RECUSADO = '`docs/decisoes/DECISAO-apagar-recusado-definitivamente.md` (03/09/2026):\nreverte, SO para esta fatia, a `DECISAO-a-ficha-nao-se-apaga.md` de\n29/08/2026. O mantenedor decidiu que um pedido recusado — que nunca\nchegou a virar aluno — pode ser apagado de vez, pelo botao "Apagar de\nvez" na tela de recusados do painel.\n\nSO ALCANCA linhas da FILA (prefixo `pre:` no order_id) com\n`status = recusada`. Uma matricula REAL (sem esse prefixo) e 404 aqui,\nsempre — esta porta nao e `DELETE /matriculas/{id}`, que continua sem\nexistir e continua sendo a lei de 29/08 intacta. Quem esta `aguardando`\ntambem nao se apaga por aqui: precisa ser recusado primeiro.\n\nIRREVERSIVEL. Depois de apagada, a linha nao existe mais em lugar\nnenhum — nem prontuario, nem historico. O caminho reversivel continua\nsendo `POST /pre-matriculas` (o botao "Aceitar mesmo assim" da mesma\ntela).\n'


@router.delete(
    "/pre-matriculas/{id}",
    operation_id="deleteRejectedPreEnrollment",
    summary="Apagar de vez um pedido RECUSADO — nunca quem ja foi aluno",
    description=DESCRICAO_APAGAR_RECUSADO,
    openapi_extra=_DELETE_REJECTED_PRE_ENROLLMENT_OPENAPI,
)
def delete_rejected_pre_enrollment(request, id: str):  # `id` sombreia o builtin,
    # como em `decide_pre_enrollment`: e o nome do parametro no contrato.
    """[APAGAR-RECUSADO] Ver `apagar_recusado`. Nenhum corpo de requisicao:
    apagar nao tem campo para mandar, so um alvo para confirmar."""
    resultado = apagar_recusado(id_da_linha=id)
    if resultado == "nao-encontrada":
        return JsonResponse(
            {"detail": "não há linha recusada na fila com este id"}, status=404
        )
    if resultado == "nao-recusada":
        return JsonResponse(
            {"detail": "esta linha ainda não foi recusada — decida antes de apagar"},
            status=409,
        )
    # 200 e nao 204: o django-ninja declara uma resposta 200 implicita para
    # toda operacao que nao diz o contrario, e um 204 real deixaria o schema
    # vivo com uma resposta a mais que o congelado nao tem
    # (`ci/contract_freeze.py`, medido na hora de congelar esta porta).
    return JsonResponse({"apagada": True}, status=200)


# [CATEGORIAS] Espelho EXATO do contrato congelado — `make contrato-check` compara
# o que o django-ninja exporta com `contracts/alunos.openapi.yaml`. As descrições
# abaixo foram COPIADAS de lá, com as quebras de linha que elas têm: uma só
# diferente reprova o freeze com um diff ilegível. Elas moram em constantes, e não
# inline, pelo mesmo motivo das irmãs deste arquivo — o dicionário fica legível.
DESCRICAO_SITUACAO = 'A porta das CINCO CATEGORIAS (`docs/decisoes/DECISAO-categorias-de-usuario.md`).\nExiste para que a home, a Caixa e o painel parem de adivinhar cada um do seu\njeito o que uma pessoa e — hoje sao quatro respostas para a mesma pergunta, e\ntres delas erram em pelo menos um caso.\n\nRESPONDE 200 COM `cadastrado` PARA QUEM ELA NAO CONHECE — NUNCA 404. "Nao\ntenho linha para esta pessoa" E a resposta, nao um erro. A porta vizinha\n(`GET /alunos/{email}/matriculas`) devolve 404 nesse caso e esta certa no\ncontexto dela; aqui um 404 obrigaria cada consumidor a traduzir "erro" em\n"cadastrado" por conta propria, e o primeiro que tratasse 404 como falha de\nrede mostraria a tela errada — fail-OPEN — para todo visitante novo do site.\n\nNAO DEVOLVE PII: sem WhatsApp, sem nome, sem eco do e-mail. E a §5 da\n`DECISAO-fila-de-liberacao.md` aplicada — o telefone sai por UMA porta so,\n`GET /pre-matriculas`, a do painel administrativo. Guarda de conjunto EXATO\nde chaves na resposta.\n\n`administrador` NAO E uma categoria possivel aqui, e a ausencia e a decisao:\nquem decide isso e a lista da celula `admin`, na hora. Se esta porta pudesse\nresponder isso, a autorizacao da area administrativa passaria a depender de\numa celula de produto (`DECISAO-onde-mora-a-sessao.md` §4).\n'

_D_CATEGORIA = "`aluno` sai da MESMA lista de status que decide acesso\n(`STATUS_QUE_VALEM`) — uma segunda lista seriam duas verdades\nsobre quem e aluno, e elas divergiriam no primeiro status novo.\n\n`pausado` (ficha `suspensa`) e `ex_aluno` (ficha `encerrada`)\nentraram em 28/08/2026\n(`DECISAO-ex-aluno-e-a-porta-que-explica.md`). Ate entao os\ndois voltavam como `cadastrado` — mentira sobre a pessoa, e a\ncausa de quem saiu da escola ver o formulario de pedir\nentrada, como se nunca tivesse pedido nada.\n\n`reembolsado` (ficha `reembolsada`) entrou em 31/08/2026\n(`DECISAO-reembolso-tira-o-acesso.md`) pela MESMA razao, e e\nADICAO pura: nenhum consumidor quebra por ela existir. Sem\nela, o reembolsado cairia em `cadastrado`, que e o mesmo tipo\nde mentira que os dois de cima nasceram para curar.\n\nNENHUM dos tres da acesso, e a diferenca entre eles e a unica\ncoisa que a pessoa quer saber: pausado e temporario, ex-aluno\ne o fim e pode pedir para voltar, reembolsado e a compra\ndesfeita e nao pede. Quem consome isto mostra telas\ndiferentes; quem autoriza continua olhando so `aluno`.\n"

_D_NA_FILA = "Preenchido SO quando `categoria` = `na_fila`; `null` nos outros casos."

_D_ESPERANDO = "Calculado PELA CELULA, nao a data crua: e ela que tem o\nrelogio e a linha. Consumidor que subtraisse datas erraria\nde um jeito diferente em cada celula. `null` depois de\ndecidida — ninguem espera mais.\n"

_D_MOTIVO = "Preenchido so quando `estado` = `recusada`. A pessoa precisa\nve-lo para poder pedir de novo: reenviar e o jeito previsto\nde corrigir um dado errado (lei da fila, §7).\n"

_D_200 = "A situacao da pessoa. Nao ha 404 — quem a celula nao conhece e `cadastrado`."

_GET_STUDENT_STANDING_OPENAPI = {
    "parameters": [
        {
            "name": "email",
            "in": "path",
            "required": True,
            "schema": {"type": "string", "format": "email"},
        }
    ],
    "responses": {
        "200": {
            "description": _D_200,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["categoria", "na_fila"],
                        "properties": {
                            "categoria": {
                                "type": "string",
                                "enum": [
                                    "cadastrado",
                                    "na_fila",
                                    "pausado",
                                    "ex_aluno",
                                    "reembolsado",
                                    "aluno",
                                ],
                                "description": _D_CATEGORIA,
                            },
                            "na_fila": {
                                "type": ["object", "null"],
                                "additionalProperties": False,
                                "description": _D_NA_FILA,
                                "required": [
                                    "estado",
                                    "esperando_ha_dias",
                                    "motivo_recusa",
                                ],
                                "properties": {
                                    "estado": {
                                        "type": "string",
                                        "enum": ["aguardando", "recusada"],
                                    },
                                    "esperando_ha_dias": {
                                        "type": ["integer", "null"],
                                        "minimum": 0,
                                        "description": _D_ESPERANDO,
                                    },
                                    "motivo_recusa": {
                                        "type": ["string", "null"],
                                        "description": _D_MOTIVO,
                                    },
                                },
                            },
                        },
                    }
                }
            },
        },
        "422": {"description": "E-mail invalido"},
    },
}


@router.get(
    "/alunos/{email}/situacao",
    operation_id="getStudentStanding",
    summary='Em que categoria esta pessoa esta — a resposta unica sobre "quem e aluno"',
    description=DESCRICAO_SITUACAO,
    openapi_extra=_GET_STUDENT_STANDING_OPENAPI,
)
def get_student_standing(request, email: str):
    """[CATEGORIAS] Em que categoria esta pessoa está. Leitura pura, sem PII.

    Nenhum 404 aqui, e é a decisão mais importante desta porta: quem a célula
    não conhece é `cadastrado`, com 200. Ver o `description` acima.
    """
    try:
        validate_email(email)
    except ValidationError:
        # 422 e não 404: um endereço malformado é pedido inválido, não pessoa
        # inexistente — e confundir os dois faria o consumidor tratar o próprio
        # bug como "esta pessoa é cadastrada".
        return JsonResponse({"detail": "e-mail inválido"}, status=422)
    return JsonResponse(situacao_de(email), status=200)


DESCRICAO_PRONTUARIO = 'A porta do PRONTUARIO (`docs/decisoes/DECISAO-a-ficha-nao-se-apaga.md` §5).\nNasce em 29/08/2026, no mesmo dia em que o apagar morreu e em que ex-aluno\nvoltou a poder pedir entrada — e as tres coisas sao a mesma decisao.\n\nPOR QUE ELA PRECISA EXISTIR: desde essa lei, quem sai e volta ganha uma\nFICHA NOVA a cada passagem (a antiga fica `encerrada`, com a data e o motivo\nda saida intactos). Isso preserva a historia, e o preco e que a mesma pessoa\npassa a ter mais de uma linha. Esta porta e a resposta a esse preco: ela\nagrupa por e-mail e devolve a trajetoria em ordem.\n\nDERIVADA DAS FICHAS, nunca de uma tabela de historico. Um historico gravado\na parte discordaria das fichas no primeiro caso de borda, e as duas telas\nmostrariam pessoas diferentes — e a lei anti-duplicacao do `CLAUDE.md` existe\npara isso.\n\nNAO E `GET /alunos/{email}/situacao`, e as duas continuam. Aquela responde\n"esta pessoa pode entrar?" — sem PII, para o site inteiro consumir. Esta\nresponde "quem e esta pessoa para a escola?" — com PII, para UMA tela. Fundir\nas duas obrigaria a porta publica a carregar telefone, que e o oposto da §5\nda lei da fila.\n\n200 COM LISTA VAZIA para quem a celula nao conhece — NUNCA 404, pela mesma\nrazao da porta da situacao: um 404 obrigaria o consumidor a traduzir "erro"\nem "pessoa nova", e o primeiro que o tratasse como falha de rede mostraria a\ntela errada.\n\nPII: devolve o WhatsApp, e por isso e PORTA DE PAINEL — a mesma familia de\n`GET /pre-matriculas` e `GET /matriculas`, e sujeita a mesma regra: o\ntelefone sai por essas portas e por nenhuma outra, nunca em evento.\n'

SUMMARY_PRONTUARIO = "O prontuario — a historia inteira de uma pessoa nesta escola"

_GET_STUDENT_RECORD_OPENAPI = {
    "parameters": [
        {
            "name": "email",
            "in": "path",
            "required": True,
            "schema": {"type": "string", "format": "email"},
        }
    ],
    "responses": {
        "200": {
            "description": "O prontuario. Sem ficha nenhuma, " "`passagens` vem vazio.",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "email",
                            "categoria",
                            "nome_completo",
                            "whatsapp",
                            "turma",
                            "comprou_em",
                            "passagens",
                        ],
                        "properties": {
                            "email": {"type": "string", "format": "email"},
                            "categoria": {
                                "type": "string",
                                "enum": [
                                    "cadastrado",
                                    "na_fila",
                                    "pausado",
                                    "ex_aluno",
                                    "reembolsado",
                                    "aluno",
                                ],
                                "description": "A "
                                "situacao "
                                "de "
                                "AGORA, "
                                "e "
                                "ela "
                                "vem "
                                "da "
                                "MESMA "
                                "funcao "
                                "que "
                                "responde\n"
                                "`GET "
                                "/alunos/{email}/situacao`. "
                                "Duas "
                                "contas "
                                "para "
                                "a "
                                "mesma\n"
                                "pergunta "
                                "divergiriam "
                                "no "
                                "primeiro "
                                "status "
                                "novo "
                                "— "
                                "e "
                                "a "
                                "tela "
                                "do\n"
                                "prontuario "
                                "mostraria "
                                "uma "
                                "coisa "
                                "enquanto "
                                "a "
                                "porta "
                                "da "
                                "Caixa\n"
                                "mostra "
                                "outra "
                                "para "
                                "a "
                                "mesma "
                                "pessoa.\n",
                            },
                            "nome_completo": {
                                "type": "string",
                                "description": "Da "
                                "passagem "
                                "MAIS "
                                "RECENTE "
                                "— "
                                "e "
                                "nao "
                                "da "
                                "primeira. "
                                "Quem "
                                "volta "
                                "anos\n"
                                "depois "
                                "pode "
                                "ter "
                                "mudado "
                                "de "
                                "nome, "
                                "e "
                                "o "
                                "que "
                                "o "
                                "mantenedor "
                                "precisa\n"
                                "ler "
                                "e "
                                "como "
                                "a "
                                "pessoa "
                                "se "
                                "chama "
                                "hoje. "
                                "String "
                                "vazia "
                                "quando "
                                "nao "
                                "ha\n"
                                "ficha "
                                "nenhuma.\n",
                            },
                            "whatsapp": {"type": "string"},
                            "turma": {"type": ["string", "null"]},
                            "comprou_em": {
                                "type": ["string", "null"],
                                "format": "date",
                            },
                            "passagens": {
                                "type": "array",
                                "description": "Uma "
                                "entrada "
                                "por "
                                "ficha, "
                                "da "
                                "MAIS "
                                "ANTIGA "
                                "para "
                                "a "
                                "mais "
                                "nova "
                                "— "
                                "o\n"
                                "contrario "
                                "das "
                                "outras "
                                "listas "
                                "desta "
                                "API, "
                                "e "
                                "de "
                                "proposito: "
                                "aqui "
                                "o\n"
                                "que "
                                "se "
                                "le "
                                "e "
                                "uma "
                                "historia, "
                                "e "
                                "historia "
                                "se "
                                "conta "
                                "na "
                                "ordem "
                                "em "
                                "que\n"
                                "aconteceu.\n",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": [
                                        "id",
                                        "site_id",
                                        "status",
                                        "origem",
                                        "nome_completo",
                                        "whatsapp",
                                        "turma",
                                        "comprou_em",
                                        "criada_em",
                                        "decidido_em",
                                        "decidido_por",
                                        "motivo_recusa",
                                    ],
                                    "properties": {
                                        "id": {"type": "string"},
                                        "site_id": {"type": "string"},
                                        "status": {
                                            "type": "string",
                                            "enum": [
                                                "ativa",
                                                "suspensa",
                                                "encerrada",
                                                "reembolsada",
                                                "aguardando",
                                                "recusada",
                                            ],
                                            "description": "TODOS "
                                            "os "
                                            "estados, "
                                            "inclusive "
                                            "os "
                                            "da "
                                            "fila "
                                            "— "
                                            "este "
                                            "e "
                                            "o "
                                            "unico\n"
                                            "lugar "
                                            "da "
                                            "API "
                                            "onde "
                                            "as "
                                            "duas "
                                            "familias "
                                            "aparecem "
                                            "juntas. "
                                            "As\n"
                                            "outras "
                                            "portas "
                                            "separam "
                                            "de "
                                            "proposito "
                                            "(uma "
                                            "decide "
                                            "entrada,\n"
                                            "a "
                                            "outra "
                                            "administra "
                                            "quem "
                                            "entrou); "
                                            "um "
                                            "prontuario "
                                            "que\n"
                                            "escondesse "
                                            "as "
                                            "passagens "
                                            "recusadas "
                                            "contaria "
                                            "a "
                                            "historia\n"
                                            "pela "
                                            "metade.\n",
                                        },
                                        "origem": {
                                            "type": "string",
                                            "enum": ["comprou", "liberado"],
                                        },
                                        "nome_completo": {"type": "string"},
                                        "whatsapp": {"type": "string"},
                                        "turma": {"type": ["string", "null"]},
                                        "comprou_em": {
                                            "type": ["string", "null"],
                                            "format": "date",
                                        },
                                        "criada_em": {
                                            "type": "string",
                                            "format": "date-time",
                                        },
                                        "decidido_em": {
                                            "type": ["string", "null"],
                                            "format": "date-time",
                                            "description": "Quando "
                                            "esta "
                                            "ficha "
                                            "foi "
                                            "decidida "
                                            "pela "
                                            "ultima "
                                            "vez "
                                            "—\n"
                                            "liberada, "
                                            "recusada, "
                                            "pausada "
                                            "ou "
                                            "encerrada. "
                                            "`null` "
                                            "enquanto\n"
                                            "ninguem "
                                            "decidiu "
                                            "nada.\n",
                                        },
                                        "decidido_por": {
                                            "type": "string",
                                            "description": "Id "
                                            "de "
                                            "plataforma "
                                            "de "
                                            "quem "
                                            "decidiu "
                                            "— "
                                            "nunca "
                                            "o "
                                            "e-mail "
                                            "dele.\n"
                                            "E-mail "
                                            "muda "
                                            "de "
                                            "dono; "
                                            "o "
                                            "id, "
                                            "nao.\n",
                                        },
                                        "motivo_recusa": {"type": "string"},
                                    },
                                },
                            },
                        },
                    }
                }
            },
        },
        "422": {"description": "E-mail invalido"},
    },
}


@router.get(
    "/alunos/{email}/prontuario",
    operation_id="getStudentRecord",
    summary=SUMMARY_PRONTUARIO,
    description=DESCRICAO_PRONTUARIO,
    openapi_extra=_GET_STUDENT_RECORD_OPENAPI,
)
def get_student_record(request, email: str):
    """[PRONTUARIO] A historia inteira de uma pessoa. Ver `prontuario_de`.

    Nenhum 404, pela mesma razão da porta da situação ao lado: quem a célula
    não conhece volta com `passagens: []`. "Não conheço esta pessoa" é uma
    resposta, e um erro obrigaria cada consumidor a traduzi-lo em tela.
    """
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"detail": "e-mail inválido"}, status=422)
    return JsonResponse(prontuario_de(email), status=200)


# [GESTAO] Espelhos EXATOS do contrato congelado — GERADOS a partir dele, e as
# descricoes longas viram constantes: elas tem quebras de linha significativas, e
# uma so diferente reprova o freeze com um diff ilegivel.
_D1 = "DERIVADO da proveniencia da linha, nunca de um campo proprio:\n`liberado` e quem entrou pela fila (o pedido sintetico `pre:`),\n`comprou` e o resto. Sai como palavra e nao como o numero do\npedido — o numero e do provedor de pagamento e nao diz nada a\nquem le a tela.\n"

_D2 = "DERIVADO da proveniencia da linha, nunca de um campo proprio:\n`liberado` e quem entrou pela fila (o pedido sintetico `pre:`),\n`comprou` e o resto. Sai como palavra e nao como o numero do\npedido — o numero e do provedor de pagamento e nao diz nada a\nquem le a tela.\n"

_D3 = "Esta linha esta na FILA — decida por POST /pre-matriculas/{id}/decisao"

# Rito de Contrato de 03/09/2026 (o placar do painel de gestão). O texto é o
# MESMO do congelado em `contracts/alunos.openapi.yaml`, byte a byte: o portão
# compara o vivo com o congelado, e uma vírgula diferente aqui é drift.
_D4 = 'Quando a pessoa VIROU ALUNA. Para quem entrou pela fila (`liberado`) e o\ninstante da liberacao; para quem comprou, o instante em que o pagamento\nconfirmou a matricula (`criada_em`). Nasceu em 03/09/2026, no Rito de\nContrato do placar do painel de gestao: a meta do mantenedor passou a ser\n"quantas pessoas compraram neste mes", e a data que conta e ESTA, nunca\n`comprou_em` (que a propria pessoa digita, opcional, pista de conferencia).\nNulo so quando a linha nao tem nenhuma das duas, o que hoje nao acontece.\n'

DESCRICAO_LISTA_DE_ALUNOS = 'A porta da GESTAO DE ALUNOS (`docs/decisoes/DECISAO-gestao-de-alunos.md`).\nAte 28/08/2026 nao existia, em lugar nenhum, como listar quem e aluno: a\ncelula so sabia responder sobre UM e-mail por vez. Era por isso que os\ncontadores de alunos do painel mostravam traco.\n\nNAO devolve quem esta na fila (`aguardando`/`recusada`) — para esses\nexiste `GET /pre-matriculas`. Duas perguntas diferentes, duas portas.\n\n`site_id` opcional: ausente = todas as escolas, e cada linha diz de qual\nveio. O painel do dono e plataforma-inteira (Lei 9).\n\nPII: devolve o WhatsApp, e continua sendo PORTA DE PAINEL — a mesma\nfamilia de `GET /pre-matriculas`. A lei da fila §5 diz que o numero sai\n"por uma porta so, a do painel administrativo"; estas duas SAO essa\nporta. Segue proibido em `GET /alunos/{email}/matriculas` e em evento.\n'

DESCRICAO_ATUALIZAR = "O formulario de gestao (`DECISAO-gestao-de-alunos.md` §3). Todo campo de\ndado e OPCIONAL: manda-se so o que muda.\n\nO QUE ESTA PORTA NAO DEIXA MUDAR, e a ausencia e a decisao:\n\n- `email` — e a IDENTIDADE da linha. Troca-lo moveria a matricula, em\n  silencio, para outra pessoa, e e por e-mail que todo o resto do\n  sistema pergunta quem e aluno.\n- `site_id`, `order_id`, `product_id` — vem do fato que criou a linha\n  (uma compra, um pedido de entrada). Edita-los seria reescrever o que\n  aconteceu.\n\nNAO decide sobre quem esta na FILA: linha `aguardando`/`recusada` responde\n409 aqui. Para essas existe `POST /pre-matriculas/{id}/decisao` — uma\nporta decide ENTRADA, a outra administra quem ja entrou.\n"

_LIST_ALL_ENROLLMENTS_OPENAPI = {
    "parameters": [
        {
            "name": "site_id",
            "in": "query",
            "required": False,
            "schema": {"type": "string"},
        },
        {
            "name": "status",
            "in": "query",
            "required": False,
            "description": "Ausente = todos os estados de gestao (nao os da " "fila).",
            "schema": {
                "type": "string",
                "enum": ["ativa", "suspensa", "encerrada", "reembolsada"],
            },
        },
    ],
    "responses": {
        "200": {
            "description": "Os alunos, do mais recente para o mais " "antigo",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "id",
                                "site_id",
                                "email",
                                "nome_completo",
                                "whatsapp",
                                "turma",
                                "comprou_em",
                                "status",
                                "origem",
                                "criada_em",
                            ],
                            "properties": {
                                "id": {"type": "string"},
                                "site_id": {"type": "string"},
                                "email": {"type": "string", "format": "email"},
                                "nome_completo": {"type": "string"},
                                "whatsapp": {"type": "string"},
                                "turma": {"type": ["string", "null"]},
                                "comprou_em": {
                                    "type": ["string", "null"],
                                    "format": "date",
                                },
                                "status": {
                                    "type": "string",
                                    "enum": [
                                        "ativa",
                                        "suspensa",
                                        "encerrada",
                                        "reembolsada",
                                    ],
                                },
                                "origem": {
                                    "type": "string",
                                    "enum": ["comprou", "liberado"],
                                    "description": _D1,
                                },
                                "criada_em": {"type": "string", "format": "date-time"},
                                "virou_aluno_em": {
                                    "type": ["string", "null"],
                                    "format": "date-time",
                                    "description": _D4,
                                },
                            },
                        },
                    }
                }
            },
        }
    },
}

_UPDATE_ENROLLMENT_OPENAPI = {
    "parameters": [
        {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
    ],
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["decidido_por"],
                    "properties": {
                        "decidido_por": {
                            "type": "string",
                            "description": "Id "
                            "de "
                            "plataforma "
                            "de "
                            "quem "
                            "mudou "
                            "— "
                            "a "
                            "auditoria "
                            "do "
                            "lado "
                            "de "
                            "ca.",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["ativa", "suspensa", "encerrada", "reembolsada"],
                        },
                        "nome_completo": {"type": "string", "minLength": 1},
                        "whatsapp": {"type": "string"},
                        "turma": {"type": ["string", "null"]},
                        "comprou_em": {"type": ["string", "null"], "format": "date"},
                    },
                }
            }
        },
    },
    "responses": {
        "200": {
            "description": "Como a matricula ficou",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "id",
                            "site_id",
                            "email",
                            "nome_completo",
                            "whatsapp",
                            "turma",
                            "comprou_em",
                            "status",
                            "origem",
                            "criada_em",
                        ],
                        "properties": {
                            "id": {"type": "string"},
                            "site_id": {"type": "string"},
                            "email": {"type": "string", "format": "email"},
                            "nome_completo": {"type": "string"},
                            "whatsapp": {"type": "string"},
                            "turma": {"type": ["string", "null"]},
                            "comprou_em": {
                                "type": ["string", "null"],
                                "format": "date",
                            },
                            "status": {
                                "type": "string",
                                "enum": [
                                    "ativa",
                                    "suspensa",
                                    "encerrada",
                                    "reembolsada",
                                ],
                            },
                            "origem": {
                                "type": "string",
                                "enum": ["comprou", "liberado"],
                                "description": _D2,
                            },
                            "criada_em": {"type": "string", "format": "date-time"},
                        },
                    }
                }
            },
        },
        "404": {"description": "Nao ha matricula com este id"},
        "409": {"description": _D3},
        "422": {"description": "Payload invalido, ou nada para mudar"},
    },
}


@router.get(
    "/matriculas",
    operation_id="listAllEnrollments",
    summary="Quem ja e aluno — a lista, para o painel administrativo",
    description=DESCRICAO_LISTA_DE_ALUNOS,
    openapi_extra=_LIST_ALL_ENROLLMENTS_OPENAPI,
)
def list_all_enrollments(request, site_id: str = None, status: str = None):
    """[GESTAO] A lista do painel. Leitura pura; devolve PII (é porta de painel)."""
    if status is not None and status not in Matricula.STATUS_DE_GESTAO:
        # Estado fora do vocabulário de gestão cai no "todos", em vez de virar
        # erro ou lista vazia — e a direção importa, como no filtro da fila:
        # esconder alunos faria o painel dizer "não há ninguém" para quem tem
        # gente. Mostrar demais para quem já está autenticado não custa nada.
        status = None
    corpo = [
        como_o_painel_ve(m) for m in alunos_do_painel(site_id=site_id, status=status)
    ]
    return JsonResponse(corpo, safe=False, status=200)


@router.patch(
    "/matriculas/{id}",
    operation_id="updateEnrollment",
    summary="Mudar o estado de um aluno, ou corrigir os dados dele",
    description=DESCRICAO_ATUALIZAR,
    openapi_extra=_UPDATE_ENROLLMENT_OPENAPI,
)
def update_enrollment(request, id: str):
    """[GESTAO] O formulário do painel. Ver `atualizar_matricula`."""
    payload, erro = _payload_valido(
        request.body,
        obrigatorias={"decidido_por"},
        opcionais=set(CAMPOS_CORRIGIVEIS) | {"status"},
    )
    if erro is not None:
        return erro

    novo_status = payload.get("status")
    if novo_status is not None and novo_status not in Matricula.STATUS_DE_GESTAO:
        # Lista de PERMISSÃO: estado da FILA não entra por aqui (a porta de lá
        # confere "já decidida" e grava motivo), e estado inventado não entra
        # de jeito nenhum.
        return JsonResponse({"detail": "status fora do vocabulário"}, status=422)

    comprou_em = payload.get("comprou_em")
    if comprou_em:
        try:
            payload["comprou_em"] = date.fromisoformat(str(comprou_em))
        except ValueError:
            return JsonResponse({"detail": "comprou_em inválido"}, status=422)

    nome = payload.get("nome_completo")
    if nome is not None and not str(nome).strip():
        # Nome em branco apagaria a única forma de o mantenedor reconhecer a
        # pessoa na lista. O contrato já diz `minLength: 1`; aqui é o mecanismo.
        return JsonResponse(
            {"detail": "nome_completo não pode ficar vazio"}, status=422
        )

    linha, resultado = atualizar_matricula(
        id_da_linha=id,
        mudancas=payload,
        decidido_por=str(payload["decidido_por"]),
        destinatario_id=_para_quem_avisar(id),
    )
    if resultado == "nao-encontrada":
        raise HttpError(404, "matrícula inexistente")
    if resultado == "na-fila":
        raise HttpError(409, "esta linha está na fila — decida por /pre-matriculas")
    if resultado == "nada-a-mudar":
        return JsonResponse({"detail": "nada para mudar"}, status=422)
    return JsonResponse(como_o_painel_ve(linha), status=200)


# A operacao `deleteEnrollment` MORREU AQUI em 29/08/2026, junto com o
# `apagar_matricula` que ela chamava e com a propria operacao no contrato
# (`DECISAO-a-ficha-nao-se-apaga.md`). O mantenedor decidiu que o cadastro de um
# aluno NUNCA e apagado: quem sai vira ex-aluno pelo `PATCH` acima, a ficha fica,
# e quem quiser voltar pede entrada de novo pela fila.
#
# A ausencia esta escrita aqui porque uma porta que some sem explicacao e um
# convite a recria-la. Guarda: `tests/test_a_ficha_nao_se_apaga.py`.
#
# [APAGAR-RECUSADO] `DELETE /matriculas/{id}` continua sem existir — isto NAO
# mudou em 03/09/2026. O que nasceu naquele dia foi uma porta DIFERENTE,
# `DELETE /pre-matriculas/{id}` (acima), que so alcanca pedidos RECUSADOS —
# nunca uma matricula que ja deu acesso. Ver `apagar_recusado` e
# `docs/decisoes/DECISAO-apagar-recusado-definitivamente.md`.
