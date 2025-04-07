(() => {
  const API = "/api/v1";
  const storage = {
    get userToken() { return localStorage.getItem("mt_user_token"); },
    set userToken(v) { v ? localStorage.setItem("mt_user_token", v) : localStorage.removeItem("mt_user_token"); },
    get currentUser() {
      try {
        return JSON.parse(localStorage.getItem("mt_current_user") || "null");
      } catch {
        return null;
      }
    },
    set currentUser(v) { v ? localStorage.setItem("mt_current_user", JSON.stringify(v)) : localStorage.removeItem("mt_current_user"); },
    get sessionToken() { return localStorage.getItem("mt_session_token"); },
    set sessionToken(v) { v ? localStorage.setItem("mt_session_token", v) : localStorage.removeItem("mt_session_token"); },
    get sessionId() { return localStorage.getItem("mt_session_id"); },
    set sessionId(v) { v ? localStorage.setItem("mt_session_id", v) : localStorage.removeItem("mt_session_id"); },
  };

  let els = {};
  let history = [];
  let busy = false;
  let sessions = [];

  const defaultGreeting = "你好！我是 **Math Teacher** 数学导师。\n\n我可以为你：\n- 📈 **图文并茂讲解函数与几何**（自动画图）\n- ✏️ **批改作业与推导步骤**\n- 🎯 **设计针对性练习题**\n\n直接在下方输入你的数学问题吧！";

  function initElements() {
    els = {
      bootView: document.getElementById("boot-view"),
      chatView: document.getElementById("chat-view"),
      bootError: document.getElementById("boot-error"),
      chatForm: document.getElementById("chat-form"),
      input: document.getElementById("input"),
      btnSend: document.getElementById("btn-send"),
      chatError: document.getElementById("chat-error"),
      messages: document.getElementById("messages"),
      suggestions: document.getElementById("suggestions"),
      btnNew: document.getElementById("btn-new-session"),
      sessionMeta: document.getElementById("session-meta"),
      chatSessionTitle: document.getElementById("chat-session-title"),
      imgModal: document.getElementById("img-modal"),
      modalImg: document.getElementById("modal-img"),
      btnCloseModal: document.getElementById("btn-close-modal"),

      // Auth elements
      userUnauthView: document.getElementById("user-unauth-view"),
      userAuthView: document.getElementById("user-auth-view"),
      btnOpenAuth: document.getElementById("btn-open-auth"),
      btnLogout: document.getElementById("btn-logout"),
      userAvatarLetter: document.getElementById("user-avatar-letter"),
      userDisplayName: document.getElementById("user-display-name"),
      userDisplayEmail: document.getElementById("user-display-email"),
      authModal: document.getElementById("auth-modal"),
      tabLogin: document.getElementById("tab-login"),
      tabRegister: document.getElementById("tab-register"),
      btnCloseAuth: document.getElementById("btn-close-auth"),
      authError: document.getElementById("auth-error"),
      formLogin: document.getElementById("form-login"),
      loginEmail: document.getElementById("login-email"),
      loginPassword: document.getElementById("login-password"),
      btnSubmitLogin: document.getElementById("btn-submit-login"),
      formRegister: document.getElementById("form-register"),
      regUsername: document.getElementById("reg-username"),
      regEmail: document.getElementById("reg-email"),
      regPassword: document.getElementById("reg-password"),
      btnSubmitRegister: document.getElementById("btn-submit-register"),

      // Session list elements
      sessionList: document.getElementById("session-list"),
      sessionListEmpty: document.getElementById("session-list-empty"),
      sessionCountBadge: document.getElementById("session-count-badge"),
    };
  }

  function showError(el, msg) {
    if (!el) return;
    if (!msg) {
      el.hidden = true;
      el.textContent = "";
      return;
    }
    el.hidden = false;
    el.textContent = msg;
  }

  function formatRelativeTime(isoStr) {
    if (!isoStr) return "";
    try {
      let dateStr = String(isoStr).trim();
      // If ISO string without timezone indicator (like 2026-08-26T04:27:00), append 'Z' so it's treated as UTC
      if (!dateStr.endsWith("Z") && !/[+-]\d{2}(?::?\d{2})?$/.test(dateStr)) {
        dateStr += "Z";
      }
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return "";

      const now = new Date();
      const diffMs = now.getTime() - date.getTime();

      if (diffMs < 60000) return "刚刚";
      const diffMin = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMin < 60) return `${diffMin}分钟前`;
      if (diffHours < 24) return `${diffHours}小时前`;
      if (diffDays < 7) return `${diffDays}天前`;
      return `${date.getMonth() + 1}/${date.getDate()}`;
    } catch {
      return "";
    }
  }

  function showChat() {
    if (els.bootView) {
      els.bootView.hidden = true;
      els.bootView.style.display = "none";
    }
    if (els.chatView) {
      els.chatView.hidden = false;
      els.chatView.style.display = "flex";
      renderMath(els.chatView);
    }
    updateSessionMetaDisplay();
  }

  function updateSessionMetaDisplay() {
    if (!els.sessionMeta) return;
    const user = storage.currentUser;
    const prefix = user ? `用户: ${user.username || user.email}` : "游客会话";
    const sid = storage.sessionId ? `\nID: ${storage.sessionId.slice(0, 8)}...` : "";
    els.sessionMeta.textContent = `${prefix}${sid}`;
  }

  function updateUserUI() {
    const user = storage.currentUser;
    if (user && storage.userToken) {
      if (els.userUnauthView) els.userUnauthView.hidden = true;
      if (els.userAuthView) {
        els.userAuthView.hidden = false;
        els.userAuthView.style.display = "flex";
      }
      if (els.userDisplayName) els.userDisplayName.textContent = user.username || user.email.split("@")[0];
      if (els.userDisplayEmail) els.userDisplayEmail.textContent = user.email;
      if (els.userAvatarLetter) {
        const char = (user.username || user.email || "用")[0].toUpperCase();
        els.userAvatarLetter.textContent = char;
      }
    } else {
      if (els.userUnauthView) {
        els.userUnauthView.hidden = false;
        els.userUnauthView.style.display = "flex";
      }
      if (els.userAuthView) els.userAuthView.hidden = true;
    }
    updateSessionMetaDisplay();
  }

  // Lightweight Markdown fallback if CDN fails
  function simpleMarkdownFallback(text) {
    if (!text) return "";
    let html = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    
    // Images: ![alt](url)
    html = html.replace(/!\[([^\]]*)\]\((data:image\/[^;]+;base64,[^\)]+|https?:\/\/[^\)]+|\/[^\)]+)\)/g, '<img src="$2" alt="$1" />');
    // Bold: **text**
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // Inline code: `code`
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    // Headers: ### text
    html = html.replace(/^### (.*$)/gim, "<h3>$1</h3>");
    html = html.replace(/^## (.*$)/gim, "<h2>$1</h2>");
    html = html.replace(/^# (.*$)/gim, "<h1>$1</h1>");
    // Line breaks
    html = html.replace(/\n/g, "<br/>");
    return html;
  }

  // KaTeX direct string renderer
  function renderKatexMath(math, isBlock) {
    if (window.katex && typeof window.katex.renderToString === "function") {
      try {
        return window.katex.renderToString(math, {
          displayMode: Boolean(isBlock),
          throwOnError: false,
        });
      } catch (e) {
        console.warn("KaTeX renderToString error:", e);
      }
    }
    const escaped = escapeHtml(math);
    return isBlock
      ? `<div class="katex-display-fallback">$$${escaped}$$</div>`
      : `<span class="katex-inline-fallback">$${escaped}$</span>`;
  }

  // Safe Markdown + LaTeX parser with formula placeholder protection
  function parseContent(rawText) {
    if (!rawText) return "";

    const mathStore = [];
    let text = String(rawText);

    // 1. Protect multi-line code blocks and extract math code blocks
    const codeBlocks = [];
    text = text.replace(/```([\s\S]*?)```/g, (match) => {
      const trimmed = match.trim();
      if (trimmed.startsWith("```math") || trimmed.startsWith("```latex")) {
        const code = trimmed.replace(/^```(?:math|latex)\s*/i, "").replace(/```$/, "").trim();
        const id = mathStore.length;
        mathStore.push({ id, math: code, display: true });
        return `\n\n%%MATH_BLOCK_${id}%%\n\n`;
      }
      const cid = codeBlocks.length;
      codeBlocks.push(match);
      return `%%CODE_BLOCK_${cid}%%`;
    });

    // 2. Protect inline code
    const inlineCodes = [];
    text = text.replace(/`([^`\n]+)`/g, (match) => {
      const iid = inlineCodes.length;
      inlineCodes.push(match);
      return `%%INLINE_CODE_${iid}%%`;
    });

    // 2.5 Protect markdown images (strip LaTeX math delimiters from alt to prevent KaTeX HTML breaking img attributes)
    const images = [];
    text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
      const imgId = images.length;
      const cleanAlt = (alt || "").replace(/\$/g, "").trim();
      images.push({ alt: cleanAlt, url: url.trim() });
      return `%%IMG_PLACEHOLDER_${imgId}%%`;
    });

    // 2.6 Protect raw HTML img tags
    const htmlImgTags = [];
    text = text.replace(/<img[^>]*>/gi, (match) => {
      const hid = htmlImgTags.length;
      htmlImgTags.push(match);
      return `%%HTML_IMG_${hid}%%`;
    });

    // 3. Extract display math: $$...$$
    text = text.replace(/\$\$([\s\S]+?)\$\$/g, (match, math) => {
      const id = mathStore.length;
      mathStore.push({ id, math: math.trim(), display: true });
      return `\n\n%%MATH_BLOCK_${id}%%\n\n`;
    });

    // 4. Extract display math: \[...\]
    text = text.replace(/\\\[([\s\S]+?)\\\]/g, (match, math) => {
      const id = mathStore.length;
      mathStore.push({ id, math: math.trim(), display: true });
      return `\n\n%%MATH_BLOCK_${id}%%\n\n`;
    });

    // 5. Extract environment display math: \begin{...}...\end{...}
    text = text.replace(/(\\begin\{(?:equation|align|aligned|gather|matrix|pmatrix|bmatrix|vmatrix|cases|split)\*?\}[\s\S]+?\\end\{(?:equation|align|aligned|gather|matrix|pmatrix|bmatrix|vmatrix|cases|split)\*?\})/g, (match, math) => {
      const id = mathStore.length;
      mathStore.push({ id, math: math.trim(), display: true });
      return `\n\n%%MATH_BLOCK_${id}%%\n\n`;
    });

    // 6. Extract inline math: \(...\)
    text = text.replace(/\\\(([\s\S]+?)\\\)/g, (match, math) => {
      const id = mathStore.length;
      mathStore.push({ id, math: math.trim(), display: false });
      return `%%MATH_INLINE_${id}%%`;
    });

    // 7. Extract inline math: $...$
    text = text.replace(/(^|[^\$])\$([^\$\n]+?)\$(?!\$)/g, (match, prefix, math) => {
      const trimmed = math.trim();
      if (!trimmed || math.startsWith(" ") || math.endsWith(" ") || /^\d+(\.\d+)?$/.test(trimmed)) {
        return match;
      }
      const id = mathStore.length;
      mathStore.push({ id, math: trimmed, display: false });
      return `${prefix}%%MATH_INLINE_${id}%%`;
    });

    // 8. Restore code blocks, inline codes, images, and HTML tags before markdown parsing
    text = text.replace(/%%INLINE_CODE_(\d+)%%/g, (_, id) => inlineCodes[Number(id)]);
    text = text.replace(/%%CODE_BLOCK_(\d+)%%/g, (_, id) => codeBlocks[Number(id)]);
    text = text.replace(/%%IMG_PLACEHOLDER_(\d+)%%/g, (_, id) => {
      const img = images[Number(id)];
      return `![${img.alt}](${img.url})`;
    });
    text = text.replace(/%%HTML_IMG_(\d+)%%/g, (_, id) => htmlImgTags[Number(id)]);

    // 9. Markdown parsing
    let html = "";
    try {
      if (window.marked && typeof window.marked.parse === "function") {
        html = window.marked.parse(text, { breaks: true, gfm: true });
      } else {
        html = simpleMarkdownFallback(text);
      }
    } catch (e) {
      console.warn("Markdown parse error, falling back:", e);
      html = simpleMarkdownFallback(text);
    }

    // 10. DOMPurify sanitize
    try {
      if (window.DOMPurify && typeof window.DOMPurify.sanitize === "function") {
        html = window.DOMPurify.sanitize(html, {
          ADD_TAGS: [
            "math", "annotation", "semantics", "mtext", "mn", "mo", "mi", "mspace",
            "mover", "munder", "msup", "msub", "msubsup", "mfrac", "mroot", "msqrt",
            "mtable", "mtr", "mtd", "span", "div", "svg", "path", "line"
          ],
          ADD_ATTR: [
            "data-*", "target", "src", "alt", "class", "style", "aria-hidden", "aria-label",
            "viewBox", "width", "height", "xmlns", "preserveAspectRatio", "d", "fill", "stroke"
          ],
        });
      }
    } catch (e) {
      console.warn("DOMPurify sanitize warning:", e);
    }

    // 11. Replace math placeholders with KaTeX rendered HTML
    mathStore.forEach((item) => {
      const rendered = renderKatexMath(item.math, item.display);
      if (item.display) {
        const blockRegex = new RegExp(`<p>\\s*%%MATH_BLOCK_${item.id}%%\\s*<\\/p>|%%MATH_BLOCK_${item.id}%%`, "g");
        html = html.replace(blockRegex, rendered);
      } else {
        const inlineRegex = new RegExp(`%%MATH_INLINE_${item.id}%%`, "g");
        html = html.replace(inlineRegex, rendered);
      }
    });

    return html;
  }

  function renderMath(node) {
    if (window.renderMathInElement && node) {
      try {
        renderMathInElement(node, {
          delimiters: [
            { left: "$$", right: "$$", display: true },
            { left: "$", right: "$", display: false },
            { left: "\\(", right: "\\)", display: false },
            { left: "\\[", right: "\\]", display: true },
          ],
          ignoredClasses: ["katex", "katex-display", "katex-html"],
          throwOnError: false,
        });
      } catch (e) {
        console.warn("KaTeX render error:", e);
      }
    }
  }

  function escapeHtml(text) {
    if (!text) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getFriendlyToolName(toolName) {
    const map = {
      router_decision: "题目意图路由与策略规划",
      python_sandbox_execute: "Python 代码沙箱自验",
      plot_math_function: "Matplotlib 函数图表绘制",
      sympy_calculate: "SymPy 代数精确核算",
      ask_human: "人工教师专家辅助",
      critic_review: "Critic 双智能体审校与质检",
    };
    return map[toolName] || toolName || "数学工具演算";
  }

  function formatStatusMessage(text, toolName = "", isCompleted = false) {
    let clean = text || "";
    if (toolName) {
      const friendlyName = getFriendlyToolName(toolName);
      if (isCompleted || clean.startsWith("✅") || clean.includes("完成")) {
        return `✅ 已完成 ${friendlyName}`;
      }
      return `⚡ 正在调用 ${friendlyName}...`;
    }
    if (isCompleted && !clean.startsWith("✅")) {
      return `✅ ${clean.replace(/正在/, "已完成")}`;
    }
    return clean;
  }

  function createStreamRenderer(bubble) {
    const segments = []; // Array of { type: "thinking"|"tool_call"|"text", ... }
    let insideThinkTag = false;
    let transientStatus = "";

    function render() {
      if (!bubble) return;
      bubble.innerHTML = "";

      // If only transient routing status exists before any segments arrive
      if (segments.length === 0 && transientStatus) {
        const statusEl = document.createElement("div");
        statusEl.className = "inline-tool-call running";
        statusEl.innerHTML = `
          <div class="tool-summary" style="padding: 0.4rem 0.6rem;">
            <span class="tool-icon">🔍</span>
            <span class="tool-status-text">${escapeHtml(transientStatus)}</span>
            <span class="tool-badge tool-badge-running">分析中...</span>
          </div>
        `;
        bubble.appendChild(statusEl);
        return;
      }

      // Render all segments in exact chronological timeline sequence
      let toolCount = 0;
      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        if (seg.type === "thinking" && seg.content) {
          const thinkEl = document.createElement("details");
          thinkEl.className = `inline-thinking-block ${seg.completed ? "completed" : "running"}`;
          if (!seg.completed) {
            thinkEl.open = true;
          }

          const elapsedText = seg.elapsed ? ` (${seg.elapsed}s)` : "";
          thinkEl.innerHTML = `
            <summary class="thinking-summary">
              <span class="thinking-spinner"></span>
              <span class="thinking-title">💭 深度思考与推理过程${escapeHtml(elapsedText)}</span>
              <span class="thinking-badge">${seg.completed ? "已完成" : "思考中..."}</span>
            </summary>
            <div class="thinking-content">${escapeHtml(seg.content)}</div>
          `;
          bubble.appendChild(thinkEl);

          if (!seg.completed) {
            const contentBox = thinkEl.querySelector(".thinking-content");
            if (contentBox) contentBox.scrollTop = contentBox.scrollHeight;
          }
        } else if (seg.type === "tool_call") {
          toolCount++;
          const statusEl = document.createElement("details");
          statusEl.className = `inline-tool-call ${seg.completed ? "completed" : "running"}`;
          if (!seg.completed) {
            statusEl.open = true;
          }

          const friendlyName = getFriendlyToolName(seg.tool_name || seg.toolName || "");
          const hasDetails = Boolean(seg.tool_args || seg.toolArgs || seg.tool_output || seg.toolOutput);

          statusEl.innerHTML = `
            <summary class="tool-summary">
              <span class="tool-step-chip">步骤 ${toolCount}</span>
              <span class="tool-icon">${seg.completed ? "🛠️" : "⚡"}</span>
              <span class="tool-status-text">${escapeHtml(seg.completed ? `已完成 ${friendlyName}` : `正在调用 ${friendlyName}...`)}</span>
              <span class="tool-badge ${seg.completed ? "tool-badge-done" : "tool-badge-running"}">
                ${seg.completed ? (hasDetails ? "查看详情 ▾" : "已完成") : "演算中..."}
              </span>
            </summary>
            ${
              hasDetails
                ? `<div class="tool-details-body">
                    ${
                      (seg.tool_args || seg.toolArgs)
                        ? `<div class="tool-detail-section">
                             <div class="tool-detail-label">${(seg.tool_name || seg.toolName) === "critic_review" ? "📥 审校目标与检查项 (Review Target)" : ((seg.tool_name || seg.toolName) === "router_decision" ? "📥 学生原始输入与上下文 (Student Input)" : "📥 输入参数 (Arguments)")}</div>
                             <pre class="tool-detail-code"><code>${escapeHtml(seg.tool_args || seg.toolArgs)}</code></pre>
                           </div>`
                        : ""
                    }
                    ${
                      (seg.tool_output || seg.toolOutput)
                        ? `<div class="tool-detail-section">
                             <div class="tool-detail-label">${(seg.tool_name || seg.toolName) === "critic_review" ? "📤 审校结论、思考与评分 (Review Assessment)" : ((seg.tool_name || seg.toolName) === "router_decision" ? "📤 意图分类与路由决策 (Routing Decision)" : "📤 执行结果 (Execution Output)")}</div>
                             <pre class="tool-detail-code"><code>${escapeHtml(seg.tool_output || seg.toolOutput)}</code></pre>
                           </div>`
                        : ""
                    }
                   </div>`
                : ""
            }
          `;
          bubble.appendChild(statusEl);
        } else if (seg.type === "text" && seg.content) {
          const textWrapper = document.createElement("div");
          textWrapper.className = "inline-text-block";
          textWrapper.innerHTML = parseContent(seg.content);
          bubble.appendChild(textWrapper);
        }
      }

      renderMath(bubble);
      if (els.messages) {
        els.messages.scrollTop = els.messages.scrollHeight;
      }
    }

    function appendThinking(chunk) {
      if (!chunk) return;
      transientStatus = "";

      const lastSeg = segments[segments.length - 1];
      let thinkSeg;
      if (lastSeg && lastSeg.type === "thinking" && !lastSeg.completed) {
        thinkSeg = lastSeg;
      } else {
        // Complete previous running segment
        segments.forEach((s) => {
          if (!s.completed) {
            s.completed = true;
            if (s.type === "thinking" && s.startTime) {
              s.elapsed = Math.max(1, Math.round((Date.now() - s.startTime) / 1000));
            }
          }
        });
        thinkSeg = {
          type: "thinking",
          content: "",
          completed: false,
          startTime: Date.now(),
          elapsed: 0,
        };
        segments.push(thinkSeg);
      }
      thinkSeg.content += chunk;
      render();
    }

    function addOrUpdateStatus(statusText, toolName = "", toolArgs = "", toolOutput = "") {
      if (!statusText) return;

      // Transient routing notification before tools
      if (!toolName && !statusText.startsWith("✅") && !statusText.includes("运算完成")) {
        if (segments.length === 0) {
          transientStatus = statusText;
          render();
        }
        return;
      }

      transientStatus = "";
      const isCompletedMsg = statusText.startsWith("✅") || statusText.includes("完成");

      // Complete previous open thinking segment
      segments.forEach((s) => {
        if (s.type === "thinking" && !s.completed) {
          s.completed = true;
          if (s.startTime) {
            s.elapsed = Math.max(1, Math.round((Date.now() - s.startTime) / 1000));
          }
        }
      });

      // Match running or same tool
      const lastSeg = segments[segments.length - 1];
      if (lastSeg && lastSeg.type === "tool_call" && (lastSeg.tool_name === toolName || (!lastSeg.completed && !lastSeg.tool_name))) {
        lastSeg.text = statusText;
        if (toolName) lastSeg.tool_name = toolName;
        if (toolArgs) lastSeg.tool_args = toolArgs;
        if (toolOutput) lastSeg.tool_output = toolOutput;
        if (isCompletedMsg) {
          lastSeg.completed = true;
        }
        render();
        return;
      }

      // Mark previous tool calls completed
      segments.forEach((s) => {
        if (s.type === "tool_call") s.completed = true;
      });

      segments.push({
        type: "tool_call",
        text: statusText,
        completed: isCompletedMsg,
        tool_name: toolName,
        tool_args: toolArgs,
        tool_output: toolOutput,
      });
      render();
    }

    function appendContent(rawChunk) {
      if (!rawChunk) return;
      transientStatus = "";
      let chunk = rawChunk;

      if (chunk.includes("<think>")) {
        insideThinkTag = true;
        const parts = chunk.split("<think>");
        if (parts[0]) appendContent(parts[0]);
        chunk = parts[1] || "";
      }
      if (insideThinkTag) {
        if (chunk.includes("</think>")) {
          insideThinkTag = false;
          const parts = chunk.split("</think>");
          appendThinking(parts[0]);
          if (parts[1]) appendContent(parts[1]);
          return;
        } else {
          appendThinking(chunk);
          return;
        }
      }

      // Complete any running thinking or tool segments
      segments.forEach((s) => {
        if (!s.completed) {
          s.completed = true;
          if (s.type === "thinking" && s.startTime) {
            s.elapsed = Math.max(1, Math.round((Date.now() - s.startTime) / 1000));
          }
        }
      });

      const lastSeg = segments[segments.length - 1];
      if (lastSeg && lastSeg.type === "text") {
        lastSeg.content += chunk;
      } else {
        segments.push({
          type: "text",
          content: chunk,
        });
      }
      render();
    }

    function finish() {
      transientStatus = "";
      segments.forEach((s) => {
        if (!s.completed) {
          s.completed = true;
          if (s.type === "thinking" && s.startTime) {
            s.elapsed = Math.max(1, Math.round((Date.now() - s.startTime) / 1000));
          }
        }
      });
      render();
    }

    function getResult() {
      const thinkParts = segments.filter((s) => s.type === "thinking" && s.content).map((s) => s.content.trim());
      const textParts = segments.filter((s) => s.type === "text" && s.content).map((s) => s.content.trim());
      const toolCallsList = segments.filter((s) => s.type === "tool_call").map((s) => ({
        tool_name: s.tool_name || s.toolName || "",
        tool_args: s.tool_args || s.toolArgs || "",
        tool_output: s.tool_output || s.toolOutput || "",
        status: s.text || s.status || "",
      }));

      const formattedSegments = segments.map((s) => {
        if (s.type === "thinking") {
          return { type: "thinking", content: s.content };
        } else if (s.type === "tool_call") {
          return {
            type: "tool_call",
            tool_name: s.tool_name || s.toolName || "",
            tool_args: s.tool_args || s.toolArgs || "",
            tool_output: s.tool_output || s.toolOutput || "",
            status: s.text || s.status || "",
          };
        } else {
          return { type: "text", content: s.content };
        }
      });

      return {
        content: textParts.join("\n\n"),
        thinking: thinkParts.join("\n\n"),
        tool_calls: toolCallsList,
        segments: formattedSegments,
      };
    }

    return {
      appendThinking,
      addOrUpdateStatus,
      appendContent,
      finish,
      getResult,
      render,
    };
  }

  function addMessageRow(role, content = "", thinking = "", toolCalls = [], segments = []) {
    if (!els.messages) return { row: null, bubble: null, body: null };

    const row = document.createElement("div");
    row.className = `msg-row ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = role === "user" ? "生" : "师";

    const body = document.createElement("div");
    body.className = "msg-body";

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    if (role === "user") {
      bubble.textContent = content;
    } else {
      // If structured chronological segments are available, render in exact event timeline sequence
      if (Array.isArray(segments) && segments.length > 0) {
        let toolCount = 0;
        segments.forEach((seg) => {
          if (seg.type === "thinking" && seg.content) {
            const thinkEl = document.createElement("details");
            thinkEl.className = "inline-thinking-block completed";
            thinkEl.innerHTML = `
              <summary class="thinking-summary">
                <span class="thinking-spinner"></span>
                <span class="thinking-title">💭 深度思考与推理过程</span>
                <span class="thinking-badge">已完成</span>
              </summary>
              <div class="thinking-content">${escapeHtml(seg.content)}</div>
            `;
            bubble.appendChild(thinkEl);
          } else if (seg.type === "tool_call") {
            toolCount++;
            const statusEl = document.createElement("details");
            statusEl.className = "inline-tool-call completed";
            const friendlyName = getFriendlyToolName(seg.tool_name || seg.toolName || "");
            const hasDetails = Boolean(seg.tool_args || seg.toolArgs || seg.tool_output || seg.toolOutput);

            statusEl.innerHTML = `
              <summary class="tool-summary">
                <span class="tool-step-chip">步骤 ${toolCount}</span>
                <span class="tool-icon">🛠️</span>
                <span class="tool-status-text">${escapeHtml(`已完成 ${friendlyName}`)}</span>
                <span class="tool-badge tool-badge-done">${hasDetails ? "查看详情 ▾" : "已完成"}</span>
              </summary>
              ${
                hasDetails
                  ? `<div class="tool-details-body">
                      ${
                        (seg.tool_args || seg.toolArgs)
                          ? `<div class="tool-detail-section">
                               <div class="tool-detail-label">${(seg.tool_name || seg.toolName) === "critic_review" ? "📥 审校目标与检查项 (Review Target)" : ((seg.tool_name || seg.toolName) === "router_decision" ? "📥 学生原始输入与上下文 (Student Input)" : "📥 输入参数 (Arguments)")}</div>
                               <pre class="tool-detail-code"><code>${escapeHtml(seg.tool_args || seg.toolArgs)}</code></pre>
                             </div>`
                          : ""
                      }
                      ${
                        (seg.tool_output || seg.toolOutput)
                          ? `<div class="tool-detail-section">
                               <div class="tool-detail-label">${(seg.tool_name || seg.toolName) === "critic_review" ? "📤 审校结论、思考与评分 (Review Assessment)" : ((seg.tool_name || seg.toolName) === "router_decision" ? "📤 意图分类与路由决策 (Routing Decision)" : "📤 执行结果 (Execution Output)")}</div>
                               <pre class="tool-detail-code"><code>${escapeHtml(seg.tool_output || seg.toolOutput)}</code></pre>
                             </div>`
                          : ""
                      }
                     </div>`
                  : ""
              }
            `;
            bubble.appendChild(statusEl);
          } else if (seg.type === "text" && seg.content) {
            const textWrapper = document.createElement("div");
            textWrapper.className = "inline-text-block";
            textWrapper.innerHTML = parseContent(seg.content);
            bubble.appendChild(textWrapper);
          }
        });
      } else {
        // Fallback: render legacy format
        let cleanContent = content || "";
        let cleanThinking = thinking || "";

        if (!cleanThinking && cleanContent.includes("<think>")) {
          const thinkMatch = cleanContent.match(/<think>([\s\S]*?)(?:<\/think>|$)/);
          if (thinkMatch && thinkMatch[1]) {
            cleanThinking = thinkMatch[1].trim();
            cleanContent = cleanContent.replace(/<think>[\s\S]*?(?:<\/think>|$)/, "").trim();
          }
        }

        if (cleanThinking) {
          const thinkEl = document.createElement("details");
          thinkEl.className = "inline-thinking-block completed";
          thinkEl.innerHTML = `
            <summary class="thinking-summary">
              <span class="thinking-spinner"></span>
              <span class="thinking-title">💭 深度思考与推理过程</span>
              <span class="thinking-badge">已完成</span>
            </summary>
            <div class="thinking-content">${escapeHtml(cleanThinking)}</div>
          `;
          bubble.appendChild(thinkEl);
        }

        if (Array.isArray(toolCalls) && toolCalls.length > 0) {
          toolCalls.forEach((tc, idx) => {
            const stepNumber = idx + 1;
            const statusEl = document.createElement("details");
            statusEl.className = "inline-tool-call completed";
            const friendlyName = getFriendlyToolName(tc.tool_name);
            const hasDetails = Boolean(tc.tool_args || tc.tool_output);

            statusEl.innerHTML = `
              <summary class="tool-summary">
                <span class="tool-step-chip">步骤 ${stepNumber}</span>
                <span class="tool-icon">🛠️</span>
                <span class="tool-status-text">${escapeHtml(`已完成 ${friendlyName}`)}</span>
                <span class="tool-badge tool-badge-done">${hasDetails ? "查看详情 ▾" : "已完成"}</span>
              </summary>
              ${
                hasDetails
                  ? `<div class="tool-details-body">
                      ${
                        tc.tool_args
                          ? `<div class="tool-detail-section">
                               <div class="tool-detail-label">${tc.tool_name === "critic_review" ? "📥 审校目标与检查项 (Review Target)" : (tc.tool_name === "router_decision" ? "📥 学生原始输入与上下文 (Student Input)" : "📥 输入参数 (Arguments)")}</div>
                               <pre class="tool-detail-code"><code>${escapeHtml(tc.tool_args)}</code></pre>
                             </div>`
                          : ""
                      }
                      ${
                        tc.tool_output
                          ? `<div class="tool-detail-section">
                               <div class="tool-detail-label">${tc.tool_name === "critic_review" ? "📤 审校结论、思考与评分 (Review Assessment)" : (tc.tool_name === "router_decision" ? "📤 意图分类与路由决策 (Routing Decision)" : "📤 执行结果 (Execution Output)")}</div>
                               <pre class="tool-detail-code"><code>${escapeHtml(tc.tool_output)}</code></pre>
                             </div>`
                          : ""
                      }
                     </div>`
                  : ""
              }
            `;
            bubble.appendChild(statusEl);
          });
        }

        if (cleanContent) {
          const textWrapper = document.createElement("div");
          textWrapper.className = "inline-text-block";
          textWrapper.innerHTML = parseContent(cleanContent);
          bubble.appendChild(textWrapper);
        }
      }

      renderMath(bubble);
    }

    body.appendChild(bubble);

    if (role === "assistant") {
      const actions = document.createElement("div");
      actions.className = "msg-actions";

      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "btn-action-icon";
      copyBtn.innerHTML = `<span>📋 复制</span>`;
      copyBtn.onclick = () => {
        const textBlocks = bubble.querySelectorAll(".inline-text-block");
        let textToCopy = "";
        if (textBlocks.length > 0) {
          textToCopy = Array.from(textBlocks).map((b) => b.innerText).join("\n\n");
        } else {
          textToCopy = bubble.innerText || content;
        }
        navigator.clipboard.writeText(textToCopy);
        copyBtn.innerHTML = `<span>✅ 已复制</span>`;
        setTimeout(() => { copyBtn.innerHTML = `<span>📋 复制</span>`; }, 2000);
      };
      actions.appendChild(copyBtn);
      body.appendChild(actions);
    }

    row.appendChild(avatar);
    row.appendChild(body);
    els.messages.appendChild(row);

    els.messages.scrollTop = els.messages.scrollHeight;
    return { row, bubble, body };
  }

  async function api(path, { method = "GET", token, body, timeoutMs = 6000 } = {}) {
    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers["Content-Type"] = "application/json";

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(`${API}${path}`, {
        method,
        headers,
        signal: controller.signal,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
      clearTimeout(timer);

      const text = await res.text();
      let data;
      try { data = text ? JSON.parse(text) : {}; } catch { data = { detail: text }; }
      if (!res.ok) {
        const detail = data.detail;
        const msg = typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
            : (data.message || res.statusText);
        throw new Error(msg || `请求失败 (${res.status})`);
      }
      return data;
    } catch (e) {
      clearTimeout(timer);
      if (e.name === "AbortError") {
        throw new Error("请求超时，请检查后端网络连接");
      }
      throw e;
    }
  }

  // ================= Auth & Session Functions =================

  async function fetchCurrentUser() {
    if (!storage.userToken) {
      storage.currentUser = null;
      updateUserUI();
      return null;
    }
    try {
      const user = await api("/auth/me", { token: storage.userToken });
      storage.currentUser = user;
      updateUserUI();
      return user;
    } catch (e) {
      console.warn("Fetch current user failed, clearing user token:", e);
      storage.userToken = null;
      storage.currentUser = null;
      updateUserUI();
      return null;
    }
  }

  async function createGuestSession() {
    const sess = await api("/auth/guest", { method: "POST" });
    storage.sessionToken = sess.token.access_token;
    storage.sessionId = sess.session_id;
    updateSessionMetaDisplay();
    return sess;
  }

  async function createUserSession() {
    const sess = await api("/auth/session", { method: "POST", token: storage.userToken });
    storage.sessionToken = sess.token.access_token;
    storage.sessionId = sess.session_id;
    updateSessionMetaDisplay();
    return sess;
  }

  async function loadUserSessions() {
    if (!storage.userToken) {
      sessions = [];
      renderSessionList();
      return;
    }
    try {
      const list = await api("/auth/sessions", { token: storage.userToken });
      sessions = Array.isArray(list) ? list : [];
      renderSessionList();
    } catch (e) {
      console.warn("Load sessions failed:", e);
    }
  }

  function renderSessionList() {
    if (!els.sessionList) return;
    els.sessionList.innerHTML = "";

    if (els.sessionCountBadge) {
      els.sessionCountBadge.textContent = String(sessions.length);
    }

    if (!sessions.length) {
      const empty = document.createElement("div");
      empty.className = "session-list-empty";
      empty.textContent = storage.userToken ? "暂无历史会话" : "登录后可保存多个历史会话";
      els.sessionList.appendChild(empty);
      return;
    }

    sessions.forEach((s) => {
      const item = document.createElement("div");
      const isActive = s.session_id === storage.sessionId;
      item.className = `session-item ${isActive ? "active" : ""}`;
      item.dataset.sessionId = s.session_id;

      const title = s.name || "新会话";
      const timeStr = formatRelativeTime(s.created_at);

      item.innerHTML = `
        <span class="session-item-icon">💬</span>
        <div class="session-item-body">
          <span class="session-title-text" title="${escapeHtml(title)}">${escapeHtml(title)}</span>
          ${timeStr ? `<span class="session-date">${escapeHtml(timeStr)}</span>` : ""}
        </div>
        <button type="button" class="btn-delete-session" title="删除该会话" aria-label="删除会话">
          🗑️
        </button>
      `;

      item.addEventListener("click", (e) => {
        if (e.target.closest(".btn-delete-session")) return;
        switchSession(s.session_id, s.token ? s.token.access_token : "", s.name);
      });

      const delBtn = item.querySelector(".btn-delete-session");
      if (delBtn) {
        delBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          deleteSession(s.session_id);
        });
      }

      els.sessionList.appendChild(item);
    });
  }

  async function switchSession(sessionId, token, sessionName = "") {
    if (busy) return;
    storage.sessionId = sessionId;
    if (token) storage.sessionToken = token;

    if (els.chatSessionTitle) {
      els.chatSessionTitle.textContent = sessionName ? `辅导室 · ${sessionName}` : "Math Teacher 辅导室";
    }

    renderSessionList();
    updateSessionMetaDisplay();

    if (els.messages) els.messages.innerHTML = "";
    showError(els.chatError, "");

    try {
      const data = await api("/chatbot/messages", { token: storage.sessionToken });
      const msgs = data.messages || [];
      if (msgs.length) {
        history = msgs.map((m) => ({
          role: m.role,
          content: m.content,
          thinking: m.thinking || "",
          tool_calls: m.tool_calls || [],
          segments: m.segments || [],
        }));
        msgs.forEach((m) =>
          addMessageRow(m.role, m.content, m.thinking || "", m.tool_calls || [], m.segments || [])
        );
      } else {
        history = [];
        addMessageRow("assistant", defaultGreeting);
      }
    } catch (e) {
      console.warn("Load session messages failed:", e);
      history = [];
      addMessageRow("assistant", `⚠️ 加载历史记录失败: ${e.message}`);
    }
  }

  async function deleteSession(sessionId) {
    if (!confirm("确定要删除此会话记录吗？")) return;
    try {
      const authToken = storage.userToken || storage.sessionToken;
      await api(`/auth/session/${sessionId}`, { method: "DELETE", token: authToken });
      sessions = sessions.filter((s) => s.session_id !== sessionId);

      if (storage.sessionId === sessionId) {
        if (sessions.length > 0) {
          const first = sessions[0];
          await switchSession(first.session_id, first.token ? first.token.access_token : "", first.name);
        } else {
          await startNewSession();
        }
      } else {
        renderSessionList();
      }
    } catch (e) {
      showError(els.chatError, `删除会话失败: ${e.message}`);
    }
  }

  function openAuthModal() {
    showError(els.authError, "");
    if (els.loginEmail && !els.loginEmail.value) {
      els.loginEmail.value = "student@math-teacher.local";
    }
    if (els.loginPassword && !els.loginPassword.value) {
      els.loginPassword.value = "Math123456!";
    }
    if (els.authModal && typeof els.authModal.showModal === "function") {
      try {
        if (!els.authModal.open) {
          els.authModal.showModal();
        }
      } catch (e) {
        console.warn("Open auth modal warning:", e);
      }
    }
  }

  async function startNewSession() {
    if (busy) return;
    if (!storage.userToken) {
      openAuthModal();
      return;
    }
    try {
      const newSess = await createUserSession();
      sessions.unshift(newSess);
      renderSessionList();

      history = [];
      if (els.messages) els.messages.innerHTML = "";
      if (els.chatSessionTitle) els.chatSessionTitle.textContent = "Math Teacher 辅导室";
      showChat();
      addMessageRow("assistant", defaultGreeting);
    } catch (err) {
      showError(els.chatError, `开启新会话失败: ${err.message}`);
    }
  }

  async function handleLogin(e) {
    e.preventDefault();
    showError(els.authError, "");
    if (els.btnSubmitLogin) els.btnSubmitLogin.disabled = true;

    const email = (els.loginEmail ? els.loginEmail.value : "").trim();
    const password = (els.loginPassword ? els.loginPassword.value : "").trim();

    try {
      const res = await api("/auth/login", {
        method: "POST",
        body: { email, password },
      });

      storage.userToken = res.access_token;
      await fetchCurrentUser();
      await loadUserSessions();

      if (els.authModal) els.authModal.close();

      if (sessions.length > 0) {
        const first = sessions[0];
        await switchSession(first.session_id, first.token ? first.token.access_token : "", first.name);
      } else {
        await startNewSession();
      }
    } catch (err) {
      showError(els.authError, `登录失败: ${err.message}`);
    } finally {
      if (els.btnSubmitLogin) els.btnSubmitLogin.disabled = false;
    }
  }

  async function handleRegister(e) {
    e.preventDefault();
    showError(els.authError, "");
    if (els.btnSubmitRegister) els.btnSubmitRegister.disabled = true;

    const username = (els.regUsername ? els.regUsername.value : "").trim() || null;
    const email = (els.regEmail ? els.regEmail.value : "").trim();
    const password = (els.regPassword ? els.regPassword.value : "").trim();

    try {
      const res = await api("/auth/register", {
        method: "POST",
        body: { email, password, username },
      });

      storage.userToken = res.token.access_token;
      storage.currentUser = { id: res.id, email: res.email, username: res.username };
      updateUserUI();

      if (els.authModal) els.authModal.close();
      await startNewSession();
    } catch (err) {
      showError(els.authError, `注册失败: ${err.message}`);
    } finally {
      if (els.btnSubmitRegister) els.btnSubmitRegister.disabled = false;
    }
  }

  async function handleLogout() {
    if (!confirm("确定要退出登录吗？")) return;
    storage.userToken = null;
    storage.currentUser = null;
    storage.sessionToken = null;
    storage.sessionId = null;
    updateUserUI();
    sessions = [];
    renderSessionList();
    if (els.messages) els.messages.innerHTML = "";
    addMessageRow("assistant", "您已退出登录。请重新登录以开启辅导对话与查看历史记录。");
    openAuthModal();
  }

  function setupAuthModal() {
    if (els.btnOpenAuth) {
      els.btnOpenAuth.addEventListener("click", () => {
        openAuthModal();
      });
    }

    if (els.btnCloseAuth && els.authModal) {
      els.btnCloseAuth.addEventListener("click", () => {
        if (!storage.userToken) {
          showError(els.authError, "系统要求必须登录后使用。");
          return;
        }
        els.authModal.close();
      });
    }

    if (els.authModal) {
      els.authModal.addEventListener("click", (e) => {
        if (e.target === els.authModal) {
          if (!storage.userToken) {
            showError(els.authError, "系统要求必须登录后使用。");
            return;
          }
          els.authModal.close();
        }
      });
    }

    if (els.tabLogin && els.tabRegister) {
      els.tabLogin.addEventListener("click", () => {
        els.tabLogin.classList.add("active");
        els.tabRegister.classList.remove("active");
        if (els.formLogin) els.formLogin.hidden = false;
        if (els.formRegister) els.formRegister.hidden = true;
        showError(els.authError, "");
      });

      els.tabRegister.addEventListener("click", () => {
        els.tabRegister.classList.add("active");
        els.tabLogin.classList.remove("active");
        if (els.formLogin) els.formLogin.hidden = true;
        if (els.formRegister) els.formRegister.hidden = false;
        showError(els.authError, "");
      });
    }

    if (els.formLogin) {
      els.formLogin.addEventListener("submit", handleLogin);
    }
    if (els.formRegister) {
      els.formRegister.addEventListener("submit", handleRegister);
    }
    if (els.btnLogout) {
      els.btnLogout.addEventListener("click", handleLogout);
    }
  }

  // ================= Boot Application =================

  async function boot() {
    initElements();
    setupAuthModal();
    showError(els.bootError, "");
    renderMath(document.body);

    try {
      // 1. Check user token
      if (storage.userToken) {
        const user = await fetchCurrentUser();
        if (user) {
          await loadUserSessions();

          // If stored session exists, verify & load it
          if (storage.sessionToken && storage.sessionId) {
            try {
              const data = await api("/chatbot/messages", { token: storage.sessionToken, timeoutMs: 3000 });
              showChat();
              if (els.messages) els.messages.innerHTML = "";
              const msgs = data.messages || [];
              if (msgs.length) {
                history = msgs.map((m) => ({
                  role: m.role,
                  content: m.content,
                  thinking: m.thinking || "",
                  tool_calls: m.tool_calls || [],
                  segments: m.segments || [],
                }));
                msgs.forEach((m) =>
                  addMessageRow(m.role, m.content, m.thinking || "", m.tool_calls || [], m.segments || [])
                );
              } else {
                addMessageRow("assistant", defaultGreeting);
              }
              return;
            } catch (e) {
              console.warn("Restore session failed:", e);
            }
          }

          if (sessions.length > 0) {
            const first = sessions[0];
            showChat();
            await switchSession(first.session_id, first.token ? first.token.access_token : "", first.name);
            return;
          } else {
            await startNewSession();
            return;
          }
        }
      }

      // Not logged in -> show chat layout and require login modal
      showChat();
      if (els.messages) els.messages.innerHTML = "";
      addMessageRow("assistant", "欢迎使用 **Math Teacher** 智能数学导师！\n\n🔒 **系统已开启用户鉴权**：请先登录或注册账号以使用数学辅导与保存历史记录。\n已为您预填默认体验账号，直接点击登录即可！");
      openAuthModal();
    } catch (err) {
      console.error("Boot error:", err);
      showChat();
      openAuthModal();
    }
  }

  // ================= Messaging =================

  async function sendMessage(text) {
    if (busy || !text.trim()) return;

    if (!storage.userToken) {
      showError(els.chatError, "请先登录账号后再发送数学问题。");
      openAuthModal();
      return;
    }

    busy = true;
    if (els.btnSend) els.btnSend.disabled = true;
    showError(els.chatError, "");

    const content = text.trim();
    if (els.input) els.input.value = "";
    addMessageRow("user", content);
    history.push({ role: "user", content });

    const { bubble: assistantBubble } = addMessageRow("assistant", "");
    const streamRenderer = createStreamRenderer(assistantBubble);
    streamRenderer.addOrUpdateStatus("🔍 正在分析题目意图与解题策略...");

    try {
      if (!storage.sessionToken) {
        await createUserSession();
      }

      const res = await fetch(`${API}/chatbot/chat/stream`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${storage.sessionToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ messages: [{ role: "user", content }] }),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || `发送失败 (${res.status})`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let hasReceivedAnyToken = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() || "";
        for (const chunk of chunks) {
          const line = chunk.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          try {
            const payload = JSON.parse(line.slice(6));

            if (payload.thinking) {
              hasReceivedAnyToken = true;
              streamRenderer.appendThinking(payload.thinking);
            }

            if (payload.status) {
              streamRenderer.addOrUpdateStatus(
                payload.status,
                payload.tool_name || "",
                payload.tool_args || "",
                payload.tool_output || ""
              );
            }

            if (payload.content) {
              hasReceivedAnyToken = true;
              streamRenderer.appendContent(payload.content);
            }
          } catch (e) {
            console.warn("Parse stream chunk error:", e);
          }
        }
      }

      streamRenderer.finish();
      const resData = streamRenderer.getResult();

      if (!hasReceivedAnyToken && !resData.content && !resData.thinking) {
        const data = await api("/chatbot/chat", {
          method: "POST",
          token: storage.sessionToken,
          body: { messages: [{ role: "user", content }] },
        });
        const msgs = (data.messages || []).filter((m) => m.role === "assistant");
        const lastMsg = msgs.length ? msgs[msgs.length - 1] : null;
        if (lastMsg) {
          if (assistantBubble) {
            assistantBubble.innerHTML = "";
            addMessageRow("assistant", lastMsg.content, lastMsg.thinking || "", lastMsg.tool_calls || [], lastMsg.segments || []);
          }
          history.push({
            role: "assistant",
            content: lastMsg.content,
            thinking: lastMsg.thinking || "",
            tool_calls: lastMsg.tool_calls || [],
            segments: lastMsg.segments || [],
          });
        }
      } else {
        history.push({
          role: "assistant",
          content: resData.content,
          thinking: resData.thinking,
          tool_calls: resData.tool_calls,
          segments: resData.segments,
        });
      }

      // Refresh sessions list after naming
      setTimeout(async () => {
        await loadUserSessions();
      }, 1200);
    } catch (err) {
      if (assistantBubble) {
        assistantBubble.innerHTML = parseContent(`❌ **出错了**: ${err.message}`);
      }
      showError(els.chatError, err.message);
    } finally {
      busy = false;
      if (els.btnSend) els.btnSend.disabled = false;
      if (els.input) els.input.focus();
    }
  }

  function bindEvents() {
    initElements();

    if (els.chatForm) {
      els.chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        sendMessage(els.input ? els.input.value : "");
      });
    }

    if (els.input) {
      els.input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendMessage(els.input.value);
        }
      });
    }

    if (els.suggestions) {
      els.suggestions.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-prompt]");
        if (!btn) return;
        sendMessage(btn.dataset.prompt);
      });
    }

    if (els.btnNew) {
      els.btnNew.addEventListener("click", () => {
        startNewSession();
      });
    }

    if (els.messages) {
      els.messages.addEventListener("click", (e) => {
        if (e.target.tagName === "IMG" && els.modalImg && els.imgModal) {
          els.modalImg.src = e.target.src;
          if (typeof els.imgModal.showModal === "function") {
            els.imgModal.showModal();
          }
        }
      });
    }

    if (els.btnCloseModal && els.imgModal) {
      els.btnCloseModal.addEventListener("click", () => els.imgModal.close());
    }
    if (els.imgModal) {
      els.imgModal.addEventListener("click", (e) => {
        if (e.target === els.imgModal) els.imgModal.close();
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      bindEvents();
      boot();
    });
  } else {
    bindEvents();
    boot();
  }
})();
