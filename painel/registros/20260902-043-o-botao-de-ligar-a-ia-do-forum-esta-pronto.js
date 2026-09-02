(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-043-o-botao-de-ligar-a-ia-do-forum-esta-pronto",
  tipo: "entrega",
  quando: "2026-09-02",
  titulo: "O passo para voce ligar a IA do forum esta pronto, e e uma linha so",
  detalhe: "Isto acompanha o ajudante de IA do forum. E a parte que fica do SEU lado, e ela ficou do jeito mais curto que eu consegui.\n\nCOMO VAI SER: voce cola UMA linha dentro da VPS. Ela baixa um programinha e roda. Ele te pede a chave, voce cola, e nada aparece na tela enquanto voce digita (isso e de proposito, e e normal). Ele guarda, recarrega o forum e te diz que terminou.\n\nPOR QUE ELE NAO ACEITA A CHAVE COMO PARTE DO COMANDO: porque tudo que se digita numa linha de comando fica gravado no historico, aparece na tela, e vai junto no print que voce me manda para mostrar que funcionou. Foi exatamente assim que um segredo do Google vazou aqui em agosto. Entao ele PERGUNTA.\n\nSE ALGO ESTIVER ESTRANHO ele para antes de mexer em qualquer coisa e diz PAROU POR SEGURANCA: chave colada pela metade, chave que nao parece uma chave, pasta errada, forum ainda nao instalado. Ele tambem guarda uma copia do arquivo antes de escrever.\n\nUM PERIGO QUE EU CONSERTEI ANTES DE ELE EXISTIR: o instalador do forum reescreve o arquivo de configuracao inteiro toda vez que roda. A sua chave e a unica coisa daquele arquivo que ele nao sabe fabricar, entao, na primeira vez que voce reinstalasse alguma coisa, ela sumiria em silencio e o botao desapareceria do forum sem nenhum erro. Agora ele guarda a sua chave antes e devolve depois.\n\nRODAR DE NOVO E SEGURO, e e assim que se troca a chave se um dia voce precisar.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/880. Guarda que EXECUTA o script contra uma plataforma de mentira: 12 casos verdes (a chave nunca na tela, recusa antes de pedir o segredo, cinco formas de chave estranha, troca sem duplicar linha, o resto do env inteiro, env sem quebra de linha no fim). Trava de deriva do provisionamento verde (32 casos). Prova por sabotagem: tirar o -s do read deixa vermelho o caso escrito para isso. Toca infra/ e ci/, os dois em CODEOWNERS, dentro do mandato.",
  verificado_em: "2026-09-02",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
