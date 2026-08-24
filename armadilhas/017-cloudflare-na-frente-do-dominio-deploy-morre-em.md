<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.17  ·  referencias antigas "ARMADILHAS §3.17" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.17 Cloudflare na frente do domínio ⇒ deploy morre em `dial tcp <host>:22: i/o timeout`

**Sintoma:** `deploy-celula`/`deploy-infra` falham na etapa de SSH com
`dial tcp ***:22: i/o timeout` — com runs verdes NO MESMO DIA, minutos antes, e a
VPS saudável (porta 22 respondendo o banner `SSH-2.0-...` no IP direto).
**Causa:** o segredo `VPS_HOST` guardava o **domínio** (`basileiatoutheou.org`). Ao
colocar o domínio atrás do Cloudflare (nuvem laranja/Proxied), o nome passa a
resolver para a borda do Cloudflare — que só repassa HTTP/HTTPS, nunca a porta 22.
A pegadinha: os primeiros deploys pós-mudança ainda PASSAM (cache de DNS com o IP
antigo), e a falha só aparece quando o cache vence — no lote 2 foram 4 deploys
verdes e o 5º vermelho, o que disfarça completamente a causa.
**Solução:** pipeline fala com a VPS por **IP**, nunca pelo domínio público
proxiado — `VPS_HOST=217.196.62.220` (trocado pelo mantenedor em 22/08/2026;
segredo de repositório é território dele). Regra geral: mudou DNS/proxy de um
host que algum pipeline usa ⇒ teste o canal do pipeline IMEDIATAMENTE, não espere
o próximo merge descobrir. Conferir SSH vivo de fora, sem ssh:
`exec 3<>/dev/tcp/217.196.62.220/22 && head -c 30 <&3` (imprime o banner).
**Origem:** janela de merge do lote 2 (22/08/2026), deploy do PR #75 — 2 reruns
para diagnosticar, causa externa, `gh run rerun <id> --failed` verde após a troca.
