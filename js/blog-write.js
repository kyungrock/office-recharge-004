(function () {
  var form = document.getElementById("write-form");
  if (!form) return;

  var titleEl = document.getElementById("post-title");
  var idEl = document.getElementById("post-id");
  var dateEl = document.getElementById("post-date");
  var leadEl = document.getElementById("post-lead");
  var descEl = document.getElementById("post-description");
  var crumbEl = document.getElementById("post-breadcrumb");
  var bodyEl = document.getElementById("post-body");
  var previewEl = document.getElementById("preview");
  var linkPanel = document.getElementById("link-panel");
  var linkTextEl = document.getElementById("link-text");
  var linkUrlEl = document.getElementById("link-url");
  var idTouched = false;

  function todayISO() {
    var d = new Date();
    var m = String(d.getMonth() + 1).padStart(2, "0");
    var day = String(d.getDate()).padStart(2, "0");
    return d.getFullYear() + "-" + m + "-" + day;
  }

  if (dateEl && !dateEl.value) dateEl.value = todayISO();

  function slugify(text) {
    return text
      .trim()
      .toLowerCase()
      .replace(/[^\w\s\u3131-\uD79D-]/g, "")
      .replace(/[\s_]+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "") || "post";
  }

  titleEl.addEventListener("input", function () {
    if (!idTouched && idEl) idEl.value = slugify(titleEl.value);
    if (descEl && !descEl.value) descEl.value = (leadEl.value || titleEl.value).slice(0, 160);
    if (crumbEl && !crumbEl.dataset.touched) crumbEl.value = titleEl.value.slice(0, 40);
  });

  idEl.addEventListener("input", function () {
    idTouched = true;
  });

  crumbEl.addEventListener("input", function () {
    crumbEl.dataset.touched = "1";
  });

  function esc(s) {
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatLink(href, label) {
    var rel = /^https?:\/\//i.test(href) ? ' rel="noopener noreferrer"' : "";
    return '<a href="' + esc(href) + '"' + rel + ">" + esc(label) + "</a>";
  }

  function inlineFormat(text) {
    var links = [];

    function stash(html) {
      var key = "%%LINK" + links.length + "%%";
      links.push(html);
      return key;
    }

    text = text.replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, function (_, label, href) {
      return stash(formatLink(href.trim(), label.trim()));
    });

    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_, label, href) {
      return stash(formatLink(href.trim(), label.trim()));
    });

    text = text.replace(/<a\s+href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi, function (_, href, label) {
      return stash(formatLink(href.trim(), label.replace(/<[^>]+>/g, "").trim()));
    });

    text = esc(text);

    text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

    text = text.replace(/(^|[\s(])((https?:\/\/)[^\s<]+)/g, function (_, before, url) {
      return before + stash(formatLink(url, url));
    });

    links.forEach(function (html, i) {
      text = text.replace("%%LINK" + i + "%%", html);
    });

    return text;
  }

  function previewBody(text) {
    if (!text || !text.trim()) return "";

    if (text.trim().startsWith("<") && text.indexOf("<div class=") !== -1) {
      return text;
    }

    var lines = text.split("\n");
    var htmlParts = [];
    var i = 0;
    var paraBuf = [];
    var listBuf = [];

    function flushPara() {
      if (!paraBuf.length) return;
      var joined = paraBuf.join(" ");
      htmlParts.push("<p>" + inlineFormat(joined) + "</p>");
      paraBuf = [];
    }

    function flushList() {
      if (!listBuf.length) return;
      htmlParts.push(
        "<ul>" + listBuf.map(function (item) {
          return "<li>" + inlineFormat(item) + "</li>";
        }).join("") + "</ul>"
      );
      listBuf = [];
    }

    while (i < lines.length) {
      var line = lines[i];
      var trimmed = line.trim();

      if (!trimmed) {
        flushPara();
        flushList();
        i += 1;
        continue;
      }

      if (trimmed.startsWith(":::warn")) {
        flushPara();
        flushList();
        var block = [];
        i += 1;
        while (i < lines.length && !lines[i].trim().startsWith(":::")) {
          block.push(lines[i]);
          i += 1;
        }
        var inner = block.map(function (l) { return inlineFormat(l); }).join("<br>");
        htmlParts.push('<div class="callout warn">' + inner + "</div>");
        if (i < lines.length) i += 1;
        continue;
      }

      if (trimmed.startsWith(":::callout")) {
        flushPara();
        flushList();
        block = [];
        i += 1;
        while (i < lines.length && !lines[i].trim().startsWith(":::")) {
          block.push(lines[i]);
          i += 1;
        }
        inner = block.map(function (l) { return inlineFormat(l); }).join("<br>");
        htmlParts.push('<div class="callout">' + inner + "</div>");
        if (i < lines.length) i += 1;
        continue;
      }

      if (trimmed.startsWith("## ")) {
        flushPara();
        flushList();
        htmlParts.push("<h2>" + inlineFormat(trimmed.slice(3)) + "</h2>");
        i += 1;
        continue;
      }

      if (trimmed.startsWith("### ")) {
        flushPara();
        flushList();
        htmlParts.push("<h3>" + inlineFormat(trimmed.slice(4)) + "</h3>");
        i += 1;
        continue;
      }

      if (trimmed.startsWith("- ")) {
        flushPara();
        listBuf.push(trimmed.slice(2));
        i += 1;
        continue;
      }

      paraBuf.push(trimmed);
      i += 1;
    }

    flushPara();
    flushList();
    return htmlParts.join("\n");
  }

  function updatePreview() {
    if (!previewEl) return;
    previewEl.innerHTML =
      '<h1 class="page-title">' + esc(titleEl.value || "제목") + "</h1>" +
      '<p class="page-lead">' + inlineFormat(leadEl.value || "") + "</p>" +
      '<article class="article">' + previewBody(bodyEl.value || "") + "</article>";
  }

  function insertAtCursor(textarea, text) {
    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    var before = textarea.value.slice(0, start);
    var after = textarea.value.slice(end);
    textarea.value = before + text + after;
    var pos = start + text.length;
    textarea.focus();
    textarea.setSelectionRange(pos, pos);
    updatePreview();
  }

  function makeLinkMarkup(label, url) {
    return "[[" + label + "|" + url + "]]";
  }

  function openLinkPanel(prefillText) {
    linkPanel.hidden = false;
    linkTextEl.value = prefillText || "";
    linkUrlEl.value = "";
    linkTextEl.focus();
  }

  function closeLinkPanel() {
    linkPanel.hidden = true;
  }

  document.getElementById("btn-insert-link")?.addEventListener("click", function () {
    openLinkPanel("");
  });

  document.getElementById("btn-wrap-link")?.addEventListener("click", function () {
    var selected = bodyEl.value.slice(bodyEl.selectionStart, bodyEl.selectionEnd).trim();
    if (!selected) {
      alert("본문에서 링크로 만들 글자를 먼저 드래그해서 선택해 주세요.\n예: 재충전소");
      return;
    }
    openLinkPanel(selected);
  });

  document.getElementById("btn-cancel-link")?.addEventListener("click", closeLinkPanel);

  document.getElementById("btn-confirm-link")?.addEventListener("click", function () {
    var label = linkTextEl.value.trim();
    var url = linkUrlEl.value.trim();
    if (!label || !url) {
      alert("링크 글자와 URL을 모두 입력해 주세요.");
      return;
    }
    var markup = makeLinkMarkup(label, url);
    var start = bodyEl.selectionStart;
    var end = bodyEl.selectionEnd;
    var selected = bodyEl.value.slice(start, end).trim();

    if (selected && selected === label) {
      bodyEl.value = bodyEl.value.slice(0, start) + markup + bodyEl.value.slice(end);
      bodyEl.focus();
      bodyEl.setSelectionRange(start + markup.length, start + markup.length);
    } else {
      insertAtCursor(bodyEl, markup);
    }

    closeLinkPanel();
    updatePreview();
  });

  bodyEl.addEventListener("input", updatePreview);
  titleEl.addEventListener("input", updatePreview);
  leadEl.addEventListener("input", updatePreview);

  function downloadDraft() {
    var post = {
      id: idEl.value.trim() || slugify(titleEl.value),
      title: titleEl.value.trim(),
      date: dateEl.value.trim() || todayISO(),
      lead: leadEl.value.trim(),
      description: (descEl.value || leadEl.value || titleEl.value).trim().slice(0, 160),
      breadcrumb: (crumbEl.value || titleEl.value).trim().slice(0, 60),
      body: bodyEl.value.trim()
    };

    if (!post.title || !post.body) {
      alert("제목과 본문을 입력해 주세요.");
      return;
    }

    var payload = {
      exported_at: new Date().toISOString(),
      site: "직장인 재충전소",
      post: post
    };

    var blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "blog-draft.json";
    a.click();
    URL.revokeObjectURL(a.href);

    var status = document.getElementById("save-status");
    if (status) {
      status.textContent =
        "blog-draft.json 다운로드 완료 → PowerShell: cd \"D:\\경락\\커서\\site setting\\300site\\4start\" 후 python publish_blog.py --add";
    }
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    downloadDraft();
  });

  document.getElementById("btn-preview")?.addEventListener("click", updatePreview);
  updatePreview();
})();
