window.initSettings = function (root) {
  if (!document.getElementById('settings-css')) {
    const st = document.createElement('style'); st.id = 'settings-css';
    st.textContent = '.sx textarea{width:100%;min-height:120px;font:12px ui-monospace,monospace;padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--fg)}' +
      '.sx pre{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:10px;overflow:auto;white-space:pre-wrap;font:12px/1.4 ui-monospace,monospace;margin:8px 0 0}' +
      '.sx .warnbox{color:var(--warn);margin:8px 0}.sx .msg{min-height:1.3em;margin-top:8px}.sx .msg.e{color:var(--err)}.sx .msg.s{color:var(--ok)}' +
      '.sx h3{margin:0 0 8px}.sx ol{margin:6px 0 8px;padding-left:22px}.sx label.f{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0}' +
      '.sx label.f span.t{flex:1;min-width:220px}.sx input[type=text]{width:90px}.sx details{margin-top:10px}';
    document.head.appendChild(st);
  }
  const el = (tag, cls, text, kids) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; (kids || []).forEach(k => e.appendChild(k)); return e; };
  const btn = (t, cls, fn) => { const b = el('button', cls, t); b.onclick = fn; return b; };
  const msgBox = () => { const m = el('div', 'msg'); m.set = (t, ok) => { m.textContent = t; m.className = 'msg ' + (ok ? 's' : 'e'); }; return m; };
  // like api() but reports errors inline instead of alert
  async function call(path, method, body) {
    const r = await fetch(path, { method: method || 'GET', headers: { 'content-type': 'application/json', 'x-requested-with': 'ytw' }, body: body ? JSON.stringify(body) : undefined });
    if (r.status === 401) { location = '/login'; throw new Error('login'); }
    let j = null; try { j = await r.json(); } catch (e) {}
    if (!r.ok) throw new Error((j && typeof j.detail === 'string' && j.detail) || 'Request failed (' + r.status + ')');
    return j;
  }
  const fmt = s => s ? new Date(s).toLocaleString() : '-';
  root.textContent = ''; root.classList.add('sx');
  const ck = el('div', 'card'), yd = el('div', 'card'), cf = el('div', 'card');
  root.append(ck, yd, cf);

  // ---- cookies ----
  const cMsg = msgBox(), cStat = el('div'), cTa = el('textarea'), cFile = el('input');
  cTa.placeholder = 'Paste the cookies.txt text here'; cTa.spellcheck = false; cTa.autocomplete = 'off';
  cFile.type = 'file'; cFile.accept = '.txt,text/plain';
  cFile.onchange = async () => { const f = cFile.files[0]; if (f) { try { cTa.value = await f.text(); cMsg.set('File loaded, press Save.', true); } catch (e) { cMsg.set('Could not read the file.'); } } };
  const cSave = btn('Save cookies', 'pri', async () => {
    if (!cTa.value.trim()) return cMsg.set('Paste the cookies text or choose a file first.');
    cSave.disabled = true;
    try { const s = await call('/api/settings/cookies', 'POST', { text: cTa.value }); cTa.value = ''; cFile.value = ''; showCk(s); cMsg.set('Cookies saved.', true); }
    catch (e) { cMsg.set(e.message); } cSave.disabled = false;
  });
  const cDel = btn('Remove cookies', 'danger', async () => {
    if (!confirm('Remove the stored YouTube cookies?')) return;
    try { showCk(await call('/api/settings/cookies', 'DELETE')); cMsg.set('Cookies removed.', true); } catch (e) { cMsg.set(e.message); }
  });
  function showCk(s) {
    cStat.textContent = '';
    if (!s.present) { cStat.append(el('span', 'mut', 'No cookies stored.')); cDel.disabled = true; return; }
    cDel.disabled = false;
    cStat.append(el('span', 'pill ok', 'Present'), el('span', 'mut', ' ' + Math.ceil(s.size / 1024) + ' KB, ' + s.entries + ' cookies (' + s.youtube_entries + ' Google/YouTube), saved ' + fmt(s.modified) + '. '));
    cStat.append(el('span', s.expired ? 'errors' : 'mut', s.earliest_expiry ? (s.expired ? 'Login expired ' : 'Login expires ') + fmt(s.earliest_expiry) : 'No login expiry found'));
    (s.warnings || []).forEach(w => cStat.append(el('div', 'warnbox', w)));
  }
  ck.append(el('h3', null, 'YouTube cookies'),
    el('p', 'mut', 'Age-restricted videos only download with a logged-in, age-verified YouTube account. To provide one:'),
    el('ol', null, null, ["Install a 'cookies.txt' export extension in a browser that is logged in to youtube.com.", 'Open youtube.com.', 'Export cookies for youtube.com with the extension.', 'Paste the text below, or choose the exported file, then press Save.'].map(t => el('li', null, t))),
    el('p', 'warnbox', 'Cookies of your main Google account can get that account flagged by YouTube; a secondary account is safer. Cookies expire or rotate, so you may need to upload them again.'),
    cStat, cTa, el('div', 'row', null, [cFile, el('span', 'grow'), cDel, cSave]), cMsg);
  call('/api/settings/cookies').then(showCk).catch(e => cMsg.set(e.message));

  // ---- yt-dlp ----
  const yMsg = msgBox(), yVer = el('span'), yOut = el('pre'), yBtn = btn('Update yt-dlp', 'pri', async () => {
    yBtn.disabled = true; yBtn.textContent = 'Updating…'; yMsg.set('');
    try {
      const r = await call('/api/settings/ytdlp/update', 'POST');
      yOut.textContent = 'before: ' + (r.before || '?') + '\nafter:  ' + (r.after || '?') + '\n\n' + r.output; yOut.classList.remove('hide');
      yMsg.set(r.changed ? 'Updated to ' + r.after + '.' : 'No change.', true); loadY();
    } catch (e) { yMsg.set(e.message); }
    yBtn.disabled = false; yBtn.textContent = 'Update yt-dlp';
  });
  yOut.classList.add('hide');
  async function loadY() { try { const r = await call('/api/settings/ytdlp'); yVer.textContent = 'Version: ' + (r.version || 'unknown') + (r.using_updatable_copy ? ' (updatable copy)' : ' (built-in copy)'); } catch (e) { yMsg.set(e.message); } }
  yd.append(el('h3', null, 'yt-dlp'), el('div', 'row', null, [yVer, el('span', 'grow'), yBtn]),
    el('p', 'mut', 'YouTube changes often; updating yt-dlp fixes most sudden download failures. Not possible while a run is active.'), yOut, yMsg);
  loadY();

  // ---- options ----
  const fields = {}, oMsg = msgBox(), raw = el('pre');
  const num = (key, lbl, w) => { const i = el('input'); i.type = 'text'; i.inputMode = 'numeric'; if (w) i.style.width = w; fields[key] = i; return i; };
  const chk = key => { const i = el('input'); i.type = 'checkbox'; fields[key] = i; return i; };
  const line = (t, ctrls) => el('label', 'f', null, [el('span', 't', t), ...ctrls]);
  const form = el('div', null, null, [
    line('Audio quality (0 best, 10 smallest)', [num('audio_quality')]),
    line('Pause between downloads (seconds): min / max', [num('sleep_interval'), num('max_sleep_interval')]),
    line('Slowest allowed speed before retrying (e.g. 100K, 1M)', [num('throttled_rate')]),
    line('Parallel fragment downloads (1-8)', [num('concurrent_fragments')]),
    line('Retries (0-50)', [num('retries')]), line('Fragment retries (0-50)', [num('fragment_retries')]),
    line('Network timeout (seconds, 5-300)', [num('socket_timeout')]),
    line('Embed cover art in the file', [chk('embed_thumbnail')]), line('Embed title/artist tags', [chk('embed_metadata')])]);
  const det = el('details', null, null, [el('summary', 'mut', 'Show raw yt-dlp.conf (read-only)'), raw]);
  const oSave = btn('Save options', 'pri', async () => {
    const values = {};
    for (const [k, i] of Object.entries(fields)) {
      if (i.type === 'checkbox') values[k] = i.checked;
      else if (i.value.trim() !== '') values[k] = k === 'throttled_rate' ? i.value.trim() : (/^\d+$/.test(i.value.trim()) ? +i.value.trim() : i.value.trim());
    }
    oSave.disabled = true;
    try { fill(await call('/api/settings/config', 'PUT', { values })); oMsg.set('Options saved (a backup of the file was kept).', true); }
    catch (e) { oMsg.set(e.message); } oSave.disabled = false;
  });
  function fill(c) {
    for (const [k, i] of Object.entries(fields)) { const v = c.values[k]; if (i.type === 'checkbox') i.checked = !!v; else i.value = v == null ? '' : v; }
    raw.textContent = c.raw;
  }
  cf.append(el('h3', null, 'Download options'), el('p', 'mut', 'Written to yt-dlp.conf, which the old bash scripts share. Empty fields are left as they are. Changes apply to the next run.'),
    form, det, el('div', 'row', null, [el('span', 'grow'), oSave]), oMsg);
  call('/api/settings/config').then(fill).catch(e => oMsg.set(e.message));
};
