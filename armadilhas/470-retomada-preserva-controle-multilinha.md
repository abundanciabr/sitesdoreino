---
schema_version: 2
armadilha: 470
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: medio
gatilho:
  - services/admin/apps/core/templates/admin/caixa_robos.html
guarda:
  tipo: CI
  dono: services/admin/tests/test_tela_de_trabalho_dos_robos.py
  detector: test_motivo_multilinha_sobrevive_ao_formulario_e_a_retomada
  motivo: repetir o formulario nao pode alterar o motivo persistido
licao: Um motivo aceito em textarea precisa continuar multilinha em toda retomada. Input de texto remove CR/LF mesmo quando o HTML conserva os caracteres no atributo value. A prova deve reenviar os controles renderizados, nao apenas conferir o contexto da view.
---

# 470: O controle de retomada faz parte da identidade do pedido

## Sintoma

Depois de um timeout, repetir um cancelamento com motivo multilinha produzia
conflito com o evento já persistido. A tela conservava o texto no HTML, mas o
input de linha única retirava suas quebras antes do reenvio.

## Correção e prova

O diálogo usa textarea, como o ramo de fila ausente. A regressão atravessa
POST com resposta perdida após persistir, reenvio dos controles renderizados,
consulta posterior e nova repetição. Modela a remoção de CR/LF do input e a
serialização CRLF do formulário. Exige motivo e bytes idênticos, um evento,
um PR e somente leituras depois do primeiro efeito. Texto com aspas, entidades
HTML e linha vazia também atravessa o percurso.

O teste reprovou com conflito antes da correção e passou com textarea.
Restaurar o input na mutação reproduziu o mesmo conflito.
