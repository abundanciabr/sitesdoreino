(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260904-021-o-placar-ganhou-memoria-o-que-mudou-desde-a-semana-passada",
  tipo: "entrega",
  quando: "2026-09-04",
  titulo: "O placar ganhou memória: o bloco 'o que mudou desde a semana passada' e a foto da semana",
  detalhe: "É o PR #957, o degrau 6 do plano reescrito em 03/09. Até aqui o placar "
    + "era a foto de agora; para dizer se a semana melhorou ou piorou ele "
    + "precisava lembrar onde cada número estava. A célula de medição ainda "
    + "não existe (degrau 7), então a memória é o livro:\n\n"
    + "A FOTO DA SEMANA é um registro tipo medição com um campo novo, 'foto', "
    + "uma linha 'cartão=valor; cartão=valor' com os números que tinham fonte "
    + "no dia. Quem tira a foto é a reunião de segunda (uma caixa 'tirar a foto "
    + "da semana' no passo 8, marcada de fábrica): ela entra no pedido para o "
    + "robô, e o robô grava o registro por PR, como todo registro. O livro "
    + "recusa foto torta e foto fora de medição.\n\n"
    + "O BLOCO 'O QUE MUDOU' compara o placar de agora com a foto anterior mais "
    + "recente e mostra só o que se moveu além do ruído, pintado pela direção "
    + "do cartão (subir e subiu: melhorou; descer e subiu: piorou; faixa: mudou). "
    + "Quando piorou, a ação do cartão aparece junto. Foto mais velha do que o "
    + "cartão aceita é dita como velha; o número do mês não compara entre meses "
    + "(zera no dia 1, é calendário e não queda). Sem foto nenhuma, o bloco diz "
    + "como tirar a primeira em vez de ficar vazio: é o estado de hoje.\n\n"
    + "Os cartões ganharam três campos opcionais, validados: frescor_maximo "
    + "(dias até a foto ser velha; 10 por padrão), dimensoes (por onde o número "
    + "se abre: site, turma, mês de entrada, canal; a tela que abre por "
    + "dimensão vem nos degraus 9 e 10) e ruido (diferença que não é "
    + "movimento). Preencher os cartões que têm fonte é o próximo PR, só de "
    + "cartões. A capa está com oito blocos dos nove permitidos.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/957",
  verificado_em: null,
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
