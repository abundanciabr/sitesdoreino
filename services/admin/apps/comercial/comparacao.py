"""O grupo de comparação: leads que ficam SEM o agente, de propósito, para
medir o efeito real dele.

"Vendas depois de uma conversa com o agente" não provam ganho: quem conversa
já estava mais perto de comprar. A única conta honesta compara grupos
parecidos, um com a abordagem e outro sem. Para isso, uma fatia pequena e
FIXA dos leads novos fica de fora do trabalho comercial e recebe só o que já
existia (as jornadas fixas da mensageria e a caixa de conversas, onde a
equipe responde).

* O `percentual` mora numa linha só (`ConfiguracaoDaComparacao`) e o padrão é
  **0**: enquanto o mantenedor não escolher, nada muda para ninguém. Muda-se
  em `/admin/crm/agentes/`, com confirmação e registro na auditoria.
* O grupo de cada lead é decidido UMA vez, quando ele aparece (`decidir`), e
  fica gravado em `MarcaDeComparacao`. A conta é um hash de `site_id` + a
  chave do contato (e-mail, ou os dígitos do telefone), sem sorteio: o mesmo
  lead cai sempre no mesmo grupo, em qualquer execução e em qualquer
  máquina. Mudar o percentual depois não move quem já foi marcado.
* A marca guarda só hashes e identificadores opacos, nunca e-mail, nome ou
  telefone. A chave leva o `site_id` dentro do hash: o mesmo e-mail em outro
  site é outra chave, e dado de um site nunca vira de outro.
* Lead sem marca é lead de antes deste recurso (ou de antes de ligar o
  percentual): fica fora da comparação, porque o tratamento dele não é
  conhecido.

A leads entrega, para cada oportunidade, a mesma chave (`chaves_de_contato`
em `/resultados/comerciais`); é assim que a tela de resultados separa os dois
grupos sem receber e-mail de ninguém.
"""

from __future__ import annotations

import hashlib
import re

from django.db import IntegrityError, models, transaction
from django.utils import timezone

GRUPO_COMPARACAO = "comparacao"
GRUPO_AGENTE = "agente"
PERCENTUAL_MAXIMO = 50  # nunca mais da metade dos leads sem o agente


class ConfiguracaoDaComparacao(models.Model):
    """Uma linha só (`pk=1`): que fatia dos leads novos fica sem o agente."""

    percentual = models.PositiveSmallIntegerField(default=0)
    atualizado_por = models.CharField(max_length=200, blank=True, default="")
    atualizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "comercial_configuracaodacomparacao"


class MarcaDeComparacao(models.Model):
    """O grupo em que um lead caiu quando apareceu. Só referências opacas."""

    site_id = models.CharField(max_length=80)
    chave = models.CharField(max_length=64)
    sessao = models.CharField(max_length=120, blank=True, default="", db_index=True)
    contato_id = models.CharField(max_length=80, blank=True, default="", db_index=True)
    grupo = models.CharField(max_length=20)
    percentual = models.PositiveSmallIntegerField(default=0)
    teste = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comercial_marcadecomparacao"
        constraints = [
            models.UniqueConstraint(fields=["site_id", "chave"], name="uma_marca_por_lead_e_site"),
        ]


# ---------------------------------------------------------------- a conta


def quem_e(email: str = "", telefone: str = "") -> str:
    """Como o lead é reconhecido: o e-mail em minúsculas; sem e-mail, os dígitos do telefone."""
    return (email or "").strip().lower() or re.sub(r"\D", "", telefone or "")


def chave_do_contato(site_id: str, quem: str) -> str:
    """O identificador opaco do lead dentro de um site. A leads calcula o mesmo."""
    return hashlib.sha256(f"chave-de-contato:{site_id}:{quem}".encode()).hexdigest()


def grupo_do_contato(site_id: str, quem: str, percentual: int) -> str:
    """O grupo que a conta dá a este lead com este percentual. Sem sorteio: o
    mesmo `site_id` e a mesma pessoa dão sempre o mesmo número de 0 a 99, e o
    lead cai na comparação quando o número é menor que o percentual."""
    percentual = max(0, min(PERCENTUAL_MAXIMO, int(percentual or 0)))
    if percentual <= 0:
        return GRUPO_AGENTE
    soma = hashlib.sha256(f"grupo-de-comparacao:{site_id}:{quem}".encode()).hexdigest()
    return GRUPO_COMPARACAO if int(soma[:8], 16) % 100 < percentual else GRUPO_AGENTE


# ---------------------------------------------------------------- o percentual


def percentual() -> int:
    """O percentual em vigor; 0 quando ninguém escolheu."""
    achado = ConfiguracaoDaComparacao.objects.filter(pk=1).values_list("percentual", flat=True).first()
    return max(0, min(PERCENTUAL_MAXIMO, int(achado or 0)))


def definir_percentual(novo: int, quem: str) -> tuple[int, int]:
    """Grava o percentual. Devolve (antes, depois). Só vale para leads novos."""
    novo = max(0, min(PERCENTUAL_MAXIMO, int(novo)))
    with transaction.atomic():
        linha, _ = ConfiguracaoDaComparacao.objects.select_for_update().get_or_create(pk=1)
        antes = linha.percentual
        linha.percentual = novo
        linha.atualizado_por = (quem or "")[:200]
        linha.atualizado_em = timezone.now()
        linha.save()
    return antes, novo


# ---------------------------------------------------------------- a marca


def _marca_existente(site_id: str, chave: str, sessao: str) -> MarcaDeComparacao | None:
    marca = MarcaDeComparacao.objects.filter(site_id=site_id, chave=chave).first()
    if marca is None and sessao:
        marca = MarcaDeComparacao.objects.filter(site_id=site_id, sessao=sessao).order_by("id").first()
    return marca


def decidir(site_id: str, quem: str, *, sessao: str = "", teste: bool = False) -> str:
    """O grupo do lead, decidido na primeira vez e guardado. A captura parcial
    e o quiz concluído da mesma sessão ficam no mesmo grupo, mesmo que a pessoa
    tenha deixado só o telefone numa e o e-mail na outra."""
    if not site_id or not quem:
        return GRUPO_AGENTE
    chave = chave_do_contato(site_id, quem)
    marca = _marca_existente(site_id, chave, sessao)
    if marca is not None:
        if marca.chave != chave:
            _gravar(site_id, chave, sessao, marca.grupo, marca.percentual, teste)
        return marca.grupo
    atual = percentual()
    grupo = grupo_do_contato(site_id, quem, atual)
    return _gravar(site_id, chave, sessao, grupo, atual, teste)


def _gravar(site_id, chave, sessao, grupo, atual, teste) -> str:
    try:
        with transaction.atomic():
            MarcaDeComparacao.objects.create(
                site_id=site_id, chave=chave, sessao=sessao[:120], grupo=grupo, percentual=atual, teste=teste)
    except IntegrityError:
        existente = MarcaDeComparacao.objects.filter(site_id=site_id, chave=chave).first()
        return existente.grupo if existente else grupo
    return grupo


def grupo_do_contato_id(site_id: str, contato_id: str) -> str | None:
    """O grupo de um contato já ligado a uma marca; `None` quando ainda não se sabe."""
    if not site_id or not contato_id:
        return None
    marca = MarcaDeComparacao.objects.filter(site_id=site_id, contato_id=contato_id).first()
    return marca.grupo if marca else None


def ligar_contato(site_id: str, quem: str, contato_id: str) -> str | None:
    """Quando a ficha do lead é achada, a marca passa a conhecer o `contato_id`.
    Devolve o grupo (`None` se o lead não tem marca: é de antes do recurso)."""
    if not site_id or not quem or not contato_id:
        return None
    marca = MarcaDeComparacao.objects.filter(site_id=site_id, chave=chave_do_contato(site_id, quem)).first()
    if marca is None:
        return None
    if marca.contato_id != contato_id[:80]:
        MarcaDeComparacao.objects.filter(site_id=site_id, sessao=marca.sessao).exclude(sessao="") \
            .filter(contato_id="").update(contato_id=contato_id[:80])
        MarcaDeComparacao.objects.filter(pk=marca.pk).update(contato_id=contato_id[:80])
    return marca.grupo


def ha_comparacao_em_curso() -> bool:
    """Há leads que precisam ficar sem o agente (percentual ligado ou lead já marcado)."""
    return percentual() > 0 or MarcaDeComparacao.objects.filter(grupo=GRUPO_COMPARACAO).exists()


def grupos_por_chave(chaves, site_id: str = "") -> dict[str, str]:
    """Para a tela de resultados: {chave: grupo} das marcas que existem."""
    chaves = [c for c in set(chaves) if c]
    if not chaves:
        return {}
    # Marca feita com o percentual em 0 nunca teve par na comparação: o lead entrou no agente sem que
    # ninguém ficasse de fora ao mesmo tempo. Contar esses leads distorceria o período dos dois lados.
    marcas = MarcaDeComparacao.objects.filter(chave__in=chaves, teste=False, percentual__gt=0)
    if site_id:
        marcas = marcas.filter(site_id=site_id)
    return {m.chave: m.grupo for m in marcas.order_by("id")}
