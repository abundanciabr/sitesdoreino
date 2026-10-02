# Como o site funciona hoje

Um site no ar, `meshcraft.top`, servido por uma única aplicação (`aplicacao`)
que reúne 18 módulos: `admin`, `alunos`, `catalogo`, `checkout`, `cursos`,
`encomendas`, `forum`, `funil`, `gamificacao`, `identidade`, `leads`,
`mensageria`, `metricas`, `notificacoes`, `pagamentos`, `pages`, `quiz` e
`sugestoes`. Na frente está um gateway único (Traefik) e atrás um Postgres e um
Redis. O que vale é o código: este texto resume `infra/plataforma.sh` e
`infra/publicar.py`, e onde divergir, eles vencem.

## De um push até o ar

Não há pull request obrigatório, workflow nem aprovação de pessoa. Empurrou na
`main`, vai ao ar.

1. O cron da VPS roda `plataforma receber` a cada minuto. Ele busca a `main`,
   vê o que mudou desde a última recebida e abre um lote (um por push; um push
   mais novo cancela o lote antigo).
2. O lote decide o que publicar. Mexeu em `services/`, `packages/` ou
   `documentos/` (os caminhos da `aplicacao` em `celulas.yml`), publica a
   `aplicacao`. Mexeu em `infra/docker-compose.yml`, `infra/traefik/` ou
   `infra/sites.json`, sincroniza a infra.
3. `plataforma publicar aplicacao <sha>` faz, nesta ordem:
   - cópia de todas as bases (`infra/backup-do-banco.sh`), antes de qualquer
     migração;
   - monta a pasta de código imutável `versoes/aplicacao/<sha>` (as 3 mais
     recentes ficam guardadas);
   - se `Dockerfile`, `requirements.txt` ou `vendor/` não mudaram, reaproveita a
     imagem base e só troca o código, montado somente leitura em `/app`; se
     mudaram, reconstrói a imagem na própria VPS;
   - ativa (`infra/deploy-celula-na-vps.sh`) e prova o endereço.
4. Prova ok: o log diz `NO-AR: aplicacao <sha>`. Prova falhou: o código volta
   sozinho para a última versão aprovada e o log diz `RECUPERADA-OU-SUPERADA`.
   Se nem a volta resolver, sai um e-mail de aviso.

**O publicador não roda testes.** Rode-os no PC antes de empurrar
(`make testes`, e `make celula CELULA=<modulo>` para um módulo).

**O banco nunca é restaurado sozinho.** Só o código volta. A cópia feita antes
da publicação está em `/opt/plataforma/backups-de-banco`, e o caminho de volta
está em `infra/COMO-RESTAURAR.md`.

## O que roda sozinho na VPS

| comando | quando | o que faz |
| --- | --- | --- |
| `plataforma receber` | a cada minuto | publica o que entrou na `main` |
| `plataforma vigiar` | a cada 2 minutos | mede o site; fora do ar, volta a última publicação aprovada e avisa por e-mail se não resolver |
| `plataforma backup` | uma vez por dia | cópia de todas as bases (`infra/backup-do-banco.sh`) |

## Como olhar e como voltar

Tudo pelo atalho `/opt/plataforma/bin/plataforma` na VPS (`ssh sitesdoreino-vps`):

- `plataforma estado`: versão no ar, última aprovada e as últimas medições.
- `publicacoes/logs/lote-<sha12>.log`: o que aconteceu com aquele push.
- `plataforma recuperar aplicacao`: volta o código para a última versão
  aprovada e prova de novo.
- `plataforma publicar aplicacao <sha>`: publica de novo um commit da `main`.
- `plataforma operar listar`: as operações de produto (`infra/operar.py`), como
  `plataforma operar operacoes-vps --operacao estado-servico --servico <servico>`.
- `plataforma receber --esperar`: recebe e fica até o lote terminar.

A correção definitiva é sempre um push novo na `main`: a próxima publicação
segue a `main`.

## Onde cada coisa mora

| o quê | onde |
| --- | --- |
| código dos módulos | `services/<modulo>/` |
| mapa de caminhos → célula | `celulas.yml` (lido por `ci/mapa_de_celulas.py`) |
| contratos HTTP e de eventos | `contracts/` |
| compose, gateway, sites e scripts de operação | `infra/` |
| cópias do banco e como devolvê-las | `infra/COMO-RESTAURAR.md` |
| dados de produção, chaves e logs | só na VPS, em `/opt/plataforma` (`env/` nunca vai ao Git) |

Site que não está em `infra/sites.json` nunca é tocado.
