"""O corredor do ChangeSpec: quem registra, o que vale registro, e a trava.

Escopo do EVO-40, e só ele. A lei é a `FORMATO-CHANGESPEC.md` §1/§3/§4/§5 e a
última linha da §8 da `ESPECIFICACAO-CELULA.md`:

> `Sugestao.status` só sai de `PLANEJADO` para `EM_DESENVOLVIMENTO` se existir
> um ChangeSpec aprovado referenciando aquele `suggestion_id`.

**Por que a célula não lê o repositório.** O ChangeSpec de verdade é um
documento em `docs/changespecs/`. Fazer a Caixa abrir o repositório em runtime
daria a ela uma dependência de sistema de arquivos que ela não tem em produção
(a imagem sobe com o código da célula, não com os `docs/`) e um modo de falha
novo — "o documento sumiu ⇒ ninguém desenvolve mais nada". O que entra aqui é
o REGISTRO: quem aprovou, quando, e onde o documento está.

**Dois papéis diferentes, e a diferença é a decisão do mantenedor (25/08/2026).**
Moderar é da EQUIPE (`SUGESTOES_STAFF_EMAILS`); autorizar desenvolvimento é do
APROVADOR (`SUGESTOES_APROVADORES`). Ele escolheu a forma mais travada sabendo
do custo: só ele autoriza. Ser da equipe **não basta**, e há guarda medindo
isso.

**Fail-closed, e é o ponto principal.** Lista vazia ou ausente ⇒ ninguém
aprova ⇒ nenhuma sugestão sai de `planejado` para `em_desenvolvimento`. Isso é
o comportamento CERTO, não um bug: até o e-mail do mantenedor existir no
servidor, nada anda — e "não sei quem pode aprovar" jamais pode virar "então
pode qualquer um". A variável é lida NO PONTO DE USO, com default vazio, como
toda variável desta célula (`config/settings.py`, topo).
"""

import os
import re
from datetime import date

from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_date

from apps.sugestoes.models import ChangeSpecAprovado

# A TELA saiu daqui em 30/08/2026 (TAR-023 degrau 4), junto com o decorador
# `exige_aprovador` que só ela usava: quem registra ChangeSpec agora é o Admin,
# em `/admin/caixa/ideia/<id>`, e ele chega por `apps/core/api_gestao.py`.
#
# **O portão NÃO mudou de dono nem afrouxou** ([INV-SUG10]): quem decide
# continua sendo `e_aprovador()`, aqui embaixo, lido do env no ponto de uso e
# fail-closed com lista vazia. O que mudou é quem o chama — antes um decorador
# de view, agora o handler do contrato, que devolve **403 com a mesma frase**
# (`SEM_MANDATO`). Estar no Admin continua não bastando, e há guarda medindo
# exatamente isso (`test_estar_no_admin_nao_da_o_direito_de_assinar`).

# `CS-{celula}-{sequencial}` (formato §3, ex.: `CS-PORTFOLIO-0001`). O sufixo
# `-v2` é a imutabilidade do §4 em pessoa: escopo que mudou não edita o
# documento, nasce outro. A largura canônica do sequencial é 4 dígitos; o
# padrão aceita mais para não recusar um registro legítimo por zero à esquerda.
FORMA_DO_CHANGE_ID = re.compile(r"^CS-[A-Z0-9]+-\d+(-v\d+)?$")

# Onde o documento pode estar: no repositório (o caminho que o EVO-41 vai
# criar) ou numa URL. Conferir a FORMA não prova que o link abre — prova que
# alguém não colou o título do documento no lugar do endereço dele.
INICIOS_DE_DOCUMENTO = ("https://", "http://", "docs/changespecs/")

SEM_MANDATO = (
    "Registrar ChangeSpec é de quem aprova, e o seu e-mail não está na lista "
    "de aprovadores desta Caixa (SUGESTOES_APROVADORES). Estar na equipe dá o "
    "crachá de moderação, não o de autorizar desenvolvimento — são dois papéis "
    "diferentes de propósito."
)


class ChangeSpecInvalido(Exception):
    """Registro recusado ANTES de qualquer escrita — recusa não precisa de
    rollback, e a mensagem é em português porque quem lê é gente."""


def emails_dos_aprovadores() -> set[str]:
    """A lista de quem autoriza, lida NO PONTO DE USO.

    Ausente ou vazia ⇒ conjunto vazio ⇒ **ninguém** aprova. A célula sobe
    normalmente e a Caixa inteira continua funcionando: o que fica fechado é
    exatamente uma coisa — mover ideia para `em_desenvolvimento`.

    Normalização igual à do staff (`apps/core/sessao.py`): minúsculas e
    `strip`, porque a variável é digitada à mão num arquivo `.env` e um espaço
    depois da vírgula não pode custar o mandato de alguém.
    """
    crua = os.environ.get("SUGESTOES_APROVADORES", "")
    return {parte.strip().lower() for parte in crua.split(",") if parte.strip()}


def e_aprovador(email: str) -> bool:
    return email.strip().lower() in emails_dos_aprovadores()


# ---------------------------------------------------------------------------
# O registro
# ---------------------------------------------------------------------------


def _conferir(campos: dict) -> dict:
    """Tudo que precisa ser verdade antes de a linha existir.

    Confere TUDO e devolve os erros juntos — quem está preenchendo formulário
    não merece descobrir um problema por vez.
    """
    erros = []

    change_id = (campos.get("change_id") or "").strip()
    if not FORMA_DO_CHANGE_ID.match(change_id):
        erros.append(
            "O CHANGE-ID tem a forma CS-{CELULA}-{sequencial}, em maiúsculas — "
            "por exemplo CS-PORTFOLIO-0001 (ou CS-PORTFOLIO-0001-v2, quando o "
            "escopo mudou e nasceu uma segunda versão)."
        )

    documento = (campos.get("documento") or "").strip()
    if not documento.startswith(INICIOS_DE_DOCUMENTO):
        erros.append(
            "O link do documento começa por https://, http:// ou "
            "docs/changespecs/ — é por ele que qualquer pessoa confere depois "
            "o que foi autorizado."
        )

    aprovado_por = (campos.get("aprovado_por") or "").strip()
    if not aprovado_por:
        erros.append(
            "Escreva o NOME de quem aprovou: o §1 do formato exige aprovação "
            "humana e nominal, e “aprovado” sem nome não é aprovação de "
            "ninguém."
        )
    elif "@" in aprovado_por:
        erros.append(
            "Aqui vai o NOME de quem aprovou, não o e-mail: nesta célula o "
            "e-mail vive numa linha só, a da identidade (DECISAO-EVO-01 §3)."
        )

    aprovado_em = parse_date((campos.get("aprovado_em") or "").strip())
    if aprovado_em is None:
        erros.append("A data da aprovação vai no formato AAAA-MM-DD.")

    if erros:
        raise ChangeSpecInvalido(erros)

    return {
        "change_id": change_id,
        "documento": documento,
        "aprovado_por": aprovado_por,
        "aprovado_em": aprovado_em or date.today(),
    }


def registrar(*, sugestao, por, **campos) -> ChangeSpecAprovado:
    """O único caminho de escrita desta tabela.

    Confere fora da transação (recusa não precisa de rollback) e deixa a
    unicidade para o banco: duas abas abertas com o mesmo CHANGE-ID viram uma
    linha e uma frase, nunca duas linhas.
    """
    limpos = _conferir(campos)
    try:
        with transaction.atomic():
            return ChangeSpecAprovado.objects.create(
                sugestao=sugestao, registrado_por=por, **limpos
            )
    except IntegrityError:
        raise ChangeSpecInvalido(
            [
                f"O ChangeSpec {limpos['change_id']} já está registrado nesta "
                "ideia. Um ChangeSpec aprovado não é editado (formato §4): "
                "escopo novo é uma versão nova, com o sufixo -v2."
            ]
        )
