(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-029-a-trava-de-numero-repetido-ja-existia",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "A trava contra número repetido no livro já existia — só faltava estar escrita onde dá para achar",
  detalhe: "Uma sessão, trabalhando em outra tarefa, viu três colisões seguidas de número de registro em poucos minutos (duas sessões diferentes escolhendo o mesmo número do dia, ao mesmo tempo) e sugeriu investigar se existia alguma trava automática contra isso — ou se precisava construir uma.\n\nInvestiguei antes de construir qualquer coisa nova, e a trava JÁ EXISTIA, completa: nasceu em 26/08/2026 (registro 20260826-041), depois de exatamente essa mesma corrida ter acontecido quatro vezes num único dia. Ela mora em painel/logica.js, tem quatro testes próprios dedicados só a ela, e roda automaticamente em TODO PR — quem tentar gravar dois registros com o mesmo número no mesmo dia recebe uma recusa que já diz para qual número renomear. Nada precisou ser construído.\n\nO que estava faltando era mais simples: essa trava não estava mencionada no documento que qualquer sessão lê antes de registrar algo (painel/LEIA-ME.md) — só um comentário dentro do código, que uma sessão apressada não vai ler. Por isso a sessão anterior não sabia que a rede de segurança já existia, e descobriu a corrida do jeito manual (olhando a pasta com os próprios olhos) em vez de deixar o sistema avisar sozinho.\n\nO CONSERTO foi só documentação: acrescentei ao LEIA-ME.md a explicação de que essa trava existe, desde quando, e o que fazer se ela disparar. Não criei trava nova, teste novo nem lógica nova — teria sido uma cópia do que já funciona, e este livro tem uma regra dura contra um mesmo fato morar em dois lugares.\n\nA PROVA veio sozinha, sem eu precisar montar cenário nenhum: enquanto este próprio registro estava sendo escrito, outras DUAS sessões pegaram o mesmo número que eu, uma atrás da outra — primeiro o '027', depois, já eu tendo trocado, o '028' de novo. As duas vezes, ao atualizar meu trabalho com o que tinha chegado de novo (o passo de rotina que toda sessão faz), a trava recusou gravar e me mandou trocar de número, até sobrar o '029' — o número deste registro. Ou seja: no meio do trabalho de dizer 'essa trava existe', ela pegou DUAS colisões de verdade, ao vivo, na frente dos meus olhos.\n\nNADA disto pede a sua atenção: é ajuste de um documento interno para robôs, os 68 testes do painel continuam todos verdes, e nenhuma tela ou comportamento do site mudou.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/320",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
