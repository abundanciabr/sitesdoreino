"""As views da célula `encomendas` (a Fila do Primeiro Dólar).

Duas coisas moram aqui: a sonda do container e a tela mínima do plantão.

**Por que a tela do plantão nasce agora, junto com a porta de máquina.** A lei
§3.6 é literal: o título de Banca ainda não existe como formação, e até existir
*"o título é dado pelo professor, na tela de plantão, com data e autor"*. Sem
título ninguém é elegível a nada (`motor.TITULO_MINIMO_DO_NIVEL`), então a fila,
o Mural e a negociação estão construídos e parados esperando este formulário.
Ele também é quem dá uso real a `apps/core/sessao.py`, e é por isso que
`celulas.yml` pode honestamente passar a `consome: [alunos, identidade]` neste
mesmo PR (`armadilhas/224`): as duas vizinhas são perguntadas aqui, de verdade.

**O que NAO nasce aqui, e o motivo:** abrir encomenda da escola (lei §3.4).
Aquele gesto precisa do briefing com a lista FECHADA de entregáveis, e essa
lista é produto da Fase 3 (o briefing blindado do cliente). Uma encomenda criada
hoje nasceria com a lista vazia, e toda proposta marca um subconjunto dela
([INV-ENC-N1]): o projeto nasceria impossível de negociar. Ele entra no degrau
seguinte, junto com o briefing.

A tela do aluno, o cardápio do cliente e o plantão cheio continuam nas Fases 4,
3 e 7.
"""

from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.core import plantao as porta_do_plantao
from apps.core import sessao
from apps.encomendas.models import PerfilProfissional, Pessoa

# Os recados da tela, por código. O POST redireciona para o GET com o código na
# barra de endereço, e a frase mora aqui: recarregar a página não repete o
# gesto, e nenhum texto vindo de fora entra na URL.
RECADOS = {
    "titulo_dado": "Pronto. O titulo foi registrado com o seu nome e a data de hoje.",
    "sem_email": "Escreva o e-mail do aluno.",
    "titulo_invalido": "Escolha um dos tres niveis.",
    "nao_e_aluno": (
        "Esta pessoa nao esta como aluna da escola agora, entao ela ainda nao "
        "pode entrar na Fila. Confira a matricula dela antes de dar o titulo."
    ),
    "sem_identidade": (
        "Ninguem com esse e-mail entrou no site ainda. Peca a ela para entrar uma "
        "vez e tente de novo."
    ),
    "vizinha_calada": (
        "Nao consegui falar com o cadastro da escola agora. Nada foi gravado: "
        "tente de novo em um minuto."
    ),
}


@require_GET
def healthz(request):
    """A sonda do container. Rota de máquina, nunca de pessoa.

    Ela responde nas DUAS formas de entrada, porque as duas existem em produção:
    `/encomendas/healthz` pela internet (o Traefik **não** remove o prefixo) e
    `/healthz` pelo healthcheck do compose (`armadilhas/029`).

    Guarda: `tests/test_healthz_script_name.py`.
    """
    return JsonResponse({"status": "ok"})


def _quem_esta_de_plantao(request) -> str | None:
    """O id de quem pode agir nesta tela, ou `None`. Fail-closed nos dois passos:
    quem não entrou não é ninguém, e quem entrou e não está na lista também não.
    """
    pessoa_id = sessao.quem_e(request)
    return pessoa_id if porta_do_plantao.e_do_plantao(pessoa_id) else None


def _porta_fechada(request):
    """A mesma resposta para visitante e para quem entrou sem ser do plantão.

    **Uma resposta só, de propósito:** distinguir as duas contaria a um curioso
    que aquela lista existe e quem está nela.
    """
    return render(request, "plantao_fechado.html", status=403)


def _de_volta(codigo: str):
    return HttpResponseRedirect(f"{reverse('plantao')}?recado={codigo}")


@require_GET
def plantao(request):
    """A tela mínima do plantão: dar o título de Banca a um aluno."""
    if _quem_esta_de_plantao(request) is None:
        return _porta_fechada(request)
    codigo = request.GET.get("recado", "")
    return render(
        request,
        "plantao.html",
        {
            "titulos": PerfilProfissional.Titulo.choices,
            "recado": RECADOS.get(codigo),
            # O sucesso é o único recado pintado como boa notícia; os outros
            # cinco são recusas, e pintá-los igual esconderia a diferença.
            "deu_certo": codigo == "titulo_dado",
        },
    )


@require_POST
def dar_titulo(request):
    """O gesto da lei §3.6: o professor é a Banca até a Banca existir.

    A ordem das conferências é a ordem do risco. Primeiro quem está agindo,
    depois o que ele escreveu, e só então as duas perguntas às vizinhas:

    1. **A `alunos` diz se a pessoa é aluna agora.** O título é o que abre a
       Fila, e abri-la para quem não é aluna seria decidir matrícula por aqui.
    2. **A `identidade` traduz o e-mail no id opaco.** O perfil se pendura no id,
       nunca no e-mail, porque e-mail muda de dono.

    **Tropeço de rede não grava nada, e diz isso.** As duas perguntas falham
    fechado de propósito: "não consegui perguntar" lido como "não é aluna"
    recusaria em silêncio um título que o professor acabou de decidir dar.
    """
    autor = _quem_esta_de_plantao(request)
    if autor is None:
        return _porta_fechada(request)

    email = (request.POST.get("email") or "").strip()
    if not email:
        return _de_volta("sem_email")
    titulo = (request.POST.get("titulo") or "").strip()
    if titulo not in PerfilProfissional.Titulo.values:
        return _de_volta("titulo_invalido")

    try:
        if sessao.categoria_na_escola(email) != sessao.CATEGORIA_DE_ALUNO:
            return _de_volta("nao_e_aluno")
        pessoa_id = sessao.pessoa_por_email(email)
        site = sessao.site_desta_instalacao()
    except (sessao.VizinhaIndisponivel, sessao.ConfiguracaoAusente):
        return _de_volta("vizinha_calada")
    if pessoa_id is None:
        return _de_volta("sem_identidade")

    Pessoa.objects.get_or_create(id_da_plataforma=pessoa_id)
    perfil, _ = PerfilProfissional.objects.get_or_create(
        pessoa_id=pessoa_id, site_id=site
    )
    perfil.titulo_banca = titulo
    perfil.titulo_dado_por = autor
    perfil.titulo_dado_em = timezone.now()
    # O banco exige os três juntos (`titulo_de_banca_tem_autor_e_data`): título
    # sem autor é exatamente o que o piloto de papel já não aceita.
    perfil.save(update_fields=["titulo_banca", "titulo_dado_por", "titulo_dado_em"])
    return _de_volta("titulo_dado")
