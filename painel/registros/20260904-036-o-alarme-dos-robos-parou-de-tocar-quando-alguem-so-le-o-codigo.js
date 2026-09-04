(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260904-036-o-alarme-dos-robos-parou-de-tocar-quando-alguem-so-le-o-codigo",
  tipo: "entrega",
  quando: "2026-09-04",
  titulo: "O alarme que protege os robôs parou de tocar quando alguém só lê o código, e continua tocando na falha de verdade",
  detalhe: "Tarefa TAR-048 da fila. O sino reconhece uma falha conhecida pela frase que ela imprime, "
    + "e por isso tocava também quando um robô só LIA o arquivo que escreve aquela frase: 43 das 81 "
    + "assinaturas apareciam em 205 arquivos comuns do projeto, e ler qualquer um deles disparava o "
    + "alarme (aconteceu quatro vezes num dia em 30/08). O PR #972 ensina o sino a distinguir ler de "
    + "executar: só cala quando o comando inteiro é leitura; qualquer execução no meio mantém o alarme "
    + "ligado (provado em 13 formas). Depois: 0 de 205 leituras tocam. Toca ci/, caminho protegido: "
    + "mandato é o despacho do lote de 03/09/2026. Vale em cada máquina no próximo refresh da pasta "
    + "principal. Nada depende de ninguém.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/972",
  verificado_em: "2026-09-04",
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
