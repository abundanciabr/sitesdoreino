"""O manual de experimentação sai do ar: publica e atualiza o que já existe.

**O sintoma medido.** `https://meshcraft.top/docs/plataforma-experimentacao-e-
aprendizado-de-conversao` responde 404, e o documento não aparece em `/docs/`
(hoje só quatro documentos estão lá). O manual entrou pela migração `0028`
(PR #2014, TAR-675), com `semear_documento`, que é `get_or_create` por
`nome` (`apps/core/documentos.py::_semear`) — por desenho, ela NUNCA toca uma
linha que já existe (para nunca pisar numa edição do mantenedor pela tela,
`armadilhas/253`).

**Duas causas cabem no mesmo sintoma, e só o banco de produção decide qual:**

1. Alguma linha com `nome="plataforma-experimentacao-e-aprendizado-de-
   conversao"` já existia (por exemplo, criada rascunho pela tela) ANTES de a
   `0028` rodar. `get_or_create` encontrou a linha e não fez nada: ela ficou
   com `publico=False` (o `default` do modelo) e nunca saiu do ar.
2. A linha nunca existiu (a pasta embutida faltou na janela daquele deploy,
   por exemplo) e `semear_documento` voltou `False` sem gravar nada
   (`armadilhas/347`, o "falso-verde" documentado: deploy `success`, `/docs/`
   sem o documento).

**Não dá para saber qual das duas aconteceu sem olhar o banco.** Quem
retomar esta lição em produção confere em `/admin/documentos/` a linha
`plataforma-experimentacao-e-aprendizado-de-conversao`: se ela existe, qual
o `publico` e o `arquivado` gravados. Esta migração conserta as DUAS causas
ao mesmo tempo, então o resultado é o mesmo — público, no ar — qualquer que
tenha sido a causa.

**Por que ela força `publico=True` numa linha que já existisse.** Isto é
diferente da regra geral de `semear_documento` (nunca sobrescrever). Aqui não
é uma correção de conteúdo por cima de uma escrita do mantenedor — é a
execução de uma decisão dele: "manual de experimentação: público em /docs"
(`DESENHO-COMUM.md`, respostas do mantenedor de 26/09/2026, 22:25 UTC, item
4). `publico` e `arquivado` são o ESTADO que essa decisão fixa, não o TEXTO
que ele possa ter escrito; forçá-los aqui não arrisca apagar prosa dele.

**Por que o CORPO só troca se ainda for exatamente o que a `0028` semeou.**
Aqui sim vale a regra de `armadilhas/253`: o corpo pode ter sido editado pela
tela depois que a `0028` rodou, e sobrescrever seria o pior desfecho de uma
migração de correção. Em vez de embutir os ~750 linhas antigos como literal
(o que tornaria este arquivo do tamanho do próprio manual, e desatualizaria
sozinho a cada nova revisão do texto), a comparação usa o SHA-256 do corpo
antigo — o mesmo texto do commit `3118c765` ("admin: publica manual de
experimentação"), a única revisão que este arquivo teve antes desta. Corpo
igual ao hash antigo: troca pelo texto revisado (lido da semente, como a
`0028` já fazia). Corpo diferente — do hash antigo E do texto novo — fica
como está: alguém pode ter escrito por cima, e o gesto de publicar não é
licença para reescrever o que essa pessoa colocou lá.

**Fonte do texto novo.** Lida de `documentos/<nome>.md` no momento do
`migrate`, exatamente como `semear_documento` já faz — não há um segundo
texto vivendo dentro desta migração. Sem a pasta ou sem o arquivo na
imagem, a migração não faz nada (mesma regra de `armadilhas/347`): falhar
aqui derrubaria a célula inteira no `migrate` por um passo de conteúdo.
"""

from __future__ import annotations

import hashlib

from django.db import migrations

from apps.core import documentos

NOME = "plataforma-experimentacao-e-aprendizado-de-conversao"

# SHA-256 do `corpo` exatamente como a migração `0028` o semeou (commit
# `3118c765`, único até aqui). Serve só para decidir se o texto ainda é
# aquele — nunca para reconstituí-lo: reconstituir não é o que esta migração
# faz.
SHA256_CORPO_SEMEADO_PELA_0028 = (
    "5984554032f7a1a2e09e95419065b212e6f016203142823e08a1874f99875630"
)


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def publicar_e_atualizar(apps, schema_editor):
    Documento = apps.get_model("core", "Documento")

    pasta = documentos.diretorio()
    if pasta is None:
        return
    caminho = pasta / f"{NOME}.md"
    if not caminho.is_file():
        return
    campos = documentos.de_texto(NOME, caminho.read_text(encoding="utf-8"))

    documento, criado = Documento.objects.get_or_create(
        nome=NOME,
        defaults={
            "titulo": campos.titulo,
            "publico": True,
            "ordem": campos.ordem,
            "corpo": campos.corpo,
        },
    )
    if criado:
        return

    a_gravar: list[str] = []
    # A decisão do mantenedor é sobre o ESTADO (no ar ou não), qualquer que
    # tenha sido a causa do 404 (linha pré-existente privada, ou arquivada).
    if not documento.publico:
        documento.publico = True
        a_gravar.append("publico")
    if documento.arquivado:
        documento.arquivado = False
        a_gravar.append("arquivado")
    # O CONTEÚDO só troca se ainda for o que a 0028 semeou: casar o hash
    # inteiro é a versão, para um documento reescrito, do "casar o trecho
    # antigo inteiro" de armadilhas/253.
    if (
        documento.corpo != campos.corpo
        and _sha256(documento.corpo) == SHA256_CORPO_SEMEADO_PELA_0028
    ):
        documento.corpo = campos.corpo
        documento.titulo = campos.titulo
        documento.ordem = campos.ordem
        a_gravar.extend(["corpo", "titulo", "ordem"])
    if a_gravar:
        documento.save(update_fields=a_gravar)


def nao_despublica(apps, schema_editor):
    """Descer não tira o manual do ar nem devolve o texto antigo.

    Um `migrate` para trás é coisa que se faz às pressas, num rollback, sem
    ninguém lendo o código; ele não pode revogar em silêncio uma decisão do
    mantenedor nem republicar um texto que já foi substituído.
    """


class Migration(migrations.Migration):
    dependencies = [("core", "0028_semear_plataforma_experimentacao")]
    operations = [migrations.RunPython(publicar_e_atualizar, nao_despublica)]
