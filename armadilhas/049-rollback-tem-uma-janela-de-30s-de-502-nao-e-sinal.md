<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.14  ·  referencias antigas "ARMADILHAS §5.14" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.14 Rollback tem uma janela de ~30s de 502 — não é sinal de que falhou

**Sintoma:** você dispara o `rollback.yml`, roda `curl` no site logo em seguida e
recebe **502**. A tentação é concluir que o rollback quebrou a produção e
disparar outra coisa por cima — no meio de uma emergência, com pressa.
**Causa:** `docker compose up -d` RECRIA o container. Enquanto o novo não fica
`healthy`, o Traefik não tem backend para a rota e devolve 502. Medido no drill
do critério 3 (23/08/2026, célula `checkout`): 502 a partir de t+30s, resposta
correta da outra versão em t+65s, run verde em t+76s.
**Solução:** medir pelo VEREDITO DO RUN (`gh run view <id> --json
status,conclusion` — §5.10), não pelo primeiro `curl`. O `--wait` do compose já
segura o run até os containers ficarem `healthy`; se o run está verde, a troca
terminou. Só depois disso o `curl` de fora significa alguma coisa.
**Números do drill, para calibrar expectativa:** 76s do disparo ao run verde
(volta) e 69s (desfaz), com `SEGUNDOS_NA_VPS` de 42 e 32 — o resto é fila do
GitHub Actions e checkout do runner. O critério do `ESQUELETO-QUE-ANDA.md` é
300s; sobra folga de 4x.
**Origem:** drill cronometrado do critério 3 da Fase D (23/08/2026), runs
32678099024 e 32678175555.
