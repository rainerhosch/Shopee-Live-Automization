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

  // ---- Events ----
  function bind() {


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
        const dev = encodeURIComponent($("input-device").value.trim());
        await api(`/api/tasks?device=${dev}`, { method: "POST", body: JSON.stringify({ ...payload, enabled: true }) });
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
      const dev = encodeURIComponent($("input-device").value.trim());
      await api(`/api/tasks?device=${dev}`, { method: "DELETE" });
      refreshBot();
    };

    $("btn-clear-queue").onclick = async () => {
      if (!confirm("Clear execution queue?")) return;
      const dev = encodeURIComponent($("input-device").value.trim());
      await api(`/api/queue?device=${dev}`, { method: "DELETE" });
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

