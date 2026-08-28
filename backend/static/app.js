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

  const num = (val, def) => { const v = parseInt(val, 10); return isNaN(v) ? def : v; };
  function updateDeviceHeaders() {
    const devLabel = $("input-device").value ? `(${$("input-device").value})` : "";
    if ($("header-dev-1")) $("header-dev-1").textContent = devLabel;
    if ($("header-dev-2")) $("header-dev-2").textContent = devLabel;
    if ($("header-dev-3")) $("header-dev-3").textContent = devLabel;
  }

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
    const feed = $("mock-feed-list");
    if (clear && box) box.innerHTML = "";
    const line = document.createElement("div");
    const level = entry.level || "info";
    line.className = `log-line ${level}`;
    const ts = (entry.ts || "").replace("T", " ").replace("Z", "");
    const msg = escapeHtml(entry.message || "");

    if (box) {
      line.innerHTML = `<span class="ts">${ts}</span> <span class="lvl">[${level}]</span> ${msg}`;
      box.appendChild(line);
      box.scrollTop = box.scrollHeight;
    }

    if (feed) {
      const timeOnly = ts.split(" ")[1] || ts;
      const feedItem = document.createElement("div");
      feedItem.className = "feed-item";
      feedItem.innerHTML = `
        <div class="feed-time">${timeOnly}</div>
        <div class="feed-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg></div>
        <div class="feed-content">
          <strong>[${level.toUpperCase()}]</strong> ${msg}
        </div>
      `;
      feed.insertBefore(feedItem, feed.firstChild);
      if (feed.children.length > 50) feed.removeChild(feed.lastChild);
    }
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
        const devName = d.name || (d.brand && d.brand !== "Unknown" ? `${d.brand} ${d.model}` : d.model) || serial;
        const devMfg = d.manufacturer && d.manufacturer !== "Unknown" ? `${d.manufacturer} · ` : "";
        btn.innerHTML = `<strong>${escapeHtml(devName)}</strong>
          <span>${escapeHtml(serial)} · ${escapeHtml(devMfg)}${d.sourceWidth || "?"}x${d.sourceHeight || "?"} · ${d.status || ""}</span>`;
        btn.onclick = () => {
          $("input-device").value = serial;
          [...list.children].forEach((c) => c.classList.remove("active"));
          btn.classList.add("active");
          refreshBot();
          updateDeviceHeaders();
        };
        list.appendChild(btn);
      });
    } catch (err) {
      setBadge($("badge-panda"), "err", "Client offline");
      list.innerHTML = `<div class="muted">Failed: ${escapeHtml(err.message)}</div>`;
    }
  }

  async function refreshBot() {
    const dev = encodeURIComponent($("input-device").value.trim());
    state.bot = await api(`/api/bot?device=${dev}`);
    updateBadges();
    if ($("bot-summary")) {
      $("bot-summary").textContent = `Status: ${state.bot.status} · device: ${state.bot.device || "-"} · profile: ${state.bot.profile} · dry_run: ${state.bot.dry_run}`;
    }
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
    if (activeLabel) {
      if (activeTask) {
        activeLabel.innerHTML = `<strong>${escapeHtml(activeTask.type)}</strong> <span>(${escapeHtml(activeTask.id)})</span>`;
        activeLabel.style.color = "var(--ok)";
      } else {
        activeLabel.innerHTML = "None";
        activeLabel.style.color = "inherit";
      }
    }

    const el = $("queue-list");
    if (!el) return;
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
        const dev = encodeURIComponent($("input-device").value.trim());
        await api(`/api/queue/${btn.dataset.delQ}?device=${dev}`, { method: "DELETE" });
        refreshBot();
      };
    });
  }

  function renderTasks(tasks) {
    const el = $("task-list");
    if (!el) return;
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
        const dev = encodeURIComponent($("input-device").value.trim());
        await api(`/api/tasks/${btn.dataset.del}?device=${dev}`, { method: "DELETE" });
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

        await api(`/api/tasks/${id}?device=${encodeURIComponent($("input-device").value.trim())}`, {
          method: "PATCH",
          body: JSON.stringify(patch),
        });
        refreshBot();
      };
    });
  }

  window.handleTaskAction = async function (action, taskType) {
    const payload = window.currentTaskPayload(taskType);
    if (payload.params && payload.params.judul === null) delete payload.params.judul;

    try {
      const dev = encodeURIComponent($("input-device").value.trim());

      if (action === 'add') {
        await api(`/api/tasks?device=${dev}`, { method: "POST", body: JSON.stringify({ ...payload, enabled: true }) });
      } else if (action === 'run') {
        await api("/api/tasks/run-once", {
          method: "POST",
          body: JSON.stringify({
            type: payload.type,
            device_serial: dev,
            params: payload.params,
          }),
        });
      }
      refreshBot();
    } catch (err) {
      alert(err.message);
    }
  };

  window.updateIklanFields = function () {
    const tujuan = $("iklan-tujuan");
    const roasRow = $("iklan-roas-row");
    const roas = $("iklan-roas");
    const roasCustom = $("iklan-roas-custom-field");
    const tipeModal = $("iklan-tipe-modal");
    const modalHarian = $("iklan-modal-harian-field");
    const modalPenambahan = $("iklan-penambahan-modal-field");

    if (tujuan && roasRow) {
      roasRow.style.display = tujuan.value === "GMV (Max ROAS)" ? "flex" : "none";
    }
    if (roas && roasCustom) {
      roasCustom.style.display = roas.value === "Masukan Target" ? "block" : "none";
    }
    if (tipeModal && modalHarian && modalPenambahan) {
      const isHarian = tipeModal.value === "Atur Modal Harian";
      modalHarian.style.display = isHarian ? "block" : "none";
      modalPenambahan.style.display = isHarian ? "block" : "none";
    }
  };

  window.currentTaskPayload = function (type) {
    type = type || state.activeTab;
    const operator = document.querySelector('.operator-input') ? document.querySelector('.operator-input').value.trim() : null;

    let result = {};
    if (type === "lelang") {
      result = {
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
    } else if (type === "iklan_live") {
      result = {
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
          penambahan_modal: num($("iklan-penambahan-modal").value, 5000),
        },
      };
    } else if (type === "bonus_koin") {
      result = {
        type,
        interval_sec: num($("bonus-interval").value, 1200),
        params: {
          untuk_dibagikan: num($("bonus-bagi").value, 100000),
          koin_per_klaim: num($("bonus-claim").value, 100),
        },
      };
    } else if (type === "hujan_bonus") {
      result = {
        type,
        interval_sec: num($("hujan-interval").value, 600),
        params: { koin_dibagikan: num($("hujan-koin").value, 255) },
      };
    } else {
      result = {
        type: "open_shopee",
        interval_sec: num($("open-interval") ? $("open-interval").value : 3600, 3600),
        params: {},
      };
    }

    if (operator) result.params.operator = operator;
    return result;
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


    if ($("task-tabs")) $("task-tabs").addEventListener("click", (e) => {
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

    if ($("btn-start")) $("btn-start").onclick = async () => {
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
    if ($("btn-pause")) $("btn-pause").onclick = async () => {
      await api("/api/bot/control", { method: "POST", body: JSON.stringify({ action: "pause" }) });
      refreshBot();
    };
    if ($("btn-stop")) $("btn-stop").onclick = async () => {
      await api("/api/bot/control", { method: "POST", body: JSON.stringify({ action: "stop" }) });
      refreshBot();
    };

    if ($("btn-add-task")) $("btn-add-task").onclick = async () => {
      const payload = currentTaskPayload();
      // strip null judul
      if (payload.params && payload.params.judul === null) delete payload.params.judul;
      try {
        const dev = encodeURIComponent($("input-device").value.trim());
        await api(`/api/tasks?device=${dev}`, { method: "POST", body: JSON.stringify({ ...payload, enabled: true }) });
        refreshBot();
      } catch (err) {
        alert(err.message);
      }
    };

    if ($("btn-run-once")) $("btn-run-once").onclick = async () => {
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

    if ($("btn-clear-tasks")) $("btn-clear-tasks").onclick = async () => {
      if (!confirm("Clear all scheduled tasks?")) return;
      const dev = encodeURIComponent($("input-device").value.trim());
      await api(`/api/tasks?device=${dev}`, { method: "DELETE" });
      refreshBot();
    };

    if ($("btn-clear-queue")) $("btn-clear-queue").onclick = async () => {
      if (!confirm("Clear execution queue?")) return;
      const dev = encodeURIComponent($("input-device").value.trim());
      await api(`/api/queue?device=${dev}`, { method: "DELETE" });
      refreshBot();
    };

    if ($("btn-clear-logs")) $("btn-clear-logs").onclick = () => {
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
        <div class="coords">${escapeHtml(item.key)} ┬╖ ${item.x}%, ${item.y}%</div>`;
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



  // MONITORING LOGIC
  let monitorInterval = null;

  async function refreshMonitor() {
    try {
      const bots = await api("/api/bots");
      const grid = document.getElementById("monitor-grid");
      grid.innerHTML = "";

      const devices = state.devices || [];

      if (Object.keys(bots).length === 0 && devices.length === 0) {
        grid.innerHTML = "<div class='muted'>No devices connected.</div>";
        return;
      }

      // Merge known devices and bot states
      const allSerials = new Set([...devices.map(d => d.serial), ...Object.keys(bots)]);

      allSerials.forEach(serial => {
        const d = devices.find(x => x.serial === serial) || {};
        const b = bots[serial] || { status: "offline", queue_length: 0, active_task: null };

        const devName = d.name || (d.brand && d.brand !== "Unknown" ? `${d.brand} ${d.model}` : d.model) || serial;

        const card = document.createElement("div");
        card.className = "monitor-card";

        const isRunning = b.status === "running";
        const statusColor = isRunning ? "var(--ok)" : b.status === "paused" ? "var(--warn)" : "var(--fg)";

        card.innerHTML = `
          <header>
            <span class="device-title">${escapeHtml(devName)}</span>
            <span style="color: ${statusColor}; font-weight: bold;">${b.status.toUpperCase()}</span>
          </header>
          <div class="status-row">
            <span>Active Task:</span>
            <span class="task-active">${b.active_task ? escapeHtml(b.active_task.type) : "None"}</span>
          </div>
          <div class="queue-info">Queue: ${b.queue_length} tasks</div>
        `;

        // Clicking a card navigates to config view and selects the device
        card.onclick = () => {
          // Select this device
          $("input-device").value = serial;
          updateDeviceHeaders();

          // Switch to config view
          document.querySelector('.nav-item[data-view="config"]').click();

          // Trigger device select visual update
          document.querySelectorAll('.device-item').forEach(c => {
            c.classList.remove('active');
            if (c.textContent.includes(serial)) c.classList.add('active');
          });
          refreshBot();
          refreshTasks();
        };

        grid.appendChild(card);
      });

    } catch (err) {
      console.error("Monitor refresh failed", err);
    }
  }

  function startMonitorLoop() {
    refreshMonitor();
    if (!monitorInterval) {
      monitorInterval = setInterval(refreshMonitor, 2000);
    }
  }

  function stopMonitorLoop() {
    if (monitorInterval) {
      clearInterval(monitorInterval);
      monitorInterval = null;
    }
  }

  let dashboardInterval = null;

  function startDashboardLoop() {
    renderModernDashboard();
    if (!dashboardInterval) {
      dashboardInterval = setInterval(renderModernDashboard, 2000);
    }
  }

  function stopDashboardLoop() {
    if (dashboardInterval) {
      clearInterval(dashboardInterval);
      dashboardInterval = null;
    }
  }

  // Init loops if active tab matches
  const activeView = document.querySelector('.nav-item.active').dataset.view;
  if (activeView === "monitor") {
    startMonitorLoop();
  } else if (activeView === "dashboard_new") {
    startDashboardLoop();
  }

  // SIDEBAR TOGGLE
  const btnToggle = document.getElementById('btn-toggle-sidebar');
  if (btnToggle) {
    btnToggle.onclick = () => {
      document.getElementById('app-sidebar').classList.toggle('collapsed');
    };
  }

  // ========================================== //
  // HOSTAR DASHBOARD MODERN (MOCK DATA)        //
  // ========================================== //

  function renderModernDashboard() {
    api("/api/bots").then(bots => {
      const devices = state.devices || [];

      let totalConnected = devices.length;
      let totalTasks = 0;
      let executingTasks = 0;
      let idleCount = 0;
      let errorCount = 0;

      const allSerials = new Set([...devices.map(d => d.serial), ...Object.keys(bots)]);

      let gridHtml = "";
      let tableHtml = "";
      let hasAnyTask = false;

      if (allSerials.size === 0) {
        gridHtml = '<div class="muted">Belum ada device yang terhubung.</div>';
      }

      allSerials.forEach(serial => {
        const d = devices.find(x => x.serial === serial) || {};
        const b = bots[serial] || { status: "offline", tasks: [] };
        const devName = d.name || (d.brand && d.brand !== "Unknown" ? `${d.brand} ${d.model}` : d.model) || serial;

        if (b.status === "paused" || b.status === "stopped") idleCount++;

        let tasksHtml = "";

        // Combine scheduled tasks, active task, and queued tasks
        let allDevTasks = [...(b.tasks || [])];
        if (b.active_task && !allDevTasks.find(x => x.id === b.active_task.id)) allDevTasks.push(b.active_task);
        (b.queue || []).forEach(qt => {
          if (!allDevTasks.find(x => x.id === qt.id)) allDevTasks.push(qt);
        });

        allDevTasks.forEach(t => {
          hasAnyTask = true;
          if (t.enabled || t.manual) totalTasks++;
          if (t.last_error) errorCount++;

          let cls = 'idle';
          let label = 'IDLE';
          let isActive = (b.active_task && b.active_task.id === t.id);
          let isQueued = (b.queue || []).find(x => x.id === t.id);

          if (t.last_error) { cls = 'error'; label = 'ERROR'; }
          else if (isActive) { cls = 'live'; label = 'RUNNING'; executingTasks++; }
          else if (isQueued) { cls = 'warn'; label = 'QUEUED'; }
          else if (b.status === 'running' && t.enabled) { cls = 'live'; label = 'LIVE'; }
          else if (b.status === 'paused' || !t.enabled) { cls = 'pause'; label = 'PAUSE'; }

          let bid = "-";
          let eta = "-";
          if (t.type === 'lelang') {
            bid = t.params.harga ? "Rp " + Number(t.params.harga).toLocaleString("id-ID") : "-";
            eta = t.params.batas_waktu || "-";
          } else if (t.type === 'iklan_live') {
            let modal = t.params.modal || t.params.modal_harian || t.params.penambahan_modal || 0;
            bid = modal ? "Rp " + Number(modal).toLocaleString("id-ID") : "No Limit";
            eta = t.params.tujuan || "-";
          } else if (t.type === 'bonus_coin') {
            bid = t.params.jumlah_koin ? t.params.jumlah_koin + " Koin" : "-";
            eta = t.params.jumlah_claim ? t.params.jumlah_claim + " Klaim" : "-";
          } else if (t.type === 'hujan_bonus') {
            bid = t.params.koin ? t.params.koin + " Koin" : "-";
            eta = t.params.durasi || "-";
          }
          
          if (cls === 'idle' || cls === 'error') {
            // Optional: keep real values even if idle/error, but maybe dim them?
            // The original logic hid them. Let's show the real config anyway!
          }

          let op = t.params.operator || "Auto";
          let prod = t.type.toUpperCase() + (t.params.judul ? " - " + t.params.judul : "");
          if (t.manual) prod = "[Manual] " + prod;

          tasksHtml += `
          <div style="border-top: 1px solid var(--border); padding-top: 0.4rem; margin-top: 0.4rem;">
            <div class="dc-product" style="display:flex; justify-content:space-between; align-items:center;">
              <strong>${escapeHtml(prod)}</strong>
              <span class="badge-status ${cls}">● ${label}</span>
            </div>
            <div class="dc-stats">
              <div><span>Target/Nilai</span> <span class="text-green">${bid}</span></div>
              <div><span>Info/Durasi</span> <span>${eta}</span></div>
              <div><span>Op</span> <span>${escapeHtml(op)}</span></div>
            </div>
          </div>
        `;

          if ((cls === 'live' || cls === 'warn' || isActive) && t.type === 'lelang') {
            tableHtml += `
            <tr>
              <td><a href="#" class="t-dev">${escapeHtml(devName)}</a></td>
              <td>${escapeHtml(prod)}</td>
              <td><span class="badge-status ${cls}">● ${label}</span></td>
              <td class="t-bid">${bid}</td>
              <td>${eta}</td>
              <td>${escapeHtml(op)}</td>
            </tr>
          `;
          }
        });

        if (allDevTasks.length > 0) {
          let devStatusCls = b.status === "running" ? "live" : (b.status === "paused" ? "pause" : "idle");
          gridHtml += `
          <div class="device-card-modern">
            <div class="dc-header">
              <div>
                <h4 class="dc-title">${escapeHtml(devName)}</h4>
                <div class="dc-subtitle">${escapeHtml(d.brand || "Unknown")}</div>
              </div>
              <span class="badge-status ${devStatusCls}">● ${b.status.toUpperCase()}</span>
            </div>
            ${tasksHtml}
          </div>
        `;
        }
      });

      if (!hasAnyTask && allSerials.size > 0) {
        gridHtml = '<div class="muted">Device terhubung, namun belum ada tugas (task) yang dikonfigurasi.</div>';
      }

      const kpiValues = document.querySelectorAll('.kpi-value');
      if (kpiValues.length >= 5) {
        kpiValues[0].innerText = totalConnected;
        kpiValues[1].innerText = totalTasks;
        kpiValues[2].innerText = executingTasks;
        kpiValues[3].innerText = idleCount;
        kpiValues[4].innerText = errorCount;
      }

      const grid = document.getElementById("mock-device-grid");
      const table = document.getElementById("mock-ticker-table");
      if (grid) grid.innerHTML = gridHtml;
      if (table) table.innerHTML = tableHtml || '<tr><td colspan="6" class="muted">Tidak ada lelang aktif</td></tr>';
    }).catch(e => console.error("Error fetching bots for dashboard:", e));

    setTimeout(() => {
      if (window.Chart && !window.myActivityChart) {
        const ctx = document.getElementById('activityChart');
        if (ctx) {
          window.myActivityChart = new Chart(ctx, {
            type: 'line',
            data: {
              labels: ['17:20', '17:50', '18:40', '19:20', '20:00', '20:40', '20:41', '20:43', '20:45'],
              datasets: [
                { label: 'Aktivitas Bid', data: [10, 15, 9, 14, 8, 15, 12, 10, 14], borderColor: '#3b82f6', tension: 0.4, borderWidth: 2 },
                { label: 'Device LIVE', data: [13, 14, 13, 15, 14, 13, 15, 15, 15], borderColor: '#00b87c', tension: 0.4, borderWidth: 2 }
              ]
            },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, grid: { color: '#1e293b' } }, x: { grid: { color: '#1e293b' } } }, plugins: { legend: { display: false } } }
          });
        }
      }
    }, 500);
  }



  // Hook into view switching to render the mock data when New Dashboard is shown

  // Hook into view switching (Updated for Partials)
  const navItems = document.querySelectorAll(".nav-item[data-view]");
  navItems.forEach(btn => {
    btn.addEventListener("click", (e) => {
      console.log("Sidebar clicked:", btn.dataset.view);

      // Hide all
      document.querySelectorAll(".view-panel").forEach(v => {
        v.classList.add("hidden");
        v.style.display = 'none'; // Force hide just in case
      });
      document.querySelectorAll(".nav-item[data-view]").forEach(b => b.classList.remove("active"));
      
      // Stop loops
      stopMonitorLoop();
      stopDashboardLoop();

      // Show target
      btn.classList.add("active");
      const target = document.getElementById("view-" + btn.dataset.view);
      if (target) {
        target.classList.remove("hidden");
        target.style.display = 'block'; // Force show just in case
        console.log("Unhidden target:", target.id);
      } else {
        console.error("Target view not found:", "view-" + btn.dataset.view);
      }

      // Run logic for specific views
      if (btn.dataset.view === "dashboard_new") {
        startDashboardLoop();
      } else if (btn.dataset.view === "monitor") {
        startMonitorLoop();
      }

      // Load partial if data-partial exists (Task Creation)
      if (btn.dataset.partial) {
        const container = document.getElementById("dynamic-task-container");
        const title = document.getElementById("task-form-title");
        if (container) {
          container.innerHTML = '<div class="muted">Loading ' + btn.dataset.partial + '...</div>';

          // Update Title based on clicked menu text
          const navText = btn.querySelector('.nav-text');
          if (navText && title) {
            // Keep the span for header-dev-1
            const devSpan = title.querySelector('#header-dev-1');
            title.innerHTML = 'Configure ' + navText.innerText;
            if (devSpan) title.appendChild(devSpan);
          }

          fetch('/static/views/' + btn.dataset.partial)
            .then(res => {
              if (!res.ok) throw new Error("HTTP " + res.status);
              return res.text();
            })
            .then(html => {
              container.innerHTML = html;
              // Re-bind listeners for the newly injected buttons
              bindPartialButtons();
            })
            .catch(err => {
              container.innerHTML = '<div class="text-red">Gagal memuat komponen: ' + err.message + '</div>';
            });
        }
      }
    });
  });

  // Helper to bind events dynamically for the newly loaded forms
  function bindPartialButtons() {
    const addBtn = document.querySelector('.btn-add-task-partial');
    const runBtn = document.querySelector('.btn-run-once-partial');

    if (addBtn) {
      addBtn.onclick = () => {
        const task = addBtn.dataset.task;
        handleTaskAction('add', task);
      };
    }

    if (runBtn) {
      runBtn.onclick = () => {
        const task = runBtn.dataset.task;
        handleTaskAction('run', task);
      };
    }
  }

  // Re-route original handleTaskAction logic here if needed, or assume it's in the old code.
  // We just need to make sure handleTaskAction (or btn-add-task logic) exists globally.


})();
