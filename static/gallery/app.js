(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const status = $('#live-status');
  let galleryUpdate = Promise.resolve();
  let photoIndex = 0;
  let photoLinks = [];
  let previewUrls = [];

  function announce(text) { status.textContent = text; }
  function clearPreviews() {
    previewUrls.forEach(url => URL.revokeObjectURL(url));
    previewUrls = [];
    $('#selected-files')?.replaceChildren();
  }
  function showFiles() {
    clearPreviews();
    const input = $('#id_photos');
    const list = $('#selected-files');
    for (const [index, file] of Array.from(input.files).entries()) {
      const item = document.createElement('li');
      const label = document.createElement('span');
      label.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} Mo`;
      if (['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
        const img = document.createElement('img');
        const url = URL.createObjectURL(file);
        previewUrls.push(url);
        img.src = url;
        img.alt = '';
        item.append(img);
      }
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'file-remove';
      remove.textContent = 'Retirer';
      remove.setAttribute('aria-label', `Retirer ${file.name}`);
      remove.addEventListener('click', () => {
        const selection = new DataTransfer();
        Array.from(input.files).forEach((candidate, i) => { if (i !== index) selection.items.add(candidate); });
        input.files = selection.files;
        showFiles();
      });
      item.append(label, remove);
      list.append(item);
    }
    announce(`${input.files.length} photo(s) sélectionnée(s).`);
  }

  function refreshGallery(url, push = true) {
    galleryUpdate = galleryUpdate.catch(() => {}).then(() => loadGallery(url, push));
    return galleryUpdate;
  }

  async function loadGallery(url, push) {
    const main = $('#main');
    main.setAttribute('aria-busy', 'true');
    try {
      const response = await fetch(url, {headers: {'X-Requested-With': 'fetch'}, cache: 'no-store'});
      if (!response.ok) throw new Error('La galerie n’a pas pu être actualisée. Réessayez.');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const replacement = $('#main', page);
      if (!replacement || !$('#upload-dialog', page)) {
        window.location.assign(response.url);
        return;
      }
      main.replaceWith(replacement);
      const newOptions = $('#id_category', page);
      if (newOptions && $('#id_category')) $('#id_category').replaceChildren(...Array.from(newOptions.children));
      if (push) history.pushState(null, '', response.url);
      announce($('.message', replacement)?.textContent || 'La galerie est à jour.');
    } finally {
      $('#main').removeAttribute('aria-busy');
    }
  }

  function showPhoto(index) {
    photoLinks = Array.from(document.querySelectorAll('[data-photo]'));
    if (!photoLinks.length) return;
    photoIndex = (index + photoLinks.length) % photoLinks.length;
    const link = photoLinks[photoIndex];
    const image = $('#large-photo');
    image.alt = link.dataset.caption;
    image.src = link.href;
    $('#large-caption').textContent = link.dataset.caption;
    $('#large-category').textContent = link.dataset.category;
    $('#large-meta').textContent = link.dataset.meta;
    $('#large-edit').hidden = !link.dataset.edit;
    $('#large-edit').href = link.dataset.edit || '#';
    $('.lightbox-error').hidden = true;
    document.querySelectorAll('[data-direction]').forEach(button => { button.hidden = photoLinks.length < 2; });
    announce(`Photo ${photoIndex + 1} sur ${photoLinks.length}. ${link.dataset.caption}`);
  }

  document.addEventListener('click', async event => {
    const open = event.target.closest('[data-dialog]');
    if (open) {
      const dialog = document.getElementById(open.dataset.dialog);
      $('.form-errors', dialog).hidden = true;
      dialog.showModal();
      return;
    }
    const close = event.target.closest('[data-close]');
    if (close) { close.closest('dialog').close(); return; }
    const toggle = event.target.closest('[data-toggle-password]');
    if (toggle) {
      const input = document.getElementById(toggle.dataset.togglePassword);
      const visible = input.type === 'password';
      input.type = visible ? 'text' : 'password';
      toggle.textContent = visible ? 'Masquer' : 'Afficher';
      toggle.setAttribute('aria-pressed', String(visible));
      return;
    }
    const direction = event.target.closest('[data-direction]');
    if (direction) { showPhoto(photoIndex + Number(direction.dataset.direction)); return; }
    const photo = event.target.closest('[data-photo]');
    if (photo && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
      event.preventDefault();
      showPhoto(Array.from(document.querySelectorAll('[data-photo]')).indexOf(photo));
      $('#photo-dialog').showModal();
      return;
    }
    const gallery = event.target.closest('[data-gallery]');
    if (gallery && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
      event.preventDefault();
      try { await refreshGallery(gallery.href); }
      catch (error) { announce(error.message); window.location.assign(gallery.href); }
    }
  });

  document.addEventListener('submit', async event => {
    const form = event.target;
    if (form.matches('[data-search]')) {
      event.preventDefault();
      const url = new URL(form.action);
      url.search = new URLSearchParams(new FormData(form)).toString();
      try { await refreshGallery(url); }
      catch (error) { window.location.assign(url); }
      return;
    }
    if (!form.matches('[data-async]')) return;
    event.preventDefault();
    if (form.dataset.busy) return;
    form.dataset.busy = 'true';
    const submit = $('button[type="submit"]', form);
    const errors = $('.form-errors', form);
    const progress = $('.upload-progress', form);
    submit.disabled = true;
    errors.hidden = true;
    if (progress) progress.hidden = false;
    let saved = false;
    let galleryUrl = '/';
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form), headers: {'X-Requested-With': 'fetch'}});
      if (response.redirected && response.url.includes('/connexion/')) {
        window.location.assign(response.url);
        return;
      }
      let data;
      try { data = await response.json(); }
      catch (error) { throw new Error('L’envoi n’a pas pu aboutir. Vérifiez votre connexion et la taille des fichiers.'); }
      if (!response.ok) {
        errors.replaceChildren();
        const messages = data.errors ? Object.values(data.errors).flat().map(item => item.message) : ['L’envoi n’a pas pu aboutir. Réessayez.'];
        messages.forEach(message => { const p = document.createElement('p'); p.textContent = message; errors.append(p); });
        errors.hidden = false;
        errors.scrollIntoView({block: 'nearest'});
        return;
      }
      saved = true;
      galleryUrl = data.url;
      // Reset before replacing category options with those in the new gallery.
      form.reset();
      clearPreviews();
      await refreshGallery(galleryUrl);
      form.closest('dialog').close();
      $('#album-title')?.scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start'});
    } catch (error) {
      if (saved) {
        // The POST succeeded: retry only the GET, never the upload.
        window.location.assign(galleryUrl);
      } else {
        errors.textContent = error.message || 'Vérifiez votre connexion puis réessayez.';
        errors.hidden = false;
      }
    } finally {
      delete form.dataset.busy;
      submit.disabled = false;
      if (progress) progress.hidden = true;
    }
  });

  document.addEventListener('change', event => { if (event.target.id === 'id_photos') showFiles(); });
  document.addEventListener('keydown', event => {
    if (!$('#photo-dialog')?.open) return;
    if (event.key === 'ArrowRight') { event.preventDefault(); showPhoto(photoIndex + 1); }
    if (event.key === 'ArrowLeft') { event.preventDefault(); showPhoto(photoIndex - 1); }
  });
  document.querySelectorAll('dialog').forEach(dialog => {
    dialog.addEventListener('click', event => {
      if (event.target === dialog) {
        const rect = dialog.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
      }
    });
    dialog.addEventListener('close', () => {
      if (dialog.id === 'photo-dialog') $('#large-photo').removeAttribute('src');
    });
  });
  $('#large-photo')?.addEventListener('error', () => { $('.lightbox-error').hidden = false; });
  const dropZone = $('#drop-zone');
  if (dropZone) {
    ['dragenter', 'dragover'].forEach(type => dropZone.addEventListener(type, event => { event.preventDefault(); dropZone.classList.add('dragging'); }));
    ['dragleave', 'drop'].forEach(type => dropZone.addEventListener(type, event => { event.preventDefault(); dropZone.classList.remove('dragging'); }));
    dropZone.addEventListener('drop', event => {
      if (event.dataTransfer.files.length) { $('#id_photos').files = event.dataTransfer.files; showFiles(); }
    });
  }
  window.addEventListener('popstate', async () => {
    if (!$('#upload-dialog')) return;
    try { await refreshGallery(window.location.href, false); }
    catch (error) { window.location.reload(); }
  });
  // Browsers may restore a logged-out gallery from their back/forward cache.
  window.addEventListener('pageshow', event => { if (event.persisted) window.location.reload(); });
})();
