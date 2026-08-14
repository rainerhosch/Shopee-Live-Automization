/* Shopee Live Bot dashboard */
(() => {
  const $ = (id) => document.getElementById(id);

  const state = {
    activeTab: "lelang",
    devices: [],
    bot: null,
    settings: null,
    calibration: null,
    activeCalKey: null,
    refImages: {},
  };

  let streamActive = false;

  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { detail: text };
    }
    if (!res.ok) {
      const msg = data?.detail || data?.error || res.statusText;
      throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
    return data;
  }

  function setBadge(el, cls, text) {
    el.className = `badge ${cls}`;
    el.innerHTML = `<span class="dot"></span> ${text}`;
  }

  function appendLog(entry, clear = false) {
    const box = $("log-box");
    if (clear) box.innerHTML = "";
    const line = document.createElement("div");
    const level = entry.level || "info";
    line.className = `log-line ${level}`;
    const ts = (entry.ts || "").replace("T", " ").replace("Z", "");
    line.innerHTML = `<span class="ts">${ts}</span> <span class="lvl">[${level}]</span> ${escapeHtml(
      entry.message || ""
    )}`;
    box.appendChild(line);
    box.scrollTop = box.scrollHeight;
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function updateConnModeUI() {
    const mode = $("select-conn-mode").value;
    if (mode === "adb") {
      $("field-adb-path").style.display = "block";
      $("field-panda-url").style.display = "none";
    } else {
      $("field-adb-path").style.display = "none";
      $("field-panda-url").style.display = "block";
    }
  }

  async function refreshSettings() {
    state.settings = await api("/api/settings");
    $("input-device").value = state.settings.default_device || $("input-device").value || "";
    $("select-conn-mode").value = state.settings.connection_mode || "adb";
    $("input-adb-path").value = state.settings.adb_path || "";
    $("input-panda-url").value = state.settings.panda_url || "ws://127.0.0.1:22222/";
    $("select-dry").value = String(!!state.settings.dry_run);
    $("input-delay").value = state.settings.step_delay_ms || 600;
    updateConnModeUI();
    updateBadges();
  }

  async function refreshProfiles() {
    const data = await api("/api/profiles");
    const sel = $("select-profile");
    sel.innerHTML = "";
    (data.profiles || []).forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      if (p === (data.default || "admin_live")) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  async function refreshDevices() {
    const btnRefresh = document.getElementById("btn-refresh-devices");
    const btnClearLogs = document.getElementById("btn-clear-logs");
    const btnStreamStart = document.getElementById("btn-stream-start");
    const btnStreamStop = document.getElementById("btn-stream-stop");
    const streamImg = document.getElementById("live-stream-img");
    const streamPlaceholder = document.getElementById("live-stream-placeholder");
    const btnCalExport = document.getElementById("btn-cal-export");
    
    const list = $("device-list");
    try {
      const data = await api("/api/devices");
      state.devices = data.devices || [];
      setBadge(
        $("badge-panda"),
        data.panda_connected ? "ok" : "err",
        data.panda_connected ? "Client connected" : "Client offline"
      );
      if (!state.devices.length) {
        const hint = data.hint || data.message || "No devices. Check Panda connection or ADB USB debugging.";
        list.innerHTML = `<div class="muted">${escapeHtml(hint)}</div>
          <p class="muted" style="margin:.4rem 0 0">You can still paste serial / IP:port manually below for calibration once API is licensed.</p>`;
        return;
      }
      list.innerHTML = "";
      state.devices.forEach((d) => {
        const serial = d.serial || d.onlySerial || "";
        const btn = document.createElement("button");
        btn.className = "device-item" + (serial === $("input-device").value ? " active" : "");
        btn.innerHTML = `<strong>${escapeHtml(d.name || d.model || serial)}</strong>
          <span>${escapeHtml(serial)} · ${d.sourceWidth || "?"}x${d.sourceHeight || "?"} · ${d.status || ""}</span>`;
        btn.onclick = () => {
          $("input-device").value = serial;
          [...list.children].forEach((c) => c.classList.remove("active"));
          btn.classList.add("active");
        };
        list.appendChild(btn);
      });
    } catch (err) {
      setBadge($("badge-panda"), "err", "Client offline");
      list.innerHTML = `<div class="muted">Failed: ${escapeHtml(err.message)}</div>`;
    }
  }

  async function refreshBot() {
    state.bot = await api("/api/bot");
    updateBadges();
    $("bot-summary").textContent = `Status: ${state.bot.status} · device: ${state.bot.device || "-"
      } · profile: ${state.bot.profile} · dry_run: ${state.bot.dry_run}`;
    renderTasks(state.bot.tasks || []);
    renderQueue(state.bot.queue || [], state.bot.active_task);
  }

  function updateBadges() {
    const st = state.bot?.status || "stopped";
    setBadge(
      $("badge-bot"),
      st === "running" ? "ok" : st === "paused" ? "warn" : "",
      `Bot ${st}`
    );
    const dry = $("select-dry").value === "true";
    setBadge($("badge-dry"), dry ? "warn" : "ok", dry ? "Dry-run ON" : "LIVE taps");
  }

  function formatParams(params) {
    if (!params || Object.keys(params).length === 0) return `<div class="muted" style="margin:.5rem 0">No parameters</div>`;
    let html = '<div class="param-list">';
    for (const [k, v] of Object.entries(params)) {
      if (v === null || v === "") continue;
      const keyStr = escapeHtml(k.replace(/_/g, ' '));
      const valStr = escapeHtml(String(v));
      html += `<div class="param-item" style="font-size:10px;"><span class="key" style="color:#94a3b8; width:120px; display:inline-block; text-transform:capitalize;">${keyStr}:</span><span class="val" style="color:#e2e8f0; font-weight:500;">${valStr}</span></div>`;
    }
    html += '</div>';
    return html;
  }

  function renderQueue(queue, activeTask) {
    const activeLabel = $("active-task-label");
    if (activeTask) {
      activeLabel.innerHTML = `<strong>${escapeHtml(activeTask.type)}</strong> <span>(${escapeHtml(activeTask.id)})</span>`;
      activeLabel.style.color = "var(--ok)";
    } else {
      activeLabel.innerHTML = "None";
      activeLabel.style.color = "inherit";
    }

    const el = $("queue-list");
    if (!queue.length) {
      el.innerHTML = `<div class="muted">Queue empty.</div>`;
      return;
    }
    el.innerHTML = "";
    queue.forEach((t) => {
      const card = document.createElement("div");
      card.className = "task-card";
      card.style.padding = "0.5rem 0.75rem";
      card.innerHTML = `
        <header style="margin-bottom:0.25rem;">
          <strong>${escapeHtml(t.type)}</strong>
          <span class="muted" style="font-size:10px;">${t.manual ? 'Manual' : 'Scheduled'}</span>
        </header>
        <div class="btn-row" style="margin-top:0.25rem">
          <button class="btn btn-sm btn-danger" data-del-q="${t.id}">Batalkan</button>
        </div>`;
      el.appendChild(card);
    });
    
    el.querySelectorAll("[data-del-q]").forEach((btn) => {
      btn.onclick = async () => {
        await api(`/api/queue/${btn.dataset.delQ}`, { method: "DELETE" });
        refreshBot();
      };
    });
  }

  function renderTasks(tasks) {
    const el = $("task-list");
    if (!tasks.length) {
      el.innerHTML = `<div class="muted">No tasks yet.</div>`;
      return;
    }
    el.innerHTML = "";
    tasks.forEach((t) => {
      const card = document.createElement("div");
      card.className = "task-card";
      card.innerHTML = `
        <header>
          <strong>${escapeHtml(t.type)}</strong>
          <span class="pill ${t.enabled ? "on" : "off"}">${t.enabled ? "enabled" : "disabled"}</span>
        </header>
        <div class="meta">id=${escapeHtml(t.id)} · interval ${t.interval_sec}s · runs=${t.run_count || 0}</div>
        ${formatParams(t.params)}
        ${t.last_error ? `<div class="meta" style="color:var(--err)">err: ${escapeHtml(t.last_error)}</div>` : ""}
        <div class="btn-row" style="margin-top:.45rem">
          <button class="btn btn-sm btn-ok" data-action="start" data-id="${t.id}" ${t.enabled ? 'disabled' : ''}>Auto Pilot</button>
          <button class="btn btn-sm btn-warn" data-action="pause" data-id="${t.id}" ${!t.enabled ? 'disabled' : ''}>Pause</button>
          <button class="btn btn-sm btn-primary" data-action="run-now" data-id="${t.id}">Run Now</button>
          <button class="btn btn-sm btn-warn" data-action="stop" data-id="${t.id}">Stop</button>
          <button class="btn btn-sm btn-danger" data-del="${t.id}">Hapus</button>
        </div>`;
      el.appendChild(card);
    });
    
    el.querySelectorAll("[data-del]").forEach((btn) => {
      btn.onclick = async () => {
        await api(`/api/tasks/${btn.dataset.del}`, { method: "DELETE" });
        refreshBot();
      };
    });
    el.querySelectorAll("button[data-action]").forEach((btn) => {
      btn.onclick = async () => {
        const id = btn.dataset.id;
        const act = btn.dataset.action;
        
        if (act === "run-now") {
          const task = tasks.find(x => x.id === id);
          if (!task) return;
          try {
            await api("/api/tasks/run-once", {
              method: "POST",
              body: JSON.stringify({
                type: task.type,
                params: task.params,
                device: $("input-device").value.trim() || null,
                profile: $("select-profile").value,
                dry_run: $("select-dry").value === "true",
              }),
            });
            refreshBot();
          } catch (err) {
            alert(err.message);
          }
          return;
        }

        let patch = {};
        if (act === "start") patch = { enabled: true };
        else if (act === "pause") patch = { enabled: false };
        else if (act === "stop") patch = { enabled: false, run_count: 0 };
        
        await api(`/api/tasks/${id}`, {
          method: "PATCH",
          body: JSON.stringify(patch),
        });
        refreshBot();
      };
    });
  }

  function currentTaskPayload() {
    const type = state.activeTab;
    if (type === "lelang") {
      return {
        type,
        interval_sec: num($("lelang-interval").value, 300),
        params: {
          judul: $("lelang-judul").value || null,
          harga: $("lelang-harga").value || null,
          kelipatan_harga: $("lelang-kelipatan-harga").value || null,
          max_harga: $("lelang-max-harga").value || null,
          mode: $("lelang-mode").value,
          peserta: $("lelang-peserta").value,
          batas_waktu: $("lelang-batas").value,
        },
      };
    }
    if (type === "iklan_live") {
      return {
        type,
        interval_sec: num($("iklan-interval").value, 600),
        params: {
          tujuan: $("iklan-tujuan").value,
          roas: $("iklan-roas").value,
          roas_custom: $("iklan-roas-custom").value,
          durasi_hari: $("iklan-durasi-hari").value,
          durasi_jam: $("iklan-durasi-jam").value,
          tipe_modal: $("iklan-tipe-modal").value,
          modal_harian: num($("iklan-modal-harian").value, 10000),
        },
      };
    }
    if (type === "bonus_koin") {
      return {
        type,
        interval_sec: num($("bonus-interval").value, 1200),
        params: {
          untuk_dibagikan: num($("bonus-bagi").value, 100000),
          koin_per_klaim: num($("bonus-claim").value, 100),
          jumlah_klaim: num($("bonus-jumlah").value, 1000),
        },
      };
    }
    if (type === "hujan_bonus") {
      return {
        type,
        interval_sec: num($("hujan-interval").value, 600),
        params: { koin_dibagikan: num($("hujan-koin").value, 255) },
      };
    }
    return {
      type: "open_shopee",
      interval_sec: num($("open-interval").value, 3600),
      params: {},
    };
  }

  function num(v, fallback) {
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  }

  // ---- Calibration ----
  async function loadCalibration() {
    const profile = $("select-profile").value || "admin_live";
    const deviceParam = $("input-device").value ? `&device=${encodeURIComponent($("input-device").value.trim())}` : "";
    state.calibration = await api(`/api/calibration/checklist?profile=${encodeURIComponent(profile)}${deviceParam}`);
    state.refImages = state.calibration.reference_images || {};
    const done = state.calibration.progress.done;
    const total = state.calibration.progress.total;
    $("cal-progress-label").textContent = `${done} / ${total} calibrated`;
    $("cal-progress-bar").style.width = total ? `${(100 * done) / total}%` : "0%";
    renderChecklist();
    // Keep current key if still valid, else first uncalibrated, else first
    const items = state.calibration.items || [];
    let next = items.find((i) => i.key === state.activeCalKey);
    if (!next) next = items.find((i) => !i.calibrated) || items[0];
    if (next) selectCalPoint(next.key);
    updateRefImage();
  }

  function renderChecklist() {
    const box = $("cal-checklist");
    box.innerHTML = "";
    (state.calibration?.items || []).forEach((item) => {
      const btn = document.createElement("button");
      btn.className = "check-item" + (item.key === state.activeCalKey ? " active" : "");
      btn.innerHTML = `
        <div class="name">${escapeHtml(item.label)}</div>
        <div class="status ${item.calibrated ? "done" : ""}">${item.calibrated ? "done" : "todo"}</div>
        <div class="coords">${escapeHtml(item.key)} · ${item.x}%, ${item.y}%</div>`;
      btn.onclick = () => selectCalPoint(item.key);
      box.appendChild(btn);
    });
  }

  function selectCalPoint(key) {
    const item = (state.calibration?.items || []).find((i) => i.key === key);
    if (!item) return;
    state.activeCalKey = key;
    $("cal-key").value = item.key;
    $("cal-label").value = item.label;
    $("cal-x").value = item.x;
    $("cal-y").value = item.y;
    // Switch group image if group maps to a known image
    const group = item.group;
    const groupSelect = $("cal-group");
    const map = { home: "home", lelang: "lelang", iklan: "iklan", lainnya: "lainnya", bonus: "bonus", hujan: "hujan" };
    if (map[group]) groupSelect.value = map[group];
    updateRefImage();
    placeCrosshair(Number(item.x), Number(item.y));
    renderChecklist();
    $("cal-hint").textContent = `Calibrating: ${item.label}. Open that screen on the phone, then click the matching spot on the reference image.`;
  }

  function updateRefImage() {
    const group = $("cal-group").value;
    const src = state.refImages[group];
    const img = $("ref-image");
    if (src) {
      img.src = src;
      img.alt = group;
    }
  }

  function placeCrosshair(xPct, yPct) {
    const img = $("ref-image");
    const cross = $("ref-crosshair");
    if (!img.complete || !img.naturalWidth) {
      cross.style.display = "none";
      return;
    }
    const rect = img.getBoundingClientRect();
    const frame = $("ref-frame").getBoundingClientRect();
    const left = rect.left - frame.left + (rect.width * xPct) / 100;
    const top = rect.top - frame.top + (rect.height * yPct) / 100;
    cross.style.display = "block";
    cross.style.left = `${left}px`;
    cross.style.top = `${top}px`;
  }

  function onRefClick(ev) {
    const img = $("ref-image");
    const rect = img.getBoundingClientRect();
    if (ev.clientX < rect.left || ev.clientX > rect.right || ev.clientY < rect.top || ev.clientY > rect.bottom) {
      return;
    }
    const x = ((ev.clientX - rect.left) / rect.width) * 100;
    const y = ((ev.clientY - rect.top) / rect.height) * 100;
    $("cal-x").value = x.toFixed(1);
    $("cal-y").value = y.toFixed(1);
    placeCrosshair(x, y);
  }

  async function saveCalPoint(testTap) {
    const profile = $("select-profile").value || "admin_live";
    const key = $("cal-key").value;
    if (!key) return alert("Select a checklist point first");
    const x = $("cal-x").value;
    const y = $("cal-y").value;
    const device = $("input-device").value.trim();
    const deviceParam = device ? `?device=${encodeURIComponent(device)}` : "";
    const body = {
      key,
      x,
      y,
      label: $("cal-label").value,
      test_tap: !!testTap,
      device: device || null,
    };
    try {
      await api(`/api/profiles/${encodeURIComponent(profile)}/points${deviceParam}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      // Bind device serial into profile meta on first save
      if (device) {
        await api(`/api/profiles/${encodeURIComponent(profile)}`, {
          method: "PATCH",
          body: JSON.stringify({ device_serial: device }),
        });
      }
      await loadCalibration();
      // Advance to next uncalibrated
      const next = (state.calibration.items || []).find((i) => !i.calibrated);
      if (next) selectCalPoint(next.key);
    } catch (err) {
      alert(err.message);
    }
  }

  async function testTapOnly() {
    const device = $("input-device").value.trim();
    if (!device) return alert("Select a device first");
    try {
      await api("/api/tap", {
        method: "POST",
        body: JSON.stringify({
          device,
          x: $("cal-x").value,
          y: $("cal-y").value,
          dry_run: $("select-dry").value === "true",
        }),
      });
    } catch (err) {
      alert(err.message);
    }
  }

  // ---- Events ----
  function bind() {
    $("btn-scrcpy").addEventListener("click", async () => {
      try {
        const device = $("input-device").value.trim();
        const url = device ? `/api/scrcpy?device=${encodeURIComponent(device)}` : `/api/scrcpy`;
        await api(url, { method: "POST" });
      } catch (err) {
        alert("Failed to launch scrcpy: " + err.message);
      }
    });

    $("btn-stream-start").addEventListener("click", () => {
      try {
        const device = $("input-device").value.trim();
        const url = device ? `/api/stream?device=${encodeURIComponent(device)}` : `/api/stream`;
        const streamImg = $("live-stream-img");
        const streamPlaceholder = $("live-stream-placeholder");
        streamImg.src = url;
        streamImg.style.display = "block";
        streamPlaceholder.style.display = "none";
        streamActive = true;
      } catch (err) {
        alert("JS Error: " + err.message);
      }
    });

    $("btn-stream-stop").addEventListener("click", () => {
      const streamImg = $("live-stream-img");
      const streamPlaceholder = $("live-stream-placeholder");
      streamImg.src = "";
      streamImg.style.display = "none";
      streamPlaceholder.style.display = "block";
      streamActive = false;
    });

    $("task-tabs").addEventListener("click", (e) => {
      const tab = e.target.closest(".tab");
      if (!tab) return;
      state.activeTab = tab.dataset.tab;
      [...$("task-tabs").children].forEach((t) => t.classList.toggle("active", t === tab));
      document.querySelectorAll(".task-form").forEach((f) => f.classList.add("hidden"));
      $(`form-${state.activeTab}`).classList.remove("hidden");
    });

    $("btn-refresh-devices").onclick = () => refreshDevices();
    $("btn-reconnect").onclick = async () => {
      await api("/api/panda/reconnect", { method: "POST" });
      refreshDevices();
    };

    $("btn-save-settings").onclick = async () => {
      try {
        await api("/api/settings", {
          method: "PUT",
          body: JSON.stringify({
            connection_mode: $("select-conn-mode").value,
            adb_path: $("input-adb-path").value.trim() || undefined,
            panda_url: $("input-panda-url").value.trim() || undefined,
            default_device: $("input-device").value.trim(),
            default_profile: $("select-profile").value,
            dry_run: $("select-dry").value === "true",
            step_delay_ms: num($("input-delay").value, 600),
          }),
        });
        await refreshSettings();
        alert("Settings saved");
      } catch (err) {
        alert(err.message);
      }
    };

    $("select-dry").onchange = updateBadges;
    $("select-profile").onchange = () => loadCalibration();
    $("select-conn-mode").onchange = updateConnModeUI;

    $("btn-start").onclick = async () => {
      try {
        await api("/api/bot/control", {
          method: "POST",
          body: JSON.stringify({
            action: "start",
            device: $("input-device").value.trim(),
            profile: $("select-profile").value,
            dry_run: $("select-dry").value === "true",
          }),
        });
        refreshBot();
      } catch (err) {
        alert(err.message);
      }
    };
    $("btn-pause").onclick = async () => {
      await api("/api/bot/control", { method: "POST", body: JSON.stringify({ action: "pause" }) });
      refreshBot();
    };
    $("btn-stop").onclick = async () => {
      await api("/api/bot/control", { method: "POST", body: JSON.stringify({ action: "stop" }) });
      refreshBot();
    };

    $("btn-add-task").onclick = async () => {
      const payload = currentTaskPayload();
      // strip null judul
      if (payload.params && payload.params.judul === null) delete payload.params.judul;
      try {
        await api("/api/tasks", { method: "POST", body: JSON.stringify({ ...payload, enabled: true }) });
        refreshBot();
      } catch (err) {
        alert(err.message);
      }
    };

    $("btn-run-once").onclick = async () => {
      const payload = currentTaskPayload();
      if (payload.params && payload.params.judul === null) delete payload.params.judul;
      try {
        await api("/api/tasks/run-once", {
          method: "POST",
          body: JSON.stringify({
            type: payload.type,
            params: payload.params,
            device: $("input-device").value.trim() || null,
            profile: $("select-profile").value,
            dry_run: $("select-dry").value === "true",
          }),
        });
      } catch (err) {
        alert(err.message);
      }
    };

    $("btn-clear-tasks").onclick = async () => {
      if (!confirm("Clear all scheduled tasks?")) return;
      await api("/api/tasks", { method: "DELETE" });
      refreshBot();
    };

    $("btn-clear-queue").onclick = async () => {
      if (!confirm("Clear execution queue?")) return;
      await api("/api/queue", { method: "DELETE" });
      refreshBot();
    };

    $("btn-clear-logs").onclick = () => {
      $("log-box").innerHTML = "";
    };

    $("btn-cal-export").onclick = () => {
      const profile = $("select-profile").value || "admin_live";
      const deviceParam = $("input-device").value ? `?device=${encodeURIComponent($("input-device").value.trim())}` : "";
      window.open(`/api/profiles/${encodeURIComponent(profile)}/export${deviceParam}`, "_blank");
    };

    $("file-import").onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const profile = $("select-profile").value || "admin_live";
      const deviceParam = $("input-device").value ? `?device=${encodeURIComponent($("input-device").value.trim())}` : "";
      const formData = new FormData();
      formData.append("file", file);
      try {
        const res = await fetch(`/api/profiles/${encodeURIComponent(profile)}/import${deviceParam}`, {
          method: "POST",
          body: formData,
        });
        if (!res.ok) throw new Error(await res.text());
        alert("Calibration imported successfully!");
        loadCalibration();
      } catch (err) {
        alert("Import failed: " + err.message);
      }
      e.target.value = "";
    };

    $("cal-group").onchange = () => {
      updateRefImage();
    };
    $("ref-image").onclick = onRefClick;
    $("ref-image").onload = () => {
      placeCrosshair(Number($("cal-x").value || 0), Number($("cal-y").value || 0));
    };
    window.addEventListener("resize", () => {
      placeCrosshair(Number($("cal-x").value || 0), Number($("cal-y").value || 0));
    });
    $("btn-cal-save").onclick = () => saveCalPoint(false);
    $("btn-cal-save-tap").onclick = () => saveCalPoint(true);
    $("btn-cal-test-only").onclick = () => testTapOnly();
    $("btn-cal-capture").onclick = () => {
      const dev = $("input-device").value.trim() || state.settings.default_device;
      if (!dev) return alert("No default device selected.");
      const img = $("ref-image");
      img.src = `/api/screen?device=${encodeURIComponent(dev)}&t=${Date.now()}`;
      img.style.display = "block";
      $("cal-hint").textContent = "Menampilkan Live Capture ADB. Silakan klik pada gambar untuk mendapatkan kordinat.";
    };
  }

  function connectLogs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/logs`);
    ws.onmessage = (ev) => {
      try {
        appendLog(JSON.parse(ev.data));
      } catch {
        /* ignore */
      }
    };
    ws.onclose = () => setTimeout(connectLogs, 1500);
  }

  async function init() {
    bind();
    connectLogs();
    await refreshSettings();
    await refreshProfiles();
    await refreshDevices();
    await refreshBot();
    await loadCalibration();
    setInterval(() => {
      refreshBot().catch(() => { });
      refreshDevices().catch(() => { });
    }, 5000);
  }

  init().catch((err) => {
    console.error(err);
    appendLog({ level: "error", message: String(err), ts: new Date().toISOString() });
  });
})();
