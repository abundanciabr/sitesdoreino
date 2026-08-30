(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-068-um-alarme-do-projeto-toca-quando-esta-tudo-bem",
  tipo: "nota",
  quando: "2026-08-30",
  titulo: "Um alarme do projeto esta tocando quando esta tudo bem, e isso ensina os robos a ignorar alarme",
  detalhe: "O projeto tem um sino que avisa o robo quando ele esta prestes a repetir um erro ja conhecido do catalogo. E uma das melhores pecas da casa. Um deles esta quebrado do jeito mais traicoeiro possivel: ele toca quando nao ha nada errado.\n\nO aviso em questao guarda a licao de quando o livro de ocorrencias fica devendo um registro. Ele foi configurado para disparar ao ver a frase 'divida do livro'. So que o programa que confere os PRs imprime exatamente essa frase toda vez que esta TUDO CERTO: 'divida do livro, aprovado, livro em dia'. Entao o sino grita 'atencao, voce vai cair numa armadilha conhecida' em cima de uma mensagem de sucesso.\n\nPor que isso importa mais do que parece: alarme que toca a toa e alarme que se aprende a ignorar. Quando a divida for de verdade, o robo ja terá aprendido a passar os olhos por cima. O projeto ja documentou essa mesma doenca em outro guarda, e ela tem nome.\n\nMedido hoje: tres disparos falsos numa sessao de robo, mais dois na sessao principal. Um deles aconteceu enquanto eu LIA o codigo-fonte, num trecho que apenas contem a frase.\n\nO conserto ja esta escrito e esperando um robo livre no balcao, com a prova exigida. Ele inclui varrer o catalogo inteiro atras do mesmo defeito em outros avisos, porque consertar so este curaria o caso e nao a categoria.\n\nNada disso afeta o site nem espera por voce.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/628 (este PR, que cria a TAR-038). CONFERIDO NA FONTE, e nao no relato do robo: armadilhas/185 declara `sinal: d[íi]vida do livro`, e ci/mergear.py imprime Resultado('dívida do livro', Estado.PASS, 'livro em dia') no caminho saudavel (linhas ~480-496). O sino disparou sobre a propria leitura desse trecho durante esta sessao.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
