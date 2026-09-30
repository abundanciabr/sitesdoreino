(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260929-081-sincronizacao-da-ponte-conferida-na-vps",
  tipo: "medicao",
  quando: "2026-09-29",
  titulo: "Ponte e infraestrutura: execução oficial conferida na VPS",
  detalhe: "Aceite restrito à TAR-987. O mantenedor confirmou o kit root verificado; a execução oficial da revisão integrada sincronizou a infraestrutura, conferiu os serviços, os sites e a entrada privada. A segunda e a terceira tentativas internas foram puladas. Não houve ensaio de disputa entre mutadores de negócio na VPS; a cobertura completa da frente PME08 continua separada.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/2350; https://github.com/abundanciabr/sitesdoreino/actions/runs/36634787768. Resposta do mantenedor call_Lx2KUDZDNIrZDkGU5fhBtd6v: KIT-ROOT-VERIFICADO, kit SHA256 18199D6A5B7DCF718C58251FAF455CC24121A32C68E2C92E823C286DA508DA5B. Run 36634787768 tentativa 2, job sincronizar 109639220918 success; INICIADA, PONTE ja esta como se quer, backup datado, serviços, sites e entrada privada OK, CONCLUIDA. Nenhum provisionador de negócio foi executado nesta medição.",
  verificado_em: "2026-09-29",
  precisa_do_dono: false,
  responde_a: "20260929-073-infra-sincronizar-a-ponte-com-trava-comum",
  relacao: "comentario",
  tarefa: "TAR-987",
  gravidade: "verde",
  frente: "fabrica",
  area: "infra",
  aceite_funcional: {
    resultado: "PASS",
    criterio: "A revisão integrada da TAR-987 executa a sincronização oficial na VPS com kit root confirmado, termina com sentinela CONCLUIDA e confere serviços, sites e entrada privada. A prova de produção cobre esta sincronização; não afirma disputa real de provisionadores de negócio na VPS nem o encerramento da PME08.",
    evidencia: "https://github.com/abundanciabr/sitesdoreino/actions/runs/36634787768: tentativa 2 do run, job sincronizar 109639220918 success, SINCRONIZACAO-INICIADA 20260929T215927Z, PONTE ja esta como se quer, backup docker-compose.yml.bak-20260929T215928Z e traefik.bak-20260929T215928Z, serviços/sites/entrada privada OK, SINCRONIZACAO-CONCLUIDA 20260929T215928Z. Kit root SHA256 18199D6A5B7DCF718C58251FAF455CC24121A32C68E2C92E823C286DA508DA5B confirmado pelo mantenedor; bloqueio concorrente verificado em Linux isolado no incremento, sem executar mutadores de negócio na VPS.",
    revisao: "6c10da517bfa7a31f6812a7177f0cfb3e48c7785",
    ambiente: "producao"
  },
  entrega: {
    pr: "https://github.com/abundanciabr/sitesdoreino/pull/2350",
    revisao: "bf24a41891801794ddf98ed9af6114063836e50d",
    arvore: "7795b2f7872d0302cf5d911953dd1f2ba521e03a",
    integracao: "6c10da517bfa7a31f6812a7177f0cfb3e48c7785",
    publicacao: "PUBLICADO",
    publicacoes: ["https://github.com/abundanciabr/sitesdoreino/actions/runs/36634787768"]
  }
}); })();
