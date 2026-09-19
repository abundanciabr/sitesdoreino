# apps/core/auth.py  # [RECEITA:R1 v1]
from django.conf import settings
from ninja.security import HttpBearer


class bearerAuth(HttpBearer):
    """Aceita os tokens estáticos de `TOKENS_ACEITOS`, um por par consumidor.

    Cópia do PADRÃO de `identidade`/`forum`/`pages` (Lei 3: copia-se o padrão
    entre células, nunca se importa código de uma na outra). Nome da classe em
    minúsculas de propósito: o freeze de contrato exige que a chave de
    `components.securitySchemes` seja `bearerAuth`, e o django-ninja usa o nome
    da classe do callback de auth como chave do security scheme.

    **Este token responde "QUEM CHAMA", e nada além disso.** Ele prova que o
    chamador é uma célula da casa; quem é a PESSOA do outro lado do navegador
    continua sendo pergunta da `identidade`, feita com o cookie, na porta de
    gente desta célula (`apps/core/porta.py`). Aqui não chega cookie e não há
    sessão.

    **O conjunto é PLANO, e isso está certo porque esta porta só LÊ**
    (`armadilhas/318`). Não existe operação que promova nem que remova
    administrador: quem faz isso é o mantenedor, na tela desta casa, com sessão.
    No dia em que uma escrita entrar aqui, o conjunto tem de virar dois graus
    (o desenho `TOKENS_SENHA_*` da `identidade`), porque hoje todo par que ganha
    o token para ler ganharia junto o poder de escrever.

    **E o Bearer é o ÚNICO cadeado desta porta.** A célula roda sob
    `SCRIPT_NAME=/admin` e o corte do prefixo é do Django, não do Traefik, então
    `/interno/...` é alcançável pela borda pública em
    `meshcraft.top/admin/interno/...` (`armadilhas/186`; a premissa está fixada
    em `tests/test_healthz_script_name.py`). Não copie daqui a frase "a porta
    interna não resolve pela borda": na `identidade` ela é verdadeira, aqui não.
    O guarda que importa é o 401 em TODAS as operações, inclusive com o conjunto
    de tokens vazio (`tests/test_porta_de_maquina.py`).
    """

    def authenticate(self, request, token: str):
        return token if token in settings.TOKENS_ACEITOS else None
