---
schema_version: 2
armadilha: 262
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  detector: ci/tests/test_reconhecer.py
  motivo: "test_pedaco_de_palavra_nao_acende_capacidade e test_texto_de_teste_e_de_semeador_nao_e_mecanismo encenam os dois falsos SIM medidos em 01/09/2026: a busca sem palavra inteira acende 'guarda arquivo' por causa de 'dominios', e a busca que inclui teste/semeador acende 'serve video' por causa de um aluno de mentira que escreveu YouTube."
sinal:
  - "a plataforma ja faz isso"
  - "capacidade existente"
  - "git grep sem --word-regexp"
  - "minio casa dentro de dominio"
  - "SIM quando a resposta certa e NAO"
---

# Medir uma capacidade por pedaço de palavra faz o plano nascer sem o trabalho que o sustenta

**Sintoma.** Uma sessão pergunta "a plataforma já sabe guardar arquivo?", roda
um `git grep` com os nomes prováveis (`FileField|ImageField|MEDIA_ROOT|boto3|minio`),
recebe três arquivos de volta e conclui **SIM**. O plano seguinte trata o
armazenamento de imagem como coisa que já existe, não abre degrau nenhum para
ele, e a ausência só aparece no meio da construção, com metade das tarefas já
na fila e o mantenedor já avisado.

Medido em 01/09/2026, na primeira execução do `ci/reconhecer.py`, no estudo do
portfólio do aluno. Os três arquivos eram:

    services/catalogo/.../seed_esqueleto.py     "DOMINIO_OPERACOES"
    services/checkout/static/checkout/api.js    "a raiz do dominio"
    services/sugestoes/.../semear_demo.py       "DOMINIO_DEMO"

**Causa.** Duas, e elas se somam:

1. **`minio` é pedaço de "doMINIOs".** Busca por substring casa dentro de
   palavra, e o vocabulário deste projeto é português: "domínio" aparece em toda
   célula que resolve host. O mesmo vale para `hls` e outras siglas curtas.
2. **Teste, semeador e tradução são TEXTO sobre o mecanismo, não o mecanismo.**
   Na mesma execução, "a casa serve aula em vídeo" acendeu porque um aluno de
   mentira do `semear_demo.py` escreveu *"ninguém explica aprovação direito no
   YouTube"*, e porque uma lista de teste tinha a string `"videoaula"`.

**Por que dói mais que o erro contrário.** Dizer NÃO onde há SIM custa um PR
desnecessário, e alguém percebe cedo: o agente encontra o molde no caminho.
Dizer SIM onde há NÃO **apaga do plano** o trabalho que sustenta a entrega, e
nada avisa até a construção bater no vazio.

**Solução.**

1. Capacidade se mede com **`git grep --word-regexp`** (`palavra_inteira=True`
   em `ci/reconhecer.py`), nunca por substring. Tema se procura por pedaço; isso
   é outra pergunta, e é de propósito que as duas usam modos diferentes.
2. Capacidade se mede **só no código de produção**: exclua testes, traduções,
   semeadores e `.md` com pathspec — e use `:(exclude,glob)caminho/**/x/**`,
   porque sem o `glob` o `*` do git para na primeira barra e a exclusão não
   exclui nada.
3. Assinatura que casa palavra comum de rota ou de API (`FILES` casa
   `pulls/N/files` do GitHub) é assinatura errada: use a forma que só existe no
   mecanismo (`request.FILES`).
4. Quando o resultado for SIM numa capacidade que você duvida, **meça de novo
   antes de escrever o plano**. Custa um comando; o erro custa uma escada.

**Onde isto vale além do reconhecimento:** qualquer portão que responda "isto
existe?" por busca de texto — inventários, censos, varredores de mapa. A
pergunta "quantos falsos SIM esta busca pode dar?" é obrigatória antes de
confiar no número.
