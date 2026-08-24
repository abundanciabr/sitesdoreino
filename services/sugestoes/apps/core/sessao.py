"""Quem está dentro, agora — a sessão da Caixa e o papel de quem a abriu.

A `DECISAO-EVO-01-identidade.md` §7 descartou uma célula de auth: "a `sugestoes`
cuida da própria sessão". Este arquivo é essa sessão inteira, e ela é
deliberadamente magra.

**O que a sessão carrega: um `Identidade.id`, e mais nada.** Nem e-mail, nem
papel, nem nome. Duas razões, e as duas são regra da casa, não gosto:

1. **O e-mail vive numa linha só** (EVO-01 §3, e há guarda para isso no
   `test_inv_sem_fk_para_fora.py`). O backend de sessão desta célula é o de
   cookie assinado: o conteúdo é *assinado*, não *cifrado* — quem tem o cookie
   consegue LER o que há dentro. E-mail ali dentro seria dado pessoal
   espalhado, exatamente o que a decisão evitou no banco.
2. **O papel NÃO é persistido, é derivado a cada requisição** da lista
   `SUGESTOES_STAFF_EMAILS`. A decisão §4 promete: "trocar quem é staff = editar
   uma variável no servidor e reiniciar a célula. Sem migração, sem deploy de
   código." Um papel gravado na linha da `Identidade` — ou dentro do cookie —
   quebraria essa promessa em silêncio: tirar alguém da lista não tiraria o
   crachá de quem já estava dentro.

Por que cookie assinado e não sessão em banco: o único conteúdo é um
identificador opaco que já é conferido contra o banco a cada leitura
(`ator_atual` faz o `SELECT`), então a tabela `django_session` daria uma
escrita por login e um `SELECT` por requisição em troca de nada. A conta muda no
dia em que a Caixa precisar **revogar** uma sessão de longe — aí a sessão volta
para o banco, e é só trocar `SESSION_ENGINE`.
"""

import os
from dataclasses import dataclass

from apps.sugestoes.models import Identidade

# Chaves do dicionário de sessão. Nomeadas aqui e importadas por quem precisa —
# string solta espalhada por views é como uma delas vira `estado_oauth2` num
# lugar só e o CSRF do OAuth para de conferir sem ninguém notar.
CHAVE_IDENTIDADE = "identidade"
CHAVE_ESTADO_OAUTH = "estado_oauth"

PAPEL_ALUNO = "aluno"
PAPEL_STAFF = "staff"


def emails_da_staff() -> set[str]:
    """A lista de staff, lida NO PONTO DE USO (EVO-01 §4).

    Ausente ou vazia ⇒ conjunto vazio, e a célula sobe normalmente: ninguém é
    staff, e a porta continua funcionando para alunos. É o default inofensivo
    que a convenção da casa pede — o oposto de fail-hard no import.
    """
    crua = os.environ.get("SUGESTOES_STAFF_EMAILS", "")
    return {parte.strip().lower() for parte in crua.split(",") if parte.strip()}


def e_staff(email: str) -> bool:
    return email.strip().lower() in emails_da_staff()


def papel_de(email: str) -> str:
    return PAPEL_STAFF if e_staff(email) else PAPEL_ALUNO


def cunhar_ou_recuperar(*, email: str, nome: str) -> Identidade:
    """A mesma pessoa entrando dez vezes tem UMA linha (EVO-01 §3).

    A idempotência é do banco, não desta função: `Identidade.email` é `unique`,
    e `get_or_create` transforma a corrida de dois logins simultâneos numa
    recuperação, não numa segunda linha.

    `nome_exibido` só é gravado na CUNHAGEM. Reentrar não sobrescreve: o campo é
    editável pela pessoa (é o nome que aparece nas sugestões dela), e deixar o
    Google reescrevê-lo a cada login apagaria essa escolha sem aviso.
    """
    identidade, _ = Identidade.objects.get_or_create(
        email=email.strip().lower(),
        defaults={"provedor": "google", "nome_exibido": nome.strip()[:120]},
    )
    return identidade


@dataclass(frozen=True)
class Ator:
    """Quem está fazendo esta requisição. `None` = ninguém, e isso é um estado
    legítimo (a porta é pública; o que está atrás dela não é)."""

    identidade: Identidade
    papel: str

    @property
    def e_staff(self) -> bool:
        return self.papel == PAPEL_STAFF


def abrir_sessao(request, identidade: Identidade) -> None:
    """`flush()` antes de gravar, sempre.

    Não é zelo: o `estado_oauth` do login que acabou de terminar ainda está na
    sessão, e uma sessão que começa carregando lixo do passo anterior é como um
    `state` já usado vira reutilizável. Sessão nova, chave nova, dicionário
    limpo — e só então o identificador de quem entrou.
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
