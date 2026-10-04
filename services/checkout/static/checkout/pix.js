// static/checkout/pix.js  [RECEITA:R6 v1] — SÓ Pix. Nada de cartão aqui (INV-P9).
// [INV-P7] Nenhuma transição local para "pago": o único jeito deste arquivo saber
// que o pedido foi pago é o GET /pedidos/{id} responder status="pago".
const PIX_COPIADO = "Código copiado. Cole no app do seu banco, na opção Pix Copia e Cola.";
const PIX_NAO_COPIADO = "Não deu para copiar sozinho. Toque e segure o código acima para copiar.";

function pixIsland() {
  return {
    orderId: JSON.parse(document.getElementById("order-id").textContent),
    qr: JSON.parse(document.getElementById("pix-data").textContent) || {},
    pixTrocado: JSON.parse(document.getElementById("pix-trocado").textContent),
    codigoAntigo: "",
    status: "aguardando_pagamento",
    aviso: "",

    async init() {
      await this.poll();
    },

    async poll() {
      try {
        const pedido = await api.get(`/pedidos/${this.orderId}`);
        this.status = pedido.status; // [INV-P7] única fonte de status
        if (pedido.pix?.qr_code && pedido.pix.qr_code !== this.qr.qr_code) {
          this.codigoAntigo = this.qr.qr_code || "";
          this.qr = pedido.pix;
          this.pixTrocado = true;
        }
      } catch (e) {
        // rede falhou nesta rodada; tenta de novo no próximo ciclo
      }
      if (this.status === "aguardando_pagamento") {
        setTimeout(() => this.poll(), 3000);
      }
    },

    // O código só serve enquanto o pedido espera o pagamento: pago, vencido ou
    // recusado, a tela não pode seguir mostrando um código para pagar.
    pagavel() {
      return this.status === "aguardando_pagamento";
    },

    prazo() {
      const fim = new Date(this.qr.expires_at || "");
      if (Number.isNaN(fim.getTime())) return "";
      const fuso = { timeZone: "America/Sao_Paulo" };
      const dia = fim.toLocaleDateString("pt-BR", { ...fuso, day: "2-digit", month: "2-digit" });
      const hora = fim.toLocaleTimeString("pt-BR", { ...fuso, hour: "2-digit", minute: "2-digit" });
      if (Date.now() > fim.getTime()) {
        // O aviso de vencimento pode chegar depois do prazo: quem pagou no
        // último minuto não pode ser convidado a pagar de novo.
        return `Este código venceu em ${dia} às ${hora} (horário de Brasília). Se você já pagou, a confirmação aparece aqui.`;
      }
      return `Pague até ${dia} às ${hora} (horário de Brasília).`;
    },

    statusLabel() {
      return (
        {
          aguardando_pagamento: "Aguardando confirmação do pagamento…",
          pago: "Pagamento confirmado!",
          expirado: "Este código Pix venceu. Faça um novo pedido para pagar.",
          recusado: "Pagamento recusado. Faça um novo pedido para tentar de novo.",
          reembolsado: "Pagamento reembolsado.",
        }[this.status] ?? this.status
      );
    },

    async copiar() {
      const codigo = this.qr.qr_code || "";
      if (!codigo) return;
      try {
        await navigator.clipboard.writeText(codigo);
        this.aviso = PIX_COPIADO;
        return;
      } catch (_) {
        // Navegador dentro de app (Instagram, Facebook) e Android antigo não
        // têm navigator.clipboard ou recusam o pedido: segue o caminho antigo.
      }
      if (this.copiarPeloCampo(codigo)) {
        this.aviso = PIX_COPIADO;
        return;
      }
      this.selecionarCodigo();
      this.aviso = PIX_NAO_COPIADO;
    },

    copiarPeloCampo(codigo) {
      let campo = null;
      try {
        campo = document.createElement("textarea");
        campo.value = codigo;
        campo.setAttribute("readonly", "");
        campo.style.position = "fixed";
        campo.style.opacity = "0";
        document.body.appendChild(campo);
        campo.select();
        campo.setSelectionRange(0, codigo.length);
        return document.execCommand("copy") === true;
      } catch (_) {
        return false;
      } finally {
        campo?.remove();
      }
    },

    selecionarCodigo() {
      try {
        const faixa = document.createRange();
        faixa.selectNodeContents(document.querySelector(".copia code"));
        const selecao = window.getSelection();
        selecao.removeAllRanges();
        selecao.addRange(faixa);
      } catch (_) {
        // Sem seleção possível, o aviso ainda explica como copiar à mão.
      }
    },
  };
}
