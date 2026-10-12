(() => {
  'use strict';
  const base = '/checkout/curso-primeiros-passos-no-blender/producao';
  const status = document.getElementById('homologacao-estado');
  const check = document.getElementById('homologacao-conferir');
  let started = false;
  // Only connection and installment calculation: no customer or payment request.
  document.querySelectorAll('form').forEach(form => form.addEventListener('submit', event => {
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true));
  async function conference() {
    check.disabled = true;
    try {
      const response = await fetch(base + '/conferencia', { cache: 'no-store' });
      const result = await response.json();
      status.textContent = result.mensagem || 'A instalação ainda precisa ser concluída.';
      if (!response.ok || !result.instalacao_concluida || started) return;
      if (result.scriptURL !== 'https://scripts.appmax.com.br/appmax.min.js' || !result.externalId) return;
      started = true;
      const script = document.createElement('script');
      script.src = result.scriptURL;
      script.onload = () => {
        try {
          window.AppmaxScripts.init({
            externalId: result.externalId,
            onIp: () => { status.textContent = 'Appmax JS de produção conectado; credenciais e parcelas conferidas. Nenhuma cobrança.'; },
            onError: () => { status.textContent = 'Credenciais conferidas; a conexão do Appmax JS ainda precisa ser verificada. Pagamentos desativados.'; },
          });
        } catch (_) {
          status.textContent = 'Não foi possível iniciar o Appmax JS de produção. Pagamentos desativados.';
        }
      };
      script.onerror = () => { status.textContent = 'Não foi possível carregar o Appmax JS de produção. Pagamentos desativados.'; };
      document.head.appendChild(script);
    } catch (_) {
      status.textContent = 'Não foi possível consultar a instalação agora. Nenhuma cobrança.';
    } finally {
      check.disabled = false;
    }
  }
  check.addEventListener('click', conference);
  conference();
})();
