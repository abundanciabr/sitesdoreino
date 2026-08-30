# tests/test_sincronizar_sites_idioma.py
# O `infra/sincronizar_sites.py` roda no deploy-infra, DENTRO do container do
# catalogo (`manage.py shell -c "$(cat sincronizar_sites.py)"`) — é a última
# barreira antes do banco de PRODUÇÃO. Aqui ele é exercitado do mesmo jeito:
# script inteiro, com SITES_JSON no ambiente, contra o banco de teste.
import json
from pathlib import Path

import pytest

from apps.sites.models import Site

pytestmark = pytest.mark.django_db

# tests/ -> catalogo/ -> services/ -> raiz do repositório
SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "sincronizar_sites.py"
SITES_JSON_REAL = Path(__file__).resolve().parents[3] / "infra" / "sites.json"


def rodar(monkeypatch, dados):
    """Executa o script como o deploy executa: código cru + SITES_JSON."""
    monkeypatch.setenv("SITES_JSON", json.dumps(dados))
    codigo = compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec")
    exec(codigo, {"__name__": "__main__"})


def declaracao(**extra):
    site = {
        "host": "meshcraft.top",
        "name": "Meshcraft",
        "active": True,
        "default_offer_slug": "curso-teste",
        "ofertas": [
            {
                "slug": "curso-teste",
                "price_cents": 990,
                "produto": {"slug": "curso-teste", "name": "Curso de Teste"},
            }
        ],
    }
    site.update(extra)
    return {"sites": [site]}


def test_cria_site_com_os_idiomas_declarados(monkeypatch):
    rodar(
        monkeypatch,
        declaracao(
            default_language="en",
            languages=[
                {"code": "en"},
                {"code": "pt-br"},
                {"code": "es", "indexable": False},
            ],
        ),
    )

    site = Site.objects.get(host="meshcraft.top")
    assert site.default_language == "en"
    assert site.languages == [
        {"code": "en", "indexable": True},
        {"code": "pt-br", "indexable": True},
        {"code": "es", "indexable": False},
    ]


def test_ajusta_idiomas_de_site_que_ja_existe(monkeypatch):
    Site.objects.create(
        host="meshcraft.top", name="Meshcraft", default_offer_slug="curso-teste"
    )  # nasceu monolíngue, como está a produção antes desta fase

    rodar(
        monkeypatch,
        declaracao(
            default_language="en",
            languages=[{"code": "en"}, {"code": "es", "indexable": False}],
        ),
    )

    site = Site.objects.get(host="meshcraft.top")
    assert site.default_language == "en"
    assert site.languages == [
        {"code": "en", "indexable": True},
        {"code": "es", "indexable": False},
    ]


def test_convergencia_e_idempotente(monkeypatch, capsys):
    dados = declaracao(
        default_language="en", languages=[{"code": "en"}, {"code": "pt-br"}]
    )
    rodar(monkeypatch, dados)
    capsys.readouterr()

    rodar(monkeypatch, dados)  # segunda passada: nada mais a ajustar

    # `indexable` normalizado dos dois lados — senão a comparação acusaria
    # "mudou" a cada deploy e o log mentiria sobre convergência.
    assert "já conforme" in capsys.readouterr().out


def test_site_sem_idioma_segue_monolingue(monkeypatch):
    rodar(monkeypatch, declaracao())

    site = Site.objects.get(host="meshcraft.top")
    assert site.default_language == ""
    assert site.languages == []


@pytest.mark.parametrize(
    "extra",
    [
        # default fora da lista
        {"default_language": "de", "languages": [{"code": "en"}]},
        # languages sem default
        {"languages": [{"code": "en"}]},
        # default sem languages
        {"default_language": "en"},
        # code duplicado
        {"default_language": "en", "languages": [{"code": "en"}, {"code": "en"}]},
        # formato errado
        {"default_language": "pt_br", "languages": [{"code": "pt_br"}]},
    ],
)
def test_declaracao_incoerente_reprova_o_deploy_e_nao_grava(monkeypatch, extra):
    with pytest.raises(SystemExit) as saida:
        rodar(monkeypatch, declaracao(**extra))

    mensagem = str(saida.value)
    assert mensagem.startswith("ERRO: idiomas de meshcraft.top incoerentes")
    # Fail-closed de verdade: a transação inteira reverte, nada meio-gravado.
    assert not Site.objects.filter(host="meshcraft.top").exists()


def test_sites_json_do_repositorio_converge_como_declarado(monkeypatch):
    # Não é teste de mentirinha: é o arquivo REAL que o deploy-infra manda para
    # a produção. Se alguém declarar idioma torto lá, isto fica vermelho.
    monkeypatch.setenv("SITES_JSON", SITES_JSON_REAL.read_text(encoding="utf-8"))
    codigo = compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec")
    exec(codigo, {"__name__": "__main__"})

    site = Site.objects.get(host="meshcraft.top")
    # `pt-br` desde 27/08/2026 (commit 388976a, "o padrao do meshcraft.top
    # passa a ser pt-br, raiz nua em portugues"): o `infra/sites.json` mudou e
    # ESTA linha ficou para tras, exigindo "en". Ficou vermelha em silencio por
    # tres dias, porque a suite do `catalogo` so roda quando um PR toca a
    # celula, e nenhum tocou. Achada em 30/08/2026 por um PR de outro assunto.
    #
    # As asserçoes iguais mais acima NAO mudam: aquelas leem uma declaraçao
    # sintetica do proprio teste, nao o arquivo real da produçao.
    assert site.default_language == "pt-br"
    assert site.languages == [
        {"code": "en", "indexable": True},
        {"code": "pt-br", "indexable": True},
        {"code": "es", "indexable": False},  # D5: o es NASCE noindex
    ]
