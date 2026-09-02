(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-011-a-vacina-do-deploy-ganhou-braco",
  tipo: "entrega",
  quando: "2026-09-02",
  titulo: "O socorro automático do site sabia o que fazer e não conseguia fazer. Agora consegue",
  detalhe: "Existe um socorro automático que cuida das entregas que não chegam ao site. Quando duas entregas chegam juntas, uma delas perde a vez e fica pelo caminho, sem nada ficar vermelho. O socorro nasceu para perceber isso sozinho e mandar a entrega de novo.\n\nEm 30 de agosto, às 23h20, ele percebeu certo e não conseguiu agir. Faltava a chave. Ele tinha duas na mesa (a sua, pessoal, e a da própria máquina) e pegava sempre a sua, que é justamente a única das duas que não abre essa porta. Ele avisou, abriu o chamado, e a entrega só chegou ao site de carona na entrega seguinte.\n\nO conserto foi dar a ele as duas chaves em vez de uma. Ele tenta a primeira e, se a porta não abrir, tenta a segunda, dizendo no relatório qual falhou. Se nenhuma abrir, ele para e avisa exatamente como antes: ele nunca diz que reenviou sem ter reenviado.\n\nIsso não foi deduzido lendo manual, foi medido. Montei três testes de verdade, cada um com o seu próprio alvo, e conferi por fora se a entrega tinha mesmo sido reenviada. A sua chave pessoal foi recusada nas duas vezes que tentei; a chave da máquina funcionou.\n\nSobrou uma coisa pequena para você, e ela não trava nada: a sua chave pessoal (o segredo PISTA_TOKEN, criado em 28 de agosto) não tem a permissão de reenviar entregas. Ela continua servindo para tudo o que já fazia. O socorro agora contorna isso sozinho.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/852",
  verificado_em: null,
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: "Nada quebra e nada fica parado: o socorro passa a usar a chave da própria máquina e resolve sozinho. O que continua é um desperdício pequeno, de uma tentativa recusada antes de cada acerto, e uma linha a mais no relatório dele dizendo que a sua chave foi negada.",
  recomendacao: "Deixar como está, por enquanto. A recomendação é só que você saiba do fato, porque a mesma chave é usada pela pista de pouso e pelo alarme, e essa lacuna de permissão pode reaparecer em outro lugar. Se você preferir limpar de vez, é um ajuste de dois cliques no GitHub, na chave que você criou em 28 de agosto: dar a ela a permissão de mexer nas execuções.",
  reversivel: true,
  impacto: "baixo"
});})();
