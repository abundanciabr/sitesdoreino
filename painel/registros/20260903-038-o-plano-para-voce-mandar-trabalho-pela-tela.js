(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260903-038-o-plano-para-voce-mandar-trabalho-pela-tela",
  tipo: "decisao",
  quando: "2026-09-03",
  titulo: "O plano para você mandar trabalho pela tela dos robôs",
  detalhe: "Depois que a página dos robôs ficou legível, eu perguntei o que você queria conseguir FAZER nela. Você marcou as duas ações: mandar trabalho por ali, e destravar as paradas por ali. Este é o plano que responde a isso.\n\nO problema de verdade cabe numa frase: o seu gesto acontece no servidor do site, e a lista de tarefas dos robôs mora no repositório de código. O site não escreve no repositório, e não vai passar a escrever. Então precisa de uma ponte, e o plano compara as duas possíveis.\n\nA ponte recomendada: quando você aperta o botão, o site pede ao GitHub que rode uma esteira; a esteira escreve a tarefa e abre o pedido de mudança sozinha; a pista mergeia como faz com qualquer outro. Nada fica esperando um robô lembrar de olhar. O outro caminho não precisaria de nada seu, mas deixaria o seu pedido parado até alguém aparecer, que é exatamente o atrito que a fila nasceu para tirar.\n\nSão cinco degraus. O primeiro é a ponte, provada por mim antes de existir tela nenhuma, e eu aperto o botão na mesma sessão para não repetir o caso de 31/08, quando entreguei um botão verde que ninguém nunca apertou e a sua tela passou a madrugada vazia.\n\nDuas coisas dependem de você: autorizar eu mexer nas pastas protegidas do repositório (o primeiro degrau), e criar uma chave no GitHub e colar (o segundo). Da chave eu mando um bloco pronto quando chegarmos lá. Nada mais.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/935",
  verificado_em: "2026-09-03",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: "A página dos robôs continua sendo só uma vitrine: você vê o que eles estão fazendo, mas não consegue mandar nada por ali. Pedir trabalho continua sendo pelo chat comigo.",
  recomendacao: "Autorizar o caminho A (a tela pede ao GitHub que rode uma esteira) e me dar o mandato para mexer em .github/ e ci/ no primeiro degrau. É o único caminho em que o seu pedido anda sozinho até o fim.",
  reversivel: true,
  impacto: "medio"
});})();
