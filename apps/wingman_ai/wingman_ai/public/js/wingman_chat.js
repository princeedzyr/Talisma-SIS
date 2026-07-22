(function () {
  "use strict";

  if (window.WingmanAIInitialized) {
    return;
  }
  window.WingmanAIInitialized = true;

  const IDS = {
    root: "wingman-ai-root",
    launcher: "wingman-ai-launcher",
    panel: "wingman-ai-panel",
    intelligence: "wingman-ai-intelligence-panel",
    messages: "wingman-ai-messages",
    input: "wingman-ai-input",
    send: "wingman-ai-send",
    loading: "wingman-ai-loading-overlay"
  };

  const API_METHOD = "wingman_ai.api.chat.send";
  const CONVERSATION_KEY = "wingman_ai_conversation_id";
  const REVIEW_STACK_KEY = "wingman_ai_review_stack";

  const ICONS = {
    bot: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="10" width="16" height="10" rx="3"></rect><circle cx="9" cy="15" r="1"></circle><circle cx="15" cy="15" r="1"></circle><path d="M12 10V6"></path><circle cx="12" cy="4" r="2"></circle></svg>',
    close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>',
    minimize: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14"></path></svg>',
    send: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m22 2-7 20-4-9-9-4Z"></path><path d="M22 2 11 13"></path></svg>',
    chevron: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"></path></svg>',
    info: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4"></path><path d="M12 8h.01"></path></svg>',
    pin: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m16 3 5 5"></path><path d="M8 14 3 21"></path><path d="m18 5-5 5"></path><path d="m7 17 10-10"></path><path d="m10 7 7 7"></path></svg>',
    expand: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H5a2 2 0 0 0-2 2v3"></path><path d="M16 3h3a2 2 0 0 1 2 2v3"></path><path d="M8 21H5a2 2 0 0 1-2-2v-3"></path><path d="M16 21h3a2 2 0 0 0 2-2v-3"></path></svg>',
    sparkles: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8Z"></path><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8Z"></path></svg>'
  };
  const DROPDOWN_MAX_VISIBLE_OPTIONS = 8;
  const LOADING_SHOW_DELAY_MS = 150;
  const LOADING_MIN_VISIBLE_MS = 260;
  const LOADING_TYPES = {
    silent: "silent",
    inline: "inline",
    card: "card",
    button: "button",
    transition: "transition"
  };
  let activeDropdown = null;
  let pinnedIntelligence = false;
  let currentIntelligenceModel = null;
  let loadingSequence = 0;
  const activeLoadingTasks = new Map();
  let loadingShowTimer = null;
  let loadingVisibleSince = 0;
  let pendingStudentOperation = null;

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn, { once: true });
      return;
    }
    fn();
  }

  function createButton(className, title, icon, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.title = title;
    button.setAttribute("aria-label", title);
    button.innerHTML = icon;
    button.addEventListener("click", onClick);
    return button;
  }

  const LoadingPolicyEngine = {
    classify: function (context) {
      const payload = normalizeLoadingContext(context);
      const action = payload.action || {};
      const method = String(payload.method || action.method || "").toLowerCase();
      const actionType = String(action.type || payload.actionType || "").toLowerCase();

      if (payload.loadingType && LOADING_TYPES[payload.loadingType]) {
        return buildLoadingPolicy(payload.loadingType, payload);
      }

      if (payload.target) {
        return buildLoadingPolicy(LOADING_TYPES.transition, payload);
      }

      if (payload.operation === "conversation" || payload.userMessage) {
        return buildLoadingPolicy(LOADING_TYPES.card, payload);
      }

      if (method.includes("link_resolution.search") || method.includes("search")) {
        return buildLoadingPolicy(LOADING_TYPES.inline, payload);
      }

      if (actionType === "collect_field" || actionType === "review_dependency" || actionType === "send_message") {
        return buildLoadingPolicy(LOADING_TYPES.card, payload);
      }

      if (actionType === "create" || actionType === "update" || actionType === "delete" || method.includes("record_creation") || method.includes("record_update") || method.includes("record_delete")) {
        return buildLoadingPolicy(LOADING_TYPES.button, payload);
      }

      if (method.includes("exception_intelligence.retry_operation")) {
        return buildLoadingPolicy(LOADING_TYPES.transition, payload);
      }

      if (method) {
        return buildLoadingPolicy(LOADING_TYPES.silent, payload);
      }

      return buildLoadingPolicy(LOADING_TYPES.silent, payload);
    }
  };

  function normalizeLoadingContext(context) {
    if (!context) {
      return {};
    }
    if (typeof context === "string") {
      return { message: context };
    }
    return context;
  }

  function buildLoadingPolicy(type, context) {
    return {
      type: type,
      message: loadingMessageFromContext(context),
      delay: Number.isFinite(context.delay) ? context.delay : LOADING_SHOW_DELAY_MS,
      blocksInteraction: type === LOADING_TYPES.transition
    };
  }

  function noopLoading(policy) {
    return {
      policy: policy || buildLoadingPolicy(LOADING_TYPES.silent, {}),
      update: function () {},
      finish: function () {}
    };
  }

  const NavigationLoadingService = {
    start: function (context) {
      const policy = LoadingPolicyEngine.classify(context);
      if (policy.type !== LOADING_TYPES.transition) {
        return noopLoading(policy);
      }
      const token = `wingman-loading-${++loadingSequence}`;
      activeLoadingTasks.set(token, {
        message: policy.message,
        delay: policy.delay,
        startedAt: Date.now()
      });
      scheduleLoadingOverlay();
      return {
        update: function (nextContext) {
          const task = activeLoadingTasks.get(token);
          if (!task) {
            return;
          }
          task.message = LoadingPolicyEngine.classify(nextContext).message;
          updateLoadingOverlayMessage();
        },
        finish: function () {
          finishLoadingTask(token);
        }
      };
    },
    run: function (context, work) {
      const loading = this.start(context);
      return Promise.resolve()
        .then(work)
        .then(
          function (result) {
            loading.finish();
            return result;
          },
          function (error) {
            loading.finish();
            throw error;
          }
        );
    },
    isBusy: function () {
      return activeLoadingTasks.size > 0;
    }
  };

  function scheduleLoadingOverlay() {
    const root = document.getElementById(IDS.root);
    if (root) {
      root.setAttribute("aria-busy", "true");
      root.classList.add("is-processing");
    }
    updateLoadingOverlayMessage();
    if (loadingShowTimer || isLoadingOverlayVisible()) {
      return;
    }
    loadingShowTimer = window.setTimeout(function () {
      loadingShowTimer = null;
      if (!activeLoadingTasks.size) {
        return;
      }
      showLoadingOverlay();
    }, currentLoadingDelay());
  }

  function currentLoadingDelay() {
    const tasks = Array.from(activeLoadingTasks.values());
    const latest = tasks[tasks.length - 1] || {};
    return latest.delay || LOADING_SHOW_DELAY_MS;
  }

  function finishLoadingTask(token) {
    activeLoadingTasks.delete(token);
    if (activeLoadingTasks.size) {
      updateLoadingOverlayMessage();
      return;
    }

    if (loadingShowTimer) {
      window.clearTimeout(loadingShowTimer);
      loadingShowTimer = null;
    }

    const elapsed = loadingVisibleSince ? Date.now() - loadingVisibleSince : 0;
    const remaining = isLoadingOverlayVisible() ? Math.max(0, LOADING_MIN_VISIBLE_MS - elapsed) : 0;
    window.setTimeout(hideLoadingOverlay, remaining);
  }

  function ensureLoadingOverlay() {
    let overlay = document.getElementById(IDS.loading);
    if (overlay) {
      return overlay;
    }
    const root = document.getElementById(IDS.root) || document.body;
    overlay = document.createElement("div");
    overlay.id = IDS.loading;
    overlay.className = "wingman-ai-loading-overlay";
    overlay.setAttribute("role", "status");
    overlay.setAttribute("aria-live", "polite");
    overlay.setAttribute("aria-atomic", "true");
    overlay.setAttribute("aria-hidden", "true");
    overlay.innerHTML = `
      <div class="wingman-ai-loading-card">
        <span class="wingman-ai-loading-avatar">${ICONS.bot}</span>
        <span class="wingman-ai-loading-text">Completing Request...</span>
        <span class="wingman-ai-loading-track" aria-hidden="true"><span></span></span>
      </div>
    `;
    overlay.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
    });
    root.appendChild(overlay);
    return overlay;
  }

  function showLoadingOverlay() {
    const overlay = ensureLoadingOverlay();
    updateLoadingOverlayMessage();
    overlay.classList.add("is-visible");
    overlay.setAttribute("aria-hidden", "false");
    loadingVisibleSince = Date.now();
  }

  function hideLoadingOverlay() {
    if (activeLoadingTasks.size) {
      return;
    }
    const overlay = document.getElementById(IDS.loading);
    if (overlay) {
      overlay.classList.remove("is-visible");
      overlay.setAttribute("aria-hidden", "true");
    }
    loadingVisibleSince = 0;
    const root = document.getElementById(IDS.root);
    if (root) {
      root.setAttribute("aria-busy", "false");
      root.classList.remove("is-processing");
    }
  }

  function isLoadingOverlayVisible() {
    const overlay = document.getElementById(IDS.loading);
    return Boolean(overlay && overlay.classList.contains("is-visible"));
  }

  function updateLoadingOverlayMessage() {
    const overlay = document.getElementById(IDS.loading);
    if (!overlay) {
      return;
    }
    const message = latestLoadingMessage();
    const text = overlay.querySelector(".wingman-ai-loading-text");
    if (text) {
      text.textContent = message;
    }
  }

  function latestLoadingMessage() {
    const tasks = Array.from(activeLoadingTasks.values());
    const latest = tasks[tasks.length - 1];
    return (latest && latest.message) || "Completing Request...";
  }

  function loadingMessageFromContext(context) {
    if (!context) {
      return "Completing Request...";
    }
    if (typeof context === "string") {
      return context;
    }
    if (context.message) {
      return context.message;
    }
    if (context.action) {
      return getActionProgressText(context.action);
    }
    if (context.target) {
      return getNavigationLoadingText(context.target);
    }
    if (context.userMessage) {
      return getMessageLoadingText(context.userMessage);
    }
    if (context.method) {
      return getFrappeMethodLoadingText(context.method, context.args);
    }
    return "Completing Request...";
  }

  function appendMessage(container, role, text, extraClass, payload) {
    const row = document.createElement("div");
    row.className = `wingman-ai-message wingman-ai-message--${role}`;
    if (extraClass) {
      row.classList.add(extraClass);
    }

    const bubble = document.createElement("div");
    bubble.className = "wingman-ai-bubble";
    renderMessageContent(bubble, text);

    row.appendChild(bubble);
    if (role === "assistant") {
      attachIntelligenceButton(row, normalizeIntelligenceModel(payload, text));
    }
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
    return row;
  }

  function updateMessage(row, text, payload) {
    const bubble = row ? row.querySelector(".wingman-ai-bubble") : null;
    if (bubble) {
      renderMessageContent(bubble, text);
      attachIntelligenceButton(row, normalizeIntelligenceModel(payload, text));
    }
  }

  function renderMessageContent(container, text) {
    container.textContent = "";
    const content = String(text || "");
    const lines = content.split(/\r?\n/);
    let list = null;

    lines.forEach(function (line) {
      const trimmed = line.trim();

      if (!trimmed) {
        list = null;
        return;
      }

      const bulletMatch = trimmed.match(/^[-*]\s+(.+)$/);
      if (bulletMatch) {
        if (!list) {
          list = document.createElement("ul");
          list.className = "wingman-ai-rendered-list";
          container.appendChild(list);
        }
        const item = document.createElement("li");
        item.textContent = bulletMatch[1];
        list.appendChild(item);
        return;
      }

      list = null;

      if (isHeadingLine(trimmed)) {
        const heading = document.createElement("strong");
        heading.className = "wingman-ai-rendered-heading";
        heading.textContent = trimmed.replace(/:$/, "");
        container.appendChild(heading);
        return;
      }

      const paragraph = document.createElement("p");
      paragraph.className = "wingman-ai-rendered-paragraph";
      paragraph.textContent = trimmed;
      container.appendChild(paragraph);
    });
  }

  function isHeadingLine(text) {
    if (text.length > 48) {
      return false;
    }

    return /:$/u.test(text)
      || /^(Overview|Key Uses|What You Can Do Next|Next Steps|Recommendation|Context|Summary|Hello|Help|Goodbye|Got It|Ready|Current Context|How I Can Help|Try Asking|Talisma OneCampus Operations|Student 360|Academic Overview|Contact & Campus|Enrollment & Courses|Attendance & Results|Alerts & Student Account|Admissions|Student Finance|Safe Changes|Choose Destination|Navigation Result|Record Lookup|Record Access|Request Timed Out|Permission Check|Connection Issue|Reasoning Request|Sales Request|Report Request|Workflow Request|Communication Request|Workflow Preview|Workflow Started|Estimated Inputs|Estimated Steps|Record Creation Review|Planning Mode|Graph Focus|Current Step|Lead Summary|Lead Search|Lead Creation Review|Lead Update Review|Lead Qualification|Lead Conversion Review|Facts|Related Activity|AI Recommendations|Captured Details|Defaults Applied|Default Configuration|System Generated Values|Derived Values|Missing Dependencies|Missing Information|Linked Record Required|Linked Records Required|Similar Existing Records|Next Required Detail|Proposed Changes|Conversion Path|Prerequisites|Current Status|Results|Reasons)$/iu.test(text);
  }

  function attachIntelligenceButton(row, model) {
    if (!row || !row.classList.contains("wingman-ai-message--assistant")) {
      return;
    }
    const bubble = getMessageBubble(row);
    if (!bubble) {
      return;
    }
    const existing = bubble.querySelector(".wingman-ai-intelligence-trigger");
    if (existing) {
      existing.remove();
    }
    if (!model) {
      return;
    }
    bubble.classList.add("has-intelligence");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "wingman-ai-intelligence-trigger";
    button.title = "View Wingman Intelligence";
    button.setAttribute("aria-label", "View Wingman Intelligence");
    button.innerHTML = ICONS.info;
    button.addEventListener("click", function () {
      openIntelligencePanel(model);
    });
    bubble.appendChild(button);
  }

  function normalizeIntelligenceModel(payload, text) {
    if (payload && payload.intelligence) {
      return payload.intelligence;
    }
    if (!text) {
      return null;
    }
    return {
      version: "client-fallback",
      administrator_view: {
        title: "Response Summary",
        status: "Information Ready",
        status_tone: "green",
        confidence_score: 70,
        confidence_label: "Limited context",
        message: "Wingman prepared the information you requested.",
        understanding: "Review the response and choose a suggested next step if one is available.",
        summary: [],
        attention: [],
        actions: [],
        note: "Wingman follows your OneCampus permissions."
      },
      operation_confidence: { score: 70, meter: 0.7, label: "Medium" },
      confidence_breakdown: [
        { label: "Response Availability", score: 70 },
        { label: "Backend Metadata", score: 0 }
      ],
      execution_readiness: {
        state: "Response Ready",
        indicator: "green",
        ready: true,
        reason: "Wingman displayed this response, but no backend intelligence model was attached."
      },
      validation_summary: [],
      dependency_summary: [{ label: "Dependencies", status: "Not evaluated", detail: "No dependency data was attached to this response." }],
      business_recommendations: [],
      ai_insights: [{ label: "AI Insights", detail: "No additional insights available." }],
      business_impact: { level: "Low", items: ["This response is informational unless an action button is confirmed."] },
      risk_assessment: { level: "Low", indicator: "green", reasons: ["No elevated risk signals were attached to this response."] },
      recommended_next_actions: [],
      operation_metadata: { current_operation: "response", execution_mode: "Read Only or Assisted" },
      performance_metrics: {
        conversation_duration: "Not measured",
        fields_collected: 0,
        dependencies_resolved: 0,
        validation_attempts: 0,
        execution_time: "Not measured"
      }
    };
  }

  function buildIntelligencePanel() {
    const panel = document.createElement("aside");
    panel.id = IDS.intelligence;
    panel.className = "wingman-ai-intelligence-panel";
    panel.setAttribute("aria-label", "Wingman Intelligence Center");
    panel.setAttribute("aria-hidden", "true");

    const header = document.createElement("div");
    header.className = "wingman-ai-intelligence-header";

    const title = document.createElement("div");
    title.className = "wingman-ai-intelligence-title";
    title.innerHTML = `<strong>Wingman Summary</strong><small>Student insights and next steps</small>`;

    const controls = document.createElement("div");
    controls.className = "wingman-ai-intelligence-controls";

    const collapse = createButton("wingman-ai-icon-btn", "Collapse Intelligence", ICONS.minimize, toggleIntelligenceCollapse);
    collapse.classList.add("wingman-ai-intelligence-collapse");

    const expand = createButton("wingman-ai-icon-btn", "Expand Intelligence", ICONS.expand, toggleIntelligenceExpand);
    expand.classList.add("wingman-ai-intelligence-expand");

    const pin = createButton("wingman-ai-icon-btn", "Pin Intelligence", ICONS.pin, toggleIntelligencePin);
    pin.classList.add("wingman-ai-intelligence-pin");

    const close = createButton("wingman-ai-icon-btn", "Close Intelligence", ICONS.close, closeIntelligencePanel);
    controls.append(collapse, expand, pin, close);
    header.append(title, controls);

    const body = document.createElement("div");
    body.className = "wingman-ai-intelligence-body";

    panel.append(header, body);
    return panel;
  }

  function openIntelligencePanel(model) {
    const panel = document.getElementById(IDS.intelligence);
    if (!panel || !model) {
      return;
    }
    currentIntelligenceModel = model;
    renderIntelligencePanel(model);
    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
  }

  function closeIntelligencePanel() {
    const panel = document.getElementById(IDS.intelligence);
    if (!panel) {
      return;
    }
    pinnedIntelligence = false;
    panel.classList.remove("is-open", "is-expanded", "is-collapsed", "is-pinned");
    panel.setAttribute("aria-hidden", "true");
    currentIntelligenceModel = null;
  }

  function toggleIntelligenceCollapse() {
    const panel = document.getElementById(IDS.intelligence);
    if (!panel) {
      return;
    }
    panel.classList.toggle("is-collapsed");
    if (panel.classList.contains("is-collapsed")) {
      panel.classList.remove("is-expanded");
    }
  }

  function toggleIntelligenceExpand() {
    const panel = document.getElementById(IDS.intelligence);
    if (!panel) {
      return;
    }
    panel.classList.toggle("is-expanded");
    if (panel.classList.contains("is-expanded")) {
      panel.classList.remove("is-collapsed");
    }
  }

  function toggleIntelligencePin() {
    const panel = document.getElementById(IDS.intelligence);
    if (!panel) {
      return;
    }
    pinnedIntelligence = !pinnedIntelligence;
    panel.classList.toggle("is-pinned", pinnedIntelligence);
    const pin = panel.querySelector(".wingman-ai-intelligence-pin");
    if (pin) {
      pin.title = pinnedIntelligence ? "Unpin Intelligence" : "Pin Intelligence";
      pin.setAttribute("aria-label", pin.title);
    }
  }

  function renderIntelligencePanel(model) {
    const panel = document.getElementById(IDS.intelligence);
    const body = panel ? panel.querySelector(".wingman-ai-intelligence-body") : null;
    if (!body) {
      return;
    }

    body.textContent = "";
    if (model.administrator_view) {
      renderAdministratorView(body, model.administrator_view);
      return;
    }
    renderConfidence(body, model.operation_confidence || {}, model.confidence_breakdown || []);
    renderReadiness(body, model.execution_readiness || {});
    renderKeyValueSection(body, "Validation Summary", model.validation_summary || []);
    renderDependencySection(body, model.dependency_summary || []);
    renderRecommendationSection(body, model.business_recommendations || []);
    renderInsightSection(body, model.ai_insights || []);
    renderImpactSection(body, model.business_impact || {});
    renderRiskSection(body, model.risk_assessment || {});
    renderActionSection(body, model.recommended_next_actions || []);
    renderObjectSection(body, "Operation Metadata", model.operation_metadata || {});
    renderObjectSection(body, "Performance Metrics", model.performance_metrics || {});
  }

  function renderAdministratorView(body, view) {
    const overview = createIntelligenceSection(view.title || "Response Summary");
    overview.classList.add("wingman-ai-admin-overview");
    const statusRow = document.createElement("div");
    statusRow.className = "wingman-ai-admin-status-row";
    const status = document.createElement("div");
    status.className = `wingman-ai-readiness wingman-ai-readiness--${view.status_tone || "green"}`;
    status.textContent = view.status || "Information Ready";
    const confidence = document.createElement("div");
    confidence.className = "wingman-ai-admin-confidence";
    const confidenceScore = Math.max(0, Math.min(100, Number(view.confidence_score || 0)));
    const confidenceTitle = document.createElement("span");
    confidenceTitle.textContent = "Confidence";
    const confidenceValue = document.createElement("strong");
    confidenceValue.textContent = `${confidenceScore}%`;
    const confidenceLabel = document.createElement("small");
    confidenceLabel.textContent = view.confidence_label || "Good match";
    confidence.append(confidenceTitle, confidenceValue, confidenceLabel);
    statusRow.append(status, confidence);
    const message = document.createElement("p");
    message.textContent = view.message || "Wingman prepared the information you requested.";
    const understanding = document.createElement("p");
    understanding.className = "wingman-ai-admin-understanding";
    understanding.textContent = view.understanding || "Wingman understood your request.";
    overview.append(statusRow, message, understanding);
    body.appendChild(overview);

    if ((view.summary || []).length) {
      renderAdministratorDetails(body, view.summary);
    }

    if ((view.attention || []).length) {
      const attention = createIntelligenceSection(view.attention_title || "Needs Attention");
      const list = document.createElement("ul");
      list.className = "wingman-ai-intelligence-list wingman-ai-admin-attention";
      view.attention.forEach(function (item) {
        const row = document.createElement("li");
        row.textContent = item;
        list.appendChild(row);
      });
      attention.appendChild(list);
      body.appendChild(attention);
    }

    renderActionSection(body, view.actions || []);
    if (view.note) {
      const note = document.createElement("p");
      note.className = "wingman-ai-admin-note";
      note.textContent = view.note;
      body.appendChild(note);
    }
  }

  function renderAdministratorDetails(body, rows) {
    const section = createIntelligenceSection("Student Details");
    section.classList.add("wingman-ai-admin-details");
    const grid = document.createElement("div");
    grid.className = "wingman-ai-admin-details-grid";
    rows.forEach(function (row) {
      const item = document.createElement("div");
      const value = String(row.value || "Not available");
      item.className = "wingman-ai-admin-detail";
      if (value.length > 28 || ["Program", "Student"].includes(row.label)) {
        item.classList.add("is-wide");
      }
      const label = document.createElement("span");
      label.textContent = row.label;
      const content = document.createElement("strong");
      content.textContent = value;
      item.append(label, content);
      grid.appendChild(item);
    });
    section.appendChild(grid);
    body.appendChild(section);
  }

  function renderConfidence(body, confidence, breakdown) {
    const section = createIntelligenceSection("Operation Confidence");
    const score = Number(confidence.score || 0);
    const summary = document.createElement("div");
    summary.className = "wingman-ai-confidence-summary";
    summary.innerHTML = `<strong>${score}%</strong><span>${confidence.label || "Medium"}</span>`;

    const meter = document.createElement("div");
    meter.className = "wingman-ai-confidence-meter";
    const fill = document.createElement("span");
    fill.style.width = `${Math.max(0, Math.min(100, score))}%`;
    meter.appendChild(fill);

    section.append(summary, meter);
    if (breakdown.length) {
      const list = document.createElement("div");
      list.className = "wingman-ai-intelligence-kv";
      breakdown.forEach(function (item) {
        appendKV(list, item.label, `${item.score}%`);
      });
      section.appendChild(list);
    }
    body.appendChild(section);
  }

  function renderReadiness(body, readiness) {
    const section = createIntelligenceSection("Execution Readiness");
    const status = document.createElement("div");
    status.className = `wingman-ai-readiness wingman-ai-readiness--${readiness.indicator || "green"}`;
    status.textContent = readiness.state || "Response Ready";
    const reason = document.createElement("p");
    reason.textContent = readiness.reason || "Wingman generated this response.";
    section.append(status, reason);
    body.appendChild(section);
  }

  function renderKeyValueSection(body, title, rows) {
    if (!rows.length) {
      return;
    }
    const section = createIntelligenceSection(title);
    const grid = document.createElement("div");
    grid.className = "wingman-ai-intelligence-kv";
    rows.forEach(function (row) {
      appendKV(grid, row.label, row.value || row.status || row.detail);
    });
    section.appendChild(grid);
    body.appendChild(section);
  }

  function renderDependencySection(body, rows) {
    const section = createIntelligenceSection("Dependency Summary");
    const list = document.createElement("ul");
    list.className = "wingman-ai-intelligence-list";
    (rows.length ? rows : [{ label: "Dependencies", status: "Clear", detail: "No missing linked records were detected." }]).forEach(function (row) {
      const item = document.createElement("li");
      const label = row.target_doctype ? `${row.target_doctype}: ${row.value || ""}` : (row.label || "Dependencies");
      item.textContent = `${label} - ${row.status || row.detail || "Clear"}`;
      list.appendChild(item);
    });
    section.appendChild(list);
    body.appendChild(section);
  }

  function renderRecommendationSection(body, rows) {
    if (!rows.length) {
      return;
    }
    const section = createIntelligenceSection("Business Recommendations");
    const list = document.createElement("ul");
    list.className = "wingman-ai-intelligence-list";
    rows.forEach(function (row) {
      const item = document.createElement("li");
      item.textContent = row.label || row.message || "Recommendation";
      list.appendChild(item);
    });
    section.appendChild(list);
    body.appendChild(section);
  }

  function renderInsightSection(body, rows) {
    const section = createIntelligenceSection("AI Insights");
    const list = document.createElement("ul");
    list.className = "wingman-ai-intelligence-list";
    (rows.length ? rows : [{ label: "AI Insights", detail: "No additional insights available." }]).forEach(function (row) {
      const item = document.createElement("li");
      item.textContent = row.detail ? `${row.label}: ${row.detail}` : (row.label || "No additional insights available.");
      list.appendChild(item);
    });
    section.appendChild(list);
    body.appendChild(section);
  }

  function renderImpactSection(body, impact) {
    const section = createIntelligenceSection("Business Impact");
    const level = document.createElement("div");
    level.className = "wingman-ai-impact-level";
    level.textContent = impact.level || "Low";
    const list = document.createElement("ul");
    list.className = "wingman-ai-intelligence-list";
    (impact.items || ["No major business impact was detected."]).forEach(function (item) {
      const li = document.createElement("li");
      li.textContent = item;
      list.appendChild(li);
    });
    section.append(level, list);
    body.appendChild(section);
  }

  function renderRiskSection(body, risk) {
    const section = createIntelligenceSection("Risk Assessment");
    const level = document.createElement("div");
    level.className = `wingman-ai-readiness wingman-ai-readiness--${risk.indicator || "green"}`;
    level.textContent = risk.level || "Low";
    const list = document.createElement("ul");
    list.className = "wingman-ai-intelligence-list";
    (risk.reasons || ["No elevated risk signals were detected."]).forEach(function (item) {
      const li = document.createElement("li");
      li.textContent = item;
      list.appendChild(li);
    });
    section.append(level, list);
    body.appendChild(section);
  }

  function renderActionSection(body, actions) {
    if (!actions.length) {
      return;
    }
    const section = createIntelligenceSection("Recommended Next Actions");
    const actionList = document.createElement("div");
    actionList.className = "wingman-ai-intelligence-action-list";
    actions.forEach(function (action) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "wingman-ai-action-button";
      button.textContent = action.label || "Run suggestion";
      button.addEventListener("click", function () {
        const message = String((action.payload || {}).message || action.message || "").trim();
        if (message) {
          sendWingmanMessage(message, { focusComposer: false });
          if (!pinnedIntelligence) {
            closeIntelligencePanel();
          }
        }
      });
      actionList.appendChild(button);
    });
    section.appendChild(actionList);
    body.appendChild(section);
  }

  function renderObjectSection(body, title, values) {
    const keys = Object.keys(values || {});
    if (!keys.length) {
      return;
    }
    const section = createIntelligenceSection(title);
    const grid = document.createElement("div");
    grid.className = "wingman-ai-intelligence-kv";
    keys.forEach(function (key) {
      appendKV(grid, labelize(key), values[key]);
    });
    section.appendChild(grid);
    body.appendChild(section);
  }

  function createIntelligenceSection(title) {
    const section = document.createElement("section");
    section.className = "wingman-ai-intelligence-section";
    const heading = document.createElement("h3");
    heading.textContent = title;
    section.appendChild(heading);
    return section;
  }

  function appendKV(container, label, value) {
    const row = document.createElement("div");
    const key = document.createElement("span");
    const val = document.createElement("strong");
    key.textContent = label || "Item";
    val.textContent = value === undefined || value === null || value === "" ? "Not available" : String(value);
    row.append(key, val);
    container.appendChild(row);
  }

  function labelize(value) {
    return String(value || "").replace(/_/g, " ").replace(/\b\w/g, function (letter) {
      return letter.toUpperCase();
    });
  }

  function getMessageBubble(row) {
    return row ? row.querySelector(".wingman-ai-bubble") : null;
  }

  function appendActionStatus(row, text) {
    const bubble = getMessageBubble(row);
    if (!bubble) {
      return null;
    }

    const status = document.createElement("div");
    status.className = "wingman-ai-action-status";
    status.textContent = text;
    bubble.appendChild(status);
    return status;
  }

  function renderActions(row, actions) {
    const executableActions = (actions || []).filter(function (action) {
      return action && action.type && action.auto_execute !== true;
    });

    if (!executableActions.length) {
      return;
    }

    const bubble = getMessageBubble(row);
    if (!bubble) {
      return;
    }

    const actionsEl = document.createElement("div");
    actionsEl.className = "wingman-ai-action-list";
    if (executableActions.some(isActionCenterAction)) {
      actionsEl.classList.add("wingman-ai-action-center");
      renderActionCenter(actionsEl, executableActions, row);
      bubble.appendChild(actionsEl);
      return;
    }

    executableActions.forEach(function (action) {
      renderActionControl(actionsEl, action, row);
    });

    bubble.appendChild(actionsEl);
  }

  function isActionCenterAction(action) {
    return Boolean(action && (action.action_center || ((action.presentation || {}).section === "action_center")));
  }

  function renderActionCenter(actionsEl, actions, row) {
    renderActionCenterHeader(actionsEl);
    const groups = [
      ["primary", "Recommended Action"],
      ["secondary", "Other Actions"],
      ["utility", "Utility"],
    ];
    groups.forEach(function (group) {
      const groupActions = (actions || []).filter(function (action) {
        return ((action.presentation || {}).group || "secondary") === group[0];
      });
      if (!groupActions.length) {
        return;
      }
      const section = document.createElement("div");
      section.className = `wingman-ai-action-center-section wingman-ai-action-center-${group[0]}`;
      const title = document.createElement("div");
      title.className = "wingman-ai-action-center-section-title";
      title.textContent = group[1];
      section.appendChild(title);
      groupActions.forEach(function (action) {
        renderActionControl(section, action, row);
      });
      actionsEl.appendChild(section);
    });
  }

  function renderActionCenterHeader(actionsEl) {
    const header = document.createElement("div");
    header.className = "wingman-ai-action-center-header";
    const title = document.createElement("strong");
    title.textContent = "Action Center";
    const summary = document.createElement("span");
    summary.textContent = "Choose an action to continue without restarting the workflow.";
    header.append(title, summary);
    actionsEl.appendChild(header);
  }

  function renderActionControl(container, action, row) {
    if (action.type === "collect_field") {
      renderCollectFieldAction(container, action);
      return;
    }
    if (action.type === "edit_update_field") {
      renderInlineUpdateFieldAction(container, action);
      return;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "wingman-ai-action-button";
    if ((action.presentation || {}).variant === "primary") {
      button.classList.add("wingman-ai-action-button-primary");
    }
    button.textContent = action.label || "Run action";
    if (action.description) {
      button.title = action.description;
    }
    if (action.enabled === false) {
      button.disabled = true;
      button.classList.add("is-disabled");
      button.title = "Required information is missing.";
      button.setAttribute("aria-disabled", "true");
    }
    button.addEventListener("click", function () {
      if (button.disabled) {
        return;
      }
      button.disabled = true;
      const result = executeAction(action, row, { trigger: button });
      if (result && typeof result.then === "function") {
        result.then(function (payload) {
          if (payload === false || (payload && payload.success === false)) {
            button.disabled = false;
          }
        });
        return;
      }
      if (result === false) {
        button.disabled = false;
      }
    });
    container.appendChild(button);
  }

  function renderCollectFieldAction(actionsEl, action) {
    const payload = action.payload || {};
    const field = payload.field || {};
    const component = field.component || {};
    const componentType = normalizeComponentType(component.type, field.fieldtype);
    if (componentType === "curriculum_requirements") {
      renderCurriculumRequirementsAction(actionsEl, action);
      return;
    }
    if (componentType === "student_group_members") {
      renderStudentGroupMembersAction(actionsEl, action);
      return;
    }
    const choices = field.choices || [];
    const form = document.createElement("form");
    form.className = "wingman-ai-field-form";

    const label = document.createElement("label");
    label.className = "wingman-ai-field-label";
    label.textContent = field.label || action.label || "Required detail";

    const control = buildFieldControl(field, componentType, choices);
    const hint = document.createElement("div");
    hint.className = "wingman-ai-field-hint";
    hint.textContent = fieldHint(field, componentType, choices);
    const recommendation = renderFieldRecommendation(field, control, componentType);

    const submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "wingman-ai-action-button wingman-ai-field-submit";
    submit.textContent = field.recommendation && field.recommendation.auto_apply ? "Next" : "Continue";

    form.append(label, control);
    if (hint.textContent) {
      form.appendChild(hint);
    }
    if (recommendation) {
      form.appendChild(recommendation);
    }
    form.appendChild(submit);

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      const value = readFieldControlValue(control, componentType);
      if (field.required && componentType !== "checkbox" && !String(value || "").trim()) {
        hint.textContent = `Please provide ${field.label || "the required detail"}.`;
        control.focus();
        return;
      }
      submit.disabled = true;
      control.disabled = true;
      if (payload.method) {
        const collectedAction = buildCollectedFieldAction(action, value);
        const result = executeAction(collectedAction, getMessageRow(form) || actionsEl.closest(".wingman-ai-message"));
        if (result && typeof result.then === "function") {
          result.then(function (payload) {
            if (payload === false || (payload && payload.success === false)) {
              submit.disabled = false;
              control.disabled = false;
              control.focus();
            }
          });
        }
        return;
      }
      sendWingmanMessage(String(value), { focusComposer: false }).then(function (payload) {
        if (payload === false || (payload && payload.success === false)) {
          submit.disabled = false;
          control.disabled = false;
          control.focus();
        }
      });
    });

    actionsEl.appendChild(form);
  }

  function renderStudentGroupMembersAction(actionsEl, action) {
    const field = ((action.payload || {}).field) || {};
    const component = field.component || {};
    const form = document.createElement("form");
    form.className = "wingman-ai-field-form wingman-ai-student-group-form";

    const label = document.createElement("label");
    label.className = "wingman-ai-field-label";
    label.textContent = "Select Students";

    const control = buildWingmanDropdown(field, field.choices || [], {
      multiple: true,
      searchable: true,
      allowCustom: false,
      allowCreate: false,
      hideDescriptions: true
    });

    const hint = document.createElement("div");
    hint.className = "wingman-ai-field-hint";
    hint.textContent = "Search by student name and select one or more students.";

    const submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "wingman-ai-action-button wingman-ai-field-submit";
    submit.textContent = "Continue with Selected Students";

    form.append(label, control, hint, submit);
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      const students = String(readFieldControlValue(control, "multiselect") || "")
        .split(",")
        .map(function (value) { return value.trim(); })
        .filter(Boolean);
      if (!students.length) {
        hint.textContent = "Select at least one student before continuing.";
        control.focus();
        return;
      }
      const labels = typeof control._wingmanGetSelectedLabels === "function"
        ? control._wingmanGetSelectedLabels()
        : [];
      submit.disabled = true;
      control.disabled = true;
      sendWingmanMessage(JSON.stringify(students), {
        displayText: `Selected students: ${labels.length ? labels.join(", ") : students.length}`,
        focusComposer: false
      }).then(function (payload) {
        if (payload === false || (payload && payload.success === false)) {
          submit.disabled = false;
          control.disabled = false;
          control.focus();
        }
      });
    });

    actionsEl.appendChild(form);
  }

  function renderCurriculumRequirementsAction(actionsEl, action) {
    const field = ((action.payload || {}).field) || {};
    const component = field.component || {};
    const courseField = component.course_field || {
      fieldname: "course",
      label: "Course",
      fieldtype: "Link",
      options: "Course",
      component: { type: "link", target_doctype: "Course", allow_create: false }
    };
    const courseChoices = field.choices || [];
    const rows = [];
    const shell = document.createElement("section");
    shell.className = "wingman-ai-curriculum-builder";

    const heading = document.createElement("div");
    heading.className = "wingman-ai-curriculum-heading";
    const headingTitle = document.createElement("strong");
    headingTitle.textContent = "Curriculum Requirements";
    const headingHelp = document.createElement("span");
    headingHelp.textContent = `${component.program ? `Linked to ${component.program}. ` : ""}Add at least one Course to continue.`;
    heading.append(headingTitle, headingHelp);

    const list = document.createElement("div");
    list.className = "wingman-ai-curriculum-list";
    const editor = document.createElement("div");
    editor.className = "wingman-ai-curriculum-editor";

    const footer = document.createElement("div");
    footer.className = "wingman-ai-curriculum-footer";
    const addButton = document.createElement("button");
    addButton.type = "button";
    addButton.className = "wingman-ai-action-button";
    addButton.textContent = "Add Requirement";
    const finishButton = document.createElement("button");
    finishButton.type = "button";
    finishButton.className = "wingman-ai-action-button wingman-ai-action-button-primary";
    finishButton.textContent = "Continue";
    finishButton.disabled = true;
    footer.append(addButton, finishButton);

    function courseLabel(value) {
      const match = normalizeDropdownChoices(courseChoices).find(function (choice) {
        return String(choice.value) === String(value);
      });
      return match ? match.label : String(value || "Course");
    }

    function requirementCode(course, index) {
      return `REQ-${String(index).padStart(2, "0")}`;
    }

    function renderRows() {
      list.innerHTML = "";
      rows.forEach(function (row, index) {
        const item = document.createElement("div");
        item.className = "wingman-ai-curriculum-row";
        const details = document.createElement("div");
        const courseName = document.createElement("strong");
        courseName.textContent = courseLabel(row.course);
        const requirementDetails = document.createElement("span");
        requirementDetails.textContent = `${row.requirement_type} · ${row.requirement_code} · Sequence ${index + 1}`;
        details.append(courseName, requirementDetails);
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "wingman-ai-curriculum-remove";
        remove.textContent = "Remove";
        remove.addEventListener("click", function () {
          rows.splice(index, 1);
          rows.forEach(function (entry, rowIndex) {
            entry.sequence = rowIndex + 1;
            entry.requirement_code = requirementCode(entry.course, rowIndex + 1);
          });
          renderRows();
        });
        item.append(details, remove);
        list.appendChild(item);
      });
      finishButton.disabled = rows.length === 0;
      finishButton.textContent = rows.length ? `Continue with ${rows.length} Requirement${rows.length === 1 ? "" : "s"}` : "Continue";
    }

    function openEditor() {
      editor.innerHTML = "";
      editor.classList.add("is-open");
      addButton.disabled = true;
      const form = document.createElement("form");
      form.className = "wingman-ai-curriculum-form";

      const courseLabelEl = document.createElement("label");
      courseLabelEl.className = "wingman-ai-field-label";
      courseLabelEl.textContent = "Course";
      const courseControl = buildWingmanDropdown(courseField, courseChoices, {
        multiple: false,
        searchable: true,
        allowCustom: false,
        allowCreate: false
      });

      const typeLabel = document.createElement("label");
      typeLabel.className = "wingman-ai-field-label";
      typeLabel.textContent = "Requirement Type";
      const typeField = {
        label: "Requirement Type",
        placeholder: "Select Requirement Type",
        fieldtype: "Select",
        component: { type: "select" }
      };
      const typeChoices = (component.requirement_types || ["Required Course"]).map(function (value) {
        return { label: value, value: value };
      });
      const typeControl = buildWingmanDropdown(typeField, typeChoices, {
        multiple: false,
        searchable: false,
        allowCustom: false
      });

      const autoGrid = document.createElement("div");
      autoGrid.className = "wingman-ai-curriculum-auto-grid";
      const codeValue = document.createElement("strong");
      codeValue.textContent = "Generated from Course";
      const sequenceValue = document.createElement("strong");
      sequenceValue.textContent = String(rows.length + 1);
      autoGrid.innerHTML = "<span>Requirement Code</span><span>Sequence</span>";
      autoGrid.append(codeValue, sequenceValue);

      const error = document.createElement("div");
      error.className = "wingman-ai-field-hint is-error";
      const controls = document.createElement("div");
      controls.className = "wingman-ai-curriculum-editor-actions";
      const save = document.createElement("button");
      save.type = "submit";
      save.className = "wingman-ai-action-button wingman-ai-action-button-primary";
      save.textContent = "Add to Curriculum";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "wingman-ai-action-button";
      cancel.textContent = "Cancel";
      controls.append(save, cancel);
      form.append(courseLabelEl, courseControl, typeLabel, typeControl, autoGrid, error, controls);
      editor.appendChild(form);

      function refreshCode() {
        const selectedCourse = readFieldControlValue(courseControl, "link");
        codeValue.textContent = selectedCourse ? requirementCode(selectedCourse, rows.length + 1) : "Generated from Course";
      }
      form.addEventListener("input", refreshCode);
      form.addEventListener("click", function () { window.setTimeout(refreshCode, 0); });
      cancel.addEventListener("click", function () {
        editor.classList.remove("is-open");
        editor.innerHTML = "";
        addButton.disabled = false;
      });
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        const course = readFieldControlValue(courseControl, "link");
        const requirementType = readFieldControlValue(typeControl, "select");
        if (!course || !requirementType) {
          error.textContent = "Select both a Course and Requirement Type.";
          return;
        }
        rows.push({
          course: course,
          requirement_type: requirementType,
          requirement_code: requirementCode(course, rows.length + 1),
          sequence: rows.length + 1,
          active: 1
        });
        editor.classList.remove("is-open");
        editor.innerHTML = "";
        addButton.disabled = false;
        renderRows();
      });
    }

    addButton.addEventListener("click", openEditor);
    finishButton.addEventListener("click", function () {
      if (!rows.length) {
        return;
      }
      addButton.disabled = true;
      finishButton.disabled = true;
      const submittedRows = rows.slice();
      sendWingmanMessage(JSON.stringify(submittedRows), {
        showUserMessage: false,
        focusComposer: false
      }).then(function (payload) {
        if (payload === false || (payload && payload.success === false)) {
          addButton.disabled = false;
          finishButton.disabled = false;
        }
      });
    });

    shell.append(heading, list, editor, footer);
    actionsEl.appendChild(shell);
  }

  function renderInlineUpdateFieldAction(actionsEl, action) {
    const payload = action.payload || {};
    const field = payload.field || {};
    const row = document.createElement("div");
    row.className = "wingman-ai-update-field-row";
    if (field.modified) {
      row.classList.add("is-modified");
    }

    renderInlineUpdateFieldSummary(row, action, actionsEl);
    actionsEl.appendChild(row);
  }

  function renderInlineUpdateFieldSummary(row, action, actionsEl) {
    const field = ((action.payload || {}).field) || {};
    row.innerHTML = "";

    const summary = document.createElement("div");
    summary.className = "wingman-ai-update-field-summary";

    const text = document.createElement("div");
    text.className = "wingman-ai-update-field-text";
    const label = document.createElement("strong");
    label.textContent = field.label || action.label || "Field";
    const value = document.createElement("span");
    value.textContent = formatInlineUpdateValue(field);
    text.append(label, value);

    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "wingman-ai-action-button wingman-ai-update-edit-button";
    edit.textContent = field.modified ? "Edit Again" : "Edit";
    edit.addEventListener("click", function () {
      renderInlineUpdateFieldEditor(row, action, actionsEl);
    });

    summary.append(text, edit);
    row.appendChild(summary);
  }

  function renderInlineUpdateFieldEditor(row, action, actionsEl) {
    const payload = action.payload || {};
    const field = payload.field || {};
    const component = field.component || {};
    const componentType = normalizeComponentType(component.type, field.fieldtype);
    const choices = field.choices || [];
    const form = document.createElement("form");
    form.className = "wingman-ai-update-field-editor";

    const label = document.createElement("label");
    label.className = "wingman-ai-field-label";
    label.textContent = field.label || action.label || "Field";

    const control = buildFieldControl(field, componentType, choices);
    setFieldControlValue(control, componentType, field.modified ? field.new_value : field.current_value);

    const hint = document.createElement("div");
    hint.className = "wingman-ai-field-hint";
    hint.textContent = "This updates Wingman’s draft first. Talisma OneCampus changes only after final confirmation.";

    const footer = document.createElement("div");
    footer.className = "wingman-ai-update-field-editor-actions";

    const save = document.createElement("button");
    save.type = "submit";
    save.className = "wingman-ai-action-button wingman-ai-field-submit";
    save.textContent = "Save Field";

    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "wingman-ai-action-button";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", function () {
      renderInlineUpdateFieldSummary(row, action, actionsEl);
    });

    footer.append(save, cancel);
    form.append(label, control, hint, footer);

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      const value = readFieldControlValue(control, componentType);
      save.disabled = true;
      cancel.disabled = true;
      control.disabled = true;
      const collectedAction = buildCollectedFieldAction(action, value);
      const result = executeAction(collectedAction, getMessageRow(form) || actionsEl.closest(".wingman-ai-message"));
      if (result && typeof result.then === "function") {
        result.then(function (payload) {
          if (payload === false || (payload && payload.success === false)) {
            save.disabled = false;
            cancel.disabled = false;
            control.disabled = false;
            control.focus();
          }
        });
      }
    });

    row.innerHTML = "";
    row.appendChild(form);
    if (control && typeof control.focus === "function") {
      control.focus();
    }
  }

  function formatInlineUpdateValue(field) {
    const currentValue = formatDisplayValue(field.current_value);
    if (field.modified) {
      return `New: ${formatDisplayValue(field.new_value)} · Current: ${currentValue}`;
    }
    return currentValue;
  }

  function formatDisplayValue(value) {
    if (value === undefined || value === null || value === "") {
      return "Blank";
    }
    if (value === true || value === 1) {
      return "Yes";
    }
    if (value === false || value === 0) {
      return "No";
    }
    if (Array.isArray(value)) {
      return value.length ? value.join(", ") : "Blank";
    }
    if (typeof value === "object") {
      return JSON.stringify(value);
    }
    return String(value);
  }

  function renderFieldRecommendation(field, control, componentType) {
    const recommendation = field.recommendation || null;
    if (!recommendation || recommendation.value === undefined || recommendation.value === null || recommendation.value === "") {
      return null;
    }

    if (recommendation.auto_apply) {
      applyFieldRecommendation(control, componentType, recommendation.value);
    }

    const panel = document.createElement("div");
    panel.className = "wingman-ai-field-recommendation";

    const text = document.createElement("div");
    text.className = "wingman-ai-field-recommendation-text";
    const label = recommendation.label || recommendation.value;
    const heading = document.createElement("strong");
    heading.textContent = recommendation.auto_apply ? "Prefilled" : "Recommended";
    const valueLabel = document.createElement("span");
    valueLabel.textContent = String(label);
    text.append(heading, valueLabel);

    const reason = document.createElement("div");
    reason.className = "wingman-ai-field-recommendation-reason";
    reason.textContent = recommendation.reason || "Most likely value based on the current conversation.";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "wingman-ai-action-button wingman-ai-recommendation-button";
    button.textContent = recommendation.auto_apply ? "Restore Suggestion" : "Use Recommendation";
    button.addEventListener("click", function () {
      applyFieldRecommendation(control, componentType, recommendation.value);
      if (control && typeof control.focus === "function") {
        control.focus();
      }
    });

    panel.append(text, reason, button);
    return panel;
  }

  function applyFieldRecommendation(control, componentType, value) {
    if (!control) {
      return;
    }
    if (componentType === "checkbox") {
      control.checked = Boolean(value);
      return;
    }
    control.value = Array.isArray(value) ? value.join(", ") : String(value);
    control.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function setFieldControlValue(control, componentType, value) {
    if (!control) {
      return;
    }
    if (componentType === "checkbox") {
      control.checked = value === true || value === 1 || String(value || "").toLowerCase() === "yes";
      return;
    }
    control.value = value === undefined || value === null ? "" : Array.isArray(value) ? value.join(", ") : String(value);
    control.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function buildCollectedFieldAction(action, value) {
    const payload = action.payload || {};
    const args = Object.assign({}, payload.args || {});
    args.value = value;
    return {
      type: payload.action_type || "update",
      label: action.label || "Continue",
      method: payload.method,
      payload: args,
      requires_confirmation: false,
      auto_execute: false,
      enabled: true
    };
  }

  function getMessageRow(element) {
    return element && typeof element.closest === "function"
      ? element.closest(".wingman-ai-message")
      : null;
  }

  function buildFieldControl(field, componentType, choices) {
    if ((componentType === "select" || componentType === "multiselect") && choices.length) {
      return buildWingmanDropdown(field, choices, {
        multiple: componentType === "multiselect",
        searchable: true,
        allowCustom: false
      });
    }

    if (isLinkComponentType(componentType)) {
      const component = field.component || {};
      return buildWingmanDropdown(field, choices || [], {
        multiple: false,
        searchable: true,
        allowCustom: true,
        allowCreate: component.allow_create !== false && component.allow_create_missing !== false
      });
    }

    if (componentType === "textarea" || componentType === "table") {
      const textarea = document.createElement("textarea");
      textarea.className = "wingman-ai-field-control";
      textarea.rows = 3;
      textarea.placeholder = field.placeholder || `Enter ${field.label || "value"}`;
      return textarea;
    }

    if (componentType === "checkbox") {
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "wingman-ai-field-checkbox";
      return checkbox;
    }

    const input = document.createElement("input");
    input.className = "wingman-ai-field-control";
    input.type = inputTypeForComponent(componentType);
    input.placeholder = field.placeholder || `Enter ${field.label || "value"}`;
    return input;
  }

  function normalizeComponentType(componentType, fieldtype) {
    const value = String(componentType || "").trim();
    if (value === "search_select") {
      return "link";
    }
    if (value === "dynamic_search_select") {
      return "dynamic_link";
    }
    if (!value && fieldtype === "Link") {
      return "link";
    }
    if (!value && fieldtype === "Dynamic Link") {
      return "dynamic_link";
    }
    return value || "text";
  }

  function isLinkComponentType(componentType) {
    return ["link", "search_select", "dynamic_link", "dynamic_search_select"].includes(String(componentType || ""));
  }

  function linkTargetDoctype(field, component) {
    const resolved = component || {};
    if (resolved.target_doctype) {
      return resolved.target_doctype;
    }
    if ((field || {}).target_doctype) {
      return field.target_doctype;
    }
    if ((field || {}).fieldtype === "Link") {
      return (field || {}).options || "";
    }
    return "";
  }

  function buildWingmanDropdown(field, choices, config) {
    const settings = Object.assign({ multiple: false, searchable: true, allowCustom: false, allowCreate: false }, config || {});
    let normalizedChoices = normalizeDropdownChoices(choices);
    if (settings.hideDescriptions) {
      normalizedChoices = normalizedChoices.map(function (choice) {
        return Object.assign({}, choice, { description: "" });
      });
    }
    const component = field.component || {};
    const componentType = normalizeComponentType(component.type, field.fieldtype);
    const targetDoctype = linkTargetDoctype(field, component);
    const searchMethod = component.search_method || "";
    const listId = `wingman-ai-list-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const wrapper = document.createElement("div");
    wrapper.className = "wingman-ai-dropdown";
    wrapper.setAttribute("data-component", settings.multiple ? "multiselect" : "dropdown");

    const shell = document.createElement("div");
    shell.className = "wingman-ai-dropdown-shell";

    const input = document.createElement("input");
    input.className = "wingman-ai-dropdown-input";
    input.type = "text";
    input.autocomplete = "off";
    input.placeholder = field.placeholder || `Select ${field.label || "value"}`;
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-haspopup", "listbox");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", listId);

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "wingman-ai-dropdown-toggle";
    toggle.innerHTML = ICONS.chevron;
    toggle.setAttribute("aria-label", `Open ${field.label || "options"}`);
    toggle.setAttribute("aria-controls", listId);

    const menu = document.createElement("div");
    menu.className = "wingman-ai-dropdown-menu";

    const list = document.createElement("div");
    list.id = listId;
    list.className = "wingman-ai-dropdown-list";
    list.setAttribute("role", "listbox");
    if (settings.multiple) {
      list.setAttribute("aria-multiselectable", "true");
    }

    menu.appendChild(list);
    shell.append(input, toggle);
    wrapper.append(shell, menu);

    let isOpen = false;
    let focusedIndex = -1;
    let filteredChoices = normalizedChoices.slice();
    let selectedValues = [];
    let searchTimer = null;
    let remoteRequestId = 0;
    let remoteLoading = false;
    let lastRemoteTerm = null;

    const api = {
      close: closeDropdown,
      reposition: function () {
        updateDropdownPosition(wrapper, menu, list);
      }
    };

    Object.defineProperty(wrapper, "value", {
      get: function () {
        return readDropdownValue();
      },
      set: function (value) {
        setDropdownValue(value);
      }
    });

    Object.defineProperty(wrapper, "disabled", {
      get: function () {
        return Boolean(input.disabled);
      },
      set: function (value) {
        input.disabled = Boolean(value);
        toggle.disabled = Boolean(value);
        wrapper.classList.toggle("is-disabled", Boolean(value));
        if (value) {
          closeDropdown();
        }
      }
    });

    wrapper.focus = function () {
      input.focus();
    };
    wrapper._wingmanGetValue = readDropdownValue;
    wrapper._wingmanGetSelectedLabels = function () {
      return selectedValues.map(labelForDropdownValue);
    };

    input.addEventListener("focus", function () {
      if (!isOpen && (normalizedChoices.length || shouldSearchRemote())) {
        openDropdown("");
      }
    });

    input.addEventListener("input", function () {
      if (!settings.multiple && selectedValues.length && normalizeSearch(input.value) !== normalizeSearch(labelForDropdownValue(selectedValues[0]))) {
        selectedValues = [];
      }
      if (!isOpen) {
        openDropdown(input.value);
      } else {
        renderDropdownOptions(input.value);
      }
      queueRemoteDropdownSearch(input.value);
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (!isOpen) {
          openDropdown(input.value);
        }
        moveDropdownFocus(1);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        if (!isOpen) {
          openDropdown(input.value);
        }
        moveDropdownFocus(-1);
        return;
      }
      if (event.key === "Enter" && isOpen) {
        const choice = filteredChoices[focusedIndex];
        if (choice) {
          event.preventDefault();
          selectDropdownChoice(choice);
        }
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        closeDropdown();
        return;
      }
      if (event.key === "Tab") {
        closeDropdown();
      }
    });

    toggle.addEventListener("click", function (event) {
      event.preventDefault();
      if (isOpen) {
        closeDropdown();
      } else {
        openDropdown("");
      }
      input.focus();
    });

    list.addEventListener("wheel", function (event) {
      event.stopPropagation();
    }, { passive: true });

    function openDropdown(searchTerm) {
      if (input.disabled || (!normalizedChoices.length && !shouldSearchRemote())) {
        return;
      }
      closeActiveDropdown(api);
      isOpen = true;
      activeDropdown = api;
      wrapper.classList.add("is-open");
      input.setAttribute("aria-expanded", "true");
      if (settings.multiple) {
        input.value = "";
      }
      renderDropdownOptions(searchTerm !== undefined ? searchTerm : input.value);
      queueRemoteDropdownSearch(searchTerm !== undefined ? searchTerm : input.value);
      window.requestAnimationFrame(function () {
        updateDropdownPosition(wrapper, menu, list);
      });
    }

    function closeDropdown() {
      if (!isOpen) {
        return;
      }
      isOpen = false;
      if (activeDropdown === api) {
        activeDropdown = null;
      }
      wrapper.classList.remove("is-open", "is-upward");
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      focusedIndex = -1;
      updateDropdownDisplay();
    }

    function renderDropdownOptions(searchTerm) {
      const term = normalizeSearch(searchTerm);
      filteredChoices = normalizedChoices.filter(function (choice) {
        if (!term) {
          return true;
        }
        return normalizeSearch(`${choice.label} ${choice.value} ${choice.description}`).includes(term);
      });
      list.textContent = "";
      focusedIndex = filteredChoices.length ? Math.max(0, Math.min(focusedIndex, filteredChoices.length - 1)) : -1;

      if (!filteredChoices.length) {
        const empty = document.createElement("div");
        empty.className = "wingman-ai-dropdown-empty";
        renderDropdownEmpty(empty, searchTerm);
        list.appendChild(empty);
        input.removeAttribute("aria-activedescendant");
        updateDropdownPosition(wrapper, menu, list);
        return;
      }

      filteredChoices.forEach(function (choice, index) {
        const option = document.createElement("button");
        option.type = "button";
        option.id = `${listId}-option-${index}`;
        option.className = "wingman-ai-dropdown-option";
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", isDropdownChoiceSelected(choice) ? "true" : "false");
        if (choice.disabled) {
          option.disabled = true;
          option.setAttribute("aria-disabled", "true");
        }
        option.title = choice.description ? `${choice.label} - ${choice.description}` : choice.label;
        option.innerHTML = `
          <span class="wingman-ai-dropdown-option-text">
            <span class="wingman-ai-dropdown-option-label"></span>
            ${choice.description ? '<span class="wingman-ai-dropdown-option-description"></span>' : ""}
          </span>
          <span class="wingman-ai-dropdown-option-check" aria-hidden="true">&#10003;</span>
        `;
        option.querySelector(".wingman-ai-dropdown-option-label").textContent = choice.label;
        const description = option.querySelector(".wingman-ai-dropdown-option-description");
        if (description) {
          description.textContent = choice.description;
        }
        option.addEventListener("pointerdown", function (event) {
          event.preventDefault();
        });
        option.addEventListener("click", function () {
          selectDropdownChoice(choice);
        });
        option.addEventListener("mouseenter", function () {
          focusedIndex = index;
          updateDropdownFocus();
        });
        list.appendChild(option);
      });
      updateDropdownFocus();
      updateDropdownPosition(wrapper, menu, list);
    }

    function shouldSearchRemote() {
      return Boolean(searchMethod && targetDoctype && typeof callFrappeMethod === "function");
    }

    function queueRemoteDropdownSearch(searchTerm) {
      if (!shouldSearchRemote()) {
        return;
      }
      const term = String(searchTerm || "").trim();
      if (term === lastRemoteTerm && normalizedChoices.length) {
        return;
      }
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(function () {
        runRemoteDropdownSearch(term);
      }, 180);
    }

    function runRemoteDropdownSearch(searchTerm) {
      if (!shouldSearchRemote()) {
        return;
      }
      const requestId = remoteRequestId + 1;
      remoteRequestId = requestId;
      lastRemoteTerm = searchTerm;
      remoteLoading = true;
      if (isOpen) {
        renderDropdownOptions(input.value);
      }

      callFrappeMethod(searchMethod, {
        doctype: targetDoctype,
        text: searchTerm,
        fieldname: field.fieldname,
        page_size: 8
      }, {
        loadingMessage: `Loading ${targetDoctype || "Search"} Results...`
      }).then(function (payload) {
        if (requestId !== remoteRequestId) {
          return;
        }
        remoteLoading = false;
        const selectedChoices = normalizedChoices.filter(function (choice) {
          return selectedValues.includes(choice.value);
        });
        normalizedChoices = normalizeDropdownChoices((payload && payload.rows) || []);
        if (settings.hideDescriptions) {
          normalizedChoices = normalizedChoices.map(function (choice) {
            return Object.assign({}, choice, { description: "" });
          });
        }
        selectedChoices.forEach(function (choice) {
          if (!normalizedChoices.some(function (candidate) { return candidate.value === choice.value; })) {
            normalizedChoices.push(choice);
          }
        });
        if (isOpen) {
          renderDropdownOptions(input.value);
        }
      }).catch(function () {
        if (requestId !== remoteRequestId) {
          return;
        }
        remoteLoading = false;
        if (isOpen) {
          renderDropdownOptions(input.value);
        }
      });
    }

    function renderDropdownEmpty(empty, searchTerm) {
      if (remoteLoading) {
        empty.textContent = "Searching...";
        return;
      }
      const term = String(searchTerm || "").trim();
      if (settings.allowCustom && settings.allowCreate && shouldSearchRemote() && term) {
        const title = document.createElement("div");
        title.className = "wingman-ai-dropdown-empty-title";
        title.textContent = `No matching ${targetDoctype || "record"} was found.`;

        const question = document.createElement("div");
        question.className = "wingman-ai-dropdown-empty-detail";
        question.textContent = "What would you like to do?";

        const actions = document.createElement("div");
        actions.className = "wingman-ai-dropdown-empty-actions";
        actions.append(
          createDropdownEmptyAction(`Create ${targetDoctype || "Record"} "${term}"`, function () {
            useCustomLinkValue(term, true);
          }),
          createDropdownEmptyAction("Search Again", function () {
            input.focus();
            runRemoteDropdownSearch(term);
          }),
          createDropdownEmptyAction("Cancel", function () {
            selectedValues = [];
            input.value = "";
            closeDropdown();
            input.focus();
          })
        );

        empty.append(title, question, actions);
        return;
      }
      if (settings.allowCustom && term) {
        empty.textContent = "Press Continue to use this value.";
        return;
      }
      if (shouldSearchRemote()) {
        empty.textContent = `Start typing to search ${targetDoctype || "records"}.`;
        return;
      }
      if (componentType === "dynamic_link" && !targetDoctype) {
        empty.textContent = "Select the linked record type first.";
        return;
      }
      empty.textContent = "No options found.";
    }

    function createDropdownEmptyAction(label, onClick) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "wingman-ai-dropdown-empty-action";
      button.textContent = label;
      button.addEventListener("pointerdown", function (event) {
        event.preventDefault();
      });
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        onClick();
      });
      return button;
    }

    function useCustomLinkValue(value, submitForm) {
      selectedValues = [String(value || "").trim()];
      updateDropdownDisplay();
      closeDropdown();
      if (!submitForm) {
        input.focus();
        return;
      }
      const form = wrapper.closest("form");
      if (!form) {
        return;
      }
      window.setTimeout(function () {
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit();
          return;
        }
        form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      }, 0);
    }

    function moveDropdownFocus(delta) {
      if (!filteredChoices.length) {
        return;
      }
      focusedIndex = focusedIndex < 0 ? 0 : (focusedIndex + delta + filteredChoices.length) % filteredChoices.length;
      updateDropdownFocus();
    }

    function updateDropdownFocus() {
      Array.from(list.querySelectorAll(".wingman-ai-dropdown-option")).forEach(function (option, index) {
        option.classList.toggle("is-focused", index === focusedIndex);
        if (index === focusedIndex) {
          input.setAttribute("aria-activedescendant", option.id);
          option.scrollIntoView({ block: "nearest" });
        }
      });
    }

    function selectDropdownChoice(choice) {
      if (!choice || choice.disabled) {
        return;
      }
      if (settings.multiple) {
        if (selectedValues.includes(choice.value)) {
          selectedValues = selectedValues.filter(function (value) { return value !== choice.value; });
        } else {
          selectedValues.push(choice.value);
        }
        renderDropdownOptions("");
        input.value = "";
        input.focus();
        return;
      }
      selectedValues = [choice.value];
      closeDropdown();
    }

    function isDropdownChoiceSelected(choice) {
      return selectedValues.includes(choice.value);
    }

    function readDropdownValue() {
      if (settings.multiple) {
        return selectedValues.join(", ");
      }
      if (selectedValues.length) {
        return selectedValues[0];
      }
      if (settings.allowCustom) {
        return input.value;
      }
      const exact = normalizedChoices.find(function (choice) {
        return normalizeSearch(choice.label) === normalizeSearch(input.value) || normalizeSearch(choice.value) === normalizeSearch(input.value);
      });
      return exact ? exact.value : "";
    }

    function setDropdownValue(value) {
      const values = Array.isArray(value) ? value : String(value || "").split(",").map(function (item) { return item.trim(); }).filter(Boolean);
      selectedValues = values.filter(function (item) {
        return settings.allowCustom || normalizedChoices.some(function (choice) { return choice.value === item; });
      });
      updateDropdownDisplay();
    }

    function updateDropdownDisplay() {
      if (settings.multiple) {
        input.value = selectedValues.map(labelForDropdownValue).join(", ");
        return;
      }
      input.value = selectedValues.length ? labelForDropdownValue(selectedValues[0]) : "";
    }

    function labelForDropdownValue(value) {
      const match = normalizedChoices.find(function (choice) { return choice.value === value; });
      return match ? match.label : value;
    }

    updateDropdownDisplay();
    return wrapper;
  }

  function normalizeDropdownChoices(choices) {
    return (choices || []).map(function (choice) {
      const value = choice && choice.value !== undefined ? String(choice.value) : String(choice || "");
      const label = choice && choice.label !== undefined ? String(choice.label) : value;
      const description = choice && choice.description !== undefined ? String(choice.description) : "";
      return {
        label: label,
        value: value,
        description: description,
        disabled: Boolean(choice && choice.disabled)
      };
    }).filter(function (choice) {
      return choice.value || choice.label;
    });
  }

  function closeActiveDropdown(exceptApi) {
    if (activeDropdown && activeDropdown !== exceptApi && typeof activeDropdown.close === "function") {
      activeDropdown.close();
    }
  }

  function normalizeSearch(value) {
    return String(value || "").toLowerCase().replace(/\s+/g, " ").trim();
  }

  function updateDropdownPosition(wrapper, menu, list) {
    if (!wrapper || !menu || !list || !wrapper.classList.contains("is-open")) {
      return;
    }

    const panel = document.getElementById(IDS.panel);
    const wrapperRect = wrapper.getBoundingClientRect();
    const panelRect = panel ? panel.getBoundingClientRect() : {
      top: 0,
      right: window.innerWidth,
      bottom: window.innerHeight,
      left: 0
    };
    const topLimit = Math.max(8, panelRect.top + 8);
    const bottomLimit = Math.min(window.innerHeight - 8, panelRect.bottom - 8);
    const spaceBelow = Math.max(0, bottomLimit - wrapperRect.bottom - 8);
    const spaceAbove = Math.max(0, wrapperRect.top - topLimit - 8);
    const desiredHeight = Math.min(320, Math.max(144, DROPDOWN_MAX_VISIBLE_OPTIONS * 38));
    const openUpward = spaceBelow < Math.min(220, desiredHeight) && spaceAbove > spaceBelow;
    const availableHeight = openUpward ? spaceAbove : spaceBelow;
    const maxHeight = Math.max(112, Math.min(desiredHeight, availableHeight || desiredHeight));

    wrapper.classList.toggle("is-upward", openUpward);
    menu.style.maxHeight = `${maxHeight}px`;
    list.style.maxHeight = `${Math.max(96, maxHeight - 6)}px`;
  }

  function inputTypeForComponent(componentType) {
    if (["email", "tel", "number", "date", "datetime-local", "time", "file"].includes(componentType)) {
      return componentType;
    }
    return "text";
  }

  function readFieldControlValue(control, componentType) {
    if (control && typeof control._wingmanGetValue === "function") {
      return control._wingmanGetValue();
    }
    if (componentType === "checkbox") {
      return control.checked ? "Yes" : "No";
    }
    if (control.tagName === "SELECT" && control.multiple) {
      return Array.from(control.selectedOptions).map(function (option) { return option.value; }).join(", ");
    }
    if (componentType === "file" && control.files && control.files[0]) {
      return control.files[0].name;
    }
    return control.value;
  }

  function fieldHint(field, componentType, choices) {
    if (componentType === "select" && choices.length) {
      return "Choose one option.";
    }
    if (isLinkComponentType(componentType)) {
      return "Search existing records, choose a match, or create the missing record.";
    }
    if (componentType === "table") {
      return "Add one entry now; Wingman will ask for more if needed.";
    }
    return "";
  }

  function executeAutomaticActions(actions, row) {
    (actions || []).forEach(function (action) {
      if (action && action.auto_execute && action.requires_confirmation !== true) {
        window.requestAnimationFrame(function () {
          executeAction(action, row, { silent: action.wingman_direct_create !== true });
        });
      }
    });
  }

  function executeAction(action, row, options) {
    const actionOptions = options || {};
    if (!action || !action.type) {
      return false;
    }

    if (action.type === "navigate") {
      const target = action.target || {};
      const status = actionOptions.silent
        ? null
        : appendActionStatus(row, `Navigating to ${target.label || "page"}...`);
      const loading = NavigationLoadingService.start({ target: target });
      const navigated = navigateToTarget(target);
      if (!navigated && status) {
        status.textContent = "I could not navigate because the application router is not available on this page.";
      }
      if (!navigated) {
        loading.finish();
        return false;
      }
      return waitForNavigationSettled(target).then(function () {
        loading.finish();
        return true;
      });
    }

    if (action.type === "collect_student") {
      return startStudentOperation(action.payload || {});
    }

    if (action.type === "edit_details") {
      const payload = action.payload || {};
      const input = document.getElementById(IDS.input);
      if (input) {
        input.value = `Edit ${payload.doctype || "record"} details: `;
        input.focus();
      }
      appendActionStatus(row, "Tell me what to change, and I will refresh the review before anything is created.");
      return true;
    }

    if (action.type === "edit_review") {
      const payload = action.payload || {};
      const input = document.getElementById(IDS.input);
      if (input) {
        input.value = payload.message || "Change this workflow: ";
        input.focus();
      }
      appendActionStatus(row, "Tell me what to change in the workflow review.");
      return true;
    }

    if (action.type === "review_dependency") {
      if (action.resume_review) {
        pushReviewResume(action.resume_review);
      }
      const payload = action.payload || {};
      const messages = document.getElementById(IDS.messages);
      if (!messages || !payload.message) {
        appendActionStatus(row, "I could not open the dependency review.");
        return false;
      }
      const childRow = appendMessage(messages, "assistant", payload.message, null, payload);
      renderActions(childRow, payload.actions);
      executeAutomaticActions(payload.actions, childRow);
      return true;
    }

    if (action.type === "cancel_review") {
      const resumeReview = popReviewResume();
      if (resumeReview) {
        appendActionStatus(row, "Cancelled. Returning to the previous review.");
        return executeAction({ type: "resume_review", payload: resumeReview }, row, { silent: false });
      }
      const status = appendActionStatus(row, "Cancelled. No Talisma OneCampus data was changed.");
      return callWingmanBackend("cancel")
        .then(function (payload) {
          const reply = getReplyText(payload);
          if (/cancel/i.test(reply) || /No (?:Talisma OneCampus|Talisma (?:SIS|OneCampus)) data was changed/i.test(reply)) {
            status.textContent = reply;
          }
          return payload;
        })
        .catch(function () {
          return true;
        });
    }

    if (action.type === "resume_review") {
      return resumeReview(action.payload || action.resume_review, row);
    }

    if (action.type === "review_update_fields") {
      const payload = action.payload || {};
      const messages = document.getElementById(IDS.messages);
      if (!messages || !payload.message) {
        appendActionStatus(row, "I could not reopen the editable update review.");
        return false;
      }
      const childRow = appendMessage(messages, "assistant", payload.message, null, payload);
      renderActions(childRow, payload.actions);
      return true;
    }

    if (action.type === "send_message") {
      const message = String((action.payload || {}).message || action.message || "").trim();
      if (!message) {
        return false;
      }
      return sendWingmanMessage(message, { focusComposer: false });
    }

    if (action.method) {
      return executeServerAction(action, row, actionOptions);
    }

    appendActionStatus(row, "This action is not available in the current Wingman release.");
    return false;
  }

  function executeServerAction(action, row, options) {
    const actionOptions = options || {};
    const status = actionOptions.silent ? null : appendActionStatus(row, getActionProgressText(action));
    const buttonLoading = ButtonLoadingService.start(actionOptions.trigger, action);

    return callFrappeMethod(action.method, buildActionArgs(action), { suppressLoader: true })
      .then(function (payload) {
        buttonLoading.finish(payload);
        if (status) {
          status.textContent = getActionResultText(action, payload);
        }
        const resumeAction = payload && payload.success !== false
          ? (payload.resume_action || ((action.payload || {}).resume_action))
          : null;
        if (payload && payload.follow_up) {
          renderFollowUp(payload.follow_up, payload);
          if (resumeAction && shouldAutoResumeParent(action, payload)) {
            if (status) {
              status.textContent = `${getActionResultText(action, payload)} Continuing the original workflow...`;
            }
            return executeAction(resumeAction, row, { silent: false });
          }
          return payload;
        }
        if (resumeAction) {
          if (status) {
            status.textContent = `${getActionResultText(action, payload)} Continuing...`;
          }
          return executeAction(resumeAction, row, { silent: false });
        }
        const resumeReviewAction = payload && payload.success !== false
          ? (action.resume_review || ((action.payload || {}).resume_review) || popReviewResume())
          : null;
        if (resumeReviewAction) {
          if (status) {
            status.textContent = `${getActionResultText(action, payload)} Returning to the previous review...`;
          }
          return executeAction({ type: "resume_review", payload: resumeReviewAction }, row, { silent: false });
        }
        return payload;
      })
      .catch(function (error) {
        buttonLoading.finish(false);
        if (status) {
          status.textContent = getActionExecutionErrorMessage(error);
        }
        return false;
      });
  }

  function shouldAutoResumeParent(action, payload) {
    const actionPayload = action && action.payload ? action.payload : {};
    if (!actionPayload.auto_resume_parent) {
      return false;
    }
    const workflow = (payload && payload.follow_up && payload.follow_up.workflow) || {};
    const remainingSteps = Number(workflow.remaining_steps || 0);
    return !remainingSteps;
  }

  const ButtonLoadingService = {
    start: function (button, action) {
      const policy = LoadingPolicyEngine.classify({ action: action });
      if (!button || policy.type !== LOADING_TYPES.button) {
        return noopLoading(policy);
      }
      const originalText = button.textContent;
      button.dataset.wingmanOriginalText = originalText;
      button.classList.add("is-loading");
      button.setAttribute("aria-busy", "true");
      button.textContent = "";
      const spinner = document.createElement("span");
      spinner.className = "wingman-ai-button-spinner";
      spinner.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      label.textContent = shortLoadingLabel(policy.message);
      button.append(spinner, label);
      return {
        policy: policy,
        update: function () {},
        finish: function () {
          button.classList.remove("is-loading");
          button.setAttribute("aria-busy", "false");
          button.textContent = button.dataset.wingmanOriginalText || originalText;
          delete button.dataset.wingmanOriginalText;
        }
      };
    }
  };

  function shortLoadingLabel(message) {
    const text = String(message || "Working...").replace(/\.\.\.$/, "");
    if (/creating/i.test(text)) {
      return "Creating...";
    }
    if (/saving|updating/i.test(text)) {
      return "Saving...";
    }
    if (/deleting/i.test(text)) {
      return "Deleting...";
    }
    if (/checking|searching/i.test(text)) {
      return "Checking...";
    }
    return text.length > 22 ? "Working..." : `${text}...`.replace(/\.\.\.\.\.\.$/, "...");
  }

  function callFrappeMethod(method, args, options) {
    const callOptions = options || {};
    const loading = callOptions.suppressLoader
      ? null
      : NavigationLoadingService.start({
        method: method,
        args: args,
        message: callOptions.loadingMessage,
        loadingType: callOptions.loadingType
      });
    return new Promise(function (resolve, reject) {
      if (!window.frappe || typeof window.frappe.call !== "function") {
        reject(new Error("The application service is not available on this page."));
        return;
      }

      window.frappe.call({
        method: method,
        args: args || {},
        callback: function (response) {
          resolve(response && response.message ? response.message : response);
        },
        error: function (error) {
          reject(error);
        }
      });
    }).then(function (payload) {
      if (loading) {
        loading.finish();
      }
      return payload;
    }, function (error) {
      if (loading) {
        loading.finish();
      }
      throw error;
    });
  }

  function buildActionArgs(action) {
    const payload = action.payload || {};

    if (action.method === "wingman_ai.api.lead_management.create_lead") {
      return {
        data: JSON.stringify(payload.data || payload || {})
      };
    }

    const args = {};
    Object.keys(payload).forEach(function (key) {
      const value = payload[key];
      args[key] = value && typeof value === "object" ? JSON.stringify(value) : value;
    });
    return args;
  }

  function renderFollowUp(followUp, sourcePayload) {
    const messages = document.getElementById(IDS.messages);
    if (!messages || !followUp || !followUp.message) {
      return;
    }

    const row = appendMessage(messages, "assistant", followUp.message, null, followUp.intelligence ? followUp : sourcePayload);
    renderActions(row, followUp.actions);
    executeAutomaticActions(followUp.actions, row);
  }

  function getActionProgressText(action) {
    const method = String(action.method || "").toLowerCase();
    if (method.includes("exception_intelligence.retry_operation")) {
      return "Retrying Operation...";
    }
    if (method.includes("exception_intelligence.notify_administrator")) {
      return "Notifying Administrator...";
    }
    if (method.includes("exception_intelligence.save_draft")) {
      return "Saving Draft...";
    }
    if (method.includes("exception_intelligence.copy_diagnostic")) {
      return "Preparing Diagnostic...";
    }
    if (method.includes("exception_intelligence.view_technical_details")) {
      return "Loading Technical Details...";
    }
    if (method.includes("exception_intelligence.cancel_operation")) {
      return "Cancelling Operation...";
    }
    if (action.method === "wingman_ai.api.lead_management.create_lead") {
      return "Creating Lead...";
    }
    if (action.method === "wingman_ai.api.record_creation.continue_dependency_create") {
      const payload = action.payload || {};
      return `Checking ${payload.doctype || "Dependencies"}...`;
    }
    if (action.method === "wingman_ai.api.record_update.continue_update_field") {
      return "Updating Draft...";
    }
    if (action.type === "create") {
      return `Creating ${((action.payload || {}).doctype) || "Record"}...`;
    }
    if (action.type === "update") {
      const payload = action.payload || {};
      return `Saving ${payload.doctype || "Record"}...`;
    }
    if (action.type === "delete") {
      const payload = action.payload || {};
      return `Deleting ${payload.doctype || "Record"}...`;
    }
    if (action.type === "review_dependency") {
      return getDependencyLoadingText(action);
    }
    if (action.type === "resume_review") {
      return "Restoring Session...";
    }
    if (action.type === "send_message") {
      return getMessageLoadingText((action.payload || {}).message || action.message);
    }
    return "Running action...";
  }

  function getNavigationLoadingText(target) {
    const label = target && (target.label || target.doctype || target.docname || labelFromRoute(target.route));
    const kind = target && target.kind;
    if (kind === "report" || routeContains(target && target.route, "query-report")) {
      return `Loading ${label || "Report"}...`;
    }
    if (kind === "dashboard") {
      return `Loading ${label || "Dashboard"}...`;
    }
    if (kind === "document") {
      return `Opening ${label || "Document"}...`;
    }
    return `Opening ${label || "Page"}...`;
  }

  function getDependencyLoadingText(action) {
    const payload = (action || {}).payload || {};
    const firstAction = ((payload.actions || [])[0] || {}).payload || {};
    const doctype = (firstAction.doctype || payload.doctype || payload.target_doctype || "").trim();
    if (doctype) {
      return `Opening ${doctype} Workflow...`;
    }
    return "Checking Dependencies...";
  }

  function getMessageLoadingText(message) {
    const text = String(message || "").trim();
    const normalized = normalizeLoadingText(text);
    const doctype = extractDoctypeFromMessage(text);

    if (/^(open|go to|navigate|show|view)\b/.test(normalized)) {
      return `Opening ${extractObjectLabel(text) || doctype || "Page"}...`;
    }
    if (/^(create|new|add|make|register|draft)\b/.test(normalized)) {
      return `Preparing ${doctype || extractObjectLabel(text) || "Record"} Creation...`;
    }
    if (/^(update|change|edit|modify|set|assign|move|mark|close|disable|enable)\b/.test(normalized)) {
      return doctype ? `Loading ${doctype} Details...` : "Preparing Update...";
    }
    if (/\b(validate|check|verify)\b/.test(normalized)) {
      return "Validating with Talisma OneCampus...";
    }
    if (/\b(search|find|lookup)\b/.test(normalized)) {
      return "Loading Search Results...";
    }
    if (/\b(recommend|suggest|next action|insight)\b/.test(normalized)) {
      return "Generating Recommendations...";
    }
    if (/\b(report|dashboard|analytics)\b/.test(normalized)) {
      return "Loading Dashboard...";
    }
    if (/\b(summary|summarize|tell me about|explain|related)\b/.test(normalized)) {
      return "Loading Talisma OneCampus Data...";
    }
    if (/^(cancel|stop|never mind|nevermind)\b/.test(normalized)) {
      return "Completing Request...";
    }
    return "Completing Request...";
  }

  function getFrappeMethodLoadingText(method, args) {
    const methodName = String(method || "").toLowerCase();
    const payload = args || {};
    if (methodName.includes("record_creation") || methodName.includes("create")) {
      return `Creating ${payload.doctype || "Record"}...`;
    }
    if (methodName.includes("record_update") || methodName.includes("update")) {
      return `Saving ${payload.doctype || "Record"}...`;
    }
    if (methodName.includes("delete")) {
      return `Deleting ${payload.doctype || "Record"}...`;
    }
    if (methodName.includes("search") || methodName.includes("link")) {
      return "Loading Search Results...";
    }
    if (methodName.includes("metadata")) {
      return "Loading Talisma OneCampus Metadata...";
    }
    if (methodName.includes("chat.send")) {
      return getMessageLoadingText(payload.message);
    }
    return "Completing Request...";
  }

  function extractDoctypeFromMessage(message) {
    const known = [
      "Curriculum Version",
      "Program Enrollment",
      "Course Enrollment",
      "Student Attendance",
      "Assessment Result",
      "Student Application",
      "Academic Year",
      "Academic Term",
      "Class Section",
      "Student",
      "Program",
      "Course",
      "Degree",
      "Report",
      "Dashboard"
    ];
    const normalized = normalizeLoadingText(message);
    return known.find(function (doctype) {
      return normalizeLoadingText(doctype).split(" ").every(function (part) {
        return normalized.includes(part);
      });
    }) || "";
  }

  function extractObjectLabel(message) {
    const text = String(message || "").trim();
    const cleaned = text.replace(/^(open|go to|navigate to|navigate|show|view|create|new|add|make|register|draft|update|change|edit|modify|set)\s+/i, "");
    const value = cleaned.split(/\b(?:with|for|to|as|from|named|called)\b/i)[0];
    return value.trim().replace(/[.?!]+$/, "");
  }

  function labelFromRoute(route) {
    if (!Array.isArray(route)) {
      return "";
    }
    return route.filter(Boolean).slice(-1)[0] || route.filter(Boolean)[0] || "";
  }

  function routeContains(route, value) {
    return Array.isArray(route) && route.some(function (item) {
      return normalizeLoadingText(item).includes(normalizeLoadingText(value));
    });
  }

  function normalizeLoadingText(value) {
    return String(value || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
  }

  function getActionResultText(action, payload) {
    if (!payload) {
      return "Wingman did not receive an action result.";
    }

    if (payload.success === false) {
      return getActionFailureText(payload);
    }

    if (action.method === "wingman_ai.api.lead_management.create_lead") {
      const result = payload.result || {};
      const name = result.name || result.lead_name || "the new Lead";
      return `Created Lead ${name}.`;
    }

    if (action.type === "create") {
      const result = payload.result || {};
      const doctype = result.doctype || ((action.payload || {}).doctype) || "record";
      const name = result.name || "successfully";
      return `Created ${doctype} ${name}.`;
    }

    if (action.type === "delete") {
      return payload.message || "Record deleted successfully.";
    }

    return payload.message || "Action completed.";
  }

  function getActionFailureText(payload) {
    const issues = [].concat(payload.validation_issues || [], payload.errors || []);
    const firstIssue = issues.find(function (issue) {
      return issue && (issue.message || issue.fieldname);
    });
    const message = payload.message || "Talisma OneCampus did not complete the action.";
    if (!firstIssue) {
      return message;
    }
    return `${message} ${firstIssue.message || firstIssue.fieldname}`;
  }

  function getActionExecutionErrorMessage(error) {
    const rawText = extractErrorText(error);
    if (rawText.toLowerCase().includes("permission")) {
      return "Talisma OneCampus denied this action for your current role.";
    }
    return "Wingman could not complete this action. Please try again after refreshing Desk.";
  }

  function navigateToTarget(target) {
    if (!target || !target.route) {
      return false;
    }

    if (target.kind === "page" && target.route[0] === "desk") {
      window.location.assign("/desk");
      return true;
    }

    if (window.frappe && typeof window.frappe.set_route === "function") {
      window.frappe.set_route.apply(window.frappe, target.route);
      return true;
    }

    return false;
  }

  function waitForNavigationSettled(target) {
    return new Promise(function (resolve) {
      let settled = false;
      const finish = function () {
        if (settled) {
          return;
        }
        settled = true;
        resolve(true);
      };

      window.setTimeout(finish, 1400);
      if (window.frappe && typeof window.frappe.after_ajax === "function") {
        try {
          window.frappe.after_ajax(function () {
            window.setTimeout(finish, 120);
          });
        } catch (error) {
          window.setTimeout(finish, 360);
        }
      }

      window.setTimeout(function () {
        const route = window.frappe && typeof window.frappe.get_route === "function"
          ? window.frappe.get_route()
          : [];
        if (target && Array.isArray(target.route) && sameRoutePrefix(route, target.route)) {
          finish();
        }
      }, 320);
    });
  }

  function sameRoutePrefix(currentRoute, targetRoute) {
    if (!Array.isArray(currentRoute) || !Array.isArray(targetRoute)) {
      return false;
    }
    return targetRoute.every(function (part, index) {
      return sameRouteValue(currentRoute[index], part);
    });
  }

  function getDeskContext() {
    const route = window.frappe && typeof window.frappe.get_route === "function"
      ? window.frappe.get_route()
      : [];
    const normalizedRoute = Array.isArray(route) ? route : [];
    const formContext = getCurrentFormContext(normalizedRoute);
    const listContext = getCurrentListContext(normalizedRoute);

    return {
      route: normalizedRoute,
      conversation_id: getConversationId(),
      page_title: document.title || "",
      pathname: window.location.pathname,
      doctype: formContext.doctype || listContext.doctype || null,
      docname: formContext.docname || null,
      docstatus: formContext.docstatus,
      context_source: formContext.source || listContext.source || "route",
      form_doctype: formContext.form_doctype || null,
      form_docname: formContext.form_docname || null,
      user: window.frappe && window.frappe.session ? window.frappe.session.user : null
    };
  }

  function getCurrentFormContext(route) {
    if (!isFormRoute(route)) {
      return {};
    }

    const form = window.cur_frm;
    const routeDoctype = route[1] || null;
    const routeDocname = route[2] || null;
    if (!form || !form.doctype) {
      return {
        doctype: routeDoctype,
        docname: routeDocname,
        docstatus: null,
        source: "route"
      };
    }

    const doc = form.doc || {};
    const formDocname = form.docname || doc.name || null;
    const formMatchesRoute = sameRouteValue(routeDoctype, form.doctype) && sameRouteValue(routeDocname, formDocname);
    return {
      doctype: routeDoctype || form.doctype,
      docname: routeDocname || formDocname,
      docstatus: formMatchesRoute && typeof doc.docstatus === "number" ? doc.docstatus : null,
      source: formMatchesRoute ? "route_and_form" : "route",
      form_doctype: form.doctype,
      form_docname: formDocname
    };
  }

  function getCurrentListContext(route) {
    if (!isListRoute(route)) {
      return {};
    }

    const list = window.cur_list;
    if (!list || !list.doctype) {
      return {
        doctype: route[1] || null,
        source: "route"
      };
    }

    return {
      doctype: route[1] || list.doctype,
      source: sameRouteValue(route[1], list.doctype) ? "route_and_list" : "route"
    };
  }

  function isFormRoute(route) {
    return Array.isArray(route) && route[0] === "Form" && route.length >= 3;
  }

  function isListRoute(route) {
    return Array.isArray(route) && route[0] === "List" && route.length >= 2;
  }

  function sameRouteValue(left, right) {
    return decodeRouteValue(left) === decodeRouteValue(right);
  }

  function decodeRouteValue(value) {
    try {
      return decodeURIComponent(String(value || ""));
    } catch (error) {
      return String(value || "");
    }
  }

  function getConversationId() {
    try {
      return window.localStorage.getItem(CONVERSATION_KEY);
    } catch (error) {
      return null;
    }
  }

  function setConversationId(conversationId) {
    if (!conversationId) {
      return;
    }

    try {
      window.localStorage.setItem(CONVERSATION_KEY, conversationId);
    } catch (error) {
      // Conversation recovery is best effort only.
    }
  }

  function getReviewStack() {
    try {
      const raw = window.sessionStorage.getItem(REVIEW_STACK_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }

  function setReviewStack(stack) {
    try {
      window.sessionStorage.setItem(REVIEW_STACK_KEY, JSON.stringify(stack || []));
    } catch (error) {
      // Review stack recovery is best effort only.
    }
  }

  function pushReviewResume(resumeReview) {
    if (!resumeReview || !resumeReview.message) {
      return;
    }
    const stack = getReviewStack();
    stack.push(resumeReview);
    setReviewStack(stack);
  }

  function popReviewResume() {
    const stack = getReviewStack();
    const resumeReview = stack.pop() || null;
    setReviewStack(stack);
    return resumeReview;
  }

  function resumeReview(resumeData, row) {
    const message = resumeData && resumeData.message;
    if (!message) {
      appendActionStatus(row, "The previous review could not be refreshed.");
      return false;
    }

    const messages = document.getElementById(IDS.messages);
    if (!messages) {
      appendActionStatus(row, "The previous review could not be displayed.");
      return false;
    }

    const pending = appendMessage(messages, "assistant", "Refreshing review...", "is-pending");
    return callWingmanBackend(message, { loadingMessage: "Restoring Session..." })
      .then(function (payload) {
        pending.classList.remove("is-pending");
        updateMessage(pending, getReplyText(payload), payload);
        renderActions(pending, payload && payload.actions);
        executeAutomaticActions(payload && payload.actions, pending);
        return payload;
      })
      .catch(function (error) {
        pending.classList.remove("is-pending");
        updateMessage(pending, getBackendErrorMessage(error), null);
        return false;
      });
  }

  function callWingmanBackend(message, options) {
    const callOptions = options || {};
    const requestId = callOptions.requestId || createWingmanRequestId();
    const loading = callOptions.suppressLoader
      ? null
      : NavigationLoadingService.start({
        operation: callOptions.operation || "conversation",
        userMessage: message,
        message: callOptions.loadingMessage,
        loadingType: callOptions.loadingType
      });
    function attemptRequest(attemptNumber) {
      return new Promise(function (resolve, reject) {
      if (!window.frappe || typeof window.frappe.call !== "function") {
        reject(new Error("The application service is not available on this page."));
        return;
      }

      window.frappe.call({
        method: API_METHOD,
        args: {
          message: message,
          conversation_id: getConversationId(),
          context: JSON.stringify(getDeskContext()),
          request_id: requestId
        },
        callback: function (response) {
          const payload = response && response.message ? response.message : response;
          if (payload && payload.conversation_id) {
            setConversationId(payload.conversation_id);
          }
          resolve(payload);
        },
        error: function (error) {
          if (attemptNumber < 1) {
            window.setTimeout(function () {
              attemptRequest(attemptNumber + 1).then(resolve, reject);
            }, 650);
            return;
          }
          reject(error);
        }
      });
      });
    }

    return attemptRequest(0).then(function (payload) {
      if (loading) {
        loading.finish();
      }
      return payload;
    }, function (error) {
      if (loading) {
        loading.finish();
      }
      throw error;
    });
  }

  function createWingmanRequestId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return `wingman-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function getReplyText(payload) {
    if (!payload) {
      return "Wingman did not receive a response from the backend.";
    }

    if (payload.status === "error") {
      return payload.message || "Wingman backend returned an error.";
    }

    return payload.message || "Wingman backend is connected.";
  }

  async function sendWingmanMessage(text, options) {
    const sendOptions = options || {};
    const messages = document.getElementById(IDS.messages);
    const input = document.getElementById(IDS.input);
    if (!messages || !String(text || "").trim()) {
      return false;
    }

    if (sendOptions.showUserMessage !== false) {
      appendMessage(messages, "user", String(sendOptions.displayText || text).trim());
    }
    const pending = appendMessage(messages, "assistant", "Thinking...", "is-pending");
    let payload;
    try {
      payload = await callWingmanBackend(String(text).trim(), { loadingMessage: getMessageLoadingText(text) });
    } catch (error) {
      pending.classList.remove("is-pending");
      updateMessage(pending, getBackendErrorMessage(error), null);
      return false;
    }

    pending.classList.remove("is-pending");
    renderSuccessfulWingmanResponse(pending, payload);
    if (sendOptions.focusComposer !== false && input) {
      input.focus();
    }
    return payload;
  }

  function renderSuccessfulWingmanResponse(row, payload) {
    const bubble = getMessageBubble(row);
    if (!bubble) {
      return;
    }

    // Render the confirmed backend message first. Optional UI enhancements must
    // never turn an HTTP 200 response into a misleading connection failure.
    renderMessageContent(bubble, getReplyText(payload));
    try {
      attachIntelligenceButton(row, normalizeIntelligenceModel(payload, getReplyText(payload)));
    } catch (error) {
      window.console.error("Wingman intelligence rendering failed", error);
    }
    const actions = (payload && payload.actions) || [];
    const directCreate = actions.some(function (action) {
      return action && action.wingman_direct_create === true;
    });
    if (!directCreate) {
      try {
        renderActions(row, actions);
      } catch (error) {
        window.console.error("Wingman action rendering failed", error);
        renderFallbackActions(row, actions);
      }
    }
    try {
      executeAutomaticActions(actions, row);
    } catch (error) {
      window.console.error("Wingman automatic action failed", error);
    }
  }

  function renderFallbackActions(row, actions) {
    const bubble = getMessageBubble(row);
    if (!bubble) {
      return;
    }
    const container = document.createElement("div");
    container.className = "wingman-ai-action-list";
    (actions || []).filter(function (action) {
      return action && action.type && action.auto_execute !== true;
    }).forEach(function (action) {
      const field = ((action.payload || {}).field) || {};
      const component = field.component || {};
      const button = document.createElement("button");
      button.type = "button";
      button.className = "wingman-ai-action-button";
      button.textContent = action.label || "Continue";
      button.disabled = action.enabled === false;
      button.addEventListener("click", function () {
        if (action.type === "collect_field" && component.type === "curriculum_requirements") {
          appendActionStatus(row, "Add at least one Course to Curriculum Requirements before continuing.");
          return;
        }
        if (action.type === "collect_field") {
          const composer = document.getElementById(IDS.input);
          if (composer) {
            composer.placeholder = field.placeholder || `Enter ${field.label || "the required value"}`;
            composer.focus();
          }
          return;
        }
        button.disabled = true;
        const result = executeAction(action, row, { trigger: button });
        if (result === false) {
          button.disabled = false;
        }
      });
      container.appendChild(button);
    });
    if (container.childNodes.length) {
      bubble.appendChild(container);
    }
  }

  function buildShell() {
    if (document.getElementById(IDS.root)) {
      return;
    }

    const root = document.createElement("section");
    root.id = IDS.root;
    root.className = "wingman-ai";
    root.setAttribute("aria-label", "Talisma Wingman AI assistant");

    const panel = document.createElement("aside");
    panel.id = IDS.panel;
    panel.className = "wingman-ai-panel";
    panel.setAttribute("aria-label", "Talisma Wingman AI chat panel");
    panel.setAttribute("aria-hidden", "true");

    const header = document.createElement("div");
    header.className = "wingman-ai-header";

    const brand = document.createElement("div");
    brand.className = "wingman-ai-brand";
    brand.innerHTML = `
      <span class="wingman-ai-avatar">${ICONS.bot}</span>
      <span>
        <strong>Talisma Wingman AI</strong>
        <small>Talisma OneCampus Assistant</small>
      </span>
    `;

    const actions = document.createElement("div");
    actions.className = "wingman-ai-actions";

    const minimize = createButton("wingman-ai-icon-btn", "Minimize Wingman", ICONS.minimize, closePanel);
    const close = createButton("wingman-ai-icon-btn", "Close Wingman", ICONS.close, closePanel);
    actions.append(minimize, close);

    header.append(brand, actions);

    const body = document.createElement("div");
    body.className = "wingman-ai-body";

    const intro = document.createElement("div");
    intro.className = "wingman-ai-intro";
    intro.innerHTML = `
      <span class="wingman-ai-intro-icon">${ICONS.sparkles}</span>
      <strong>How can I help?</strong>
      <p>Complete student operations in Talisma OneCampus using natural language.</p>
    `;

    const quickPrompts = [
      { label: "Student 360", question: "Which student would you like me to review?", template: "Tell me about student {student}" },
      { label: "Enrollment", question: "Which student's enrollment should I show?", template: "Show enrollment for student {student}" },
      { label: "Courses & Grades", question: "Which student's courses and grades should I summarize?", template: "Summarize courses and grades for student {student}" },
      { label: "Account Balance", question: "Which student's account balance should I show?", template: "Show account balance for student {student}" },
      { label: "Applications", message: "Open student applications" },
      { label: "Attendance", message: "Open student attendance" }
    ];
    const quickGrid = document.createElement("div");
    quickGrid.className = "wingman-ai-quick-prompts";
    quickGrid.setAttribute("aria-label", "Common SIS operations");
    quickPrompts.forEach(function (item) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "wingman-ai-quick-prompt";
      button.textContent = item.label;
      button.title = item.question || item.message;
      button.addEventListener("click", function () {
        if (item.template) {
          startStudentOperation({
            question: item.question,
            message_template: item.template,
            placeholder: "Type student name…"
          });
          return;
        }
        sendWingmanMessage(item.message, { focusComposer: false });
      });
      quickGrid.appendChild(button);
    });
    intro.appendChild(quickGrid);

    const messages = document.createElement("div");
    messages.id = IDS.messages;
    messages.className = "wingman-ai-messages";
    messages.setAttribute("aria-live", "polite");
    messages.appendChild(intro);

    body.appendChild(messages);

    const composer = document.createElement("form");
    composer.className = "wingman-ai-composer";
    composer.setAttribute("aria-label", "Ask Talisma Wingman AI");

    const input = document.createElement("textarea");
    input.id = IDS.input;
    input.className = "wingman-ai-input";
    input.placeholder = "Ask Talisma Wingman AI...";
    input.rows = 1;

    const send = createButton("wingman-ai-send", "Send message", ICONS.send, function () {});
    send.id = IDS.send;
    send.type = "submit";

    composer.append(input, send);
    composer.addEventListener("submit", async function (event) {
      event.preventDefault();
      const text = input.value.trim();
      if (!text) {
        input.focus();
        return;
      }

      input.value = "";
      input.style.height = "";
      send.disabled = true;
      input.disabled = true;

      try {
        if (pendingStudentOperation) {
          const operation = pendingStudentOperation;
          pendingStudentOperation = null;
          input.placeholder = "Ask Talisma Wingman AI...";
          const request = String(operation.message_template || "Tell me about student {student}").replace("{student}", text);
          await sendWingmanMessage(request, { displayText: text });
        } else {
          await sendWingmanMessage(text);
        }
      } finally {
        send.disabled = false;
        input.disabled = false;
        input.focus();
      }
    });

    input.addEventListener("input", function () {
      input.style.height = "auto";
      input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        composer.requestSubmit();
      }
      if (event.key === "Escape") {
        closePanel();
      }
    });

    panel.append(header, body, composer);

    const launcher = createButton("wingman-ai-launcher", "Open Talisma Wingman AI", ICONS.bot, togglePanel);
    launcher.id = IDS.launcher;
    launcher.setAttribute("aria-controls", IDS.panel);
    launcher.setAttribute("aria-expanded", "false");

    const intelligencePanel = buildIntelligencePanel();

    root.append(panel, intelligencePanel, launcher);
    document.body.appendChild(root);

    document.addEventListener("pointerdown", function (event) {
      const target = event.target;
      if (target && target.closest && target.closest(".wingman-ai-dropdown")) {
        return;
      }
      closeActiveDropdown(null);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeActiveDropdown(null);
      }
    });

    window.addEventListener("resize", function () {
      if (activeDropdown && typeof activeDropdown.reposition === "function") {
        activeDropdown.reposition();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "w") {
        event.preventDefault();
        togglePanel();
      }
    });
  }

  function startStudentOperation(payload) {
    const messages = document.getElementById(IDS.messages);
    const input = document.getElementById(IDS.input);
    if (!messages || !input) {
      return false;
    }
    pendingStudentOperation = {
      message_template: payload.message_template || "Tell me about student {student}"
    };
    appendMessage(messages, "assistant", payload.question || "Which student should I use?");
    input.value = "";
    input.placeholder = payload.placeholder || "Type student name…";
    input.disabled = false;
    input.focus();
    return true;
  }

  function isOpen() {
    const panel = document.getElementById(IDS.panel);
    return panel && panel.classList.contains("is-open");
  }

  function openPanel() {
    const panel = document.getElementById(IDS.panel);
    const launcher = document.getElementById(IDS.launcher);
    const input = document.getElementById(IDS.input);
    if (!panel || !launcher) {
      return;
    }

    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
    launcher.setAttribute("aria-expanded", "true");
    window.setTimeout(function () {
      if (input) {
        input.focus();
      }
    }, 60);
  }

  function closePanel() {
    const panel = document.getElementById(IDS.panel);
    const launcher = document.getElementById(IDS.launcher);
    if (!panel || !launcher) {
      return;
    }

    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    launcher.setAttribute("aria-expanded", "false");
    if (!pinnedIntelligence) {
      closeIntelligencePanel();
    }
    launcher.focus();
  }

  function togglePanel() {
    if (isOpen()) {
      closePanel();
    } else {
      openPanel();
    }
  }

  function getBackendErrorMessage(error) {
    const rawText = extractErrorText(error);
    const normalized = rawText.toLowerCase();

    if (normalized.includes("timed out") || normalized.includes("timeout") || normalized.includes("request timed out")) {
      return [
        "Request Took Too Long",
        "Wingman could not complete the OneCampus request within the expected time.",
        "",
        "Current Status",
        "- Talisma OneCampus is still running.",
        "- Wingman stopped waiting so you can continue working.",
        "- No Talisma OneCampus data was changed.",
        "",
        "What You Can Do Next",
        "- Try the request again with a student, program, or record name.",
        "- Use a direct command such as \"open students\" or \"open Liam Patel\".",
        "- If this continues, contact your OneCampus administrator."
      ].join("\n");
    }

    if (normalized.includes("not permitted") || normalized.includes("permission")) {
      return [
        "Permission Check",
        "Talisma Wingman AI could not complete this request because Talisma OneCampus denied access.",
        "",
        "What You Can Do Next",
        "- Confirm you are logged in.",
        "- Check that your Talisma OneCampus role has permission for this action."
      ].join("\n");
    }

    return [
      "Request Temporarily Unavailable",
      "Talisma Wingman AI could not complete this request at the moment.",
      "",
      "Current Status",
      "- Your Curriculum Version draft is preserved.",
      "- No Talisma OneCampus data was changed.",
      "",
      "What You Can Do Next",
      "- Try the same response again.",
      "- If the problem continues, refresh Talisma OneCampus and reopen Wingman."
    ].join("\n");
  }

  function extractErrorText(error) {
    if (!error) {
      return "";
    }

    const parts = [];
    if (error.message) {
      parts.push(error.message);
    }
    if (error.statusText) {
      parts.push(error.statusText);
    }
    if (error.responseText) {
      parts.push(error.responseText);
    }
    if (error._server_messages) {
      parts.push(error._server_messages);
    }
    if (error.responseJSON) {
      parts.push(JSON.stringify(error.responseJSON));
    }
    return parts.join(" ");
  }

  ready(buildShell);
})();
