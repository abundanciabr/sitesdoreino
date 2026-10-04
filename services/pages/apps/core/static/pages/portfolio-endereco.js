(() => {
  'use strict';
  document.querySelectorAll('[data-address-preview]').forEach(preview => {
    const input = preview.closest('form')?.querySelector('[name="apelido"]');
    const text = preview.querySelector('[data-address-text]');
    if (!input || !text) return;
    const update = () => {
      const slug = input.value.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase()
        .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, input.maxLength > 0 ? input.maxLength : 48).replace(/-+$/g, '');
      text.textContent = preview.dataset.addressBase + slug;
    };
    input.addEventListener('input', update);
    update();
  });
})();
