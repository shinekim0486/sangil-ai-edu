"use strict";
(() => {
  const records = window.GAME_GALLERY || [];
  const $ = (id) => document.getElementById(id);
  const labels = { screen: "주행 기록 화면", camera: "도로 영상" };
  let category = "all";
  let filtered = [];
  let current = 0;
  let opener = null;
  const fileUrl = (filename) => encodeURIComponent(filename);
  const compare = (a, b) => a.localeCompare(b, "ko", { numeric: true });
  const size = (bytes) => `${(bytes / 1024).toFixed(1)} KB`;

  function showImage(index) {
    current = index;
    const record = filtered[current];
    if (!record) return;
    $("viewer-title").textContent = record.title;
    $("viewer-category").textContent = `${labels[record.category]} / STUDENT WORK`;
    $("viewer-image").src = fileUrl(record.files[0]);
    $("viewer-image").alt = record.title;
    $("viewer-info").textContent = `${record.width} × ${record.height} px · PNG · ${size(record.bytes)} · 동일 이미지 파일 ${record.files.length}개`;
    $("viewer-position").textContent = `${current + 1} / ${filtered.length}`;
    $("previous").disabled = current === 0;
    $("next").disabled = current === filtered.length - 1;
    $("original-size").checked = false;
    $("viewer-stage").classList.remove("original");
    $("viewer-stage").scrollTo(0, 0);
    $("downloads").replaceChildren(...record.files.map((filename) => {
      const link = document.createElement("a");
      link.href = fileUrl(filename);
      link.download = filename;
      link.textContent = `${filename} ↓`;
      return link;
    }));
  }

  function openImage(index, trigger) {
    opener = trigger;
    showImage(index);
    $("viewer").showModal();
    $("viewer").scrollTop = 0;
    document.body.style.overflow = "hidden";
    $("close-viewer").focus();
  }

  function render() {
    const terms = $("search").value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    filtered = records.filter((record) => {
      const searchable = `${record.title} ${labels[record.category]} ${record.files.join(" ")}`.toLocaleLowerCase();
      return (category === "all" || record.category === category) && terms.every((term) => searchable.includes(term));
    });
    filtered.sort((a, b) => {
      if ($("sort").value === "name") return compare(a.files[0], b.files[0]);
      if ($("sort").value === "size") return b.width * b.height - a.width * a.height || a.id - b.id;
      return a.id - b.id;
    });
    $("result-count").textContent = `전체 ${records.length}개 장면 중 ${filtered.length}개 · 동일 이미지 복사본 묶음`;
    $("empty").hidden = filtered.length !== 0;
    const cards = filtered.map((record, index) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "card";
      card.setAttribute("aria-label", `${record.title} 상세 보기`);
      const thumbnail = document.createElement("div");
      thumbnail.className = "thumbnail";
      const image = document.createElement("img");
      image.src = fileUrl(record.files[0]);
      image.alt = record.title;
      image.loading = "lazy";
      image.width = record.width;
      image.height = record.height;
      thumbnail.append(image);
      const number = document.createElement("span");
      number.className = "image-index";
      number.textContent = `RECORD ${String(record.id).padStart(2, "0")}`;
      thumbnail.append(number);
      if (record.files.length > 1) {
        const copies = document.createElement("span");
        copies.className = "copy-count";
        copies.textContent = `동일 파일 ${record.files.length}개`;
        thumbnail.append(copies);
      }
      const content = document.createElement("span");
      content.className = "card-content";
      const badge = document.createElement("span");
      badge.className = "card-category";
      badge.textContent = record.category === "screen" ? "INTERFACE / 주행 기록" : "CAMERA / 도로 영상";
      const title = document.createElement("span");
      title.className = "card-title";
      title.textContent = record.title;
      const meta = document.createElement("span");
      meta.className = "card-meta";
      const detail = document.createElement("span");
      detail.textContent = `${record.width} × ${record.height} · PNG`;
      const arrow = document.createElement("span");
      arrow.textContent = "↗";
      arrow.setAttribute("aria-hidden", "true");
      meta.append(detail, arrow);
      content.append(badge, title, meta);
      card.append(thumbnail, content);
      card.addEventListener("click", () => openImage(index, card));
      return card;
    });
    $("cards").replaceChildren(...cards);
  }

  function reset() {
    category = "all";
    $("search").value = "";
    $("sort").value = "default";
    document.querySelectorAll("[data-category]").forEach((button) => {
      const active = button.dataset.category === "all";
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    render();
  }

  $("stat-files").textContent = records.reduce((total, record) => total + record.files.length, 0);
  $("stat-unique").textContent = records.length;
  $("stat-screen").textContent = records.filter((record) => record.category === "screen").length;
  $("stat-camera").textContent = records.filter((record) => record.category === "camera").length;
  const featured = records.find((record) => record.category === "camera");
  if (featured) $("featured-image").src = fileUrl(featured.files[0]);
  document.querySelectorAll("[data-category]").forEach((button) => button.addEventListener("click", () => {
    category = button.dataset.category;
    document.querySelectorAll("[data-category]").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    render();
  }));
  $("search").addEventListener("input", render);
  $("sort").addEventListener("change", render);
  $("reset").addEventListener("click", reset);
  $("empty-reset").addEventListener("click", reset);
  $("close-viewer").addEventListener("click", () => $("viewer").close());
  $("viewer").addEventListener("close", () => {
    document.body.style.overflow = "";
    if (opener && opener.isConnected) opener.focus({ preventScroll: true });
  });
  $("viewer").addEventListener("click", (event) => {
    const rect = $("viewer").getBoundingClientRect();
    if (event.target === $("viewer") && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) $("viewer").close();
  });
  $("previous").addEventListener("click", () => { if (current > 0) showImage(current - 1); });
  $("next").addEventListener("click", () => { if (current < filtered.length - 1) showImage(current + 1); });
  $("original-size").addEventListener("change", () => $("viewer-stage").classList.toggle("original", $("original-size").checked));
  document.addEventListener("keydown", (event) => {
    if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
    if ($("viewer").open) {
      if (event.key === "ArrowLeft" && current > 0) { event.preventDefault(); showImage(current - 1); }
      if (event.key === "ArrowRight" && current < filtered.length - 1) { event.preventDefault(); showImage(current + 1); }
    } else if (event.key === "/") { event.preventDefault(); $("search").focus(); }
  });
  render();
})();
