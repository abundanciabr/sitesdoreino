"""Quem é administrador desta área — a metade que mora no banco.

**Isto reverte, em parte, a `DECISAO-celula-admin` §2**, que dizia *"derivada e
nunca gravada"*. A reversão é decisão do mantenedor de 28/08/2026, tomada com o
preço na mesa (`DECISAO-administradores-e-apagar.md` §2): com a lista no banco,
passa a ser possível ganhar acesso de administrador **sem tocar no servidor**.

**A lista efetiva é `ADMIN_EMAILS` (do servidor) ∪ os ativos daqui**, e o env
continua sendo o CHÃO. Duas consequências, as duas desejadas:

- **não existe como se trancar para fora**: quem está no env entra sempre, e o
  botão de remover recusa mexer nele — a saída continua sendo o servidor;
- **banco vazio, corrompido ou restaurado de backup não fecha a porta.**

Ver `apps/core/porta.py`, que é quem soma as duas metades — e que trata falha
de banco como "vale só o env", nunca como "deixa entrar".
"""

from django.db import models


class Administrador(models.Model):
    """Um e-mail promovido pela TELA. O do env não passa por aqui."""

    # `unique` para promover duas vezes não criar duas linhas — e para o
    # "remover" ter um alvo só. Guardado sempre em minúsculas: a porta compara
    # normalizado, e uma linha com maiúscula seria uma promoção que não vale
    # nada e que ninguém consegue explicar depois.
    email = models.EmailField(unique=True)
    # Remover é DESATIVAR, não apagar: a linha é o que dá contexto às linhas de
    # auditoria que falam dela, e promover de novo vira uma reativação em vez
    # de uma segunda história.
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["ativo"])]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return f"{self.email}{'' if self.ativo else ' (removido)'}"
