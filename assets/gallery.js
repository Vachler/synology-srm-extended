(() => {
  const items = [...document.querySelectorAll('[data-gallery]')];
  const dialog = document.querySelector('.lightbox');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  const image = dialog.querySelector('.lightbox-image');
  const caption = dialog.querySelector('.lightbox-caption');
  const original = dialog.querySelector('.lightbox-original');
  let current = 0;
  let trigger;
  let previousOverflow;
  function show(index) {
    current = (index + items.length) % items.length;
    const item = items[current];
    image.src = item.href;
    image.alt = item.dataset.caption;
    caption.textContent = `${current + 1} / ${items.length} · ${item.dataset.caption}`;
    original.href = item.href;
  }
  items.forEach((item, index) => item.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    trigger = item;
    show(index);
    previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.showModal();
  }));
  function dismiss() {
    document.body.style.overflow = previousOverflow;
    dialog.close();
  }
  dialog.querySelector('[data-close]').addEventListener('click', dismiss);
  dialog.addEventListener('cancel', event => { event.preventDefault(); dismiss(); });
  dialog.querySelector('[data-prev]').addEventListener('click', () => show(current - 1));
  dialog.querySelector('[data-next]').addEventListener('click', () => show(current + 1));
  dialog.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft') { event.preventDefault(); show(current - 1); }
    if (event.key === 'ArrowRight') { event.preventDefault(); show(current + 1); }
  });
  dialog.addEventListener('click', event => {
    const bounds = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) dismiss();
  });
  dialog.addEventListener('close', () => {
    document.body.style.overflow = previousOverflow;
    trigger?.focus();
  });
})();
