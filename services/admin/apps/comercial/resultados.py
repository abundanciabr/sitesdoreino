"""A análise de resultados: o trabalho `analisar_resultados` (de hora em hora).

Toda a lógica mora em `otimizador.py` — medir por versão, quiz, campanha e
oferta, propor, testar uma fatia, concluir e voltar à versão anterior. Este
módulo guarda os nomes que o coordenador e a tela já usam.
"""

from __future__ import annotations

from .otimizador import MIN_AMOSTRA, analisar as executar, numeros, z_de_duas_proporcoes  # noqa: F401
