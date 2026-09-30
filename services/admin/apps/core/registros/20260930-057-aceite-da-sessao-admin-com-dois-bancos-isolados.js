(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260930-057-aceite-da-sessao-admin-com-dois-bancos-isolados",
  tipo: "medicao",
  quando: "2026-09-30",
  titulo: "Aceite da sessão admin com dois bancos isolados",
  detalhe: "A abertura local de duas tarefas admin criou clusters PostgreSQL 17 distintos, cada um com banco admin e coordenacao_db. A retomada preservou apenas os dados e o segredo da própria tarefa; segredo divergente foi recusado antes de escrever .env. O PR foi integrado e publicado no run admin; ci/sessao.py é um preparador local e sua prova funcional foi executada no repositório integrado, sem alegar execução no serviço admin de produção.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/2380 https://github.com/abundanciabr/sitesdoreino/actions/runs/36665836639 — python ci/esperar.py --entrega 2380 --so-desfecho: estado PUBLICADO, merge 4b41fd0e156974f40fe8ee33da3938c12247dbc7, jobs_sem_prova []. python -m pytest ci/tests/test_sessao.py -q: 138 passed in 13.65s. Ensaio PostgreSQL 17 local com Sessao.preparar_servicos() e Sessao.escrever_env(): dois clusters e portas distintos; coordenacao_db da segunda tarefa vazio; 4/4 conexões cruzadas recusadas; retomada da primeira preservou dado, segredo e porta. Com segredo divergente: SEGREDO_DIVERGENTE_RECUSADO=True, ENV_INTACTO=True, ERRO_SEM_SEGREDO=True, SEGREDO_RESTAURADO=True, SONDA_POSITIVA=True. git diff --exit-code 3d6d6339f2ad2c3ea6e16d47299b0b42005751a3 4b41fd0e156974f40fe8ee33da3938c12247dbc7 -- ci/sessao.py ci/tests/test_sessao.py: exit 0. docker container inspect dos dois contêineres exclusivos: state=exited, dados preservados.",
  verificado_em: "2026-09-30",
  precisa_do_dono: false,
  responde_a: "20260930-027-ci-abrir-coordenacao-isolada-por-tarefa-na-admin",
  relacao: "comentario",
  tarefa: "TAR-1014",
  gravidade: "verde",
  frente: "fabrica",
  area: "ci",
  entrega: {
    pr: "https://github.com/abundanciabr/sitesdoreino/pull/2380",
    revisao: "cf4626a277ae2c911837b40875a826bf2d09bfce",
    arvore: "a9ddf83eab6b150b1a103f036159f701b34ab79e",
    integracao: "4b41fd0e156974f40fe8ee33da3938c12247dbc7",
    publicacao: "PUBLICADO",
    publicacoes: ["https://github.com/abundanciabr/sitesdoreino/actions/runs/36665836639"]
  },
  aceite_funcional: {
    resultado: "PASS",
    criterio: "Cada tarefa admin abre bancos admin e coordenacao_db em cluster exclusivo, retoma apenas os próprios dados e segredo e recusa segredo divergente antes de gravar .env.",
    comando: "python -m pytest ci/tests/test_sessao.py -q",
    evidencia: "python -m pytest ci/tests/test_sessao.py -q: 138 passed in 13.65s no código integrado. Ensaio PostgreSQL 17 local executou Sessao.preparar_servicos() e Sessao.escrever_env(): clusters e portas distintos, segunda coordenacao_db vazia, 4/4 acessos cruzados negados, retomada preservada. Segredo divergente recusado antes de .env: SEGREDO_DIVERGENTE_RECUSADO=True, ENV_INTACTO=True, ERRO_SEM_SEGREDO=True, SEGREDO_RESTAURADO=True, SONDA_POSITIVA=True. git diff --exit-code HEAD validado 3d6d6339f2ad2c3ea6e16d47299b0b42005751a3 e merge 4b41fd0e156974f40fe8ee33da3938c12247dbc7 nos dois alvos ci/: exit 0. O run admin publicou a revisão, mas não executa ci/sessao.py; o aceite funcional ocorreu no repositório integrado.",
    revisao: "4b41fd0e156974f40fe8ee33da3938c12247dbc7",
    ambiente: "repositorio-integrado"
  },
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
