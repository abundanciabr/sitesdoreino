# Rede do Revisor — proposta, não aplicada

Registro privado no site: `https://meshcraft.top/admin/documentos/revisor-modelos-3d-changespec-20261014`.
Destino da ferramenta: `https://meshcraft.top/ferramentas/revisor-de-modelos-3d/`.

## O que foi conferido na VPS

Em 14/10/2026, PostgreSQL 17.10 em `interna`, IP 172.16.2.4, sem porta
publicada no host. Aplicação em `edge` (172.16.1.3) e `interna` (172.16.2.5).
Traefik em `edge` (172.16.1.6) e meshcraft-funil. As redes edge e interna
estão com Internal=false; não são isolamento suficiente para o Revisor.
IPs .250/.251 propostos estavam livres. A faixa 172.16.20.0/24 não aparece
no IPAM Docker consultado; conferir também rotas do host antes da aplicação.

Base/role revisor já criados. A prova anterior de login em loopback incidia
em trust e não demonstrava validação da senha. Nesta preparação, nova prova
na interface 172.16.2.4 aceitou a senha correta e recusou uma incorreta por
password authentication failed, usando somente a própria base. Sem mudanças.

## Configuração a autorizar

Rede Docker própria meshcraft-revisor, internal=true, sem portas publicadas.
Web e worker somente nessa rede. Parser em namespace sem rede e sem segredos;
o worker supervisiona o parser, mas a rede do worker nunca é herdada por ele.
Não conectar a aplicação às redes compartilhadas nem montar socket Docker.

Três intermediários pequenos, com destinos fixos:

| Origem | Intermediário/destino | Permissão |
|---|---|---|
| Traefik existente | entrada própria em edge → web:8000 | Somente host meshcraft.top e caminho do Revisor |
| web/worker | relay de banco → postgres:5432 | Só usuário revisor na base revisor, imposto no HBA |
| web/worker | gateway de contratos → aplicacao:8000 | GET nas quatro operações abaixo, tokens próprios |
| parser | nenhum | Sem rede, DNS externo, banco ou credencial |

Entrada proposta 172.16.1.250:8080; gateway de contratos 172.16.1.251 na edge;
relay de banco 172.16.2.250 na interna. Escutar os gateways de saída somente
na interface privada. Sem encaminhamento IP, capacidades ou privilégios extras.
Aplicar filtros de saída IPv4/IPv6 só aos novos containers/interfaces: relay
só postgres:5432, contratos só aplicação:8000, entrada só web:8000. A rede
internal=true sozinha não restringe o container que também está na edge/interna.
Não criar proxy CONNECT, URL arbitrária ou encaminhamento de redirects.
IPs do upstream devem ser resolvidos/atualizados na entrega; não presumir que
o IP observado da aplicação sobreviva a uma publicação.

## Banco: bloquear a permissão herdada sem mexer no banco de testes

Acrescentar bloco específico no INÍCIO do HBA existente: permitir revisor/revisor
apenas do relay e do loopback autenticado; rejeitar outras combinações vindas
do relay; rejeitar o usuário revisor em todas as demais origens/bases, incluindo
socket local e replicação. Preservar regras dos demais usuários. O arquivo
candidato está em `https://github.com/abundanciabr/sitesdoreino/blob/codex/revisor-rede-20261014/services/revisor/infra/postgres-revisor.conf`.

Isso impede a conexão à antiga base de testes com CONNECT público sem acessar
ou alterar essa base. Revogar CONNECT diretamente do role não anularia o grant
herdado de PUBLIC. HBA usa a primeira regra correspondente, independentemente
desse grant. Fonte: `https://www.postgresql.org/docs/17/auth-pg-hba-conf.html`.
Validar pg_hba_file_rules e recarregar a configuração, sem reiniciar PostgreSQL.
O reload não revoga sessões antigas: conferir e encerrar somente eventuais
sessões revisor antes da prova final; não afetar conexões dos outros usuários.

## HTTP e credenciais

Destino interno confirmado pela topologia: http://aplicacao:8000, Host meshcraft.top.
Gateway admite apenas métodos/caminhos canônicos e parâmetros listados:

- GET /api/identidade/sessao/completa: cookie meshcraft_sessao opaco; token
  próprio revisor→identidade, aceito em TOKENS_ACEITOS_REVISOR e
  TOKENS_COMPLETOS_REVISOR. Sem permissão de senha.
- GET /api/alunos/alunos/{email_encoded}/matriculas: token próprio
  revisor→alunos em TOKENS_ACEITOS_REVISOR; conferir site e matrícula ativa.
- GET /api/cursos/cursos/{curso}/aulas e /api/cursos/cursos/{curso}/aulas/{numero}:
  token próprio revisor→cursos em TOKENS_ACEITOS_REVISOR; site_id obrigatório,
  parte quando aplicável. Apenas aulas publicadas e acessíveis são apresentadas.
  A resposta getLesson contém conteúdo interno: extrair só título/identificador/
  endereço necessários; nunca expor roteiro ou guia do mentor ao aluno/IA.

Tokens dos provedores ficam somente no gateway privado; cada destino recebe
apenas seu token. O Revisor não recebe tokens gerais da escola. Gateway exige
autenticação própria do cliente Revisor e rejeita todos os outros métodos e
caminhos, inclusive normalizações ambíguas/duplo encoding. Timeout de conexão
2s, total 5s; falha de sessão/matrícula resulta em indisponibilidade orientada.
Não registrar cookies, Authorization, e-mails em caminhos, corpos ou queries.
Nem credenciais nem o diretório completo env da plataforma são montados no Revisor.

Os três provedores leem tokens na inicialização. Habilitar os novos pares pode
exigir recarregar a aplicação compartilhada; não prometer troca sem impacto.
O manifesto instalado foi consultado somente pelos nomes dos arquivos: protege
`/opt/plataforma/env/checkout.env`, `/opt/plataforma/env/pagamentos.env`,
`/opt/plataforma/.env` e `/opt/plataforma/docker-compose.yml`. Os arquivos dos
três provedores não constam nessa seção. Propor cadastro apenas em
`/opt/plataforma/env/identidade.env`, `/opt/plataforma/env/alunos.env` e
`/opt/plataforma/env/cursos.env`, com backup privado; nenhum valor foi lido.
Usar Compose próprio em `/opt/plataforma/revisor/compose.yml` (destino futuro),
sem editar o Compose compartilhado protegido. Recarregar provedores pela
esteira, preservando imagem e código congelados.
Conferir a política instalada antes de editar configurações. Esta proposta NÃO
autoriza exceção ao Mercado Pago congelado. Se o registro do par exigir alterar
arquivo/imagem/configuração protegidos, parar com a diferença concreta para
autorização específica, sem emprestar token de outro consumidor.

Narrativa por IA precisa de HTTPS para um endpoint fixo de provedor. Provedor,
modelo e credencial ainda não foram definidos; saída permanece fechada nesta
configuração. Escolha e endpoint exatos serão apresentados antes de abrir essa
saída. Isso não remove a narrativa do escopo da primeira entrega. Nenhum arquivo
3D, captura, dado de identidade ou texto arbitrário do arquivo será enviado.

## Entrada, desfazer e limite desta autorização

Arquivo novo de rota, separado do arquivo compartilhado protegido:
`/opt/plataforma/traefik/dynamic/revisor.yml` (destino futuro na VPS).
Host exato meshcraft.top; Path exato /ferramentas/revisor-de-modelos-3d ou
PathPrefix /ferramentas/revisor-de-modelos-3d/. Não capturar a categoria inteira.
Sem stripPrefix se Django servir o prefixo contratado. TLS existente; apenas
Traefik chega à entrada privada. Limite do arquivo continua 50.000.000 bytes;
permitir margem finita no envelope multipart, com validação própria do arquivo.
Não habilitar buffering de uploads em disco compartilhado do Traefik.
Ativar rota só quando o serviço responder e o fluxo estiver provado; sem tela
exclusiva de admins, sem menu, lista, sitemap ou aviso divulgando o endereço.

Antes de aplicar: backup privado de HBA, configuração/estado de rede e artefatos
afetados. Ensaiar em ambiente descartável e conferir isolamento real após aplicação:
base própria aceita senha correta, senha errada falha, outras bases são rejeitadas
ANTES de abrir sessão, parser sem rede, gateway nega POST e destinos não previstos.
Conferir também saúde do site e preservação da configuração congelada.
Nenhuma leitura de tabelas de outras células integra a prova.

Desfazer: parar apenas serviços próprios, retirar somente rota/conexões novas,
restaurar o bloco de configuração alterado a partir do backup, validando que não
sobrescreve trabalho concorrente. Se o HBA precisar voltar ao anterior, desabilitar
LOGIN do role revisor enquanto não houver contenção equivalente; não reabrir
acesso público herdado por efeito do rollback. Não apagar/restaurar banco.

A autorização pedida é para essa rede interna, restrição HBA e pares HTTP, com
backup e provas. Divulgação do link segue separada. Este documento e os arquivos
candidatos são uma configuração proposta; nenhum deles foi aplicado na VPS.
