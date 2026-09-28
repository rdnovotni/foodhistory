(() => {
  const root = document.querySelector("[data-editor-root]");
  if (!root) return;
  const debounce = (fn, delay = 250) => { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); }; };
  const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));

  document.querySelectorAll("[data-picker]").forEach(picker => {
    const query = picker.querySelector("[data-picker-query]");
    const results = picker.querySelector("[data-picker-results]");
    const selected = picker.querySelector("[data-picker-selected]");
    const kind = picker.dataset.picker;
    query.addEventListener("input", debounce(async () => {
      if (query.value.trim().length < 2) { results.innerHTML = ""; return; }
      const response = await fetch(`${picker.dataset.endpoint}?q=${encodeURIComponent(query.value.trim())}`);
      const items = response.ok ? await response.json() : [];
      results.innerHTML = items.map(item => {
        const id = kind === "entities" ? item.public_id : item.citation_id;
        const label = kind === "entities" ? `${item.label} · ${item.type_code}` : `${item.source_label} · ${item.locator_text || item.page_label || "source"}`;
        return `<button type="button" data-add-value="${escapeHtml(id)}">${escapeHtml(label)}</button>`;
      }).join("");
    }));
    results.addEventListener("click", event => {
      const button = event.target.closest("[data-add-value]");
      if (!button) return;
      const values = selected.value.split(",").map(value => value.trim()).filter(Boolean);
      if (!values.includes(button.dataset.addValue)) values.push(button.dataset.addValue);
      selected.value = values.join(", "); button.disabled = true;
    });
  });

  const article = root.querySelector("[data-wiki-editor]");
  const suggestions = root.querySelector("[data-wiki-suggestions]");
  if (article && suggestions) {
    let matches = [], range = null, active = 0, requestId = 0;
    const hide = () => { suggestions.hidden = true; suggestions.replaceChildren(); matches = []; };
    const context = () => {
      const before = article.value.slice(0, article.selectionStart);
      const opening = before.lastIndexOf("[[");
      if (opening < 0 || before.slice(opening).includes("]]")) return null;
      const query = before.slice(opening + 2);
      return /^[\w -]{0,60}$/.test(query) ? {opening, query: query.trim()} : null;
    };
    const choose = index => {
      if (!range || !matches[index]) return;
      const slug = matches[index].slug;
      article.value = article.value.slice(0, range.opening) + `[[${slug}]]` + article.value.slice(range.end);
      article.focus(); article.setSelectionRange(range.opening + slug.length + 4, range.opening + slug.length + 4);
      hide();
    };
    const update = debounce(async () => {
      const current = context();
      if (!current) { hide(); return; }
      const id = ++requestId;
      const response = await fetch(`/editor/pickers/wiki?q=${encodeURIComponent(current.query)}`);
      const latest = context();
      if (id !== requestId || !response.ok || !latest || latest.opening !== current.opening || latest.query !== current.query) return;
      matches = await response.json(); range = {opening:current.opening, end:article.selectionStart}; active = 0;
      suggestions.innerHTML = matches.map((item, index) => `<button type="button" role="option" data-wiki-index="${index}">${escapeHtml(item.title)} · ${escapeHtml(item.slug)}</button>`).join("");
      suggestions.hidden = !matches.length;
    }, 180);
    article.addEventListener("input", update);
    article.addEventListener("click", update);
    article.addEventListener("keydown", event => {
      if (suggestions.hidden) return;
      if (event.key === "Escape") { hide(); return; }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault(); active = (active + (event.key === "ArrowDown" ? 1 : -1) + matches.length) % matches.length;
        suggestions.querySelectorAll("button").forEach((button, index) => button.classList.toggle("active", index === active));
      } else if (event.key === "Enter" || event.key === "Tab") {
        event.preventDefault(); choose(active);
      }
    });
    suggestions.addEventListener("mousedown", event => {
      const button = event.target.closest("[data-wiki-index]");
      if (button) { event.preventDefault(); choose(Number(button.dataset.wikiIndex)); }
    });
  }

  const mediaRoot = document.querySelector("[data-media-picker]");
  if (!mediaRoot) return;
  const selectedRoot = mediaRoot.querySelector("[data-selected-media]");
  const imageData = mediaRoot.querySelector("[data-image-data]");
  const initial = JSON.parse(mediaRoot.querySelector("[data-initial-images]").textContent || "[]");
  let images = initial.map(item => ({public_id:item.public_id, label:item.preferred_label || item.label || item.public_id, placement:item.placement || "gallery", alt_text:item.alt_text || "", caption:item.caption || ""}));
  const payload = () => images.map(({public_id, placement, alt_text, caption}) => ({public_id, placement, alt_text, caption}));
  const sync = () => {
    imageData.value = JSON.stringify(payload());
    selectedRoot.innerHTML = images.map((item, index) => `<article class="media-selection" data-media-index="${index}"><strong>${escapeHtml(item.label)}</strong><label>Placement<select data-media-field="placement"><option value="lead" ${item.placement === "lead" ? "selected" : ""}>Lead</option><option value="gallery" ${item.placement === "gallery" ? "selected" : ""}>Gallery</option><option value="inline" ${item.placement === "inline" ? "selected" : ""}>Inline</option></select></label><label>Alternative text<input data-media-field="alt_text" value="${escapeHtml(item.alt_text)}" required></label><label>Caption<input data-media-field="caption" value="${escapeHtml(item.caption)}"></label><button type="button" class="secondary" data-remove-media>Remove</button></article>`).join("");
  };
  const addMedia = item => { if (!images.some(image => image.public_id === item.public_id)) images.push({public_id:item.public_id, label:item.label, placement:images.length ? "gallery" : "lead", alt_text:"", caption:""}); sync(); };
  selectedRoot.addEventListener("input", event => { const card = event.target.closest("[data-media-index]"); if (!card || !event.target.dataset.mediaField) return; const index = Number(card.dataset.mediaIndex); if (event.target.dataset.mediaField === "placement" && event.target.value === "lead") { images.forEach((image, other) => { if (other !== index && image.placement === "lead") image.placement = "gallery"; }); images[index].placement = "lead"; sync(); return; } images[index][event.target.dataset.mediaField] = event.target.value; imageData.value = JSON.stringify(payload()); });
  selectedRoot.addEventListener("click", event => { const card = event.target.closest("[data-media-index]"); if (!card || !event.target.closest("[data-remove-media]")) return; images.splice(Number(card.dataset.mediaIndex), 1); sync(); });
  const mediaQuery = mediaRoot.querySelector("[data-media-query]");
  const mediaResults = mediaRoot.querySelector("[data-media-results]");
  mediaQuery.addEventListener("input", debounce(async () => { if (mediaQuery.value.trim().length < 2) { mediaResults.innerHTML = ""; return; } const response = await fetch(`/editor/pickers/media?q=${encodeURIComponent(mediaQuery.value.trim())}`); const items = response.ok ? await response.json() : []; mediaResults.innerHTML = items.map(item => `<button type="button" data-media-id="${escapeHtml(item.public_id)}">${escapeHtml(item.label)} · ${escapeHtml(item.public_id)}</button>`).join(""); mediaResults.querySelectorAll("[data-media-id]").forEach((button, index) => button.addEventListener("click", () => addMedia(items[index]))); }));
  mediaRoot.querySelector("[data-media-upload-button]").addEventListener("click", async () => { const input = mediaRoot.querySelector("[data-media-upload]"); if (!input.files.length) return; const form = new FormData(); form.append("csrf_token", root.dataset.csrf); form.append("upload", input.files[0]); const response = await fetch("/editor/media", {method:"POST", body:form}); if (!response.ok) { alert((await response.json()).detail || "Upload failed"); return; } addMedia(await response.json()); input.value = ""; });
  sync();
})();
