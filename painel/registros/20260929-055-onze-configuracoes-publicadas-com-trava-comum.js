(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260929-055-onze-configuracoes-publicadas-com-trava-comum",
  tipo: "medicao",
  quando: "2026-09-29",
  titulo: "Onze comandos de configuração estão disponíveis com a trava comum",
  detalhe: "As onze fontes públicas da main são byte a byte iguais aos comandos testados. Ensaios Linux sem rede provaram a espera pela trava comum antes da mutação, inclusive durante recuperação. O deploy do painel terminou. Nenhum desses comandos foi executado na VPS neste aceite.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/2356 https://github.com/abundanciabr/sitesdoreino/actions/runs/36620554167. Merge df22bf4723277119b25f087ecc00c273e8701c48; 11/11 fontes https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/ conferidas com curl.exe -fsSL e SHA256 idêntico à revisão testada; 96 testes focais Linux sem rede, 33 testes de preservação de env e oito scripts com bash -n. ci/esperar.py --entrega 2356 --so-desfecho: PUBLICADO, quatro jobs exigidos success, jobs_sem_prova []. Nenhum provisionamento foi executado na VPS.",
  verificado_em: "2026-09-29",
  precisa_do_dono: false,
  responde_a: "20260929-050-infra-serializar-configuracoes-da-vps",
  relacao: "comentario",
  tarefa: "TAR-991",
  gravidade: "verde",
  frente: "fabrica",
  area: "infra",
  aceite_funcional: {
    resultado: "PASS",
    criterio: "Cada um dos onze comandos publicados pela fonte oficial contém a guarda testada e os ensaios isolados demonstram espera e recuperação sob FD8 antes de mutações; o deploy exigido da revisão integrada concluiu sem job pendente.",
    evidencia: "curl.exe -fsSL das onze URLs raw da main e Get-FileHash SHA256: 11/11 iguais aos arquivos do PR #2356; pytest Linux sem rede 96 passed para exclusão e 33 passed para preservação de env; bash -n em oito scripts; deploy-celula 36620554167 com quatro jobs success. A verificação não executou os comandos de provisionamento na VPS.",
    revisao: "df22bf4723277119b25f087ecc00c273e8701c48",
    ambiente: "producao"
  },
  entrega: {
    pr: "https://github.com/abundanciabr/sitesdoreino/pull/2356",
    revisao: "50f95d0f788c87c34c816030c4b785e23d33e6cc",
    arvore: "010c022eb50930ea6ec47caa1ae8c3c95baa26d2",
    integracao: "df22bf4723277119b25f087ecc00c273e8701c48",
    publicacao: "PUBLICADO",
    publicacoes: ["https://github.com/abundanciabr/sitesdoreino/actions/runs/36620554167"]
  },
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();