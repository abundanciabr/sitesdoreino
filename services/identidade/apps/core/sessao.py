"""Quem está dentro do SITE, agora — a sessão e o papel de quem a abriu.

Herdeira direta da sessão da Caixa (o arquivo homônimo de `sugestoes`, hoje
aposentado lá): a DECISAO-celula-de-identidade mudou a sessão de casa sem
mudar o desenho, que continua deliberadamente magro.

**O que a sessão carrega: um `Identidade.id`, e mais nada.** Nem e-mail, nem
papel, nem nome. Duas razões, e as duas são regra da casa, não gosto:

1. **O e-mail vive numa linha só** (EVO-01 §3). O backend de sessão é o de
   cookie assinado: o conteúdo é *assinado*, não *cifrado* — quem tem o cookie
   consegue LER o que há dentro. E-mail ali seria dado pessoal espalhado.
2. **O papel NÃO é persistido, é derivado a cada requisição** da lista
   `IDENTIDADE_STAFF_EMAILS`. Trocar quem é staff = editar uma variável no
   servidor e reiniciar a célula — sem migração, sem deploy de código (a
   promessa da EVO-01 §4, que a resposta de `/sessao` continua honrando).
   Papel gravado na linha — ou dentro do cookie — quebraria isso em silêncio.

E vale o INVARIANTE da DECISAO-onde-mora-a-sessao §4, agora com esta célula
respondendo: **o papel desta sessão nunca autoriza nada.** A lista de staff da
Caixa é DELA (`SUGESTOES_STAFF_EMAILS`, conferida lá, sobre o e-mail que a
resposta completa entrega ao par autorizado); a daqui só decide o que o site
MOSTRA. Papel novo = lista própria (DECISAO-onde-mora-a-sessao §5.5).
"""

import os
from dataclasses import dataclass

from apps.identidade.models import Identidade

# Chaves do dicionário de sessão. Nomeadas aqui e importadas por quem precisa —
# string solta espalhada por views é como uma delas vira `estado_oauth2` num
# lugar só e o CSRF do OAuth para de conferir sem ninguém notar.
CHAVE_IDENTIDADE = "identidade"
CHAVE_ESTADO_OAUTH = "estado_oauth"
CHAVE_DESTINO = "destino"

PAPEL_ALUNO = "aluno"
PAPEL_STAFF = "staff"


def emails_da_staff() -> set[str]:
    """A lista de staff DESTA célula, lida NO PONTO DE USO.

    Ausente ou vazia ⇒ conjunto vazio, e a célula sobe normalmente: ninguém é
    staff, e a porta continua funcionando. É o default inofensivo que a
    convenção da casa pede — o oposto de fail-hard no import.
    """
    crua = os.environ.get("IDENTIDADE_STAFF_EMAILS", "")
    return {parte.strip().lower() for parte in crua.split(",") if parte.strip()}


def e_staff(email: str) -> bool:
    return email.strip().lower() in emails_da_staff()


def papel_de(email: str) -> str:
    # O vocabulário (`aluno`/`staff`) é o que o contrato de sessão já falava
    # quando a Caixa respondia — mudou quem responde, não a resposta.
    return PAPEL_STAFF if e_staff(email) else PAPEL_ALUNO


def cunhar_ou_recuperar(*, email: str, nome: str) -> Identidade:
    """A mesma pessoa entrando dez vezes tem UMA linha (EVO-01 §3).

    A idempotência é do banco, não desta função: `Identidade.email` é `unique`,
    e `get_or_create` transforma a corrida de dois logins simultâneos numa
    recuperação, não numa segunda linha.

    `nome_exibido` só é gravado na CUNHAGEM. Reentrar não sobrescreve: o campo
    poderá ser editável pela pessoa, e deixar o Google reescrevê-lo a cada
    login apagaria essa escolha sem aviso.
    """
    identidade, _ = Identidade.objects.get_or_create(
        email=email.strip().lower(),
        defaults={"provedor": "google", "nome_exibido": nome.strip()[:120]},
    )
    return identidade


@dataclass(frozen=True)
class Ator:
    """Quem está fazendo esta requisição. `None` = ninguém, e isso é um estado
    legítimo (a porta é pública; o que cada célula guarda atrás dela não é)."""

    identidade: Identidade
    papel: str

    @property
    def e_staff(self) -> bool:
        return self.papel == PAPEL_STAFF


def abrir_sessao(request, identidade: Identidade) -> None:
    """`flush()` antes de gravar, sempre.

    Não é zelo: o `estado_oauth` do login que acabou de terminar ainda está na
    sessão, e uma sessão que começa carregando lixo do passo anterior é como um
    `state` já usado vira reutilizável. Sessão nova, dicionário limpo — e só
    então o identificador de quem entrou.
    """
    request.session.flush()
    request.session[CHAVE_IDENTIDADE] = identidade.id


def encerrar_sessao(request) -> None:
    request.session.flush()


def ator_atual(request):
    """O ator desta requisição, ou `None`.

    A identidade é reconferida no banco a cada requisição, de propósito: um
    cookie assinado sobrevive à linha que ele aponta. Identidade apagada ⇒ o
    cookie deixa de valer no mesmo instante, sem precisar revogar nada.
    """
    identificador = request.session.get(CHAVE_IDENTIDADE)
    if not identificador:
        return None
    identidade = Identidade.objects.filter(pk=identificador).first()
    if identidade is None:
        return None
    return Ator(identidade=identidade, papel=papel_de(identidade.email))
