(() => {
  const get = id => document.getElementById(id);
  let offset = 0, next = null, rows = [], busy = false;
  const updateButtons = () => {
    get('previous').disabled = busy || offset === 0;
    get('next').disabled = busy || next === null;
    get('reload').disabled = busy;
    get('datasetKind').disabled = busy;
    get('download').disabled = busy || rows.length === 0;
    get('downloadCsv').hidden = busy || rows.length === 0 || get('datasetKind').value !== 'signs';
    get('downloadCsv').href = `/api/datasets/signs?format=csv&limit=50&offset=${offset}`;
  };
  async function load() {
    busy = true; rows = []; next = null; updateButtons();
    get('datasetMessage').textContent = 'Consultando Supabase…';
    get('datasetBody').replaceChildren(); get('datasetHead').replaceChildren();
    const kind = get('datasetKind').value;
    try {
      const response = await fetch(`/api/datasets/${kind}?limit=50&offset=${offset}`, {cache: 'no-store'});
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'No se pudo consultar el historial.');
      rows = payload.data; next = payload.next_offset;
      const keys = kind === 'sensors' ? ['received_at', 'device_id', 'source', 'components'] : ['captured_at', 'label', 'prediction', 'confidence', 'handedness'];
      const titles = kind === 'sensors' ? ['Fecha UTC', 'Dispositivo', 'Origen', 'Mediciones'] : ['Fecha UTC', 'Etiqueta real', 'Predicción', 'Confianza (0–1)', 'Mano'];
      const header = document.createElement('tr');
      titles.forEach(title => {const th = document.createElement('th'); th.textContent = title; header.append(th);});
      get('datasetHead').append(header);
      rows.forEach(row => {
        const tr = document.createElement('tr');
        keys.forEach(key => {const td = document.createElement('td'); td.textContent = typeof row[key] === 'object' ? JSON.stringify(row[key]) : String(row[key] ?? '—'); tr.append(td);});
        get('datasetBody').append(tr);
      });
      get('datasetMessage').textContent = rows.length ? `${rows.length} registros desde la posición ${offset + 1}.` : 'Sin registros en esta página.';
    } catch (error) {get('datasetMessage').textContent = error.message;}
    finally {busy = false; updateButtons();}
  }
  get('datasetKind').addEventListener('change', () => {offset = 0; load();});
  get('reload').addEventListener('click', load);
  get('previous').addEventListener('click', () => {offset = Math.max(0, offset - 50); load();});
  get('next').addEventListener('click', () => {if (next !== null) {offset = next; load();}});
  get('download').addEventListener('click', () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(rows, null, 2)], {type: 'application/json'}));
    const a = document.createElement('a'); a.href = url; a.download = `${get('datasetKind').value}-${offset}.json`; a.click(); URL.revokeObjectURL(url);
  });
  load();
})();
