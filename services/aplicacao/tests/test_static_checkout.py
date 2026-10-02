from pathlib import Path
import importlib.util


def test_scripts_do_checkout_chegam_ao_modulo_que_os_serve():
    fonte = Path(__file__).resolve().parents[1] / "config" / "registry.py"
    spec = importlib.util.spec_from_file_location("registro_estaticos_checkout", fonte)
    registro = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(registro)
    for caminho in ("/static/checkout/api.js", "/static/checkout/dados.js"):
        assert registro.service_for_path(caminho) == ("checkout", "")
    assert registro.service_for_path("/static/checkout-outro/dados.js") == ("funil", "")
