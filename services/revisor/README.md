# Revisor de Modelos 3D — primeira entrega

ChangeSpec: `https://meshcraft.top/admin/documentos/revisor-modelos-3d-changespec-20261014`.
Endereço pretendido: `https://meshcraft.top/ferramentas/revisor-de-modelos-3d/`.
Categoria existente: `https://meshcraft.top/ferramentas/`.

Nascer com acesso normal de alunos, sem allowlist/admin-only. Não acrescentar
link à categoria, menus, avisos ou mensagens antes da liberação expressa do
mantenedor. Login/matrícula e dez análises por dia pertencem ao produto aprovado.

## Estado desta entrega

Motor de medições, importador Blender isolável, envelope de upload, tabela
Roblox de 14/10/2026, corpus reproduzível e contrato OpenAPI inicial. Nenhuma
rota HTTP, banco ou rede foi instalada. O esquema Django e a migração inicial
já estão preparados, com reserva atômica e idempotência. As páginas, fila persistente,
adaptador de sessão e narrativa serão a próxima entrega de código; não existe
serviço utilizável por alunos ainda. Não confundir esse começo com a camada 1
concluída. Fixtures são geradas em diretórios temporários pelos testes.

Os limites/cobertura são próprios desta célula. O código não importa células
alheias. Não há XP, medalha, add-on, tutor ou portfólio aqui. A lista real dos
quinze erros, as explicações e as aulas continuam pendentes da Lívia. Normais
fornecidas pelo arquivo e unidades/attachments ainda não são certificadas; o
boletim informa essas lacunas. Artefatos de modelo só existem durante a análise.

## Próximo degrau reservado: banco

Preparar uma base PostgreSQL nova chamada `revisor`, com role própria chamada
`revisor`, senha gerada e armazenada somente na VPS. Sem grants em outras bases,
sem cópia de dados de alunos, identidade ou sugestões. Não executar criação
até receber a palavra do dono, conforme o pedido específico desta célula.

O schema próprio terá projetos e revisões por `site_id` e `actor_id` opacos;
reserva diária por pessoa/site/data de São Paulo, contador de 0 a 10; unique
por pessoa/site/Idempotency-Key; hash do upload para conflito idempotente;
perfil, versões, estado/tentativa, timestamps, métricas/achados/cobertura em
JSONB e narrativa validada. Nenhum arquivo, textura ou e-mail no banco.
Índices próprios para dono/histórico e fila. Quota e criação em uma transação,
serializadas por lock do dono. O lock global de execução e recuperação de
uploads órfãos ainda pertencem à entrega do worker. Nenhuma FK para banco alheio.

Migração preparada: `https://github.com/abundanciabr/sitesdoreino/blob/codex/revisor-persistencia-20261014/services/revisor/revisor/migrations/0001_initial.py`.
Cria somente Owner, Project, DailyQuota e Review. Owner tem IDs opacos; não
replica nome, e-mail ou matrícula. Review conserva o hash da chave e do pedido,
não o arquivo nem o nome original. A função de reserva pressupõe autenticação
e rejeição do envelope feitas antes pelo futuro adaptador HTTP. Não é endpoint
ativo. Modelo recebido permanece em estado received até o handoff seguro do worker.

Comprovação de 14/10/2026: nove testes passaram contra PostgreSQL 16 descartável,
com Django 5.1.4 do ambiente de testes existente. Vinte solicitações simultâneas
consumiram exatamente dez vagas; doze retries simultâneos geraram uma revisão
e uma cobrança de quota. Isso não escolhe Django 5.1.4 para produção: o runtime
próprio atualizado e seu isolamento ainda serão preparados e comprovados.
O banco descartável foi encerrado e nenhum banco da VPS foi criado ou migrado.
Testes: Django test runner com `db_cases` e `db_settings`, incluindo a pasta
tests no PYTHONPATH. A variável REVISOR_TEST_PG_PORT seleciona exclusivamente
o PostgreSQL descartável em 127.0.0.1; sem ela usa SQLite em memória e pula
as duas provas de concorrência que exigem lock de linha real.

A criação da base é a autorização pedida, não a autorização de rede. Pares
HTTP para identidade, alunos e cursos, segredo Django e provedor da narrativa
serão provisionados em entrega própria após autorização. Não reutilizar
tokens/credenciais de outros consumidores nem mudar a aplicação congelada.

## Provas

Executar unittest na raiz da célula, com as dependências próprias. O teste de
data real reprova a tabela após 180 dias. O ensaio Linux deve comprovar bwrap,
ausência de rede/montagens privadas e encerramento da árvore de processos;
não instalar em produção se essa prova faltar. Testes em Windows não provam
o isolamento Linux. A nova imagem e sua reversão precisam de prova na VPS.

O contrato descreve a interface a implementar, não endpoints ativos. Ele deve
ser comparado com a API Django real na próxima entrega antes da conexão.
Concluir corpus por defeito e comparação dos importadores antes de alegar
cobertura completa. O processo Blender pode descartar informação na importação;
por isso os testes de preservação são parte da prova, não decoração.

## Desfazer

Antes de instalar: backup de artefato/configuração/dados relacionados. A primeira
ativação deve poder voltar ao serviço desligado; seguintes à imagem/código
aprovados anteriores. Nenhum rollback apaga revisões ou restaura banco sozinho.
Preparar a operação administrativa de desfazer na entrega operacional; não
modificar áreas administrativas existentes para criar uma prévia do produto.
