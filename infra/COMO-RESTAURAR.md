# Como devolver os dados do site

Este guia é para quem não é técnico. Para cada situação há uma frase pronta. Copie a frase,
cole numa conversa com o robô aberta na pasta do projeto e troque o que está entre colchetes.

## Onde estão as cópias

- **Na VPS**, na pasta `/opt/plataforma/backups-de-banco`. Ela recebe uma cópia de todas as bases
  antes de cada publicação e outra uma vez por dia, às 3h30 da manhã (horário de Brasília).
- **No seu PC**, na pasta `C:\Users\davia\Cofre-sitesdoreino`. A tarefa "Cofre sitesdoreino" do
  Windows traz para essa pasta o que é novo na VPS, uma vez por dia e sempre que você entra no
  Windows. Nada é apagado dessa pasta.
- **Para ver a data da última cópia**, abra `C:\Users\davia\Cofre-sitesdoreino\ultima-copia.txt`.
  A primeira linha tem a data. A última linha diz se o PC e a VPS têm os mesmos arquivos.

O que as cópias guardam:

- as 17 bases do site: alunos, matrículas, pagamentos, pedidos, contas, cursos, fórum, pontos,
  medalhas, contatos e o resto;
- a lista de usuários do banco, sem senha;
- quantas linhas cada tabela tinha na hora da cópia;
- uma foto do Redis;
- no PC, também as pastas `admin-midia` (arquivos anexados no painel) e `admin-dados` (a fila
  antiga).

As senhas e chaves (a pasta `env` da VPS) não vão para o PC.

O nome de cada arquivo diz de quando ele é. Por exemplo, `alunos_db-20261002-155607Z-diario.dump`
é a base de alunos de 02/10/2026 às 15:56 no horário UTC, que é 12:56 em Brasília (três horas a
menos). O fim do nome diz por que a cópia foi feita:

- `diario` é a cópia do dia;
- letras e números são a cópia feita logo antes de uma publicação.

## "Sumiu um aluno, uma matrícula ou um pagamento"

> Sumiu [o que sumiu: a matrícula de tal pessoa, o pagamento de tal dia]. Ainda existia em [dia
> aproximado]. Siga o infra/COMO-RESTAURAR.md: restaure lado a lado o backup de antes desse dia,
> ache o que sumiu e devolva ao site só essas linhas. Não troque a base inteira.

O site não sai do ar. O robô monta uma cópia ao lado, procura o que sumiu e devolve só o que
faltava.

## "Uma publicação estragou os dados"

> A publicação de [dia e hora] estragou os dados do site. Siga o infra/COMO-RESTAURAR.md: troque as
> bases pelo backup feito logo antes dessa publicação. Eu autorizo sobrescrever.

Saiba antes:

- tudo o que entrou no site depois da hora do backup sai do site;
- as bases de antes da troca ficam guardadas, com `__antes_` no nome, e nada é apagado;
- o site fica fora do ar por alguns segundos, no máximo poucos minutos;
- se o site não abrir depois da troca, ela se desfaz sozinha.

O código de uma publicação ruim volta sozinho. O banco não volta sozinho: é este o caminho.

## "A VPS sumiu"

> A VPS do site sumiu. Siga o infra/COMO-RESTAURAR.md: me ajude a contratar uma VPS nova, rode o
> provisionamento, devolva as 17 bases e os arquivos a partir do cofre do meu PC e ponha o site no
> ar de novo.

Contratar a VPS custa dinheiro, então o robô pede a sua palavra antes. As chaves da Appmax, do
Mercado Pago, da OpenAI e do e-mail não estão no cofre. Elas precisam ser geradas de novo nos
painéis de cada um.

## Pagamentos: uma segunda fonte

Todo pagamento também fica registrado no painel da Appmax e no do Mercado Pago. Eles servem para
conferir o que o site diz.

> Confira os pagamentos do site de [período] contra o painel da Appmax e o do Mercado Pago e me
> diga o que não bate.

## Para provar que as cópias voltam

> Rode o ensaio de restauração com o backup mais novo do cofre e me mostre os números.

---

## Para o robô

Os comandos rodam na VPS (`ssh sitesdoreino-vps`), em `/opt/plataforma`, com os scripts da main
recebida: `S=codigo/ferramentas/atual/infra`.

- **Escolher o backup.** `ls -lt backups-de-banco/ | head`. Os conjuntos completos têm
  `<CARIMBO>.contagens.tsv` e `papeis-<CARIMBO>.sql`. O CARIMBO é o trecho entre o nome da base e
  `.dump`. Os dumps de antes de 02/10/2026 têm um horário por base e não têm contagens. Eles
  restauram arquivo por arquivo, mas não com `--todas`.
- **Do PC para a VPS**, quando o arquivo só existe no cofre:
  `scp C:\Users\davia\Cofre-sitesdoreino\backups-de-banco\<arquivo> sitesdoreino-vps:/opt/plataforma/backups-de-banco/`.
- **Lado a lado**, sem tocar no site e sem precisar da palavra:
  `bash $S/restaurar-backup.sh --lado-a-lado backups-de-banco/<base>-<CARIMBO>.dump`.
  - Isso cria `<base>__copia_<hora>`.
  - Para devolver linhas, o Postgres é `P=$(docker ps -q --filter label=com.docker.compose.service=postgres --filter label=com.docker.compose.project=plataforma)`.
    Rode `docker exec $P psql -U postgres -d <base>__copia_<hora> -c "\copy (SELECT * FROM <tabela> WHERE <filtro>) TO STDOUT"`
    e mande a saída por pipe para `docker exec -i $P psql -U postgres -d <base> -c "\copy <tabela> FROM STDIN"`.
  - Antes, confira as chaves estrangeiras e a sequência do id.
  - A cópia pode ficar. O backup diário pula as bases `__copia_`, `__antes_` e `__falhou_`.
- **Trocar** pede a palavra do mantenedor, porque descarta o que entrou depois do backup.
  - Uma base: `bash $S/restaurar-backup.sh --trocar backups-de-banco/<base>-<CARIMBO>.dump --sim-eu-quero-sobrescrever`.
  - Todas: `bash $S/restaurar-backup.sh --trocar --todas <CARIMBO> --sim-eu-quero-sobrescrever`.
  - Sem a palavra no fim, o comando só mostra o que faria.
  - Os passos:
    1. restaura ao lado e confere dono e contagens;
    2. para a `aplicacao`;
    3. renomeia a base viva para `__antes_<hora>` e a cópia para o nome certo;
    4. sobe a `aplicacao` e confere https://meshcraft.top/;
    5. se o site não abrir, desfaz tudo.
- **VPS nova:**
  1. Rode `infra/provisionamento-vps.sh`.
  2. Ponha as chaves em `/opt/plataforma/env/`. Os papéis do banco pegam as senhas do `DATABASE_URL` de lá.
  3. Suba só o `postgres` e o `redis`.
  4. Copie o conjunto mais novo do cofre para `backups-de-banco/`.
  5. Rode `bash $S/restaurar-backup.sh --vps-nova <CARIMBO>`. Isso cria os papéis que faltam e as 17 bases, com dono e contagens conferidos.
  6. Devolva `admin-midia/` e `admin-dados/` (o `.tar.gz` do cofre).
  7. Publique.
  8. A foto do Redis, `redis-<CARIMBO>.rdb`, vai para `/data/dump.rdb` do contêiner do redis, com ele parado.
- **Números sem nome de ninguém**, para comparar o site no ar com um backup:
  `bash $S/numeros-do-banco.sh`.
- **Ensaio** no PC, com Docker e Git Bash: `bash infra/ensaiar-restauracao.sh C:/Users/davia/Cofre-sitesdoreino/backups-de-banco`.
  Ele monta um Postgres de mentira e restaura tudo. Também troca uma base, e troca outra vez por
  uma cópia que derruba o site, para provar que a troca se desfaz sozinha. Termina em
  `ENSAIO-PASSOU`.
- **Cópia manual**: `/opt/plataforma/bin/plataforma backup`. Para puxar para o PC agora:
  `powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\davia\Cofre-sitesdoreino\puxar-cofre.ps1`.
- **Nunca** rode `pg_restore --clean` nem `DROP DATABASE` numa base viva. Também nunca rode
  `docker compose down -v`, `docker volume rm` nem `docker system prune --volumes`.
