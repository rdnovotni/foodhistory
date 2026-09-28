(() => {
  const article = document.querySelector('.wiki-article');
  if (!article) return;
  const card = document.createElement('div');
  card.className = 'reader-popover';
  card.setAttribute('role', 'status');
  card.hidden = true;
  document.body.append(card);
  let controller = null;
  const hide = () => { card.hidden = true; if (controller) controller.abort(); controller = null; };
  const show = (element, title, detail, href) => {
    card.replaceChildren();
    const heading = document.createElement('strong'); heading.textContent = title;
    const description = document.createElement('p'); description.textContent = detail;
    card.append(heading, description);
    if (href) {
      const link = document.createElement('a'); link.href = href; link.textContent = 'Read article'; card.append(link);
    }
    const bounds = element.getBoundingClientRect();
    card.style.left = `${Math.max(12, Math.min(bounds.left, window.innerWidth - 340))}px`;
    card.style.top = `${Math.min(bounds.bottom + 8, window.innerHeight - 140)}px`;
    card.hidden = false;
  };
  article.addEventListener('pointerover', async event => {
    const link = event.target.closest('.wiki-body a[href^="/wiki/"]');
    if (link) {
      const match = /^\/wiki\/([a-z0-9-]+)$/.exec(new URL(link.href).pathname);
      if (!match) return;
      hide(); controller = new AbortController();
      try {
        const response = await fetch(`/v1/wiki/pages/${match[1]}/preview`, {signal: controller.signal});
        if (!response.ok || !link.matches(':hover')) return;
        const data = await response.json();
        show(link, data.title, `${data.summary || 'A Food History Wiki article.'} · ${data.reading_minutes} min read`, `/wiki/${data.slug}`);
      } catch (error) { if (error.name !== 'AbortError') hide(); }
      return;
    }
    const footnote = event.target.closest('.wiki-body .footnote-ref a[href^="#fn"]');
    if (footnote) {
      const target = document.getElementById(decodeURIComponent(footnote.hash.slice(1)));
      if (target) show(footnote, `Footnote ${footnote.textContent}`, target.textContent.replace(/↩︎/g, '').trim());
    }
  });
  article.addEventListener('pointerout', event => {
    if (!event.relatedTarget?.closest('.reader-popover')) hide();
  });
  article.addEventListener('focusin', event => {
    const footnote = event.target.closest('.wiki-body .footnote-ref a[href^="#fn"]');
    if (footnote) {
      const target = document.getElementById(decodeURIComponent(footnote.hash.slice(1)));
      if (target) show(footnote, `Footnote ${footnote.textContent}`, target.textContent.replace(/↩︎/g, '').trim());
    }
  });
  article.addEventListener('click', event => {
    const term = event.target.closest('.glossary-term');
    if (term) { show(term, term.textContent, term.dataset.definition, term.dataset.article ? `/wiki/${term.dataset.article}` : null); return; }
    if (!event.target.closest('.reader-popover')) hide();
  });
  card.addEventListener('pointerleave', hide);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') hide(); });
})();
