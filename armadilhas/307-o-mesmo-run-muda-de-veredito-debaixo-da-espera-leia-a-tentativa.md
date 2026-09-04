---
schema_version: 2
armadilha: 307
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: o esperar.py e o gh run view leem o run pelo id, e o GitHub responde pela tentativa mais recente; ensinar o esperar.py a dizer "esta é a tentativa N, e ela foi refeita" é mudança em ci/ (CODEOWNERS), proposta aqui e não feita neste PR
sinal:
  - `"total_count":0,"jobs":\[\]`
  - `terminou 'cancelled' · levou 0s`
  - `run_attempt` maior que 1 num run que você ainda está esperando
---

# O mesmo run muda de veredito debaixo da espera: quando a vacina refaz, leia a TENTATIVA, não o run

**Sintoma.** Medido em 04/09/2026, no deploy do PR #953 (run 33830235534):

1. `esperar.py --run 33830235534` pelo Monitor disse `terminou 'failure'` às 23:48:04.
2. Onze segundos depois, o MESMO comando em foreground disse `terminou 'cancelled'
   · levou 0s`, e `gh run view --json status,conclusion` confirmou `cancelled`.
3. `gh run view --json jobs` devolveu lista vazia; `gh api .../runs/<id>/jobs`
   devolveu `{"total_count":0,"jobs":[]}`. Um run "concluído" sem nenhum job.
4. `gh run view <id> --log-failed` não imprimiu nada.

Quem lê isso pensa que o run foi cancelado pela cadeira musical da
[188](188-deploy-de-push-cancelado-pela-cadeira-musical-fica-fora-do-ar.md) e que o
merge está fora do ar. Não estava: dois minutos depois o mesmo id estava
`queued`, depois `in_progress`, e terminou `failure` de novo, agora com os jobs
inteiros para ler.

**Causa.** A `vacina-do-deploy` (armadilha
[127](127-deploy-vermelho-com-i-o-timeout-e-a-vps-viva-nao-e.md), `ci/rerun_de_deploy.py`)
viu o `i/o timeout` da primeira tentativa e pediu `rerun`. Um rerun **não cria run
novo**: ele vira `run_attempt: 2` do mesmo id. E tanto `gh run view <id>` quanto a
API `/runs/<id>` respondem **só pela tentativa mais recente**. A tentativa 2 foi
expulsa pela concorrência do `deploy-celula` antes de criar job algum (por isso a
lista vazia e o `0s`), e a vacina pediu a tentativa 3. Do lado de fora, o id
parecia um run só, mudando de ideia.

**Solução.**

1. Antes de acreditar em qualquer veredito, leia a tentativa:
   `gh api repos/<dono>/<repo>/actions/runs/<id> --jq '.run_attempt'`. Maior que 1 é
   a vacina trabalhando, e `cancelled` numa tentativa intermediária **não é
   veredito**, é a cadeira musical entre dois reruns.
2. Os jobs de uma tentativa específica moram em
   `gh api .../actions/runs/<id>/attempts/<N>/jobs`, e o log de um job dela em
   `gh run view <id> --attempt <N> --job <job_id> --log`. A tentativa 1 continua
   legível mesmo depois de refeita: foi assim que o `i/o timeout` apareceu.
3. O veredito que vale é o da **última tentativa concluída com jobs**. Se o run
   está `queued` de novo, espere o mesmo id de novo (`esperar.py --run <id>`), não
   procure outro run.
4. Célula nova continua vermelha pela [088](088-celula-nova-deixa-o-deploy-celula-vermelho-ate-o.md)
   mesmo depois de a vacina curar o timeout: o `i/o timeout` da tentativa 1
   ESCONDEU o motivo real, que só apareceu na tentativa 3
   (`'encomendas' não tem serviço algum em /opt/plataforma/docker-compose.yml`).
   Dois vermelhos com causas diferentes no mesmo id; leia o log da tentativa que
   decidiu, não o da primeira.

**Padrão** (`RETROSPECTIVA-FASE-D.md`): prova de fora (o veredito é o da API, por
tentativa, não a frase de uma ferramenta que lê o id) · falso-verde ao contrário
(um `cancelled` que parece "fora do ar" e é a cura em andamento).
