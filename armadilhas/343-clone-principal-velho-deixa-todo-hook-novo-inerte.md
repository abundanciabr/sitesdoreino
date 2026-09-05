---
schema_version: 2
armadilha: 343
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  dono: ci/tests/test_prestacao_de_contas.py
sinal:
  - `can't open file` + `[Errno 2] No such file or directory` num hook
  - "IDADE DO ESPELHO: N commits atrás de origin/main"
---

# Hook novo é INERTE no clone principal velho — e, no gancho Stop, ele PRENDE a sessão

**Sintoma:** você mergeia um mecanismo novo (hook + lei + teste), o CI fica
verde, a lei entra no censo do `ci/leis_sem_mecanismo.py` — e na janela do
mantenedor **nada acontece**. Nenhum erro, nenhum aviso: o mecanismo
simplesmente não existe para ele. Meses depois alguém descobre que a regra
"vale desde tal data" nunca disparou uma vez.

Medido em 05/09/2026: o clone principal do mantenedor estava parado em
`552e86a9` (03/09), **746 commits atrás**. O gancho `SessionStart` do
`ci/padrao_de_trabalho.py`, mergeado em 04/09, **nunca rodou na máquina dele** —
a prova é que a abertura de sessão imprimia só dois avisos, e o aviso do Padrão
não estava entre eles.

**Causa — duas, e a segunda é a que morde:**

1. **Os hooks são lidos do `.claude/settings.json` DO CLONE ONDE A SESSÃO ABRE**,
   e as sessões do mantenedor abrem no clone principal. Esse clone é espelho por
   lei (`armadilhas/135`) e **atualizá-lo é decisão de quem está na frente do
   computador** — quer dizer, de um leigo que não tem motivo para pensar em
   `git pull`. Enquanto ele não puxa, a fiação que vale é a antiga. Não é o
   arquivo do repositório que manda: é o arquivo do disco dele.

2. **Se a fiação nova chamar um script que ainda não existe naquele clone, o
   `python` sai com código 2** — e 2 num gancho `Stop` significa **RECUSAR o fim
   do turno**. A sessão fica presa num laço de recusa cuja única mensagem é
   `can't open file ... [Errno 2]`. O portão que existia para curar o silêncio
   vira a pior travessura possível: trava a máquina do dono, sem saída e sem
   sentido. (`PreToolUse` tem a mesma aritmética — exit 2 recusa a ferramenta.)

**Solução — as duas metades, e as duas são obrigatórias:**

1. **A fiação de todo hook novo confere o arquivo antes de chamá-lo.** Não
   `python "${CLAUDE_PROJECT_DIR}/ci/x.py"`, e sim um bootstrap que sai 0 quando
   o arquivo falta:

   ```json
   "command": "python -c \"import os,sys,runpy;p=os.path.join(os.environ.get('CLAUDE_PROJECT_DIR',''),'ci','x.py');sys.exit(0) if not os.path.isfile(p) else runpy.run_path(p,run_name='__main__')\" --modo"
   ```

   O teste que prova isto roda o comando LITERAL do `settings.json` pelo shell,
   com `CLAUDE_PROJECT_DIR` apontando para uma pasta vazia, e exige exit 0
   (`test_clone_sem_o_portao_nao_prende_a_sessao`). O par verde do mesmo teste
   roda o mesmo comando contra o repositório de verdade e exige a recusa.

2. **Mecanismo novo que precisa alcançar a janela dele vem com o pedido de
   atualizar o espelho, em bloco único de colar, no relatório final.** Não é
   opcional e não é detalhe de rodapé: sem esse passo o PR é decoração. A lei
   proíbe o agente atualizar o clone compartilhado por conta própria
   (`armadilhas/135` — outra sessão pode ter trabalho não commitado lá), então
   quem faz é ele, e cabe ao agente entregar o comando pronto e dizer em qual
   janela colar.

**Como descobrir se você está caindo nisto agora:** o `SessionStart` já grita a
idade do espelho ("IDADE DO ESPELHO: N commits atrás"). Se N for grande, assuma
que **nenhuma lei recente vale naquela sessão** e confira a fiação de verdade:

```bash
python -c "import json;print(list(json.load(open('.claude/settings.json',encoding='utf-8'))['hooks']))"
```

**Parente próximo:** a [148](148-ler-do-origin-main-nunca-do-clone-principal.md) (ler do
`origin/main`, nunca do espelho). A diferença é a direção: lá o espelho velho te
faz LER uma verdade vencida; aqui ele faz o seu mecanismo novo não EXECUTAR, e
o silêncio é idêntico ao sucesso.

**Origem:** o portão da prestação de contas, 05/09/2026. O buraco apareceu ao
medir por que o aviso do Padrão de Trabalho não saía na abertura da sessão do
mantenedor, e o exit 2 foi medido antes de a fiação ser escrita —
`python /caminho/que/nao/existe.py` na máquina dele devolve `EXIT=2`.
