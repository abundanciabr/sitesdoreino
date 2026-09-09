---
schema_version: 2
armadilha: 444
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/encerramento_alertas.py
gatilho:
  - painel/registros/*
licao: conclusão verde que cita PR de entrega em alerta precisa embarcar baixa explícita, verde e comprovada, com responde_a escalar; o relato de sucesso sozinho não encerra o alerta.
---

# O conserto terminou, mas a conclusão não deu baixa no alerta

Em 09/09/2026, os PRs #1472 e #1474 já estavam incorporados e o run
34307380203 terminou com sucesso. O registro 20260909-041 documentou a
publicação e a conferência pública, mas não respondeu às entregas 037 e 039.
As duas continuaram âmbar no painel, apesar da tarefa relatada como PRONTO.

A cor âmbar cria um estado aberto; não é decoração de um acontecimento.
O painel calcula a baixa por `responde_a`, sem interpretar prosa sobre
sucesso. Escrever a medição verde sem esse vínculo deixa a conta aberta.

O caminho agora é atômico: a conclusão nova que cita a URL completa de um
PR com entrega em alerta só passa na muralha quando o mesmo livro contém
baixa específica, verde, com evidência do PR e data conferida a partir do
alerta. Cada alerta recebe seu próprio `responde_a` em texto. Uma lista
unitária não pode contornar a prova pela coerção de JavaScript.

`ci/encerramento_alertas.py` só lê: a recusa não cria outra pendência e ensina
a corrigir o próprio PR. Compara novos registros contra `BASE_REF`, sem cobrar
o passado inteiro. Repositório e número identificam juntos o PR, incluindo
as abas files, commits e checks. Base ou Node indisponível resulta em ERROR.

Prova: `ci/tests/test_encerramento_alertas.py` reproduz os registros reais,
aceita baixas específicas e preserva alerta legítimo sem relação.
`ci/tests/test_muralha_do_painel.py` executa a muralha com uma conclusão órfã
e com uma resposta em lista sem prova. Antes da correção a muralha devolveu
PASS e a regressão reprovou com `assert 0 == 1`.

Limite: o portão verifica vínculo e evidência declarada. Não consulta produção,
não entende referência livre como `#1474` sem repositório e não certifica a
verdade do PRONTO escrito na conversa.
