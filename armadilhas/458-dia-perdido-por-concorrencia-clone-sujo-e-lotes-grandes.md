---
schema_version: 2
armadilha: 458
estado: guardada
degrau: 1
confianca: alta
custo_por_queda: alto
gatilho:
  - clone principal com alterações locais
  - múltiplas tarefas no mesmo diretório
  - PR com mais de 15 arquivos de código
  - gh api rate limit exceeded
  - acesso negado em pytest tmp_path
guarda:
  tipo: procedimento
  detector: ci/sessao.py
sinal:
  - "ahead 1, behind 492"
  - "escopo estourou o orçamento de arquivos"
  - "HTTP 403: API rate limit exceeded"
  - "PermissionError: [WinError 5] Acesso negado"
licao: Um clone compartilhado e atrasado mistura entregas, força conflitos em arquivos de lições, estoura o orçamento do PR e mascara dependências entre filhas. A abertura deve criar uma bancada limpa por tarefa, a divisão deve seguir os commits e cada filha deve declarar sua base. Valide o diretório temporário dentro da bancada e confira a cota do GitHub antes de armar o pouso.
---

# O dia travou antes de o código travar

Em 09/09/2026, o clone principal estava com alterações locais de várias frentes,
uma confirmação local à frente e 492 confirmações atrás de `origin/main`. Duas
tarefas administrativas escreveram no mesmo diretório. O trabalho de telefone
acabou misturado com CI, infra, contratos e registros de outras tarefas, e a
sessão precisou parar para separar o índice do Git.

O PR 1506 juntou quatro entregas independentes em 43 arquivos, com 33 arquivos
de código medidos. A muralha recusou o lote por orçamento. Quando o lote foi
dividido, os testes dos robôs revelaram a dependência real da primeira filha,
`admin_dados`; a filha correta precisou ser empilhada sobre o PR 1510.

Houve ainda falhas de ambiente que consumiram tempo: o Windows encontrou um
`bash` que não conseguia iniciar `/bin/bash`, o pytest apontou para um diretório
temporário compartilhado sem permissão e o portão de pouso não conseguiu ler
evidências porque o `gh` tinha credencial inválida e a API estava sem cota.

O procedimento que fica é curto: congelar novas tarefas no clone principal,
abrir uma bancada por tarefa com `ci/sessao.py`, dividir pelo limite de código,
testar cada base empilhada antes de abrir o próximo PR e separar o teste
temporário da `.venv` compartilhada. O pouso só é armado depois de confirmar
autenticação e cota da API.
