"""Materializa os projetos Django existentes com nomes exclusivos.

Os fontes em ``services/<modulo>`` continuam sendo a fonte de verdade. Esta
transformacao acontece na imagem, para que todos os apps possam compartilhar um
unico registry Django sem disputar ``apps.core`` e ``config``.
"""

from __future__ import annotations

import ast
import argparse
from pathlib import Path
import re
import shutil


MODULOS = (
    "admin", "alunos", "catalogo", "checkout", "cursos", "encomendas",
    "forum", "funil", "gamificacao", "identidade", "leads", "mensageria",
    "metricas", "notificacoes", "pagamentos", "pages", "quiz", "sugestoes",
)
IGNORAR = {"tests", "vendor", "staticfiles", "__pycache__", ".pytest_cache", ".venv"}


def _classe_app_config(caminho: Path) -> str | None:
    if not caminho.exists():
        return None
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    for no in arvore.body:
        if isinstance(no, ast.ClassDef) and any(
            isinstance(base, ast.Name) and base.id == "AppConfig"
            or isinstance(base, ast.Attribute) and base.attr == "AppConfig"
            for base in no.bases
        ):
            return no.name
    return None


def _reescrever(codigo: str, modulo: str, apps_locais: set[str],
               config_locais: set[str]) -> str:
    # Caminhos de importacao aparecem em codigo e em strings de configuracao.
    # `apps.get_model()` e a API do registry Django, usada por migrations;
    # apenas nomes de pacotes locais podem ser qualificados aqui.
    if apps_locais:
        nomes = "|".join(re.escape(app) for app in sorted(apps_locais, key=len, reverse=True))
        codigo = re.sub(rf"(?<![\w.])apps\.(?=(?:{nomes})\b)",
                        f"modules.{modulo}.apps.", codigo)
    if config_locais:
        nomes = "|".join(re.escape(nome) for nome in sorted(config_locais, key=len, reverse=True))
        codigo = re.sub(rf"(?<![\w.])config\.(?=(?:{nomes})\b)",
                        f"modules.{modulo}.config.", codigo)
    if modulo == "pagamentos":
        codigo = re.sub(r"(?<![\w.])pagamentos\.",
                        "modules.pagamentos.pagamentos.", codigo)
    codigo = re.sub(r"(?m)^(\s*from\s+)apps(\s+import\s+)",
                    rf"\1modules.{modulo}.apps\2", codigo)
    codigo = re.sub(r"(?m)^(\s*from\s+)config(\s+import\s+)",
                    rf"\1modules.{modulo}.config\2", codigo)
    for app in sorted(apps_locais, key=len, reverse=True):
        # Relacoes ORM em strings, inclusive migrations, usam app_label.Model.
        codigo = re.sub(rf"(?<![\w.]){re.escape(app)}\.([A-Z][A-Za-z0-9_]*)",
                        rf"{modulo}_{app}.\1", codigo)
        # Django serializa referencias de FK em minusculas nas migrations.
        codigo = re.sub(
            rf"(\b(?:to|through)\s*=\s*[\"']){re.escape(app)}\.",
            rf"\1{modulo}_{app}.", codigo,
        )
        # Grafo de migrations: ('core', '0001_initial').
        codigo = re.sub(
            rf"([\"']){re.escape(app)}\1(?=\s*,\s*[\"']\d{{4}})",
            lambda m: m.group(1) + f"{modulo}_{app}" + m.group(1), codigo,
        )
        # apps.get_model('core', 'Modelo').
        codigo = re.sub(
            rf"(get_model\(\s*)([\"']){re.escape(app)}\2",
            lambda m: m.group(1) + m.group(2) + f"{modulo}_{app}" + m.group(2),
            codigo,
        )
    return codigo


def _tem_opcao(meta: ast.ClassDef, nome: str) -> bool:
    return any(
        isinstance(no, (ast.Assign, ast.AnnAssign))
        and any(isinstance(alvo, ast.Name) and alvo.id == nome
                for alvo in (no.targets if isinstance(no, ast.Assign) else [no.target]))
        for no in meta.body
    )


def _preservar_tabelas_modelos(codigo: str, app: str) -> str:
    arvore = ast.parse(codigo)
    alterado = False
    classes = {no.name: no for no in arvore.body if isinstance(no, ast.ClassDef)}
    modelos = {
        no.name for no in classes.values()
        if any(isinstance(base, ast.Attribute) and base.attr == "Model"
               for base in no.bases)
    }
    # A concrete model can inherit an abstract Model declared in this file.
    # Django still derives its table from the original (unprefixed) app label.
    while True:
        derivados = {
            no.name for no in classes.values()
            if any(isinstance(base, ast.Name) and base.id in modelos
                   for base in no.bases)
        }
        if derivados <= modelos:
            break
        modelos |= derivados
    for classe in arvore.body:
        if not isinstance(classe, ast.ClassDef):
            continue
        if classe.name not in modelos:
            continue
        meta = next((no for no in classe.body
                     if isinstance(no, ast.ClassDef) and no.name == "Meta"), None)
        if meta and (_tem_opcao(meta, "db_table") or _tem_opcao(meta, "abstract")
                     or _tem_opcao(meta, "proxy")):
            continue
        tabela = f"{app}_{classe.name.lower()}"
        atribuicao = ast.Assign(targets=[ast.Name(id="db_table", ctx=ast.Store())],
                                value=ast.Constant(tabela))
        if meta:
            meta.body.append(atribuicao)
        else:
            classe.body.append(ast.ClassDef(name="Meta", bases=[], keywords=[],
                                            body=[atribuicao], decorator_list=[]))
        alterado = True
    return ast.unparse(ast.fix_missing_locations(arvore)) + "\n" if alterado else codigo


def _preservar_tabelas_migracoes(codigo: str, app: str) -> str:
    # Uma migracao legada consultava o alias global `default` para detectar o
    # dialeto. No registry unico, o alias correto e o do schema_editor.
    codigo = re.sub(r"(?<!schema_editor\.)\bconnection\.vendor\b",
                    "schema_editor.connection.vendor", codigo)
    arvore = ast.parse(codigo)
    alterado = False
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        nome_funcao = no.func.attr if isinstance(no.func, ast.Attribute) else (
            no.func.id if isinstance(no.func, ast.Name) else "")
        if nome_funcao != "CreateModel":
            continue
        nome = next((kw.value.value for kw in no.keywords
                     if kw.arg == "name" and isinstance(kw.value, ast.Constant)
                     and isinstance(kw.value.value, str)), None)
        if not nome:
            continue
        opcoes = next((kw for kw in no.keywords if kw.arg == "options"), None)
        if opcoes and isinstance(opcoes.value, ast.Dict):
            chaves = [k.value for k in opcoes.value.keys if isinstance(k, ast.Constant)]
            if any(chave in chaves for chave in ("db_table", "abstract", "proxy")):
                continue
            opcoes.value.keys.append(ast.Constant("db_table"))
            opcoes.value.values.append(ast.Constant(f"{app}_{nome.lower()}"))
        elif opcoes is None:
            no.keywords.append(ast.keyword(
                arg="options", value=ast.Dict(keys=[ast.Constant("db_table")],
                                               values=[ast.Constant(f"{app}_{nome.lower()}")]),
            ))
        else:
            continue
        alterado = True
    return ast.unparse(ast.fix_missing_locations(arvore)) + "\n" if alterado else codigo


def preparar(origem: Path, destino: Path) -> None:
    origem = origem.resolve()
    destino = destino.resolve()
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "__init__.py").touch()
    for modulo in MODULOS:
        fonte = origem / modulo
        if not (fonte / "config" / "settings.py").is_file():
            raise FileNotFoundError(f"projeto Django ausente: {fonte}")
        alvo = destino / modulo
        if alvo.exists():
            shutil.rmtree(alvo)
        shutil.copytree(
            fonte, alvo,
            ignore=lambda _p, nomes: set(nomes) & IGNORAR,
        )
        (alvo / "__init__.py").touch()
        raiz_apps = alvo / ("pagamentos" if modulo == "pagamentos" else "apps")
        apps = {p.name for p in raiz_apps.iterdir() if p.is_dir()}
        config = {p.stem for p in (alvo / "config").glob("*.py")}
        for arquivo in alvo.rglob("*.py"):
            codigo = arquivo.read_text(encoding="utf-8")
            novo = _reescrever(codigo, modulo, apps, config)
            for app in apps:
                pasta_app = raiz_apps / app
                if arquivo == pasta_app / "models.py":
                    novo = _preservar_tabelas_modelos(novo, app)
                elif pasta_app / "migrations" in arquivo.parents:
                    novo = _preservar_tabelas_migracoes(novo, app)
            if novo != codigo:
                arquivo.write_text(novo, encoding="utf-8")
        for app in sorted(apps):
            pacote = raiz_apps / app
            classe = _classe_app_config(pacote / "apps.py")
            if classe:
                heranca = f"from .apps import {classe}\n\nclass UnifiedConfig({classe}):"
            else:
                heranca = "from django.apps import AppConfig\n\nclass UnifiedConfig(AppConfig):"
            (pacote / "unified_config.py").write_text(
                f"{heranca}\n"
                f"    name = 'modules.{modulo}.{'pagamentos' if modulo == 'pagamentos' else 'apps'}.{app}'\n"
                f"    label = '{modulo}_{app}'\n\n"
                f"    def import_models(self):\n"
                f"        from config.runtime import load_original_settings, install_contextual_settings, serving\n"
                f"        load_original_settings()\n"
                f"        install_contextual_settings()\n"
                f"        with serving('{modulo}'):\n"
                f"            return super().import_models()\n\n"
                f"    def ready(self):\n"
                f"        from config.runtime import serving\n"
                f"        with serving('{modulo}'):\n"
                f"            return super().ready()\n",
                encoding="utf-8",
            )
    documentos = origem.parent / "documentos"
    if documentos.is_dir():
        shutil.copytree(documentos, destino / "admin" / "documentos_embutidos",
                        dirs_exist_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--origem", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--destino", type=Path, default=Path("/app/modules"))
    args = parser.parse_args()
    preparar(args.origem, args.destino)
