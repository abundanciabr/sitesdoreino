'use strict';
window.iniciarJornada = (scope = document, host = {}) => {
  const root = scope.getElementById('inicio-jornada');
  if (!root) return;
  const $ = id => scope.getElementById(`inicio-${id}`);
  const forms = {motivo: $('form-motivo'), plano: $('form-plano'), criacao: $('form-criacao'), item: $('form-item')};
  const dirty = new Set();
  let data = null;
  let busy = false;
  let motivoStep = 1;
  const motivoReturnLabel = () => data?.inicio.etapas?.some(etapa => etapa.etapa === 1 && etapa.xp_recebido > 0) ? 'Voltar' : 'Depois eu faço isso';
  const embedded = Boolean(host.close);
  const lifecycle = new AbortController();
  const navigate = destination => host.navigate ? host.navigate(destination) : window.location.assign(destination);
  function showMotivoStep(step, focus = false) {
    motivoStep = step;
    if (!$('motivo-escolha')) return;
    $('motivo-escolha').hidden = step !== 1;
    $('motivo-reflexao').hidden = step !== 2;
    $('motivo-contagem').textContent = `Etapa ${step} de 2`;
    if (focus) $(step === 1 ? 'motivo-escolha-titulo' : 'motivo-reflexao-titulo').focus();
  }
  function otherMotivo() {
    if ($('outro-campo')) $('outro-campo').hidden = !root.querySelector('input[name="motivo"][value="outro"]:checked');
  }
  async function leaveMotivo() {
    if (busy) return;
    if (dirty.size && !await save(forms.motivo, 'inicio-motivo', {concluir: 'nao', motivo_etapa: String(motivoStep)})) return;
    if (embedded) host.close();
    else navigate('/trilha/');
  }
  const date = value => new Date(value).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'});
  const announce = (message, error = false) => {
    $('status').textContent = message;
    $('status').dataset.erro = String(error);
  };
  const files = () => data.anexos.filter(file => file.passo === 2);
  const setBusy = value => {
    busy = value;
    root.setAttribute('aria-busy', String(value));
    root.querySelectorAll('button, input, textarea, select').forEach(control => { control.disabled = value; });
  };
  function fileCard(file, index, total) {
    const article = document.createElement('article');
    article.className = 'inicio-arquivo-cartao';
    if (file.previa) {
      const img = document.createElement('img');
      img.src = file.previa;
      img.alt = `Minha criação: ${file.nome}`;
      img.loading = 'lazy';
      img.addEventListener('error', () => { img.hidden = true; });
      article.append(img);
    } else {
      const icon = document.createElement('div');
      icon.className = 'inicio-modelo';
      icon.textContent = '◇';
      icon.setAttribute('aria-hidden', 'true');
      article.append(icon);
    }
    const small = document.createElement('small');
    small.textContent = `Registro ${total - index} · ${date(file.criado_em)}`;
    const link = document.createElement('a');
    link.href = file.url;
    link.textContent = file.nome;
    link.setAttribute('download', '');
    article.append(small, link);
    for (const [field, label] of [['aprendi', 'O que percebi'], ['duvida', 'Minha dúvida']]) {
      if (!file[field]) continue;
      const p = document.createElement('p');
      const strong = document.createElement('strong');
      strong.textContent = `${label}: `;
      p.append(strong, document.createTextNode(file[field]));
      article.append(p);
    }
    return article;
  }
  function render() {
    const start = data.inicio;
    if (forms.motivo) {
      for (const id of ['motivo-depois-1', 'motivo-depois-2']) {
        if ($(id)) $(id).textContent = `← ${motivoReturnLabel()}`;
      }
    }
    const savedFiles = files();
    const completed = data.etapas.some(etapa => etapa.ordem === 2 && etapa.alcancada);
    if ($('confirmacao')) $('confirmacao').textContent = start.confirmado_em ? `Compromisso assumido em ${date(start.confirmado_em)}. Você pode revisá-lo aqui.` : 'O rascunho fica guardado; você assume o compromisso quando fizer sentido para você.';
    if (forms.criacao) {
      $('objetivo-salvo').textContent = start.objetivo ? `Minha criação: ${start.objetivo}` : 'Escolha uma pequena criação para começar.';
      $('pratica').textContent = start.pratica;
      $('apoio-texto').textContent = ({guiado: 'Comece pela forma principal. Se travar, prepare uma dúvida para pedir orientação.', autonomo: 'Tente uma versão com o que já sabe. Depois escolha um ajuste.', desafio: 'Experimente uma segunda versão com uma mudança intencional e observe o que aprendeu.'})[start.apoio];
      $('criacao-estado').textContent = start.item_pronto ? 'Você já marcou sua criação como pronta. Pode continuar quando quiser.' : 'Quando sua peça estiver pronta, confirme abaixo.';
    }
    if (!forms.item) return;
    $('enviar').textContent = completed ? 'Enviar uma nova versão' : savedFiles.length ? 'Confirmar meu envio e concluir' : 'Enviar meu 3D e concluir';
    $('item-estado').textContent = completed
      ? 'Envio concluído. Seu arquivo está guardado em privado. Novas versões preservam os registros anteriores.'
      : savedFiles.length
        ? 'Seu arquivo anterior continua guardado. Você pode confirmar esse envio ou escolher uma nova versão.'
        : 'O envio só acontece quando você confirma no botão acima.';
    $('historico').hidden = !savedFiles.length;
    $('versoes').replaceChildren();
    if (savedFiles.length) {
      const title = document.createElement('h3');
      title.textContent = 'Minha evolução · da versão mais recente à primeira';
      const grid = document.createElement('div');
      grid.className = 'inicio-grade-versoes';
      savedFiles.forEach((file, index) => grid.append(fileCard(file, index, savedFiles.length)));
      $('versoes').append(title, grid);
    }
  }
  function fill() {
    if (forms.motivo) {
      $('opcoes').replaceChildren();
      data.inicio.motivos.forEach(motivo => {
        const label = document.createElement('label');
        label.className = 'inicio-motivo';
        const radio = document.createElement('input');
        radio.type = 'radio'; radio.name = 'motivo'; radio.value = motivo.valor;
        radio.checked = motivo.valor === data.inicio.motivo;
        const text = document.createElement('span');
        text.textContent = motivo.nome;
        label.append(radio, text);
        $('opcoes').append(label);
      });
      forms.motivo.elements.motivo_pessoal.value = data.inicio.motivo_pessoal || '';
      if (forms.motivo.elements.motivo_outro) forms.motivo.elements.motivo_outro.value = data.inicio.motivo_outro || '';
      otherMotivo();
      showMotivoStep(data.inicio.motivo_etapa === 2 ? 2 : 1);
    }
    if (forms.plano) {
      ['sonho', 'objetivo', 'quando', 'obstaculo', 'plano_b', 'compromisso', 'apoio'].forEach(key => {
        forms.plano.elements[key].value = data.inicio[key] || '';
      });
    }
  }
  async function request(body) {
    const response = await fetch(root.dataset.api, {method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', headers: body ? {'X-CSRFToken': data.csrf} : {}, ...(body ? {body} : {})});
    const hidePrivateContent = () => { $('conteudo').hidden = true; $('comparacao')?.remove(); };
    if (response.status === 401 || response.status === 403) hidePrivateContent();
    let result;
    try { result = await response.json(); } catch (_) { throw new Error('Não foi possível salvar ou abrir seu registro agora. Suas respostas continuam nesta tela. Tente novamente.'); }
    if (!response.ok) throw new Error(result.detail || 'Não foi possível salvar agora. Suas respostas continuam nesta tela.');
    if (data && (data.pessoa_id !== result.pessoa_id || data.site_id !== result.site_id)) {
      hidePrivateContent();
      throw new Error('Sua conta mudou. Entre novamente na conta em que começou e reabra esta página.');
    }
    return result;
  }
  async function open() {
    if (busy) return;
    setBusy(true);
    try {
      const result = await request();
      if (data && dirty.size) {
        // A consulta explícita mostra a cópia atual sem substituir o rascunho na tela.
        let comparison = $('comparacao');
        if (!comparison) {
          comparison = document.createElement('details'); comparison.id = 'inicio-comparacao'; comparison.className = 'inicio-detalhes';
          $('status').after(comparison);
        }
        comparison.replaceChildren(); comparison.open = true;
        const heading = document.createElement('summary'); heading.textContent = 'Versão salva na sua conta'; comparison.append(heading);
        const fields = forms.motivo ? [['motivo', 'Caminho'], ['motivo_outro', 'Outro motivo'], ['motivo_pessoal', 'Motivo pessoal']] : forms.plano ? [['objetivo', 'Objetivo'], ['quando', 'Próximo passo'], ['sonho', 'Sonho'], ['obstaculo', 'Dificuldade'], ['plano_b', 'Plano alternativo'], ['compromisso', 'Compromisso'], ['apoio', 'Apoio']] : [];
        for (const [key, label] of fields) {
          const p = document.createElement('p'); p.textContent = `${label}: ${result.inicio[key] || 'Ainda não preenchido'}`; comparison.append(p);
        }
        data = result;
        render();
        if (forms.item) {
          const p = document.createElement('p');
          p.textContent = 'Os arquivos e as notas salvos agora aparecem no histórico abaixo. Seu arquivo selecionado e suas notas continuam no formulário.';
          comparison.append(p);
        }
        announce('Sua versão salva está abaixo. Suas respostas continuam nos campos; revise-as antes de salvar novamente.');
      } else {
        data = result; fill(); render();
        announce(data.inicio.salvo_em ? `Salvo na sua conta em ${date(data.inicio.salvo_em)}. Continue de onde parou.` : 'Comece com o que faz sentido para você hoje.');
      }
      $('conteudo').hidden = false;
      if (forms.criacao && data.inicio.item_pronto && location.hash === '#inicio-form-item') {
        navigate(root.dataset.envio);
      }
      if (!dirty.size && forms.item && ['#inicio-form-item', '#inicio-item'].includes(location.hash)) {
        document.getElementById(location.hash.slice(1)).scrollIntoView({block: 'start'});
      }
      $('recarregar').hidden = true;
    } catch (error) {
      announce(error.message, true); $('recarregar').hidden = false;
    } finally { setBusy(false); }
  }
  async function save(form, action, extras = {}) {
    if (busy || !data) return false;
    const body = new FormData(form);
    body.set('acao', action); body.set('revisao', String(data.revisao));
    body.set('contexto_pessoa', data.pessoa_id); body.set('contexto_site', data.site_id);
    Object.entries(extras).forEach(([key, value]) => body.set(key, value));
    setBusy(true); announce('Guardando na sua conta…');
    try {
      data = await request(body);
      dirty.delete(form.id);
      render();
      $('recarregar').hidden = true;
      $('comparacao')?.remove();
      announce('Salvo na sua conta. Você pode sair e retomar quando quiser.');
      return true;
    } catch (error) {
      announce(error.message, true);
      $('recarregar').textContent = 'Conferir versão salva'; $('recarregar').hidden = false;
      return false;
    } finally { setBusy(false); }
  }
  root.querySelectorAll('a').forEach(link => link.addEventListener('click', event => { if (busy) { event.preventDefault(); announce('Seu registro está sendo guardado. Aguarde um instante.'); } }));
  Object.values(forms).filter(Boolean).forEach(form => form.addEventListener('input', () => { dirty.add(form.id); announce(forms.motivo ? `Você pode continuar ou usar “${motivoReturnLabel()}” para guardar e voltar à faixa.` : 'Há alterações nesta tela. Use o botão de salvar para retomá-las depois.'); }));
  forms.motivo?.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    if ($('motivo-escolha') && motivoStep === 1) {
      if (!new FormData(forms.motivo).get('motivo')) { announce('Escolha seu motivo para continuar.', true); return; }
      if (await save(forms.motivo, 'inicio-motivo', {concluir: 'nao', motivo_etapa: '2'})) {
        showMotivoStep(2, true);
        announce('Agora, se quiser, conte por que esse motivo é importante para você.');
      }
      return;
    }
    const concluir = event.submitter?.value === 'pausar' ? 'nao' : 'sim';
    if (await save(forms.motivo, 'inicio-motivo', {concluir, motivo_etapa: '1'})) {
      let destination = concluir === 'sim' ? data.conquista_url || root.dataset.conquistas : root.dataset.conquistas;
      if (embedded && data.conquista_url && concluir === 'sim') destination += (destination.includes('?') ? '&' : '?') + 'embutido=1';
      navigate(destination);
    }
  });
  forms.plano?.addEventListener('submit', async event => {
    event.preventDefault();
    const assumir = event.submitter?.value || 'nao';
    if (await save(forms.plano, 'inicio-plano', {assumir})) navigate(assumir === 'sim' ? data.conquista_url || root.dataset.conquistas : root.dataset.conquistas);
  });
  forms.criacao?.addEventListener('submit', async event => {
    event.preventDefault();
    if (await save(forms.criacao, 'inicio-item')) navigate(data.conquista_url || root.dataset.conquistas);
  });
  $('sugestao')?.addEventListener('click', () => {
    if (forms.plano.elements.compromisso.value.trim()) {
      announce('Seu compromisso já tem suas palavras. Você pode editá-lo diretamente; a sugestão aparece quando o campo está vazio.'); return;
    }
    const objective = forms.plano.elements.objetivo.value.trim().replace(/[.!?]+$/, '');
    const when = forms.plano.elements.quando.value.trim().replace(/[.!?]+$/, '');
    forms.plano.elements.compromisso.value = `Meu próximo objetivo: ${objective || 'criar meu primeiro item 3D'}.${when ? ` Vou reservar este momento: ${when}.` : ''} Vou guardar minhas tentativas, pedir ajuda quando precisar e ajustar meu ritmo para continuar.`;
    dirty.add(forms.plano.id);
    forms.plano.elements.compromisso.focus();
    announce('Esta é uma sugestão. Edite com suas palavras e salve quando fizer sentido.');
  });
  forms.item?.addEventListener('submit', async event => {
    event.preventDefault();
    const file = $('arquivo').files[0];
    if (!file && !files().length) { announce('Escolha um arquivo do seu item ou uma imagem dele para enviar.', true); return; }
    if (file && file.size > 20 * 1024 * 1024) { announce('Escolha um arquivo de até 20 MB.', true); return; }
    if (!file && ($('aprendi').value.trim() || $('duvida').value.trim())) { announce('Para guardar estas notas, escolha o arquivo da nova versão. Seus registros anteriores continuam guardados.', true); return; }
    const count = files().length;
    const hasNotes = Boolean($('aprendi').value.trim() || $('duvida').value.trim());
    if (await save(forms.item, 'inicio-envio', {passo: '2', estado: 'feito'})) {
      forms.item.reset();
      announce(files().length === count ? (hasNotes ? 'Envio confirmado. Suas notas foram atualizadas e o arquivo foi preservado.' : 'Envio confirmado. Seu arquivo continua guardado em privado.') : 'Envio concluído. Seu 3D está guardado em privado e sua conquista foi registrada.');
      if (data.conquista_url) navigate(data.conquista_url);
    }
  });
  $('pedir-ajuda')?.addEventListener('click', () => {
    if ($('ajuda').hidden) {
      const lastDoubt = files().find(file => file.duvida)?.duvida;
      if (!$('mensagem').value) $('mensagem').value = `Estou praticando modelagem 3D.${data.inicio.objetivo ? ` Meu objetivo é: ${data.inicio.objetivo}` : ''}\n\n${lastDoubt ? `Minha dúvida é: ${lastDoubt}` : 'Minha dúvida é: '}\n\nO que já tentei: `;
      $('ajuda').hidden = false; $('pedir-ajuda').setAttribute('aria-expanded', 'true');
    }
    $('mensagem').focus();
  });
  $('copiar')?.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText($('mensagem').value); announce('Pedido copiado. Você decide se quer publicá-lo no Fórum.'); }
    catch (_) { $('mensagem').focus(); $('mensagem').select(); announce('Selecione e copie o pedido acima para compartilhar quando quiser.'); }
  });
  forms.motivo?.addEventListener('change', otherMotivo);
  for (const id of ['motivo-depois-1', 'motivo-depois-2']) $(id)?.addEventListener('click', leaveMotivo);
  $('motivo-anterior')?.addEventListener('click', () => {
    if (busy) return;
    showMotivoStep(1, true); dirty.add(forms.motivo.id);
  });
  $('recarregar').addEventListener('click', open);
  window.addEventListener('beforeunload', event => { if (dirty.size) { event.preventDefault(); event.returnValue = ''; } }, {signal: lifecycle.signal});
  window.addEventListener('pageshow', event => { if (event.persisted) open(); }, {signal: lifecycle.signal});
  open();
  return {close: leaveMotivo, destroy: () => lifecycle.abort()};
};
window.iniciarJornada();
