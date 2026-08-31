(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-122-a-tela-abriu-vazia-e-o-motivo-era-outro",
  tipo: "incidente",
  quando: "2026-08-31",
  titulo: "Voce abriu a tela e ela estava vazia. O motivo nao era a tela",
  detalhe: "Voce abriu https://meshcraft.top/admin/economia/ e viu o titulo, o texto explicativo e a frase 'nenhuma regra esta ligada' — e nenhuma regra embaixo. Nenhum cartao, nenhum botao de ligar.\n\nO QUE ERA: as regras nunca foram criadas no servidor. As tabelas existem la (isso as migracoes fazem sozinhas, no momento da publicacao), mas as LINHAS dentro delas precisam de um comando separado, e esse comando nunca rodou em producao. Ele so tinha rodado no banco de teste — que e onde eu media, e por isso eu acreditava que estava tudo semeado.\n\nPOR QUE NINGUEM TINHA PERCEBIDO ANTES: ate hoje nao havia por onde olhar. A unica porta que existia devolvia o perfil de uma pessoa, e um site sem regra nenhuma responde exatamente igual a um site com seis regras desligadas. A tela que voce abriu foi o primeiro lugar do sistema inteiro capaz de mostrar essa diferenca — ela achou o problema no primeiro uso.\n\nJA TINHA ACONTECIDO ONTEM, com o forum: ele nasceu dizendo 'ainda nao ha nenhuma area aberta para voce' pelo mesmo motivo exato. Duas vezes em dois dias. A licao que fica e simples de dizer e facil de esquecer: publicar o codigo de uma parte do sistema e ENCHER essa parte de conteudo sao dois passos, e o segundo nao acontece sozinho.\n\nO CONSERTO: um botao no painel de publicacao que cria as linhas, no mesmo molde dos quatro que ja existem (a Caixa, as areas do forum, as duvidas do forum). Voce nao precisa colar nada: eu disparo. Ele e seguro de rodar duas vezes, nao duplica nada, e NAO LIGA regra nenhuma — todas continuam nascendo desligadas, porque ligar e decisao sua.\n\nUM CUIDADO QUE EU PUS E VALE EXPLICAR: o comando precisa saber de qual escola sao as linhas. Eu poderia ter escrito esse numero no script, mas se ele fosse diferente do que a tela procura, as linhas existiriam no banco e continuariam invisiveis para voce — tudo funcionando, tela vazia, e nenhum erro em lugar nenhum. Entao o script LE esse numero de dentro do proprio servico, e se recusa a rodar se nao achar.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/796. DIAGNOSTICO MEDIDO, nao suposto: nenhuma migracao de gamificacao semeia (varredura por RunPython em services/gamificacao/apps/gamificacao/migrations/ acha so as duas de hoje, que sao esquema e correcao de campo); infra/deploy-celula-na-vps.sh nao cita semear; e nao existe workflow semear-economia em .github/workflows/ (existem quatro para outras celulas: semear-caixa, semear-demo-caixa, semear-areas-do-forum, semear-duvidas-do-forum). O comando semear_economia exige --site e imprime SEMEADURA DA ECONOMIA OK, e o script confere as duas coisas. bash -n limpo; o workflow tem a mesma forma estrutural do molde (workflow_dispatch, grupo proprio, 4 passos), conferido por leitura em YAML dos dois arquivos.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: true,
  impacto: "medio"
});})();
