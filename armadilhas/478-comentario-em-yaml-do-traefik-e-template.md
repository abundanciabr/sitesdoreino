# Comentário no YAML do Traefik é template, e derruba o site inteiro

O provedor de arquivo do Traefik renderiza o arquivo como template Go ANTES de
interpretar o YAML. Comentário YAML não é comentário para o template: um
`{{ ... }}` dentro de `#` é ação de template. Se a ação for inválida, o arquivo
inteiro é recusado, o provedor `file` cai junto e TODOS os arquivos da pasta
dinâmica somem, inclusive os que estavam certos. O sintoma é Traefik de pé
servindo 404 em todos os hosts, sem erro nenhum aparente.

Em 15/09/2026 a linha que documentava o ensaio da entrada privada,
`` #   - `{{ env }}` funciona no provedor de arquivo ``, derrubou a borda
pública três vezes. `env` sem argumento reprovou o template e levou
`plataforma.yml` e a raiz do site junto. O erro só aparece no log do container:

    ERR Error while building configuration (for the first time)
    error="/etc/traefik/dynamic/entrada-privada.yml: template: :20:10:
           executing "" at <env>: wrong number of args for env: want 1 got 0"

Ao escrever sobre a sintaxe de template num arquivo dinâmico, descreva em
palavras, nunca com as chaves duplas. Quem faz valer:
`ci/tests/test_entrada_privada_da_ponte.py::test_todo_template_dos_arquivos_dinamicos_e_uma_injecao_de_variavel`.

gatilho: infra/traefik/dynamic/
licao: Todo `{{ ... }}` num arquivo dinâmico do Traefik, mesmo em comentário, é
  executado. Um inválido recusa o arquivo inteiro e derruba o provedor.
