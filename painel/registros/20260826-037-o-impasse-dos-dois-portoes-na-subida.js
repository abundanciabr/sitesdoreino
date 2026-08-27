(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-037-o-impasse-dos-dois-portoes-na-subida",
  tipo: "incidente",
  quando: "2026-08-26",
  titulo: "Na hora de subir, duas travas boas se trancaram uma na outra — e nada quebrou",
  detalhe: "A primeira tentativa de subir a peça nova ficou vermelha, e vale contar porque o motivo é curioso: NENHUMA das duas travas estava errada.\n\nO QUE ACONTECEU: subir uma peça nova envolve duas entregas ao servidor — a lista de peças (que diz que ela existe) e a peça em si. As duas foram disparadas ao mesmo tempo. A peça chegou primeiro, procurou o próprio nome na lista do servidor, não achou, e parou — corretamente, porque a alternativa seria mandar reiniciar a plataforma inteira. E aí a entrega da LISTA viu que algo tinha ficado vermelho e se recusou a continuar — também corretamente, porque a regra é não avançar com alarme aceso.\n\nResultado: cada uma esperando a outra, e repetir não resolvia — o problema e a solução estavam no mesmo pacote.\n\nA SAÍDA foi entregar a lista sozinha, num pacote separado, e só então repetir a peça. Funcionou de primeira.\n\nNADA QUEBROU E NINGUÉM VIU: a plataforma continuou respondendo o tempo todo. O que ficou vermelho foi a subida da peça nova, que ainda não estava sendo usada por ninguém.\n\nO QUE FIZ ALÉM DE RESOLVER: escrevi a regra no lugar onde o próximo robô vai olhar — dentro do próprio arquivo da lista — e uma entrada completa na memória da casa, inclusive com o atalho errado que alguém poderia ser tentado a usar (desligar a trava que reclamou). Aquele atalho resolveria hoje e cegaria a plataforma para sempre.",
  autoridade: "github",
  evidencia: "Runs 33029073463 (deploy-celula, 'não tem serviço algum em docker-compose.yml') e 33029073525 (deploy-infra, 'vermelhos-nao-previstos'); destravado pelo PR #252 (só o compose) e pelo rerun do primeiro, ambos verdes; armadilhas/134",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
