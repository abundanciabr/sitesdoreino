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

import logging
import os
import secrets
import string
from dataclasses import dataclass

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction

from apps.identidade import eventos
from apps.identidade.models import Identidade
from apps.identidade.tasks import relay_apos_commit

# Chaves do dicionário de sessão. Nomeadas aqui e importadas por quem precisa —
# string solta espalhada por views é como uma delas vira `estado_oauth2` num
# lugar só e o CSRF do OAuth para de conferir sem ninguém notar.
logger = logging.getLogger("identidade.sessao")

CHAVE_IDENTIDADE = "identidade"
# O site de onde a pessoa veio, guardado entre o "vai para o Google" e a volta.
# Mesma razão do destino: o redirecionamento externo apaga tudo que não estiver
# na sessão, e este valor precisa existir na hora da cunhagem, do outro lado.
CHAVE_SITE = "site_de_origem"
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


def cunhar_ou_recuperar(*, email: str, nome: str, site_id: str = "") -> Identidade:
    """A mesma pessoa entrando dez vezes tem UMA linha (EVO-01 §3).

    A idempotência é do banco, não desta função: `Identidade.email` é `unique`,
    e `get_or_create` transforma a corrida de dois logins simultâneos numa
    recuperação, não numa segunda linha.

    `nome_exibido` só é gravado na CUNHAGEM. Reentrar não sobrescreve: o campo
    poderá ser editável pela pessoa, e deixar o Google reescrevê-lo a cada
    login apagaria essa escolha sem aviso.

    **Desde 31/08/2026 a cunhagem ANUNCIA o fato** (`identidade.pessoa-cadastrada`,
    degrau 1 do `PLANO-SEQUENCIAS-DE-MENSAGENS`), na MESMA transação em que a
    linha nasce. Só a cunhagem: reentrar não é cadastrar-se, e um evento por
    login mandaria boas-vindas para sempre à mesma pessoa.

    **`site_id` vazio ⇒ a pessoa é cunhada e o fato NÃO é anunciado**, com um
    ERROR no log. É a única degradação possível aqui, e ela é o lado certo:
    esta célula não resolve Host→Site (isso é do catálogo, e ela nem fala com
    ele), então o site chega de quem já o conhece — o `funil`, na URL de
    entrada. Publicar um fato com o site errado seria pior que não publicar:
    quem escuta usa esse campo para escolher template e remetente, e uma
    mensagem sairia com a marca de outro site. Entrar continua funcionando nos
    dois casos, que é o que não pode quebrar nunca.
    """
    with transaction.atomic():
        identidade, criada = Identidade.objects.get_or_create(
            email=email.strip().lower(),
            defaults={"provedor": "google", "nome_exibido": nome.strip()[:120]},
        )
        if criada:
            if site_id:
                eventos.pessoa_cadastrada(site_id=site_id, pessoa_id=identidade.id)
            else:
                logger.error(
                    "pessoa %s cunhada SEM site_id — o fato nao foi anunciado, "
                    "e nenhuma sequencia de boas-vindas vai comecar por ela. "
                    "Quem manda o site e a porta de entrada (parametro `site`).",
                    identidade.id,
                )
    if criada:
        # Depois do COMMIT, nunca dentro: é o que dá latência de segundos sem
        # furar a outbox — no fio nunca há evento de um fato que não aconteceu.
        # Falhar aqui não perde nada: a linha fica pendente e a task periódica
        # do relay a republica.
        transaction.on_commit(relay_apos_commit)
    return identidade


def definir_senha(
    *, email: str, senha: str, nome: str = "", site_id: str = ""
) -> tuple[Identidade, bool]:
    """`setPassword` — o segundo jeito de provar quem é (DECISAO-login-por-senha.md).

    Mesma forma de `cunhar_ou_recuperar`: idempotente por e-mail
    (`get_or_create`), anuncia `pessoa_cadastrada` só na CUNHAGEM (reentrar
    para trocar a senha não é cadastrar-se de novo). A diferença é o
    `provedor` — `"senha"` em vez de `"google"` — e que aqui a senha é sempre
    gravada, mesmo numa linha que já existia: é o "definir" do nome da
    operação, não um "definir só se ainda não tinha".

    A senha NUNCA aparece em texto puro depois desta função — só o hash que
    `make_password` produz entra na linha.
    """
    with transaction.atomic():
        identidade, criada = Identidade.objects.get_or_create(
            email=email.strip().lower(),
            defaults={"provedor": "senha", "nome_exibido": nome.strip()[:120]},
        )
        identidade.senha_hash = make_password(senha)
        identidade.save(update_fields=["senha_hash"])
        if criada:
            if site_id:
                eventos.pessoa_cadastrada(site_id=site_id, pessoa_id=identidade.id)
            else:
                logger.error(
                    "pessoa %s cunhada por senha SEM site_id — o fato nao foi "
                    "anunciado, e nenhuma sequencia de boas-vindas vai comecar "
                    "por ela.",
                    identidade.id,
                )
    if criada:
        transaction.on_commit(relay_apos_commit)
    return identidade, criada


def verificar_senha(*, email: str, senha: str) -> "Identidade | None":
    """`entrar_senha` confere aqui — devolve a `Identidade` se a senha bate,
    `None` em QUALQUER outro caso (e-mail sem linha, linha sem senha
    definida, senha errada). Os três casos são indistinguíveis de propósito
    (`DECISAO-login-por-senha.md` §6.1): a chave de recusa é a mesma, para
    não virar um jeito de descobrir quais e-mails têm conta.
    """
    identidade = Identidade.objects.filter(email=email.strip().lower()).first()
    if identidade is None or not identidade.senha_hash:
        return None
    if not check_password(senha, identidade.senha_hash):
        return None
    return identidade


def gerar_senha_aleatoria() -> str:
    """A senha nova do reset manual (`resetPassword`) — nunca escolhida por
    quem chama, sempre sorteada aqui. Sai em texto puro só na resposta
    daquele POST, uma vez; esta função não grava nada, quem chama grava o
    hash com `make_password`."""
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(12))


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
