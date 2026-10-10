(() => {
  'use strict';
  const root = document.getElementById('inicio-jornada');
  if (!root) return;
  const $ = id => document.getElementById(`inicio-${id}`);
  const forms = {motivo: $('form-motivo'), plano: $('form-plano'), item: $('form-item')};
  const dirty = new Set();
  let data = null;
  let busy = false;
  let current = 1;
  const date = value => new Date(value).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'});
  const announce = (message, error = false) => {
    $('status').textContent = message;
    $('status').dataset.erro = String(error);
  };
  const files = () => data.anexos.filter(file => file.passo === 2);
  const setBusy = value => {
    busy = value;
    root.setAttribute('aria-busy', String(value));
    root.querySelectorAll('button').forEach(button => { button.disabled = value; });
  };
  function step(number, focus = true) {
    current = number;
    root.querySelectorAll('[data-painel]').forEach(panel => { panel.hidden = Number(panel.dataset.painel) !== number; });
    root.querySelectorAll('.inicio-passos button').forEach(button => {
      if (Number(button.dataset.passo) === number) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });
    $('proximo').hidden = number === 1;
    if (focus) root.querySelector(`[data-painel="${number}"] h2`).focus({preventScroll: true});
  }
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
    const savedFiles = files();
    const completed = data.etapas.some(etapa => etapa.ordem === 2 && etapa.alcancada);
    root.querySelector('[data-resumo="1"]').textContent = start.motivo ? 'Escolhido · pode editar' : 'Escolher';
    root.querySelector('[data-resumo="2"]').textContent = start.confirmado_em ? 'Assumido · pode editar' : start.objetivo ? 'Rascunho salvo' : 'Planejar';
    root.querySelector('[data-resumo="3"]').textContent = completed ? 'Conquista registrada' : savedFiles.length ? 'Tentativa guardada' : 'Criar';
    $('confirmacao').textContent = start.confirmado_em ? `Compromisso assumido em ${date(start.confirmado_em)}. Você pode revisá-lo aqui.` : 'O rascunho fica guardado; você assume o compromisso quando fizer sentido para você.';
    $('objetivo-salvo').textContent = start.objetivo ? `Seu objetivo: ${start.objetivo}` : 'Escolha uma pequena criação para começar.';
    $('pratica').textContent = start.pratica;
    $('apoio-texto').textContent = ({guiado: 'Comece pela forma principal. Se travar, salve a tentativa e prepare uma dúvida para pedir orientação.', autonomo: 'Tente uma versão com o que já sabe. Depois escolha um ajuste para a próxima tentativa.', desafio: 'Experimente uma segunda versão com uma mudança intencional. Compare as duas e observe o que aprendeu.'})[start.apoio];
    $('concluir').hidden = completed;
    if (completed) $('item-estado').textContent = 'Seu primeiro item já faz parte das suas conquistas. Você pode continuar guardando versões; os registros anteriores permanecem aqui.';
    $('obra').hidden = !savedFiles.length;
    $('destaque').replaceChildren();
    $('versoes').replaceChildren();
    if (savedFiles.length) {
      $('obra-legenda').textContent = savedFiles.length === 1 ? 'Você tem um ponto de partida guardado. Volte a ele para perceber o que mudou.' : `${savedFiles.length} registros guardados. Compare as versões e escolha seu próximo ajuste.`;
      $('destaque').append(fileCard(savedFiles[0], 0, savedFiles.length));
      const title = document.createElement('h3');
      title.textContent = 'Minha evolução · da versão mais recente à primeira';
      const grid = document.createElement('div');
      grid.className = 'inicio-grade-versoes';
      savedFiles.forEach((file, index) => grid.append(fileCard(file, index, savedFiles.length)));
      $('versoes').append(title, grid);
    }
  }
  function fill() {
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
    ['sonho', 'objetivo', 'quando', 'obstaculo', 'plano_b', 'compromisso', 'apoio'].forEach(key => {
      forms.plano.elements[key].value = data.inicio[key] || '';
    });
  }
  async function request(body) {
    const response = await fetch(root.dataset.api, {method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', headers: body ? {'X-CSRFToken': data.csrf} : {}, ...(body ? {body} : {})});
    let result;
    try { result = await response.json(); } catch (_) { throw new Error('Não foi possível salvar ou abrir seu registro agora. Suas respostas continuam nesta tela. Tente novamente.'); }
    if (!response.ok) throw new Error(result.detail || 'Não foi possível salvar agora. Suas respostas continuam nesta tela.');
    if (data && (data.pessoa_id !== result.pessoa_id || data.site_id !== result.site_id)) throw new Error('Sua conta mudou. Entre novamente na conta em que começou e reabra esta página.');
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
        for (const [key, label] of [['motivo', 'Caminho'], ['motivo_pessoal', 'Motivo pessoal'], ['objetivo', 'Objetivo'], ['quando', 'Próximo passo'], ['sonho', 'Sonho'], ['obstaculo', 'Dificuldade'], ['plano_b', 'Plano alternativo'], ['compromisso', 'Compromisso'], ['apoio', 'Apoio']]) {
          const p = document.createElement('p'); p.textContent = `${label}: ${result.inicio[key] || 'Ainda não preenchido'}`; comparison.append(p);
        }
        data = result;
        render();
        announce('Sua versão salva está abaixo. Suas respostas continuam nos campos; revise-as antes de salvar novamente.');
      } else {
        data = result; fill(); render();
        const hashStep = {'#inicio-motivo': 1, '#inicio-plano': 2, '#inicio-item': 3}[location.hash];
        step(hashStep || (data.inicio.confirmado_em || files().length ? 3 : data.inicio.motivo ? 2 : 1), false);
        $('conteudo').hidden = false;
        announce(data.inicio.salvo_em ? `Salvo na sua conta em ${date(data.inicio.salvo_em)}. Continue de onde parou.` : 'Comece com o que faz sentido para você hoje.');
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
      announce(dirty.size ? 'Este passo foi salvo. Ainda há alterações em outro passo; salve-as antes de sair.' : 'Salvo na sua conta. Você pode sair e retomar quando quiser.');
      return true;
    } catch (error) {
      announce(error.message, true);
      $('recarregar').textContent = 'Conferir versão salva'; $('recarregar').hidden = false;
      return false;
    } finally { setBusy(false); }
  }
  root.querySelectorAll('[data-passo]').forEach(button => button.addEventListener('click', () => step(Number(button.dataset.passo))));
  Object.values(forms).forEach(form => form.addEventListener('input', () => { dirty.add(form.id); announce('Há alterações nesta tela. Use o botão de salvar para retomá-las depois.'); }));
  forms.motivo.addEventListener('submit', async event => {
    event.preventDefault();
    if (await save(forms.motivo, 'inicio-motivo')) step(2);
  });
  forms.plano.addEventListener('submit', async event => {
    event.preventDefault();
    const assumir = event.submitter?.value || 'nao';
    if (await save(forms.plano, 'inicio-plano', {assumir}) && assumir === 'sim') step(3);
  });
  $('sugestao').addEventListener('click', () => {
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
  forms.item.addEventListener('submit', async event => {
    event.preventDefault();
    const action = event.submitter?.value || 'anexo';
    const file = $('arquivo').files[0];
    if (!file && (action === 'anexo' || !files().length)) { announce('Escolha um arquivo do seu item ou uma imagem dele para guardar.', true); return; }
    if (file && file.size > 20 * 1024 * 1024) { announce('Escolha um arquivo de até 20 MB.', true); return; }
    if (!file && ($('aprendi').value.trim() || $('duvida').value.trim())) { announce('Para guardar estas notas, escolha o arquivo da nova versão. Seus registros anteriores continuam guardados.', true); return; }
    const count = files().length;
    const hasNotes = Boolean($('aprendi').value.trim() || $('duvida').value.trim());
    if (await save(forms.item, action, {passo: '2', estado: 'feito'})) {
      forms.item.reset();
      announce(action === 'declaracao' ? 'Seu primeiro item faz parte das suas conquistas. Escolha seu próximo passo abaixo.' : files().length === count ? (hasNotes ? 'Este arquivo já estava guardado. Suas notas foram atualizadas.' : 'Este arquivo já estava guardado. A versão anterior foi preservada.') : 'Versão guardada em privado. Cada tentativa ajuda você a perceber sua evolução.');
    }
  });
  $('pedir-ajuda').addEventListener('click', () => {
    if ($('ajuda').hidden) {
      const lastDoubt = files().find(file => file.duvida)?.duvida;
      if (!$('mensagem').value) $('mensagem').value = `Estou praticando modelagem 3D.${data.inicio.objetivo ? ` Meu objetivo é: ${data.inicio.objetivo}` : ''}\n\n${lastDoubt ? `Minha dúvida é: ${lastDoubt}` : 'Minha dúvida é: '}\n\nO que já tentei: `;
      $('ajuda').hidden = false; $('pedir-ajuda').setAttribute('aria-expanded', 'true');
    }
    $('mensagem').focus();
  });
  $('copiar').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText($('mensagem').value); announce('Pedido copiado. Você decide se quer publicá-lo no Fórum.'); }
    catch (_) { $('mensagem').focus(); $('mensagem').select(); announce('Selecione e copie o pedido acima para compartilhar quando quiser.'); }
  });
  $('recarregar').addEventListener('click', open);
  window.addEventListener('beforeunload', event => { if (dirty.size) { event.preventDefault(); event.returnValue = ''; } });
  open();
})();
