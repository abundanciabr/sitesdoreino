(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-024-a-auditoria-interna-passou-o-pente-fino-no-dia",
  tipo: "medicao",
  quando: "2026-08-29",
  titulo: "A auditoria interna passou o pente-fino no trabalho do dia: confirmou o grosso e achou 4 coisas",
  detalhe: "Você pediu uma auditoria do que foi feito hoje, e ela foi feita medindo — no GitHub e no código, nunca confiando no que a conversa disse.\n\nO QUE SE CONFIRMOU: os 20 pedidos do dia entraram de verdade; as 8 muralhas rodam e ficam verdes na linha principal limpa; 851 testes passam; os arquivos montados do painel estão mesmo fora do controle de versão; a cerca caiu e as peças que a substituem existem e mordem; as sabotagens de teste foram todas desfeitas (o contrato de leads está inteiro, o teste apagado voltou); e a esteira de pouso está verde desde o conserto.\n\nO QUE A AUDITORIA ACHOU:\n\n1. Uma publicação tinha falhado às 15:29 (o servidor não atendeu — intermitência conhecida) e NINGUÉM tinha olhado, violando a regra da casa de conferir toda publicação. O painel online ficou meia hora desatualizado. Repique feito, verde, painel em dia.\n\n2. Nessa mesma falha, a volta automática estreou num incidente real: escolheu a imagem certa (funcionou!), mas não alcançou o servidor — pelo mesmo motivo da falha original — e a mensagem final dizia para tratar a parte como QUEBRADA. Ela não estava: nada tinha sido publicado, o site seguia são na versão anterior. Mensagem alarmante errada gasta a confiança que a mensagem certa precisa. Consertado: agora ela distingue 'o servidor nunca atendeu, nada mudou, sem emergência' de 'algo rodou e parou no meio, aí sim é grave'.\n\n3. O guarda local que impede robô de commitar arquivo montado estava sem a permissão de execução — em máquina Linux ele não rodaria. A casa já tinha tropeçado nisso uma vez, com o guarda vizinho. Consertado.\n\n4. Honestidade sobre o placar: os mandatos-título das 4 ondas estão completos, mas 5 recomendações aceitas da tabela detalhada do plano ainda não foram construídas — cópia de segurança antes de migração, credencial do banco só dentro da publicação, teto em função da duração dos testes, revisor-robô no pouso, e o verificador de maiúsculas/fim de linha. Dizer 'o plano inteiro está no ar' foi dizer mais do que o medido. O certo: as ondas estão no ar; a tabela tem 5 pendências, listadas para a auditoria externa.\n\nA lição que atravessa as 4: conferir o instrumento, não só o resultado — a mesma que você ensinou hoje mais cedo, cobrando de novo.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/PRNUM. Medidas: PRs 434-453 MERGED (gh pr view); muralhas PASS e 851 testes verdes na main limpa; git ls-tree sem gerados; run 33260367237 vermelho por 'dial tcp :22 i/o timeout' nas 3 tentativas + reversao failure pelo mesmo motivo, rerun verde; .githooks/pre-commit em modo 100644 contra 100755 do pre-push.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
