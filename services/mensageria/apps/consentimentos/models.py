"""Permissão para a equipe chamar a pessoa pelo WhatsApp.

Livro de registros, nunca editado: cada aceite, recusa ou mudança vira uma
linha. A situação atual sai da leitura das linhas (`servico.situacao`), e o
histórico fica consultável. Chave = site + telefone (o WhatsApp é por número).
"""

from django.db import models

ORIGENS = (
    "quiz.completado",
    "quiz.captura_parcial",
    "quiz.consentimento",
    "equipe",
)


class ConsentimentoWhatsapp(models.Model):
    site_id = models.CharField(max_length=100)
    # Telefone em dígitos com DDI (o mesmo formato das conversas).
    endereco = models.CharField(max_length=32)
    # Compara números brasileiros com ou sem o nono dígito.
    chave = models.CharField(max_length=32)
    aceito = models.BooleanField()
    origem = models.CharField(max_length=40, choices=[(o, o) for o in ORIGENS])
    sessao = models.CharField(max_length=64, blank=True, default="")
    referencia = models.CharField(max_length=64, blank=True, default="")
    texto = models.TextField(blank=True, default="")
    versao_texto = models.CharField(max_length=32, blank=True, default="")
    event_id = models.UUIDField(null=True, blank=True, unique=True)
    # Id de plataforma (identidade), quando achado, e o que houve com a
    # preferência das jornadas.
    pessoa_id = models.CharField(max_length=64, blank=True, default="")
    preferencia_motivo = models.CharField(max_length=200, blank=True, default="")
    registrado_em = models.DateTimeField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["site_id", "chave", "registrado_em"], name="consent_site_chave_em"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(origem__in=ORIGENS), name="consentimento_origem_conhecida"
            ),
        ]
