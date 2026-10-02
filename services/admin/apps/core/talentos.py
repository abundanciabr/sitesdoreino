"""A rede de talentos e suas contagens diárias persistidas no painel."""

from __future__ import annotations

import datetime as dt
import uuid

from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import RegistroDoPlacar
from .mudancas import FRESCOR_PADRAO, foto_em_texto, ler_foto
from .placar import diretorio_dos_cartoes, ler_cartao, montar_o_placar, site_de

#: As três contagens que a escola digita, na ordem em que o laço gira. Cada
#: tupla é `(campo do formulário, nome do cartão, rótulo que o mantenedor lê)`.
#: O nome do cartão é também a chave dentro da linha `foto` do registro, e ele
#: NUNCA aparece em tela: quem o vê são as máquinas. O rótulo existe para que a
#: recusa fale a mesma língua da etiqueta que ele acabou de ler no formulário,
#: e por isso é o próprio formulário que o imprime (`talentos.html` percorre
#: esta tupla; `tests/test_talentos.py` prova que os três chegam à tela).
#:
#: O rótulo dos encaixes conta TRABALHOS, e não pessoas, porque é isso que o
#: cartão `encaixes-com-estudio` define ("a mesma aluna em dois trabalhos conta
#: duas vezes"). O laço mede oportunidades abertas nesta etapa; quem conta
#: pessoas é a etapa seguinte, a dos resultados (`armadilhas/303`).
DIGITADAS = (
    (
        "talentos",
        "alunos-selecionados-para-a-rede",
        "Alunas já selecionadas para a rede",
    ),
    ("estudios", "estudios-parceiros", "Estúdios que já aceitaram receber alunas"),
    (
        "encaixes",
        "encaixes-com-estudio",
        "Trabalhos que alunas já começaram em estúdios",
    ),
)

#: Os seis passos do laço (Scale OS 2 §45). O sétimo é o retorno ao primeiro, e
#: por isso não tem cartão próprio: quem o desenha é a tela.
#:
#: `origem` diz de onde o número daquele passo vem, e é o que decide o estado:
#: `ao-vivo` (a célula `alunos` responde agora), `digitada` (a escola conta e o
#: livro guarda) e `cartao` (quem mede é o placar, e o número chega aqui pela
#: mesma linha `foto` que o placar acabou de montar). Os dois passos `cartao`
#: de hoje não têm fonte nenhuma, e aí quem explica o porquê é o próprio
#: cartão, nunca esta tela.
LACO = (
    {
        "chave": "alunas",
        "titulo": "Mais alunas",
        "porque": "O laço começa na escola cheia: sem alunas não há talento para escolher.",
        "cartao": "alunos-na-plataforma",
        "origem": "ao-vivo",
    },
    {
        "chave": "talentos",
        "titulo": "Mais talentos",
        "porque": "Das alunas, a escola escolhe as que já podem ser apresentadas a um estúdio.",
        "cartao": "alunos-selecionados-para-a-rede",
        "origem": "digitada",
    },
    {
        "chave": "estudios",
        "titulo": "Mais estúdios",
        "porque": "Talento bom atrai estúdio: cada aluna apresentada é a prova que abre a próxima porta.",
        "cartao": "estudios-parceiros",
        "origem": "digitada",
    },
    {
        "chave": "encaixes",
        "titulo": "Mais oportunidades",
        "porque": "Estúdio parceiro só vira oportunidade quando uma aluna de fato começa um trabalho.",
        "cartao": "encaixes-com-estudio",
        "origem": "digitada",
    },
    {
        "chave": "resultados",
        "titulo": "Mais resultados",
        "porque": "O trabalho feito vira resultado profissional da aluna, que é a primeira estrela-guia da escola.",
        "cartao": "alunos-com-resultado-profissional",
        "origem": "cartao",
    },
    {
        "chave": "valor",
        "titulo": "Mais valor da Meshcraft",
        "porque": "Aluna com resultado é a melhor propaganda que existe, e é ela que traz a próxima turma: o laço fecha aqui e recomeça em cima.",
        "cartao": "margem-mensal",
        "origem": "cartao",
    },
)


def _data(texto: object) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(texto)[:10])
    except (TypeError, ValueError):
        return None


def ultima_medicao(registros: list[dict] | None, nome: str) -> dict | None:
    """A contagem mais recente daquele cartão nos registros; `None` se não há nenhuma.

    Olha toda medição com foto, inclusive as contagens anteriores que não
    aparecem na foto mais recente do placar.
    """
    melhor: dict | None = None
    for r in registros or []:
        if r.get("tipo") != "medicao":
            continue
        valores = ler_foto(r.get("foto"))
        dia = _data(r.get("quando"))
        if valores is None or dia is None or nome not in valores:
            continue
        if melhor is None or dia >= melhor["quando"]:
            melhor = {
                "quando": dia,
                "valor": valores[nome],
                "arquivo": r.get("arquivo"),
            }
    return melhor


def montar(
    registros: list[dict] | None,
    total_de_alunos: int | None,
    hoje: dt.date,
    medidos: dict[str, int | float] | None = None,
    pasta=None,
) -> dict:
    """Os seis passos do laço, cada um com o número que a casa tem hoje.

    `total_de_alunos` vem do placar (a célula `alunos` ao vivo) e pode ser
    `None`: a porta não respondeu. `registros` `None` é os registros indisponíveis
    até esta imagem, que é outra coisa de "nenhuma contagem feita", e as duas
    aparecem diferentes na tela (`armadilhas/271`).

    `medidos` é `nome do cartão → valor` do que o placar mediu agora, lido da
    mesma linha `foto` que ele monta. É por ele que os passos de origem
    `cartao` mostram o número em vez de mandar o leitor procurar no placar: o
    degrau 17 prometeu o número AO LADO de cada etapa, e mandar procurar em
    outra tela não é cumprir a promessa. `None` é o placar que não mediu.
    """
    pasta = pasta if pasta is not None else diretorio_dos_cartoes()
    passos = []
    for passo in LACO:
        cartao, problemas = ler_cartao(passo["cartao"], pasta)
        item = {
            **passo,
            "cartao_lido": cartao,
            "problemas": problemas,
            "valor": None,
            "contado_em": None,
            "dias": None,
            "velha": False,
        }
        if cartao is None:
            item["estado"] = "sem-cartao"
        elif passo["origem"] == "ao-vivo":
            item["estado"] = "medido" if total_de_alunos is not None else "nao-medi"
            item["valor"] = total_de_alunos
        elif passo["origem"] == "cartao":
            # Três fatos diferentes, e nenhum deles é zero (`armadilhas/271`):
            # o placar trouxe o número; o cartão tem fonte e o placar não
            # trouxe nada agora; e o cartão não tem fonte nenhuma, caso em que
            # `sem_fonte_porque` é obrigatório no cartão e é ele quem fala.
            valor = (medidos or {}).get(passo["cartao"])
            if valor is not None:
                item["estado"] = "medido"
                item["valor"] = valor
            elif cartao.get("fonte"):
                item["estado"] = "sem-numero-agora"
            else:
                item["estado"] = "sem-fonte"
        elif registros is None:
            item["estado"] = "nao-consigo-olhar"
        else:
            medicao = ultima_medicao(registros, passo["cartao"])
            if medicao is None:
                item["estado"] = "nunca-contado"
            else:
                dias = (hoje - medicao["quando"]).days
                frescor = cartao.get("frescor_maximo") or FRESCOR_PADRAO
                item["estado"] = "medido"
                item["valor"] = medicao["valor"]
                item["contado_em"] = medicao["quando"]
                item["dias"] = dias
                item["velha"] = dias > frescor
        passos.append(item)
    return {
        "passos": passos,
        "livro_ausente": registros is None,
        "nunca_contadas": sum(1 for p in passos if p["estado"] == "nunca-contado"),
    }


def ler_as_contagens(campos) -> tuple[dict[str, int], list[str]]:
    """O que o mantenedor digitou: `cartão → contagem`, e o que foi recusado.

    Campo vazio é campo não digitado (a escola conta uma etapa hoje e outra na
    semana que vem), e não zero: gravar zero por um campo em branco apagaria
    uma contagem verdadeira no painel.
    """
    contagens: dict[str, int] = {}
    recusas: list[str] = []
    for campo, cartao, rotulo in DIGITADAS:
        bruto = str(campos.get(campo, "")).strip()
        if not bruto:
            continue
        try:
            valor = int(bruto)
        except ValueError:
            recusas.append(
                f"Não entendi o campo '{rotulo}': você digitou "
                f"'{bruto}', e ali cabe um número inteiro de 0 para cima."
            )
            continue
        if valor < 0:
            recusas.append(
                f"O campo '{rotulo}' não pode ser negativo: você digitou {valor}."
            )
            continue
        contagens[cartao] = valor
    return contagens, recusas


def salvar_contagem(contagens: dict[str, int], hoje: dt.date, admin: dict,
                    foto_do_placar: str | None) -> None:
    """Acrescenta uma medição histórica; nunca altera uma medição anterior."""
    foto = ler_foto(foto_do_placar) or {}
    foto.update(contagens)
    arquivo = "talentos-" + timezone.now().strftime("%Y%m%d%H%M%S%f") + "-" + uuid.uuid4().hex
    dados = {
        "arquivo": arquivo,
        "tipo": "medicao",
        "quando": hoje.isoformat(),
        "titulo": "Contagem da rede de talentos",
        "detalhe": "Contagem registrada no painel.",
        "foto": foto_em_texto(foto),
        "autoridade": (admin or {}).get("email") or (admin or {}).get("id"),
    }
    RegistroDoPlacar.objects.create(arquivo=arquivo, dados=dados)


@require_http_methods(["GET", "POST"])
def talentos(request):
    hoje = timezone.localdate()
    contexto = montar_o_placar(hoje, site_de(request))
    total = (contexto.get("contagem") or {}).get("total_de_alunos")
    foto_do_placar = (contexto.get("mudancas") or {}).get("foto_de_hoje")
    medidos = ler_foto(foto_do_placar)
    enviados = request.POST if request.method == "POST" else {}
    contagens: dict[str, int] = {}
    recusas: list[str] = []
    if request.method == "POST":
        contagens, recusas = ler_as_contagens(enviados)
        if not recusas and contagens:
            salvar_contagem(contagens, hoje, request.admin, foto_do_placar)
            return redirect(request.path + "?salvo=1")
    return render(
        request,
        "admin/talentos.html",
        {
            "admin": request.admin,
            "laco": montar(contexto["registros"], total, hoje, medidos),
            "digitadas": [
                {"campo": campo, "rotulo": rotulo, "valor": enviados.get(campo, "")}
                for campo, _cartao, rotulo in DIGITADAS
            ],
            "recusas": recusas,
            "salvo": request.GET.get("salvo") == "1",
            "vazio": request.method == "POST" and not recusas and not contagens,
        },
    )
