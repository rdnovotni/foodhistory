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
