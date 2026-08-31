# apps/core/tokens_de_entrada.py — a defesa de CSRF do login por senha
"""`issueLoginToken`/`entrar_senha` (DECISAO-login-por-senha.md §3).

Login por senha CRIA sessão, e `services/identidade/LICOES.md` já registra,
por escrito, que o padrão de `/entrar/sair` (Origin/Referer, `csrf_exempt`)
é só para ações que DESTROEM estado. Como quem RENDERIZA o formulário de
senha é o `funil`, não esta célula, nenhum CSRF token nativo do Django
chegaria intacto de um lado para o outro (segredos diferentes, dois
processos). A saída: um token efêmero, ASSINADO por esta célula e conferido
por ela mesma — o `funil` só carrega o valor opaco, do mesmo jeito que já
carrega o `state` do OAuth do Google de um lado para o outro.

`TimestampSigner` é biblioteca padrão do Django (`django.core.signing`) —
nenhuma dependência nova. O valor não guarda e-mail nem senha nenhuma, só
prova "isto foi pedido a este site, agora".
"""

from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

# O SALT separa esta assinatura de qualquer outro uso futuro de
# TimestampSigner nesta célula (a chave derivada muda com o salt, mesmo
# SECRET_KEY) — sem ele, um token assinado para OUTRO propósito, com o
# mesmo SECRET_KEY, validaria aqui por acidente.
_SALT = "identidade.tokens_de_entrada"
_ASSUNTO = "token-de-entrada"
# Generoso o bastante para alguém abrir /login e digitar com calma, curto o
# bastante para não valer a pena guardar um token roubado para depois.
VALIDADE_SEGUNDOS = 20 * 60


def _signer() -> TimestampSigner:
    return TimestampSigner(salt=_SALT)


def emitir() -> str:
    return _signer().sign(_ASSUNTO)


def confere(token: str) -> bool:
    """`True` só se o token foi emitido por esta célula (mesmo salt), com o
    conteúdo esperado, e ainda dentro da validade. Qualquer outro caso
    (assinatura errada, conteúdo diferente, vencido, vazio) é `False` —
    nunca levanta, quem chama decide o que fazer com a recusa."""
    if not token:
        return False
    try:
        valor = _signer().unsign(token, max_age=VALIDADE_SEGUNDOS)
    except (BadSignature, SignatureExpired):
        return False
    return valor == _ASSUNTO
