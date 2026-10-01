(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-044-a-medicao-que-faltou-no-registro-anterior",
  tipo: "medicao",
  quando: "2026-08-26",
  titulo: "A medição que faltou no registro anterior — feita agora, e o veredito continua o mesmo",
  detalhe: "Correção de método, não de conclusão. No registro 042 eu disse que a falha de conexão com o servidor era 'entre a nuvem e a máquina' — e disse isso SEM ter feito a medição que o próprio projeto exige para separar os dois casos possíveis.\n\nA medição existe, está escrita na memória de campo desde hoje de manhã, e é uma linha só: perguntar direto ao servidor se a porta de conexão está viva. Rodei agora. Ela respondeu, identificando-se normalmente. Isso confirma o diagnóstico: a máquina está viva e alcançável daqui; o que falha é o caminho entre o robô da nuvem e ela. Uma repetição resolve, que foi o que aconteceu.\n\nPOR QUE REGISTRO UMA CORREÇÃO QUE NÃO MUDA O RESULTADO: porque acertar por sorte e acertar por medição são a mesma coisa no papel e coisas opostas na prática. Se o veredito tivesse sido o outro, eu teria reportado a você um diagnóstico errado com a mesma confiança.\n\nUMA TENSÃO QUE DEIXO ANOTADA PARA QUEM VIER: o projeto tem duas réguas para esta mesma falha, e elas não dizem a mesma coisa. Uma conta episódios ('três numa semana viram estrutura') — e por ela as quatro de hoje já seriam estrutura. A outra manda medir, e diz que enquanto o servidor responder é blip, com o limite em três repetições vermelhas seguidas (hoje foi uma, e passou). Segui a segunda, que é mais nova e nasceu exatamente deste fenômeno. Quem revisitar decide se as duas continuam convivendo.",
  autoridade: "sonda",
  evidencia: "medição feita do PC em 26/08/2026: a porta 22 de 217.196.62.220 respondeu 'SSH-2.0-OpenSSH_9.6p1 Ubuntu-3' (exit 0), o teste prescrito por armadilhas/127 para separar blip de causa estrutural (armadilhas/017); o deploy do PR 260 passou em uma repetição, e o site respondeu 200 durante toda a falha",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260826-042-a-vps-recusou-o-robo-pela-quarta-vez-hoje",
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
