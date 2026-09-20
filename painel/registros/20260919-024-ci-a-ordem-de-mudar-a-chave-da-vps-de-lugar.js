(function(){(window.REGISTROS=window.REGISTROS||[]).push({
arquivo: "20260919-024-ci-a-ordem-de-mudar-a-chave-da-vps-de-lugar",
tipo: "decisao",
quando: "2026-09-19",
titulo: "A chave da VPS vai para um ambiente que so aceita a main, nesta ordem",
detalhe: "Dezesseis dos vinte e cinco programas do GitHub abrem conexao com o servidor, e treze nao conferiam nada antes. O PR 1738 poe neles a recusa de disparo por ramo que nao seja a main. Em 18/09 o robo parou e avisou que esse passo mora no proprio ramo, entao quem empurra um ramo apaga o passo no mesmo empurrao, e que so um ambiente do GitHub com trava de branch fecha isso de verdade.\n\nVoce concordou e deu a ordem: primeiro o PR faz os dezessete trabalhos citarem o ambiente vps; depois voce cria esse ambiente com a trava na main e a chave dentro; so entao apaga a chave antiga, com uma publicacao de verdade verde no meio.\n\nEntre o primeiro passo e o segundo nada quebra, e isso foi medido, nao suposto. O ambiente ainda nao existe, e o GitHub cria sozinho um ambiente citado que falta, sem regra e sem chave propria: a chave continua vindo de onde vem hoje e nenhum trabalho fica esperando aprovacao. As execucoes ja feitas desses dezesseis programas sairam todas da main, entao a trava nao tira nada do seu uso normal.",
autoridade: "mantenedor",
evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1738",
verificado_em: "2026-09-19",
precisa_do_dono: false,
responde_a: null,
gravidade: "info",
area: "ci"
});})();
