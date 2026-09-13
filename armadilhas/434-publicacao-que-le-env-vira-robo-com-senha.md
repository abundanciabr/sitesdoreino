schema_version: 2
armadilha: 434
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - infra/deploy-celula-na-vps.sh
  - infra/sincronizar-infra-na-vps.sh
  - infra/restaurar-backup.sh
  - .github/workflows/deploy-celula.yml
  - .github/workflows/deploy-infra.yml
guarda:
  tipo: CI
  dono: ci/tests/test_credencial_so_na_publicacao.py
  detector: test_scripts_automaticos_nao_abrem_credencial_do_banco
sinal: 'o caminho automático ganhou DATABASE_URL, POSTGRES_PASSWORD, SENHA_DB ou um arquivo env real'
licao: 'O robô deve publicar sem alcançar a senha do banco. A credencial fica no provisionamento e no runtime da VPS, enquanto workflows, publicação, sincronização e restauração usam apenas o acesso SSH e o socket local; uma inspeção reproduzível precisa vigiar os nomes e os arquivos, não confiar em comentários.'
---

# 434: Publicação que lê env vira robô com senha

**Data:** 09/09/2026. **Onde:** caminho automático de publicação da
infraestrutura e das células.

## Sintoma e causa

Um script de publicação pode começar a abrir `env/*.env` ou a transportar
`DATABASE_URL` porque o acesso já existe na VPS. A entrega continua verde, mas
o robô passa a ter a credencial do banco por acidente, em vez de operar só com
a chave SSH e o socket local do Postgres.

## Solução e evidência

O teste inspeciona os três scripts remotos e os dois workflows de publicação,
ignorando comentários e recusando os nomes das credenciais, leitura de `.env` e
cópia de `env/`. A mutação que inseriu `DATABASE_URL` no deploy ficou vermelha;
o caminho restaurado passou a suíte.
