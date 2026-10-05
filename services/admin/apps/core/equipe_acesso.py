"""Acesso da equipe por link (01/10/2026): o aparelho ligado direto à pessoa.

Pedido do mantenedor: o link conecta o aparelho à pessoa que JÁ existe na
equipe (`MembroDaEquipe`), com as tarefas e o histórico dela, antes de ela
preencher qualquer cadastro. O vínculo é pelo identificador interno da
pessoa; e-mail e senha vêm depois, em "Meu perfil", e só complementam a
entrada: trocar o e-mail não muda quem responde pelo trabalho.

## As três peças

| Peça                | O que é                                                    |
|---------------------|------------------------------------------------------------|
| `MembroDaEquipe`    | A pessoa, com tarefas e responsabilidades, mesmo sem e-mail |
| `LinkDeAcesso`      | O convite para conectar UM aparelho àquela pessoa          |
| `AparelhoDaEquipe`  | O vínculo entre um navegador e a pessoa; desconecta sozinho |

## Como anda

1. Na ficha do Ryan (`/equipe/pessoas/<id>`), o mantenedor gera o link:
   `https://meshcraft.top/admin/equipe/magic-link?client=desktop_app#<código>:<base64>`.
2. Ryan abre no computador e cai nas tarefas dele: o navegador troca o
   código por uma credencial própria (cookie `HttpOnly`, `Secure`,
   `SameSite=Lax`), que se renova enquanto ele usa.
3. Do computador conectado, "Conectar meu celular" gera outro link, com QR
   code, para a mesma pessoa. Cada navegador tem a sua credencial, e a ficha
   desconecta um aparelho perdido sem mexer nos outros.
4. Retirar a pessoa da equipe encerra todos os aparelhos e guarda o
   histórico inteiro.

## O formato do link

* `client` diz para que aparelho o link foi feito: `desktop_app` (o que o
  mantenedor gera) ou `mobile_app` (o de "Conectar meu celular").
* Depois do `#` vem `<código>:<dados>`. O CÓDIGO (32 caracteres) é a única
  parte secreta, e é só ela que o servidor confere. Os DADOS são o e-mail da
  pessoa, em base64, ou o nome dela enquanto não houver e-mail: servem para a
  página dizer "conectando como Ryan", e o servidor não confia neles.
* Tudo o que vem depois do `#` o navegador nunca manda ao servidor: não fica
  em log, nem na pré-visualização que o WhatsApp busca do link.

## Por que cada regra é assim

* **Vale uma vez.** Depois de usado, copiar o link não abre nada. Antes de
  usado, quem tiver o link entra: ele é a credencial, por isso tem prazo
  (7 dias o do mantenedor; 30 minutos o "Conectar meu celular", que é usado
  na hora) e gerar outro cancela o anterior da mesma origem.
* **Abriu, entrou.** A página lê o código e entra sozinha, sem botão.
* **O banco guarda hash, nunca o código nem a credencial.**
* **Desconectar e retirar não apagam nada.** Marcam a hora; a porta deixa de
  aceitar.
* **E-mail escrito pela própria pessoa não abre a conta Google dele** até o
  mantenedor conferir na ficha (`email_a_conferir`): digitar o e-mail de
  outra pessoa não pode entregar o painel a ela.

Quem entra por aparelho recebe o mesmo crachá de equipe da conta associada
por e-mail: só `/equipe/`. O resto da área continua respondendo 404.
"""

from __future__ import annotations

import base64
import functools
import hashlib
import logging
import re
import secrets
from datetime import timedelta
from urllib.parse import quote

import segno
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError
from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .equipe import RESULTADOS, _com_resultado, _membro_da_sessao, _nao_existe, _quem
from .models import AparelhoDaEquipe, LinkDeAcesso, MembroDaEquipe

logger = logging.getLogger("admin.equipe")

Origem = LinkDeAcesso.Origem

COOKIE_DO_APARELHO = "admin_equipe_aparelho"
# 400 dias é o teto que os navegadores aceitam para um cookie. Ele se renova a
# cada dia de uso: é isso que faz o acesso ficar, na prática, permanente.
DURACAO_DO_APARELHO = timedelta(days=400)
RENOVAR_DEPOIS_DE = timedelta(days=1)
VALIDADE = {
    Origem.MANTENEDOR: timedelta(days=7),
    Origem.PROPRIO: timedelta(minutes=30),
}
CLIENTE = {Origem.MANTENEDOR: "desktop_app", Origem.PROPRIO: "mobile_app"}
TIPO_DO_CLIENTE = {"desktop_app": "computador", "mobile_app": "celular"}
TENTATIVAS_DE_SENHA = 5
TRAVA_DA_SENHA = timedelta(minutes=15)
TAMANHO_MINIMO_DA_SENHA = 8


@functools.cache
def _senha_de_ninguem() -> str:
    """Um hash de verdade que ninguém conhece, para que e-mail desconhecido
    gaste o mesmo tempo que senha errada: o tempo da resposta não pode dizer
    quem é da equipe. (`make_password(None)` não serve: o Django recusa esse
    na hora, sem calcular nada.)"""
    return make_password(secrets.token_hex(16))


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def _caminho_do_cookie() -> str:
    # A credencial só viaja para o painel da equipe: o prefixo dele, com o
    # `/admin` na frente quando a célula roda sob ele.
    return reverse("painel_da_equipe")


def _destino_de_volta(cru: str) -> str:
    """O `next` de quem entrou, só se for um endereço do próprio painel."""
    base = reverse("painel_da_equipe")
    if cru.startswith(base) and not any(c in cru for c in ("//", "\\", "\n", "\r")):
        return cru
    return base


# ---------------------------------------------------------------- o aparelho


def aparelho_da_requisicao(request) -> AparelhoDaEquipe | None:
    """O aparelho conectado que este navegador apresenta, se ainda vale.

    Usado pela porta. Banco fora ⇒ nenhum: erro nunca vira permissão.
    """
    chave = request.COOKIES.get(COOKIE_DO_APARELHO)
    if not chave:
        return None
    try:
        aparelho = (
            AparelhoDaEquipe.objects.select_related("membro")
            .filter(
                chave_hash=_hash(chave),
                desconectado_em__isnull=True,
                membro__ativo=True,
            )
            .first()
        )
        if aparelho is None:
            return None
        agora = timezone.now()
        aparelho.renovar = agora - aparelho.ultimo_uso_em > RENOVAR_DEPOIS_DE
        if aparelho.renovar:
            AparelhoDaEquipe.objects.filter(pk=aparelho.pk).update(ultimo_uso_em=agora)
        aparelho.chave = chave
        return aparelho
    except DatabaseError:
        logger.error("porta: não deu para ler os aparelhos da equipe do banco")
        return None


def gravar_cookie_do_aparelho(resposta, chave: str) -> None:
    resposta.set_cookie(
        COOKIE_DO_APARELHO,
        chave,
        max_age=int(DURACAO_DO_APARELHO.total_seconds()),
        httponly=True,
        secure=settings.CSRF_COOKIE_SECURE,
        samesite="Lax",
        path=_caminho_do_cookie(),
    )


def _conectar(request, membro: MembroDaEquipe, como: str, tipo: str, destino: str):
    """Cria o aparelho, grava a credencial no navegador e leva ao painel."""
    chave = secrets.token_urlsafe(32)
    if not tipo:
        agente = request.META.get("HTTP_USER_AGENT", "")
        tipo = "celular" if "Mobi" in agente else "computador"
    AparelhoDaEquipe.objects.create(
        membro=membro,
        chave_hash=_hash(chave),
        como_entrou=como,
        tipo=tipo,
        ultimo_uso_em=timezone.now(),
    )
    resposta = _com_resultado(destino, "aparelho_conectado")
    gravar_cookie_do_aparelho(resposta, chave)
    return resposta


# ---------------------------------------------------------------- o link


def _dados_do_link(membro: MembroDaEquipe) -> str:
    """O que vai depois dos dois-pontos: o e-mail, ou o nome, em base64."""
    quem = membro.email or membro.nome
    return base64.urlsafe_b64encode(quem.encode()).decode().rstrip("=")


def _gerar_link(request, membro: MembroDaEquipe, origem: str) -> dict:
    """Cancela o link ainda não usado da mesma origem e cria outro. Devolve o
    endereço completo, que só existe nesta resposta."""
    agora = timezone.now()
    LinkDeAcesso.objects.filter(
        membro=membro, origem=origem, usado_em__isnull=True, cancelado_em__isnull=True
    ).update(cancelado_em=agora)
    codigo = secrets.token_hex(16)
    link = LinkDeAcesso.objects.create(
        membro=membro,
        origem=origem,
        codigo_hash=_hash(codigo),
        criado_por=_quem(request),
        expira_em=agora + VALIDADE[origem],
    )
    endereco = (
        request.build_absolute_uri(reverse("magic_link"))
        + f"?client={CLIENTE[origem]}#{codigo}:{_dados_do_link(membro)}"
    )
    qr = segno.make(endereco, error="m").svg_inline(
        scale=4, dark="#000", light="#fff", border=4
    )
    return {"endereco": endereco, "link": link, "qr": mark_safe(qr)}


_SCRIPT_EMBUTIDO = re.compile(
    rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
)


def _com_csp_do_script(resposta):
    """A página do link é a única desta área com script: ele lê o que vem
    depois do `#`. O CSP libera exatamente aqueles bytes, por hash, e mantém o
    hash do estilo da casa — o mesmo desenho de `livro.py`."""
    from .porta import PortaAdministrativa

    scripts = "".join(
        " 'sha256-"
        + base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode()
        + "'"
        for m in _SCRIPT_EMBUTIDO.finditer(resposta.content)
    )
    resposta["Content-Security-Policy"] = (
        f"default-src 'self'; script-src 'self'{scripts}; "
        f"style-src 'self'{PortaAdministrativa.hashes_de_estilo(resposta)}; "
        "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'self'"
    )
    return resposta


@require_http_methods(["GET", "POST"])
def magic_link(request):
    """A página que o link abre. Sem crachá: o crachá é o que ela entrega."""
    cliente = (request.GET.get("client") or "").strip()
    if request.method == "GET":
        return _com_csp_do_script(
            render(request, "admin/equipe_magic_link.html", {"recusado": False})
        )

    codigo = (request.POST.get("codigo") or "").strip().lower()
    agora = timezone.now()
    link = (
        LinkDeAcesso.objects.select_related("membro")
        .filter(codigo_hash=_hash(codigo))
        .first()
        if codigo
        else None
    )
    # Reabrir o convite no aparelho que já entrou não é uma nova conexão.
    # A credencial do aparelho, e não o código já usado, autoriza a volta.
    if link and link.usado_em and not link.cancelado_em and link.membro.ativo:
        aparelho = aparelho_da_requisicao(request)
        if aparelho and aparelho.membro_id == link.membro_id:
            return HttpResponseRedirect(reverse("painel_da_equipe") + "?visao=minhas")
    # Usar é um UPDATE condicional: dois navegadores abrindo o mesmo link ao
    # mesmo tempo, só um muda a linha, e só ele entra.
    usado = (
        link is not None
        and LinkDeAcesso.objects.filter(
            pk=link.pk,
            usado_em__isnull=True,
            cancelado_em__isnull=True,
            expira_em__gt=agora,
            membro__ativo=True,
        ).update(usado_em=agora)
        == 1
    )
    if not usado:
        if link and link.cancelado_em:
            motivo = "Foi gerado outro link para esta pessoa ou este acesso foi cancelado. Use o link mais recente."
        elif link and link.usado_em:
            motivo = "Este link já conectou um aparelho. Nesse aparelho, abra o painel; para conectar outro, peça um novo link."
        elif link and link.expira_em <= agora:
            motivo = "O prazo deste link terminou. Peça um novo link."
        else:
            motivo = "O link está incompleto, não foi reconhecido ou a pessoa não está mais ativa na equipe. Peça um novo link."
        return _com_csp_do_script(
            render(
                request,
                "admin/equipe_magic_link.html",
                {"recusado": True, "motivo": motivo},
                status=400,
            )
        )
    return _conectar(
        request,
        link.membro,
        "link",
        TIPO_DO_CLIENTE.get(cliente, ""),
        reverse("painel_da_equipe") + "?visao=minhas",
    )


# ---------------------------------------------------------------- e-mail e senha


def _tela_de_entrar(request, destino, erro="", email="", status=200):
    return render(
        request,
        "admin/equipe_entrar.html",
        {
            "destino": destino,
            "erro": erro,
            "email": email,
            "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
            "entrar_com_google": (
                f"{settings.URL_DE_ENTRADA}?next={quote(destino, safe='/')}"
            ),
        },
        status=status,
    )


@require_http_methods(["GET", "POST"])
def entrar_na_equipe(request):
    """Entrar sem link: com o e-mail e a senha escolhidos em Meu perfil, ou
    com a conta Google, que é como o mantenedor entra."""
    destino = _destino_de_volta(
        request.POST.get("next") or request.GET.get("next") or ""
    )
    if request.method == "GET":
        return _tela_de_entrar(request, destino)

    email = (request.POST.get("email") or "").strip().lower()[:254]
    senha = request.POST.get("senha") or ""
    agora = timezone.now()
    membro = (
        MembroDaEquipe.objects.filter(ativo=True, email=email).first()
        if email
        else None
    )
    if membro and membro.senha_travada_ate and membro.senha_travada_ate > agora:
        return _tela_de_entrar(
            request,
            destino,
            "Muitas tentativas erradas para este e-mail. Espere 15 minutos e "
            "tente de novo.",
            email,
            status=429,
        )
    certa = check_password(
        senha, membro.senha if membro and membro.senha else _senha_de_ninguem()
    )
    if not (membro and membro.senha and certa):
        if membro:
            MembroDaEquipe.objects.filter(pk=membro.pk).update(
                erros_de_senha=F("erros_de_senha") + 1
            )
            membro.refresh_from_db(fields=["erros_de_senha"])
            if membro.erros_de_senha >= TENTATIVAS_DE_SENHA:
                MembroDaEquipe.objects.filter(pk=membro.pk).update(
                    erros_de_senha=0, senha_travada_ate=agora + TRAVA_DA_SENHA
                )
        return _tela_de_entrar(
            request, destino, "E-mail ou senha não conferem.", email, status=400
        )
    MembroDaEquipe.objects.filter(pk=membro.pk).update(
        erros_de_senha=0, senha_travada_ate=None
    )
    return _conectar(request, membro, "senha", "", destino)


@require_POST
def sair_da_equipe(request):
    """Desconecta ESTE aparelho. Os outros aparelhos da pessoa continuam."""
    aparelho_id = request.admin.get("aparelho_id")
    if aparelho_id:
        AparelhoDaEquipe.objects.filter(pk=aparelho_id).update(
            desconectado_em=timezone.now()
        )
    resposta = HttpResponseRedirect(reverse("entrar_na_equipe") + "?resultado=saiu")
    resposta.delete_cookie(COOKIE_DO_APARELHO, path=_caminho_do_cookie())
    return resposta


# ---------------------------------------------------------------- meu perfil


def _tela_do_perfil(request, membro, dados, erros, status=200):
    return render(
        request,
        "admin/equipe_perfil.html",
        {
            "admin": request.admin,
            "membro": membro,
            "dados": dados,
            "erros": erros,
            "aparelhos": (
                list(membro.aparelhos.filter(desconectado_em__isnull=True))
                if membro
                else []
            ),
            "aparelho_atual": request.admin.get("aparelho_id"),
            "tamanho_minimo": TAMANHO_MINIMO_DA_SENHA,
            "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
        },
        status=status,
    )


@require_http_methods(["GET", "POST"])
def meu_perfil(request):
    """Nome, e-mail e senha da própria pessoa. Complementam a entrada; a
    pessoa, as tarefas e o histórico continuam os mesmos."""
    membro = _membro_da_sessao(request)
    if request.method == "GET" or membro is None:
        dados = {
            "nome": membro.nome if membro else "",
            "email": membro.email if membro else "",
        }
        return _tela_do_perfil(request, membro, dados, [])

    dados = {
        "nome": (request.POST.get("nome") or "").strip()[:80],
        "email": (request.POST.get("email") or "").strip().lower()[:254],
    }
    senha = request.POST.get("senha") or ""
    confirmacao = request.POST.get("confirmacao") or ""
    erros = []
    if not dados["nome"]:
        erros.append("Escreva o seu nome: é ele que aparece nas tarefas.")
    if dados["email"]:
        try:
            validate_email(dados["email"])
        except ValidationError:
            erros.append("Esse e-mail não parece um e-mail.")
        else:
            if (
                MembroDaEquipe.objects.filter(email=dados["email"])
                .exclude(pk=membro.pk)
                .exists()
            ):
                erros.append("Esse e-mail já é de outra pessoa da equipe.")
    if senha or confirmacao:
        if len(senha) < TAMANHO_MINIMO_DA_SENHA:
            erros.append(
                f"A senha precisa de pelo menos {TAMANHO_MINIMO_DA_SENHA} letras."
            )
        elif senha != confirmacao:
            erros.append("A senha e a confirmação não são iguais.")
    if (senha or membro.senha) and not dados["email"]:
        erros.append("Para entrar com senha, informe também o e-mail.")
    if erros:
        return _tela_do_perfil(request, membro, dados, erros, status=400)

    if dados["email"] != membro.email:
        # E-mail novo escrito pela própria pessoa: serve para entrar com senha,
        # mas só abre a conta Google depois que o mantenedor conferir.
        membro.email_a_conferir = bool(dados["email"])
    membro.nome = dados["nome"]
    membro.email = dados["email"]
    campos = ["nome", "email", "email_a_conferir"]
    if senha:
        membro.senha = make_password(senha)
        membro.erros_de_senha = 0
        membro.senha_travada_ate = None
        campos += ["senha", "erros_de_senha", "senha_travada_ate"]
    membro.save(update_fields=campos)
    return _com_resultado(reverse("meu_perfil"), "perfil_salvo")


@require_POST
def conectar_meu_celular(request):
    """Do aparelho já conectado, um link (e QR code) para outro aparelho da
    MESMA pessoa. Cada navegador recebe a própria credencial."""
    membro = _membro_da_sessao(request)
    if membro is None:
        return _nao_existe(request)
    gerado = _gerar_link(request, membro, Origem.PROPRIO)
    return render(
        request,
        "admin/equipe_link.html",
        {"admin": request.admin, "pessoa": membro, "para_si": True, **gerado},
    )


# ---------------------------------------------------------------- a ficha


def _so_administrador(request):
    return not request.admin.get("equipe_apenas")


@require_GET
def ficha_da_pessoa(request, id: int):
    """A ficha de uma pessoa: conta, aparelhos, link e se ainda é da equipe.
    Só do administrador, como a lista de pessoas."""
    if not _so_administrador(request):
        return _nao_existe(request)
    pessoa = get_object_or_404(MembroDaEquipe, pk=id)
    agora = timezone.now()
    return render(
        request,
        "admin/equipe_pessoa.html",
        {
            "admin": request.admin,
            "pessoa": pessoa,
            "aparelhos": list(pessoa.aparelhos.filter(desconectado_em__isnull=True)),
            "links_pendentes": list(
                pessoa.links.filter(
                    usado_em__isnull=True,
                    cancelado_em__isnull=True,
                    expira_em__gt=agora,
                )
            ),
            "tarefas_abertas": pessoa.tarefas.exclude(situacao="concluida").count(),
            "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
        },
    )


@require_POST
def ficha_gerar_link(request, id: int):
    """O mantenedor gera o link do aparelho da pessoa."""
    if not _so_administrador(request):
        return _nao_existe(request)
    pessoa = get_object_or_404(MembroDaEquipe, pk=id, ativo=True)
    gerado = _gerar_link(request, pessoa, Origem.MANTENEDOR)
    return _com_csp_do_script(
        render(
            request,
            "admin/equipe_link.html",
            {"admin": request.admin, "pessoa": pessoa, "para_si": False, **gerado},
        )
    )


@require_POST
def ficha_desconectar(request, id: int):
    """Desconecta UM aparelho (o perdido), ou todos, com o link pendente."""
    if not _so_administrador(request):
        return _nao_existe(request)
    pessoa = get_object_or_404(MembroDaEquipe, pk=id)
    agora = timezone.now()
    ficha = reverse("ficha_da_pessoa", args=[pessoa.id])
    aparelho = request.POST.get("aparelho") or ""
    if aparelho == "todos":
        pessoa.aparelhos.filter(desconectado_em__isnull=True).update(
            desconectado_em=agora
        )
        pessoa.links.filter(usado_em__isnull=True, cancelado_em__isnull=True).update(
            cancelado_em=agora
        )
        return _com_resultado(ficha, "aparelhos_desconectados")
    if aparelho.isdigit():
        pessoa.aparelhos.filter(pk=int(aparelho), desconectado_em__isnull=True).update(
            desconectado_em=agora
        )
    return _com_resultado(ficha, "aparelho_desconectado")


@require_POST
def ficha_ativo(request, id: int):
    """Retirar da equipe (ou trazer de volta). Retirar encerra todos os
    aparelhos e links, e guarda tarefas, comentários e compromissos."""
    if not _so_administrador(request):
        return _nao_existe(request)
    pessoa = get_object_or_404(MembroDaEquipe, pk=id)
    ficha = reverse("ficha_da_pessoa", args=[pessoa.id])
    if request.POST.get("ativo") == "1":
        pessoa.ativo = True
        pessoa.save(update_fields=["ativo"])
        return _com_resultado(ficha, "pessoa_de_volta")
    agora = timezone.now()
    pessoa.ativo = False
    pessoa.save(update_fields=["ativo"])
    pessoa.aparelhos.filter(desconectado_em__isnull=True).update(desconectado_em=agora)
    pessoa.links.filter(usado_em__isnull=True, cancelado_em__isnull=True).update(
        cancelado_em=agora
    )
    return _com_resultado(ficha, "pessoa_retirada")
