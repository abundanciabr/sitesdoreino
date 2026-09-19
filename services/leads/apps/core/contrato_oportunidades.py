# apps/core/contrato_oportunidades.py
"""A superfície OpenAPI das oportunidades, escrita à mão, em código.

Por que os schemas moram aqui e não em `ninja.Schema`: o freeze de contrato
compara o documento exportado com `contracts/leads.openapi.yaml` byte a byte
(`ci/contract_freeze.py::_normalizar`). O gerador do pydantic decora o que
emite (`title`, `enum` com `type` junto, `anyOf` no lugar de `oneOf`,
`const` acompanhado de `type`), e nada disso está no congelado. Declarar o
documento à mão é o único jeito de a fonte viva ser IGUAL ao contrato sem
derivar uma da outra: este arquivo é código, o congelado é lei, e o portão
continua medindo a distância entre os dois.

Quem lê isto daqui: `apps/core/oportunidades.py` (uma entrada `openapi_extra`
por operação) e o `export_openapi` da célula (components e os parâmetros de
caminho, que o django-ninja só sabe emitir por operação).
"""

ETAPAS_ABERTAS = ["nova", "qualificada", "proposta", "negociacao"]
ETAPAS_ENCERRADAS = ["ganha", "perdida", "desqualificada"]
TIPOS_DE_FONTE = ["captura", "quiz", "pedido", "pagamento", "timeline_lead"]
TIPOS_DE_HISTORICO = [
    "nota",
    "contato",
    "etapa_alterada",
    "transferencia_solicitada",
    "transferencia_aceita",
    "transferencia_recusada",
    "encerramento",
    "reabertura",
]
TIPOS_DE_HISTORICO_HUMANO = ["nota", "contato"]
ESTADOS_DE_TRANSFERENCIA = ["pendente", "aceita", "recusada"]


def _ref(nome: str) -> dict:
    return {"$ref": f"#/components/schemas/{nome}"}


def _texto() -> dict:
    return {"type": "string", "minLength": 1}


def _instante() -> dict:
    return {"type": "string", "format": "date-time"}


def _corpo(nome: str) -> dict:
    return {
        "required": True,
        "content": {"application/json": {"schema": _ref(nome)}},
    }


def _resposta(descricao: str, nome: str) -> dict:
    return {
        "description": descricao,
        "content": {"application/json": {"schema": _ref(nome)}},
    }


_NEGADA = {"$ref": "#/components/responses/AcaoNaoAutorizada"}


def _oportunidade(*, encerrada: bool, com_historico: bool) -> dict:
    propriedades = {
        "id": {"type": "string"},
        "lead_id": {"type": "string"},
        "etapa": _ref(
            "EtapaEncerradaOportunidade" if encerrada else "EtapaAbertaOportunidade"
        ),
        "situacao": {"const": "encerrada" if encerrada else "aberta"},
        "titular": _ref("TitularOportunidade"),
        "fonte": _ref("FonteOportunidade"),
        "proximo_passo": _ref("ProximoPasso"),
        "criada_em": _instante(),
        "atualizada_em": _instante(),
    }
    obrigatorios = [
        "id",
        "lead_id",
        "etapa",
        "situacao",
        "titular",
        "fonte",
        "proximo_passo",
    ]
    if encerrada:
        propriedades["desfecho"] = _ref("DesfechoOportunidade")
        obrigatorios.append("desfecho")
    obrigatorios += ["criada_em", "atualizada_em"]
    if com_historico:
        propriedades["historico"] = {
            "type": "array",
            "items": _ref("RegistroHistoricoOportunidade"),
        }
        obrigatorios.append("historico")
    return {
        "type": "object",
        "additionalProperties": False,
        "required": obrigatorios,
        "properties": propriedades,
    }


def _resultado(nome_da_oportunidade: str) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["oportunidade", "evento"],
        "properties": {
            "oportunidade": _ref(nome_da_oportunidade),
            "evento": _ref("RegistroHistoricoOportunidade"),
        },
    }


SCHEMAS = {
    "EtapaOportunidade": {
        "type": "string",
        "enum": ETAPAS_ABERTAS + ETAPAS_ENCERRADAS,
    },
    "EtapaAbertaOportunidade": {"type": "string", "enum": ETAPAS_ABERTAS},
    "EtapaEncerradaOportunidade": {"type": "string", "enum": ETAPAS_ENCERRADAS},
    "SituacaoOportunidade": {"type": "string", "enum": ["aberta", "encerrada"]},
    "TitularOportunidade": {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "funcao"],
        "properties": {
            "id": {
                "type": "string",
                "description": "Identificador opaco da conta, nunca e-mail.",
            },
            "funcao": {"type": "string", "enum": ["comercial"]},
        },
    },
    "ProximoPasso": {
        "type": "object",
        "additionalProperties": False,
        "required": ["descricao", "executar_ate", "evidencia_esperada"],
        "properties": {
            "descricao": _texto(),
            "executar_ate": _instante(),
            "evidencia_esperada": _texto(),
        },
    },
    "FonteOportunidade": {
        "type": "object",
        "additionalProperties": False,
        "required": ["tipo", "referencia_id"],
        "properties": {
            "tipo": {"type": "string", "enum": TIPOS_DE_FONTE},
            "referencia_id": _texto(),
        },
    },
    "DesfechoOportunidade": {
        "type": "object",
        "additionalProperties": False,
        "required": ["resultado", "motivo", "evidencia", "encerrada_em"],
        "properties": {
            "resultado": {"type": "string", "enum": ETAPAS_ENCERRADAS},
            "motivo": _texto(),
            "evidencia": _texto(),
            "encerrada_em": _instante(),
        },
    },
    "RegistroHistoricoOportunidade": {
        "type": "object",
        "description": (
            "Evento imutável da oportunidade; a API não expõe alteração nem remoção."
        ),
        "additionalProperties": False,
        "required": ["id", "registrado_em", "autor_id", "tipo", "descricao"],
        "properties": {
            "id": {"type": "string"},
            "registrado_em": _instante(),
            "autor_id": {"type": "string"},
            "tipo": {"type": "string", "enum": TIPOS_DE_HISTORICO},
            "descricao": {"type": "string"},
            "evidencia": {"type": "string"},
        },
    },
    "Oportunidade": {
        "description": (
            "A situação define variantes disjuntas: aberta não tem desfecho; "
            "encerrada exige etapa final e desfecho."
        ),
        "oneOf": [_ref("OportunidadeAberta"), _ref("OportunidadeEncerrada")],
    },
    "OportunidadeAberta": _oportunidade(encerrada=False, com_historico=False),
    "OportunidadeEncerrada": _oportunidade(encerrada=True, com_historico=False),
    "OportunidadeComHistorico": {
        "oneOf": [
            _ref("OportunidadeAbertaComHistorico"),
            _ref("OportunidadeEncerradaComHistorico"),
        ]
    },
    "OportunidadeAbertaComHistorico": _oportunidade(
        encerrada=False, com_historico=True
    ),
    "OportunidadeEncerradaComHistorico": _oportunidade(
        encerrada=True, com_historico=True
    ),
    "CriarOportunidade": {
        "type": "object",
        "additionalProperties": False,
        "required": ["lead_id", "etapa", "titular_id", "fonte", "proximo_passo"],
        "properties": {
            "lead_id": {"type": "string"},
            "etapa": _ref("EtapaAbertaOportunidade"),
            "titular_id": {"type": "string"},
            "fonte": _ref("FonteOportunidade"),
            "proximo_passo": _ref("ProximoPasso"),
        },
    },
    "AtualizarOportunidade": {
        "type": "object",
        "additionalProperties": False,
        "minProperties": 1,
        "properties": {
            "etapa": _ref("EtapaAbertaOportunidade"),
            "proximo_passo": _ref("ProximoPasso"),
        },
    },
    "RegistrarHistoricoOportunidade": {
        "type": "object",
        "additionalProperties": False,
        "required": ["tipo", "descricao"],
        "properties": {
            "tipo": {"type": "string", "enum": TIPOS_DE_HISTORICO_HUMANO},
            "descricao": _texto(),
            "evidencia": {"type": "string"},
        },
    },
    "TransferirResponsabilidadeOportunidade": {
        "type": "object",
        "additionalProperties": False,
        "required": ["novo_titular_id", "motivo"],
        "properties": {
            "novo_titular_id": {"type": "string"},
            "motivo": _texto(),
        },
    },
    "TransferenciaResponsabilidade": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "oportunidade_id",
            "de_titular_id",
            "para_titular_id",
            "motivo",
            "estado",
            "solicitada_em",
        ],
        "properties": {
            "id": {"type": "string"},
            "oportunidade_id": {"type": "string"},
            "de_titular_id": {"type": "string"},
            "para_titular_id": {"type": "string"},
            "motivo": {"type": "string"},
            "estado": {"type": "string", "enum": ESTADOS_DE_TRANSFERENCIA},
            "solicitada_em": _instante(),
            "concluida_em": _instante(),
            "motivo_recusa": _texto(),
        },
        "allOf": [
            {
                "if": {
                    "properties": {"estado": {"const": "recusada"}},
                    "required": ["estado"],
                },
                "then": {"required": ["motivo_recusa"]},
            }
        ],
    },
    "TransferenciaComEvento": {
        "type": "object",
        "additionalProperties": False,
        "required": ["transferencia", "evento"],
        "properties": {
            "transferencia": _ref("TransferenciaResponsabilidade"),
            "evento": _ref("RegistroHistoricoOportunidade"),
        },
    },
    "ResultadoDaMutacaoDaOportunidade": _resultado("OportunidadeComHistorico"),
    "ResultadoDaAtualizacaoDaOportunidade": _resultado(
        "OportunidadeAbertaComHistorico"
    ),
    "ResultadoDoEncerramentoDaOportunidade": _resultado(
        "OportunidadeEncerradaComHistorico"
    ),
    "ResultadoDaReaberturaDaOportunidade": _resultado("OportunidadeAbertaComHistorico"),
    "RecusarTransferenciaOportunidade": {
        "type": "object",
        "additionalProperties": False,
        "required": ["motivo"],
        "properties": {"motivo": _texto()},
    },
    "EncerrarOportunidade": {
        "type": "object",
        "additionalProperties": False,
        "required": ["resultado", "motivo", "evidencia"],
        "properties": {
            "resultado": {"type": "string", "enum": ETAPAS_ENCERRADAS},
            "motivo": _texto(),
            "evidencia": _texto(),
        },
    },
    "ReabrirOportunidade": {
        "type": "object",
        "additionalProperties": False,
        "required": ["motivo", "etapa", "proximo_passo"],
        "properties": {
            "motivo": _texto(),
            "etapa": _ref("EtapaAbertaOportunidade"),
            "proximo_passo": _ref("ProximoPasso"),
        },
    },
    "PaginaDeOportunidades": {
        "type": "object",
        "additionalProperties": False,
        "required": ["itens", "proximo_cursor"],
        "properties": {
            "itens": {"type": "array", "items": _ref("Oportunidade")},
            "proximo_cursor": {"type": ["string", "null"]},
        },
    },
}

RESPOSTAS = {
    "AcaoNaoAutorizada": {
        "description": (
            "A conta autenticada não tem permissão para executar esta ação "
            "neste recurso."
        )
    }
}

# O django-ninja só sabe emitir parâmetro por OPERAÇÃO; o congelado declara os
# de caminho uma vez por rota. As operações destas rotas mandam
# `"parameters": []` no `openapi_extra` e o exportador reancora a lista aqui.
PARAMETROS_DE_CAMINHO = {
    "/opportunities/{opportunity_id}": [
        {
            "name": "opportunity_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        }
    ],
    "/opportunities/{opportunity_id}/history": [
        {
            "name": "opportunity_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        }
    ],
    "/opportunities/{opportunity_id}/transfers": [
        {
            "name": "opportunity_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        }
    ],
    "/opportunities/{opportunity_id}/transfers/{transfer_id}/accept": [
        {
            "name": "opportunity_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        },
        {
            "name": "transfer_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        },
    ],
    "/opportunities/{opportunity_id}/transfers/{transfer_id}/refuse": [
        {
            "name": "opportunity_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        },
        {
            "name": "transfer_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        },
    ],
    "/opportunities/{opportunity_id}/close": [
        {
            "name": "opportunity_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        }
    ],
    "/opportunities/{opportunity_id}/reopen": [
        {
            "name": "opportunity_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        }
    ],
}

SEM_PARAMETROS_NA_OPERACAO = {"parameters": []}


def _autorizacao(recurso: str, acao: str, escopo: str) -> dict:
    return {
        "recurso": recurso,
        "acao": acao,
        "permitido_para": ["comercial"],
        "escopo": escopo,
    }


LISTAR = {
    "x-autorizacao": _autorizacao("oportunidade", "listar", "titular"),
    "parameters": [
        {
            "name": "lead_id",
            "in": "query",
            "schema": {"type": "string"},
            "description": (
                "Identificador opaco do lead cujas oportunidades serão listadas."
            ),
        },
        {
            "name": "titular_id",
            "in": "query",
            "schema": {"type": "string"},
            "description": (
                "Identificador opaco da pessoa responsável pela oportunidade."
            ),
        },
        {"name": "etapa", "in": "query", "schema": _ref("EtapaOportunidade")},
        {"name": "situacao", "in": "query", "schema": _ref("SituacaoOportunidade")},
        {
            "name": "atrasada",
            "in": "query",
            "schema": {"type": "boolean"},
            "description": (
                "Quando verdadeiro, retorna somente oportunidades com etapa "
                "aberta e próximo passo vencido."
            ),
        },
        {"name": "cursor", "in": "query", "schema": {"type": "string"}},
    ],
    "responses": {
        200: _resposta("Página de oportunidades", "PaginaDeOportunidades"),
        403: _NEGADA,
    },
}

CRIAR = {
    "x-autorizacao": _autorizacao("oportunidade", "criar", "titular_autorizado"),
    "requestBody": _corpo("CriarOportunidade"),
    "responses": {
        201: _resposta("Oportunidade criada", "OportunidadeComHistorico"),
        403: _NEGADA,
        404: {"description": "Lead ou fonte vinculada inexistente"},
        422: {"description": "Payload inválido"},
    },
}

CONSULTAR = {
    "x-autorizacao": _autorizacao("oportunidade", "consultar", "titular"),
    **SEM_PARAMETROS_NA_OPERACAO,
    "responses": {
        200: _resposta("Oportunidade encontrada", "OportunidadeComHistorico"),
        403: _NEGADA,
        404: {"description": "Oportunidade inexistente"},
    },
}

ATUALIZAR = {
    "x-autorizacao": _autorizacao("oportunidade", "atualizar", "titular"),
    **SEM_PARAMETROS_NA_OPERACAO,
    "requestBody": _corpo("AtualizarOportunidade"),
    "responses": {
        200: _resposta(
            "Oportunidade atualizada", "ResultadoDaAtualizacaoDaOportunidade"
        ),
        403: _NEGADA,
        404: {"description": "Oportunidade inexistente"},
        409: {
            "description": (
                "A oportunidade está encerrada; use a reabertura para retomá-la"
            )
        },
        422: {"description": "Payload inválido"},
    },
}

REGISTRAR_HISTORICO = {
    "x-autorizacao": _autorizacao("oportunidade", "registrar_historico", "titular"),
    **SEM_PARAMETROS_NA_OPERACAO,
    "requestBody": _corpo("RegistrarHistoricoOportunidade"),
    "responses": {
        201: _resposta("Registro criado", "RegistroHistoricoOportunidade"),
        403: _NEGADA,
        404: {"description": "Oportunidade inexistente"},
        422: {"description": "Payload inválido"},
    },
}

TRANSFERIR = {
    "x-autorizacao": _autorizacao("oportunidade", "transferir", "titular"),
    **SEM_PARAMETROS_NA_OPERACAO,
    "requestBody": _corpo("TransferirResponsabilidadeOportunidade"),
    "responses": {
        201: _resposta(
            "Transferência pendente de aceite do novo titular",
            "TransferenciaComEvento",
        ),
        403: _NEGADA,
        404: {"description": "Oportunidade inexistente"},
        409: {"description": "Já há uma transferência pendente para esta oportunidade"},
        422: {"description": "Payload inválido"},
    },
}

ACEITAR = {
    "x-autorizacao": _autorizacao("transferencia", "aceitar", "novo_titular"),
    **SEM_PARAMETROS_NA_OPERACAO,
    "responses": {
        200: _resposta("Transferência concluída", "ResultadoDaMutacaoDaOportunidade"),
        403: _NEGADA,
        404: {"description": "Oportunidade ou transferência inexistente"},
        409: {
            "description": (
                "A transferência não está pendente ou pertence a outro titular"
            )
        },
    },
}

RECUSAR = {
    "x-autorizacao": _autorizacao("transferencia", "recusar", "novo_titular"),
    **SEM_PARAMETROS_NA_OPERACAO,
    "requestBody": _corpo("RecusarTransferenciaOportunidade"),
    "responses": {
        200: _resposta(
            "Transferência recusada; o titular atual permanece responsável",
            "TransferenciaComEvento",
        ),
        403: _NEGADA,
        404: {"description": "Oportunidade ou transferência inexistente"},
        409: {
            "description": (
                "A transferência não está pendente ou pertence a outro titular"
            )
        },
        422: {"description": "Payload inválido"},
    },
}

ENCERRAR = {
    "x-autorizacao": _autorizacao("oportunidade", "encerrar", "titular"),
    **SEM_PARAMETROS_NA_OPERACAO,
    "requestBody": _corpo("EncerrarOportunidade"),
    "responses": {
        200: _resposta(
            "Oportunidade encerrada", "ResultadoDoEncerramentoDaOportunidade"
        ),
        403: _NEGADA,
        404: {"description": "Oportunidade inexistente"},
        409: {"description": "A oportunidade já está encerrada"},
        422: {"description": "Payload inválido"},
    },
}

REABRIR = {
    "x-autorizacao": _autorizacao("oportunidade", "reabrir", "titular"),
    **SEM_PARAMETROS_NA_OPERACAO,
    "requestBody": _corpo("ReabrirOportunidade"),
    "responses": {
        200: _resposta("Oportunidade reaberta", "ResultadoDaReaberturaDaOportunidade"),
        403: _NEGADA,
        404: {"description": "Oportunidade inexistente"},
        409: {"description": "A oportunidade ainda está aberta"},
        422: {"description": "Payload inválido"},
    },
}
