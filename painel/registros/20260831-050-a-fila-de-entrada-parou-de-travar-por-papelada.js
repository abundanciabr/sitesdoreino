(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-050-a-fila-de-entrada-parou-de-travar-por-papelada",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "A fila de entrada parou de travar por papelada, e isso custou o seu tempo hoje",
  detalhe: "Hoje voce colou a linha do aviso no celular e recebeu um erro tres vezes seguidas. O motivo nao era a sua linha nem o servidor: o script ainda nao tinha entrado no projeto, porque a FILA DE ENTRADA estava travada.\n\nPOR QUE ELA TRAVA: existe uma regra boa na casa, que voce mesmo pediu: todo trabalho que entra tem que virar um registro aqui no seu painel, senao ninguem te conta o que aconteceu. Um porteiro cobra isso, e ele segura a fila INTEIRA enquanto alguem estiver devendo.\n\nO DEFEITO: o porteiro dispensava quem so mexia no seu livro (faz sentido: esse trabalho JA e o registro), mas nao dispensava quem mexia no livro E na lista de tarefas dos robos ao mesmo tempo. E isso e exatamente o que um robo faz quando termina um trabalho: escreve o registro para voce e da baixa na tarefa dele. Resultado: uma divida sem dono de verdade, travando todo mundo, ate alguem escrever um registro sobre um trabalho que nao tinha o que registrar.\n\nISSO ACONTECEU TRES VEZES SO HOJE, com tres robos diferentes, e a terceira foi a que segurou a sua linha. Ja tinha acontecido ontem tambem.\n\nO CONSERTO: o porteiro passou a dispensar quem so escritura, seja no livro, seja na lista de tarefas, seja nos dois. Quem entrega CODIGO continua devendo registro, e isso e o que importa: e o seu trabalho de saber o que mudou no site.\n\nTem tres testes novos que provam as duas metades, inclusive a que nao pode afrouxar (mexeu em codigo, deve registro). E a licao de campo que descrevia o problema desde ontem foi marcada como curada, com o custo anotado.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/733. PROVA VERMELHO->VERDE: com o codigo antigo, o guarda novo 'test_so_escriturar_isenta_mesmo_misturando_livro_e_fila' reprova; com o conserto, os 18 passam. Os tres devedores do dia foram os PRs 694, 696 e 697, todos de escrituracao pura, de robos diferentes.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
