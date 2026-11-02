// Progressive project fan, native film dialog and horizontal pointer gestures.
(() => {
  const grid = document.querySelector('#work .projects-grid');
  if (!grid) return;
  const es = document.documentElement.lang === 'es';
  const cards = [...grid.children], browser = document.createElement('div');
  browser.className = 'project-browser';
  const stage = document.createElement('div');
  stage.className = 'project-stage'; stage.setAttribute('role', 'group');
  stage.setAttribute('aria-label', es ? 'Seleccionar proyecto' : 'Select a project');
  const controls = document.createElement('div'); controls.className = 'project-controls';
  const hint = document.createElement('p'); hint.className = 'project-hint';
  hint.textContent = es ? 'Elige una tarjeta y desplázate · ← → · desliza' : 'Select a card, then scroll · ← → · swipe';
  const status = document.createElement('span'); status.setAttribute('role', 'status');
  const previous = document.createElement('button'), next = document.createElement('button');
  previous.textContent = '←'; next.textContent = '→';
  previous.setAttribute('aria-label', es ? 'Proyecto anterior' : 'Previous project');
  next.setAttribute('aria-label', es ? 'Proyecto siguiente' : 'Next project');
  controls.append(previous, status, next); grid.before(browser); browser.append(stage, grid, hint, controls);
  const dialog = document.querySelector('.project-film'), video = dialog.querySelector('video');
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  let opener, selected = 0, blockedClick = false, gesture;
  const clamp = index => Math.max(0, Math.min(cards.length - 1, index));
  function play(button) {
    opener = button; video.src = cards.find(card => card.dataset.cardVideo).dataset.cardVideo;
    dialog.showModal(); video.play().catch(() => {});
  }
  dialog.querySelector('button').onclick = () => dialog.close();
  dialog.addEventListener('click', event => {
    const box = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom)) dialog.close();
  });
  dialog.addEventListener('close', () => {
    video.pause(); video.removeAttribute('src'); video.load(); opener?.focus({preventScroll: true});
  });
  const tiles = cards.map((card, index) => {
    const tile = document.createElement('button'); tile.className = 'project-tile'; tile.type = 'button';
    tile.setAttribute('aria-controls', card.id);
    const art = document.createElement('span'); art.className = 'project-art art-' + index; art.setAttribute('aria-hidden', 'true');
    art.append(card.querySelector('svg').cloneNode(true));
    if (card.dataset.cardImage) {
      const image = new Image(); image.alt = ''; image.draggable = false; image.src = card.dataset.cardImage;
      art.classList.add('image-art'); image.onerror = () => {image.remove(); art.classList.remove('image-art');}; art.append(image);
    }
    const title = document.createElement('span'); title.className = 'tile-title'; title.textContent = card.querySelector('h3').textContent;
    const category = document.createElement('span'); category.className = 'tile-category'; category.textContent = card.querySelector('.project-category').textContent;
    const number = document.createElement('span'); number.className = 'tile-number'; number.textContent = String(index + 1).padStart(2, '0');
    tile.append(art, title, category, number);
    tile.addEventListener('click', event => {
      if (blockedClick && event.detail) {blockedClick = false; return;}
      blockedClick = false;
      if (index === selected && card.dataset.cardVideo && (event.target.closest('.project-art') || !event.detail)) play(tile);
      else select(index);
    });
    stage.append(tile); card.classList.remove('reveal', 'reveal-ready'); return tile;
  });
  function draw(progress = 0, dx = 0) {
    tiles.forEach((tile, index) => {
      const relative = index - selected, offset = relative - progress;
      tile.style.setProperty('--x', (relative === 0 ? dx : 94 * offset) + 'px');
      tile.style.setProperty('--y', (offset < 0 ? 12 : 30) * offset + 'px');
      tile.style.setProperty('--r', 9 * offset + 'deg');
      tile.style.setProperty('--s', String(1 - .055 * Math.min(Math.abs(offset), 5)));
      tile.style.zIndex = progress && relative === 0 ? 20 : 10 - Math.abs(relative);
    });
  }
  function resetGesture() {
    if (!gesture) return;
    const id = gesture.id; gesture = null; stage.classList.remove('is-dragging');
    if (stage.hasPointerCapture(id)) stage.releasePointerCapture(id);
  }
  function cancelDrag() {if (gesture) {blockedClick = true; resetGesture(); draw();}}
  function select(index, focus = false) {
    resetGesture(); selected = clamp(index);
    cards.forEach((card, index) => {card.hidden = index !== selected;});
    tiles.forEach((tile, index) => {
      tile.classList.toggle('is-selected', index === selected); tile.setAttribute('aria-pressed', String(index === selected));
      if (cards[index].dataset.cardVideo) {
        tile.setAttribute('aria-label', tile.querySelector('.tile-title').textContent + (index === selected ? ' · ' + (es ? 'Reproducir video' : 'Play film') : ''));
        tile.setAttribute('aria-haspopup', 'dialog');
      }
      tile.tabIndex = index === selected ? 0 : -1;
    });
    draw(); status.textContent = `${String(selected + 1).padStart(2, '0')} / 06`;
    previous.disabled = selected === 0; next.disabled = selected === cards.length - 1;
    if (focus) tiles[selected].focus({preventScroll: true});
  }
  previous.onclick = () => select(selected - 1); next.onclick = () => select(selected + 1);
  stage.addEventListener('keydown', event => {
    if (event.key === 'Escape') {cancelDrag(); return;}
    const index = {ArrowRight: selected + 1, ArrowLeft: selected - 1, Home: 0, End: cards.length - 1}[event.key];
    if (index !== undefined) {event.preventDefault(); select(index, true);}
  });
  let wheel = 0, lastWheel = 0;
  stage.addEventListener('wheel', event => {
    if (event.ctrlKey) return;
    const horizontal = Math.abs(event.deltaX) > Math.abs(event.deltaY);
    if (!horizontal && !stage.contains(document.activeElement)) return;
    const delta = (horizontal ? event.deltaX : event.deltaY) * (event.deltaMode === 1 ? 16 : 1);
    if (selected === 0 && delta < 0 || selected === cards.length - 1 && delta > 0) return;
    event.preventDefault(); if (Math.sign(wheel) !== Math.sign(delta)) wheel = 0;
    wheel += delta;
    if (Math.abs(wheel) > 45 && performance.now() - lastWheel > 180) {select(selected + Math.sign(wheel)); wheel = 0; lastWheel = performance.now();}
  }, {passive: false});
  stage.addEventListener('dragstart', event => event.preventDefault());
  stage.addEventListener('pointerdown', event => {
    if (event.isPrimary === false || event.button !== 0) {cancelDrag(); return;}
    cancelDrag(); blockedClick = false;
    gesture = {id: event.pointerId, x: event.clientX, y: event.clientY, dx: 0, horizontal: false};
  });
  function move(event) {
    if (!gesture || gesture.id !== event.pointerId) return;
    const dx = event.clientX - gesture.x, dy = event.clientY - gesture.y;
    gesture.dx = dx;
    if (!gesture.horizontal) {
      if (Math.max(Math.abs(dx), Math.abs(dy)) < 8) return;
      blockedClick = true;
      if (Math.abs(dy) >= Math.abs(dx)) {resetGesture(); return;}
      stage.getAnimations({subtree: true}).forEach(animation => animation.finish());
      gesture.horizontal = true; stage.classList.add('is-dragging'); stage.setPointerCapture(event.pointerId);
    }
    if (event.cancelable) event.preventDefault();
    const atEdge = clamp(selected - Math.sign(dx)) === selected;
    draw(atEdge ? 0 : Math.max(-1, Math.min(1, -dx / 180)), atEdge ? dx * .2 : dx);
  }
  stage.addEventListener('pointermove', move);
  stage.addEventListener('pointerup', event => {
    move(event); if (!gesture || gesture.id !== event.pointerId) return;
    const dx = gesture.dx, old = tiles[selected], from = getComputedStyle(old).transform;
    const target = clamp(selected - (gesture.horizontal && Math.abs(dx) > 45 ? Math.sign(dx) : 0));
    const changed = target !== selected, focus = stage.contains(document.activeElement);
    select(target, focus);
    if (changed && !motion.matches) old.animate([
      {transform: from, opacity: 1, zIndex: 20},
      {transform: `translate(${Math.sign(dx) * Math.max(320, stage.clientWidth)}px, -24px) rotate(${Math.sign(dx) * 22}deg) scale(.9)`, opacity: 0, zIndex: 20}
    ], {duration: 300, easing: 'ease-out'});
  });
  stage.addEventListener('pointercancel', cancelDrag);
  stage.addEventListener('lostpointercapture', event => {if (event.target === stage && !stage.hasPointerCapture(event.pointerId)) cancelDrag();});
  window.addEventListener('blur', cancelDrag);
  motion.addEventListener('change', () => {cancelDrag(); stage.getAnimations({subtree: true}).forEach(animation => animation.finish());});
  function fromHash() {const index = cards.findIndex(card => '#' + card.id === location.hash); if (index >= 0) select(index);}
  browser.classList.add('is-ready'); select(0); fromHash(); window.addEventListener('hashchange', fromHash);
})();
