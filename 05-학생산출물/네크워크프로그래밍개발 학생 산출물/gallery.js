"use strict";
(() => {
  const docs = window.GALLERY_DATA || [];
  const stages = {
    1: { title: "패킷 구조 설계", label: "1차시 · 패킷 설계", description: "패킷 필드와 TYPE을 정의하고 오류 검사 방식을 비교한 설계 기록" },
    2: { title: "네트워크 지연 측정", label: "2차시 · 지연 측정", description: "RTT와 패킷 유실을 측정하고 전송 전략의 효과를 비교한 실험 기록" },
    3: { title: "안전 프로토콜 설계", label: "3차시 · 안전 규칙", description: "측정 근거를 바탕으로 안전 규칙과 검증 방법을 정리한 설계 기록" }
  };
  const $ = (id) => document.getElementById(id);
  const state = { className: "all", stage: "all" };
  const escape = (text) => String(text).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const compare = (a, b) => a.localeCompare(b, "ko", { numeric: true });
  const sourceUrl = (doc) => doc.path.split("/").map(encodeURIComponent).join("/");

  function inline(text) {
    const tokens = [];
    const token = (html) => { tokens.push(html); return `\u0000${tokens.length - 1}\u0000`; };
    let value = text.replace(/`([^`]+)`/g, (_, code) => token(`<code>${escape(code)}</code>`));
    value = escape(value);
    value = value.replace(/\\([\\`*_{}\[\]()#+.!|>~-])/g, (_, char) => token(escape(char)));
    value = value.replace(/\[([^\]]+)\]\(([^\s)]+)\)/g, (_, label, url) => {
      if (!/^https?:\/\//i.test(url)) return label;
      return `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`;
    });
    value = value.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/__(.+?)__/g, "<strong>$1</strong>");
    value = value.replace(/(^|\s)\*([^*\n]+)\*(?=\s|[.,!?]|$)/g, "$1<em>$2</em>");
    return value.replace(/\u0000(\d+)\u0000/g, (_, index) => tokens[Number(index)]);
  }

  function markdown(source) {
    const lines = source.replace(/\r\n?/g, "\n").split("\n");
    const output = [];
    const cells = (line) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map((cell) => cell.trim());
    const isDivider = (line) => /^\s*\|?\s*:?-{3,}/.test(line || "") && cells(line).every((cell) => /^:?-{3,}:?$/.test(cell));
    const isBlock = (index) => /^(#{1,6}\s|\s*>|\s*[-*+]\s|\s*\d+\.\s|\s*```|\s*(?:-{3,}|\*{3,}|_{3,})\s*$)/.test(lines[index] || "") || ((lines[index] || "").includes("|") && isDivider(lines[index + 1]));
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) { i++; continue; }
      if (/^\s*```/.test(line)) {
        const code = [];
        i++;
        while (i < lines.length && !/^\s*```/.test(lines[i])) code.push(lines[i++]);
        i++;
        output.push(`<pre><code>${escape(code.join("\n"))}</code></pre>`);
        continue;
      }
      const heading = line.match(/^(#{1,6})\s+(.+?)\s*#*$/);
      if (heading) { output.push(`<h${heading[1].length}>${inline(heading[2])}</h${heading[1].length}>`); i++; continue; }
      if (/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)) { output.push("<hr>"); i++; continue; }
      if (line.includes("|") && isDivider(lines[i + 1])) {
        const header = cells(line);
        i += 2;
        const rows = [];
        while (i < lines.length && lines[i].trim() && lines[i].includes("|")) {
          rows.push(`<tr>${cells(lines[i++]).map((cell) => `<td>${inline(cell)}</td>`).join("")}</tr>`);
        }
        output.push(`<div class="table-scroll" tabindex="0" role="region" aria-label="문서 표"><table><thead><tr>${header.map((cell) => `<th scope="col">${inline(cell)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`);
        continue;
      }
      if (/^\s*>/.test(line)) {
        const quoted = [];
        while (i < lines.length && /^\s*>/.test(lines[i])) quoted.push(lines[i++].replace(/^\s*>\s?/, ""));
        output.push(`<blockquote>${markdown(quoted.join("\n"))}</blockquote>`);
        continue;
      }
      const list = line.match(/^\s*([-*+]|\d+\.)\s+(.+)/);
      if (list) {
        const ordered = /\d/.test(list[1]);
        const pattern = ordered ? /^\s*\d+\.\s+(.+)/ : /^\s*[-*+]\s+(.+)/;
        const items = [];
        while (i < lines.length && pattern.test(lines[i])) {
          let item = lines[i++].match(pattern)[1];
          while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !isBlock(i)) item += " " + lines[i++].trim();
          items.push(`<li>${inline(item)}</li>`);
        }
        const tag = ordered ? "ol" : "ul";
        output.push(`<${tag}${ordered ? ` start="${parseInt(list[1], 10)}"` : ""}>${items.join("")}</${tag}>`);
        continue;
      }
      const paragraph = [line];
      i++;
      while (i < lines.length && lines[i].trim() && !isBlock(i)) paragraph.push(lines[i++]);
      output.push(`<p>${paragraph.map(inline).join("<br>")}</p>`);
    }
    return output.join("\n");
  }

  function chips(container, entries, key) {
    entries.forEach(([value, label]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chip" + (value === "all" ? " active" : "");
      button.textContent = label;
      button.setAttribute("aria-pressed", String(value === "all"));
      button.addEventListener("click", () => {
        state[key] = value;
        container.querySelectorAll("button").forEach((item) => {
          const active = item === button;
          item.classList.toggle("active", active);
          item.setAttribute("aria-pressed", String(active));
        });
        render();
      });
      container.append(button);
    });
  }

  function render() {
    const query = $("search").value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const team = $("team").value;
    const results = docs.filter((doc) => {
      if (state.className !== "all" && doc.className !== state.className) return false;
      if (state.stage !== "all" && String(doc.stage) !== state.stage) return false;
      if (team !== "all" && doc.team !== team) return false;
      const searchable = `${doc.student} ${doc.team} ${doc.className} ${doc.filename} ${stages[doc.stage].label} ${stages[doc.stage].title} ${doc.content}`.toLocaleLowerCase();
      return query.every((word) => searchable.includes(word));
    });
    results.sort((a, b) => {
      if ($("sort").value === "stage") return a.stage - b.stage || compare(a.student, b.student) || compare(a.path, b.path);
      if ($("sort").value === "name") return compare(a.filename, b.filename) || compare(a.path, b.path);
      return compare(a.student, b.student) || a.stage - b.stage || compare(a.path, b.path);
    });
    $("result-count").textContent = `전체 ${docs.length}개 중 ${results.length}개 산출물`;
    $("empty").hidden = results.length !== 0;
    const fragment = document.createDocumentFragment();
    results.forEach((doc) => {
      const stage = stages[doc.stage];
      const card = document.createElement("button");
      card.type = "button";
      card.className = `card stage-${doc.stage}`;
      card.setAttribute("aria-label", `${doc.className} 학번 ${doc.student} ${doc.team} ${stage.title} 열기`);
      card.innerHTML = `<span class="card-top"><span class="badge">${stage.label}</span><span class="class-tag">${escape(doc.className)} 폴더</span></span><span class="card-title">${stage.title}</span><span class="card-description">${stage.description}</span><span class="card-bottom"><span class="avatar" aria-hidden="true">${doc.student.slice(-2)}</span><strong>${doc.student}</strong><span class="team-tag">/ ${escape(doc.team)}</span><span class="card-arrow" aria-hidden="true">↗</span></span>`;
      card.addEventListener("click", () => openDocument(doc));
      fragment.append(card);
    });
    $("cards").replaceChildren(fragment);
  }

  function openDocument(doc) {
    $("viewer-title").textContent = stages[doc.stage].title;
    $("viewer-meta").textContent = `${doc.className} 폴더 · ${doc.student} · ${doc.team} · ${doc.stage}차시`;
    $("viewer-file").textContent = doc.filename;
    $("download").href = sourceUrl(doc);
    $("download").download = doc.filename;
    $("document").innerHTML = markdown(doc.content);
    $("viewer").showModal();
    $("viewer").scrollTop = 0;
    document.body.style.overflow = "hidden";
  }

  function reset() {
    $("search").value = "";
    $("team").value = "all";
    $("sort").value = "student";
    state.className = "all";
    state.stage = "all";
    [$("class-filters"), $("stage-filters")].forEach((group) => group.querySelectorAll("button").forEach((button, index) => {
      button.classList.toggle("active", index === 0);
      button.setAttribute("aria-pressed", String(index === 0));
    }));
    render();
  }

  const classes = [...new Set(docs.map((doc) => doc.className))].sort(compare);
  $("stat-docs").textContent = docs.length;
  $("stat-students").textContent = new Set(docs.map((doc) => doc.student)).size;
  $("stat-classes").textContent = classes.length;
  chips($("class-filters"), [["all", "전체"], ...classes.map((name) => [name, `${name}반`])], "className");
  chips($("stage-filters"), [["all", "전체"], ...Object.entries(stages).map(([key, value]) => [key, value.label])], "stage");
  [...new Set(docs.map((doc) => doc.team))].sort(compare).forEach((team) => $("team").add(new Option(team, team)));
  $("search").addEventListener("input", render);
  $("team").addEventListener("change", render);
  $("sort").addEventListener("change", render);
  $("reset").addEventListener("click", reset);
  $("empty-reset").addEventListener("click", reset);
  $("close-viewer").addEventListener("click", () => $("viewer").close());
  $("viewer").addEventListener("close", () => { document.body.style.overflow = ""; });
  $("viewer").addEventListener("click", (event) => {
    const rect = $("viewer").getBoundingClientRect();
    if (event.target === $("viewer") && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) $("viewer").close();
  });
  $("print").addEventListener("click", () => window.print());
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && !$("viewer").open && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      event.preventDefault();
      $("search").focus();
    }
  });
  render();
})();
