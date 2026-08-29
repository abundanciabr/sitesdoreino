---
schema_version: 2
armadilha: 176
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  dono: ci/tests/test_guarda_declarada_e_sino.py
sinal:
  - `UnicodeEncodeError: 'charmap' codec can't encode character`
---

# Hook fail-open esconde o PRÓPRIO defeito: ele cala, e silêncio parece "nada a dizer"

**Sintoma:** um hook que aconselha (não bloqueia) é escrito fail-open — toda
exceção vira `return 0` —, os testes de unidade das funções internas passam, e
**em execução real ele nunca fala**. Não há erro em lugar nenhum: nem no
terminal, nem no transcript, nem no log. O `stdout` volta vazio e quem lê
conclui "não havia o que avisar".

No caso real (29/08/2026, o sino das armadilhas), o defeito era a
[003](003-unicodeencodeerror-acento-virando-lixo-na-saida-de.md): o aviso tem
emoji e acento, o console é cp1252, e o `print` estourava
`UnicodeEncodeError` — capturado pelo próprio `except Exception: return 0` que
existe para não travar a sessão. O teste que pegou foi o que rodava o hook
**como processo**, comparando o JSON de saída; os testes que chamavam as funções
por dentro passavam verdes, porque a decisão estava certa: só a ENTREGA
quebrava.

**Causa:** fail-open é a escolha certa para um mecanismo que aconselha (conselho
que trava a sessão é pior que conselho nenhum), mas ele transforma qualquer
defeito interno em silêncio — e silêncio é exatamente o que um hook correto
produz na maior parte do tempo. Os dois estados se tornam indistinguíveis de
fora. É o padrão 1 da `docs/decisoes/RETROSPECTIVA-FASE-D.md` (falso-verde)
vestido de tolerância a falha.

**Solução — três, e as três valem juntas:**

1. **Prepare a saída ANTES de decidir qualquer coisa.** `sys.stdout.reconfigure(
   encoding="utf-8", errors="replace")` na primeira linha do `main()`, antes de
   qualquer `print` (é a 003, e ela pega justamente quem escreve mensagem
   bonita com emoji).
2. **Teste o hook como PROCESSO, não só as funções.** Rode-o por
   `subprocess.run`, entregue o JSON no stdin e faça asserção sobre o `stdout`
   que ele produz. Só esse teste vê a diferença entre "decidiu calar" e
   "quebrou ao falar".
3. **Prove o silêncio nas duas direções.** Um caso que EXIGE fala (assinatura
   plantada ⇒ JSON com o aviso) e um que exige silêncio (saída benigna ⇒
   `stdout` vazio). Guarda que só testa o silêncio fica verde com o hook morto.

**Parente próximo:** a [132](132-o-guarda-de-fail-closed-que-nasceu-verde-sem-encenar.md)
(guarda que nasce verde sem encenar falha nenhuma). A diferença é a direção: lá
o guarda nunca viu a falha que promete pegar; aqui o mecanismo nunca conseguiu
executar a ação que promete fazer — e a tolerância a falha apagou o rastro.

**Origem:** PR do sino das armadilhas, 29/08/2026. O defeito foi encontrado
porque o teste de processo reprovou com `JSONDecodeError: Expecting value` —
isto é, `stdout` vazio onde deveria haver JSON. A depuração fora do `except`
mostrou a `UnicodeEncodeError` escondida.
