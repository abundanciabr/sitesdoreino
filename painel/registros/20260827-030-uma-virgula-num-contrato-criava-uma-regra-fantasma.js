(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-030-uma-virgula-num-contrato-criava-uma-regra-fantasma",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Uma vírgula sem aspas fazia um contrato do sistema descrever uma regra que não existe",
  detalhe: "Este registro paga uma dívida do livro: um trabalho entrou na plataforma hoje e ninguém tinha te contado. Achei ao conferir a porta do merge, que se recusou a mergear enquanto isso não fosse contado — a trava funcionou.\n\nO QUE ERA: os “contratos” são os acordos escritos entre as partes do sistema — o documento que diz o que uma parte promete responder à outra. Num deles, uma frase de descrição estava sem aspas, e uma vírgula no meio da frase fez o computador ler metade da frase como se fosse uma REGRA NOVA, inventada. O arquivo continuava válido aos olhos de qualquer verificador; o acordo é que tinha virado bobagem.\n\nPOR QUE IMPORTA: quem fosse programar a parte que obedece a esse acordo só conseguiria ficar verde reproduzindo a bobagem — publicando a regra fantasma para todo mundo que dependesse dela. A alternativa era ficar vermelho para sempre. O conserto foi uma linha: as aspas de volta.\n\nA LIÇÃO ficou guardada como armadilha do projeto (vírgula dentro de chaves, em YAML, separa entradas — texto sem aspas vira chave nova), para o próximo robô não repetir.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/302 — MERGED em 27/08/2026 18:06 UTC; muda uma linha de contracts/alunos.openapi.yaml (aspas na descrição do 422). Registro escrito depois, ao pagar a dívida do livro que a porta do merge cobrou.",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
