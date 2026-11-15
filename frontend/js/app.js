/**
 * ASV Inventory Training - Simplified Factory App
 * Scope: Form -> Slides (1-20) -> Test (10 questions) -> Result -> Admin
 */

const STATE = {
  token: localStorage.getItem('asv_simple_token') || '',
  logoTheme: localStorage.getItem('asv_logo_theme') || 'light', // 'light' (đen trên trắng) hoặc 'dark' (trắng trên đen)
  learner: null,
  progress: null,
  currentScreen: 'start', // 'start', 'slides', 'test', 'result', 'admin'
  
  // Slides State
  slides: [],
  currentSlideIndex: 0,
  zoomImageSrc: null,

  // Test State
  testAttemptId: null,
  testQuestions: [],
  currentQuestionIndex: 0,
  testAnswers: {}, // qid -> option_id
  testResult: null,

  // Admin State
  adminToken: localStorage.getItem('asv_simple_admin_token') || '',
  adminReport: [],
  adminFilter: 'ALL',
  adminFilterPos: 'ALL',
  adminSearch: '',
  sheetWebhookUrl: ''
};

// API Helper
async function api(path, method = 'GET', body = null, token = null) {
  const headers = { 'Content-Type': 'application/json' };
  const authToken = token || STATE.token;
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || 'Lỗi hệ thống');
  }
  return data;
}

// Initialization
async function init() {
  window.addEventListener('hashchange', handleRoute);
  
  // If hash is #admin, go to admin
  if (window.location.hash === '#admin') {
    STATE.currentScreen = 'admin';
    render();
    return;
  }

  // Check existing session
  if (STATE.token) {
    try {
      const data = await api('/api/simple/session');
      STATE.learner = data.learner;
      STATE.progress = data.progress;
      
      if (data.progress.has_passed) {
        // Already passed, show result or allow reviewing slides
        STATE.currentScreen = 'result';
        loadLatestResult();
      } else if (data.progress.is_completed_slides) {
        // Completed slides, ready for test
        STATE.currentScreen = 'test';
        loadTest();
      } else {
        // In progress of slides
        STATE.currentScreen = 'slides';
        loadSlides(data.progress.slides_viewed_count);
      }
    } catch (e) {
      STATE.token = '';
      localStorage.removeItem('asv_simple_token');
      STATE.currentScreen = 'start';
    }
  } else {
    STATE.currentScreen = 'start';
  }

  render();
}

function handleRoute() {
  if (window.location.hash === '#admin') {
    STATE.currentScreen = 'admin';
    render();
  } else if (STATE.currentScreen === 'admin') {
    STATE.currentScreen = STATE.learner ? 'slides' : 'start';
    render();
  }
}

// ---------------- MAIN RENDER ----------------
function render() {
  const root = document.getElementById('app-root');
  if (!root) return;

  let html = `
    <header class="simple-header">
      <div class="brand-title">
        <div class="ajax-brand-badge ${STATE.logoTheme === 'dark' ? 'theme-dark' : 'theme-light'}" 
             onclick="toggleLogoTheme()" 
             title="Bấm để đổi: Chữ đen trên nền trắng ↔ Chữ trắng trên nền đen">
          <img src="/images/ajax-logo-${STATE.logoTheme === 'dark' ? 'white' : 'black'}.png" alt="AJAX Systems" class="ajax-logo-img" />
        </div>
        <h1>Học kiểm kê Sản xuất</h1>
      </div>
      <div class="user-badge">
        ${STATE.learner ? `
          <span>👤 <strong>${STATE.learner.full_name}</strong> (${STATE.learner.employee_id}) · ${STATE.learner.position}</span>
          <button class="btn-action btn-outline-danger" style="min-height:44px; padding:6px 14px; font-size:16px;" onclick="changeLearner()">Đổi người học</button>
        ` : ''}
        ${STATE.currentScreen !== 'admin' ? `
          <a href="#admin" style="color:#ffffff; font-size:16px; margin-left:12px; text-decoration:underline;">Quản lý</a>
        ` : `
          <a href="#" style="color:#ffffff; font-size:16px; margin-left:12px; text-decoration:underline;">Về học viên</a>
        `}
      </div>
    </header>

    <main class="main-wrapper" id="content-area">
      <!-- Screen content dynamically loaded -->
    </main>

    ${STATE.zoomImageSrc ? `
      <div class="modal-overlay" onclick="closeZoomModal()">
        <div class="modal-header">
          <span style="font-size:20px; font-weight:700;">🔍 Phóng to hình ảnh</span>
          <button class="btn-action btn-danger" style="min-height:44px; padding:6px 18px;" onclick="closeZoomModal()">✕ ĐÓNG</button>
        </div>
        <div class="modal-body" onclick="event.stopPropagation()">
          <img src="${STATE.zoomImageSrc}" class="modal-image" alt="Hình phóng to" />
        </div>
      </div>
    ` : ''}
  `;

  root.innerHTML = html;
  renderCurrentScreen();
}

function renderCurrentScreen() {
  const container = document.getElementById('content-area');
  if (!container) return;

  switch (STATE.currentScreen) {
    case 'start':
      renderStartScreen(container);
      break;
    case 'slides':
      renderSlidesScreen(container);
      break;
    case 'test':
      renderTestScreen(container);
      break;
    case 'result':
      renderResultScreen(container);
      break;
    case 'admin':
      renderAdminScreen(container);
      break;
  }
}

// ---------------- SCREEN 1: BẮT ĐẦU ----------------
function renderStartScreen(container) {
  container.innerHTML = `
    <div class="box-card" style="max-width: 640px; margin: 20px auto;">
      <h2 style="font-size: 28px; margin-bottom: 8px; color: var(--accent-green);">Chào mừng bạn</h2>
      <p style="color: var(--text-muted); font-size: 20px; margin-bottom: 24px;">
        Vui lòng nhập thông tin để bắt đầu xem 20 trang học và làm bài kiểm tra quy trình kiểm kê.
      </p>

      <form id="form-start" onsubmit="handleStartSubmit(event)">
        <div class="form-group">
          <label class="form-label" for="input-emp-id">Mã nhân viên (bắt buộc):</label>
          <input type="text" id="input-emp-id" class="form-input" placeholder="Ví dụ: 0123 hoặc mã thẻ" required autofocus />
          <small style="color: var(--text-muted); font-size: 16px;">Giữ nguyên số 0 ở đầu nếu có.</small>
        </div>

        <div class="form-group">
          <label class="form-label" for="input-full-name">Họ và tên (bắt buộc):</label>
          <input type="text" id="input-full-name" class="form-input" placeholder="Ví dụ: Nguyễn Văn A" required />
        </div>

        <div class="form-group">
          <label class="form-label" for="select-position">Vị trí (bắt buộc):</label>
          <select id="select-position" class="form-select" onchange="toggleCustomPosition(this.value)" required>
            <option value="">-- Chọn vị trí --</option>
            <option value="Line leader">Line leader</option>
            <option value="Group leader">Group leader</option>
            <option value="Feeder">Feeder</option>
            <option value="Dispatcher">Dispatcher (Điều phối)</option>
            <option value="QD">QD (Quản lý chất lượng)</option>
            <option value="Workcell manager">Workcell manager</option>
            <option value="Khác">Khác (nhập vị trí)</option>
          </select>
        </div>

        <div class="form-group" id="group-custom-pos" style="display: none;">
          <label class="form-label" for="input-custom-pos">Nhập vị trí khác:</label>
          <input type="text" id="input-custom-pos" class="form-input" placeholder="Nhập tên vị trí của bạn" />
        </div>

        <button type="submit" class="btn-action btn-primary btn-full" style="margin-top: 10px;">
          BẮT ĐẦU HỌC →
        </button>
      </form>

      <div id="start-confirm-modal" style="display: none; margin-top: 20px;"></div>
    </div>
  `;
}

function toggleCustomPosition(val) {
  const el = document.getElementById('group-custom-pos');
  if (el) el.style.display = (val === 'Khác') ? 'block' : 'none';
}

async function handleStartSubmit(e) {
  e.preventDefault();
  const rawEmpId = document.getElementById('input-emp-id').value;
  const fullName = document.getElementById('input-full-name').value;
  const position = document.getElementById('select-position').value;
  const customPos = document.getElementById('input-custom-pos') ? document.getElementById('input-custom-pos').value : '';

  try {
    const res = await api('/api/simple/start', 'POST', {
      employee_id: rawEmpId,
      full_name: fullName,
      position: position,
      custom_position: customPos
    });

    if (res.exists) {
      // Existing user prompt: "Đúng là tôi"
      const modal = document.getElementById('start-confirm-modal');
      modal.style.display = 'block';
      modal.innerHTML = `
        <div style="background: #eef7f0; border: 2px solid var(--accent-green); padding: 20px; border-radius: 8px;">
          <h3 style="color: var(--accent-green); margin-bottom: 10px;">Đã tìm thấy thông tin của bạn!</h3>
          <p style="font-size: 20px; margin-bottom: 16px;">
            Mã <strong>${res.existing_learner.employee_id}</strong> đang ghi nhận tên: <strong>${res.existing_learner.full_name}</strong> (${res.existing_learner.position}).
          </p>
          <p style="font-size: 18px; color: var(--text-muted); margin-bottom: 20px;">
            Tiến độ hiện tại: đã học <strong>${res.progress.slides_viewed_count}/20 trang</strong> · Kết quả: <strong>${res.progress.status_text}</strong>.
          </p>
          <div style="display: flex; gap: 12px; flex-wrap: wrap;">
            <button class="btn-action btn-primary" style="flex: 1;" onclick="confirmExistingLearner('${res.existing_learner.employee_id}')">
              ĐÚNG LÀ TÔI · TIẾP TỤC HỌC
            </button>
            <button class="btn-action btn-secondary" onclick="updateExistingLearner('${res.existing_learner.employee_id}')">
              Cập nhật lại tên/vị trí mới
            </button>
          </div>
        </div>
      `;
      modal.scrollIntoView({ behavior: 'smooth' });
      return;
    }

    // New user
    STATE.token = res.token;
    STATE.learner = res.learner;
    STATE.progress = res.progress;
    localStorage.setItem('asv_simple_token', res.token);
    
    STATE.currentScreen = 'slides';
    loadSlides(0);
  } catch (err) {
    alert(err.message);
  }
}

async function confirmExistingLearner(empId) {
  try {
    const res = await api('/api/simple/start', 'POST', {
      employee_id: empId,
      full_name: 'CONFIRM',
      position: 'CONFIRM',
      confirm: true
    });
    STATE.token = res.token;
    STATE.learner = res.learner;
    STATE.progress = res.progress;
    localStorage.setItem('asv_simple_token', res.token);

    if (res.progress.has_passed) {
      STATE.currentScreen = 'result';
      loadLatestResult();
    } else if (res.progress.is_completed_slides) {
      STATE.currentScreen = 'test';
      loadTest();
    } else {
      STATE.currentScreen = 'slides';
      loadSlides(res.progress.slides_viewed_count);
    }
  } catch (err) {
    alert(err.message);
  }
}

async function updateExistingLearner(empId) {
  const fullName = document.getElementById('input-full-name').value;
  const position = document.getElementById('select-position').value;
  const customPos = document.getElementById('input-custom-pos') ? document.getElementById('input-custom-pos').value : '';

  try {
    const res = await api('/api/simple/start', 'POST', {
      employee_id: empId,
      full_name: fullName,
      position: position,
      custom_position: customPos,
      update_info: true
    });
    STATE.token = res.token;
    STATE.learner = res.learner;
    STATE.progress = res.progress;
    localStorage.setItem('asv_simple_token', res.token);

    STATE.currentScreen = 'slides';
    loadSlides(res.progress.slides_viewed_count);
  } catch (err) {
    alert(err.message);
  }
}

function changeLearner() {
  if (confirm('Bạn có chắc chắn muốn đổi người học trên thiết bị này?')) {
    STATE.token = '';
    STATE.learner = null;
    STATE.progress = null;
    localStorage.removeItem('asv_simple_token');
    STATE.currentScreen = 'start';
    render();
  }
}

// ---------------- SCREEN 2: HỌC BẰNG SLIDE ----------------
async function loadSlides(resumeIndex = 0) {
  try {
    const data = await api('/api/simple/slides');
    STATE.slides = data.slides || [];
    
    // Choose starting index
    if (resumeIndex > 0 && resumeIndex < STATE.slides.length) {
      STATE.currentSlideIndex = resumeIndex;
    } else if (resumeIndex >= STATE.slides.length) {
      STATE.currentSlideIndex = STATE.slides.length - 1;
    } else {
      STATE.currentSlideIndex = 0;
    }
    render();
  } catch (err) {
    alert(err.message);
  }
}

function renderSlidesScreen(container) {
  if (!STATE.slides || STATE.slides.length === 0) {
    container.innerHTML = '<div class="box-card"><p>Đang tải bài học slide...</p></div>';
    return;
  }

  const slide = STATE.slides[STATE.currentSlideIndex];
  const isLast = (STATE.currentSlideIndex === STATE.slides.length - 1);
  const isFirst = (STATE.currentSlideIndex === 0);

  let visualContent = '';
  if (slide.type === 'image') {
    visualContent = `
      <div class="slide-frame">
        <img src="/${slide.image}" class="slide-image" alt="${slide.title_vi}" id="current-slide-img" />
        <button class="btn-zoom" onclick="openZoomModal('/${slide.image}')">🔍 PHÓNG TO</button>
      </div>
    `;
  } else {
    // S20: Summary large text card
    visualContent = `
      <div style="background:#0c0f0d; color:#ffffff; padding:32px 24px; border-radius:10px; border:2px solid var(--accent-green);">
        <h3 style="font-size:28px; color:var(--accent-green); margin-bottom:18px;">${slide.title_vi}</h3>
        <ul style="font-size:22px; line-height:1.7; padding-left:24px;">
          ${(slide.bullets_vi || []).map(b => `<li style="margin-bottom:12px;">${b}</li>`).join('')}
        </ul>
      </div>
    `;
  }

  container.innerHTML = `
    <div class="box-card">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <span style="font-size:22px; font-weight:800; color:var(--accent-green);">
          Trang ${STATE.currentSlideIndex + 1}/20
        </span>
        <h2 style="font-size:24px;">${slide.title_vi}</h2>
      </div>

      ${visualContent}

      <div class="remember-card">
        <strong>💡 Cần nhớ:</strong> ${slide.remember_vi}
      </div>

      <div style="display:flex; justify-content:space-between; gap:16px; margin-top:24px; flex-wrap:wrap;">
        <button class="btn-action btn-secondary" style="flex:1;" ${isFirst ? 'disabled style="opacity:0.4;"' : ''} onclick="prevSlide()">
          ← QUAY LẠI
        </button>

        ${isLast ? `
          <button class="btn-action btn-primary" style="flex:2;" onclick="confirmSlideAndProceed(true)">
            LÀM BÀI KIỂM TRA →
          </button>
        ` : `
          <button class="btn-action btn-primary" style="flex:2;" onclick="confirmSlideAndProceed(false)">
            TÔI ĐÃ XEM · TRANG TIẾP →
          </button>
        `}
      </div>
    </div>
  `;
}

function openZoomModal(imgSrc) {
  STATE.zoomImageSrc = imgSrc;
  render();
}

function closeZoomModal() {
  STATE.zoomImageSrc = null;
  render();
}

function prevSlide() {
  if (STATE.currentSlideIndex > 0) {
    STATE.currentSlideIndex--;
    render();
  }
}

async function confirmSlideAndProceed(isFinal) {
  const slide = STATE.slides[STATE.currentSlideIndex];
  try {
    // Record view on server
    const res = await api('/api/simple/slides/view', 'POST', {
      slide_id: slide.id,
      slide_order: slide.order
    });
    STATE.progress = res.progress;

    if (isFinal) {
      // Completed all 20 slides -> jump to test
      STATE.currentScreen = 'test';
      loadTest();
    } else {
      STATE.currentSlideIndex++;
      render();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  } catch (err) {
    alert(err.message);
  }
}

// ---------------- SCREEN 3: BÀI KIỂM TRA ----------------
async function loadTest() {
  try {
    const data = await api('/api/simple/test');
    STATE.testAttemptId = data.attempt_id;
    STATE.testQuestions = data.questions || [];
    STATE.testAnswers = data.answers || {};
    STATE.currentQuestionIndex = 0;
    render();
  } catch (err) {
    alert(err.message);
    // If not completed slides, redirect back to slides
    if (err.message.includes('20 trang')) {
      STATE.currentScreen = 'slides';
      loadSlides(0);
    }
  }
}

function renderTestScreen(container) {
  if (!STATE.testQuestions || STATE.testQuestions.length === 0) {
    container.innerHTML = '<div class="box-card"><p>Đang chuẩn bị bài kiểm tra...</p></div>';
    return;
  }

  const q = STATE.testQuestions[STATE.currentQuestionIndex];
  const isFirst = (STATE.currentQuestionIndex === 0);
  const isLast = (STATE.currentQuestionIndex === STATE.testQuestions.length - 1);
  const selectedOptId = STATE.testAnswers[q.id] || null;
  const answeredCount = Object.keys(STATE.testAnswers).length;
  const allAnswered = (answeredCount >= STATE.testQuestions.length);

  container.innerHTML = `
    <div class="box-card">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;">
        <span style="font-size:22px; font-weight:800; color:var(--accent-green);">
          Câu ${STATE.currentQuestionIndex + 1}/10
        </span>
        <span style="font-size:18px; color:var(--text-muted);">
          Đã chọn: <strong>${answeredCount}/10</strong> câu
        </span>
      </div>

      <h2 style="font-size:24px; line-height:1.4; margin-bottom:24px;">
        ${q.question_vi}
      </h2>

      <div style="margin-bottom:24px;">
        ${q.options.map((opt, idx) => `
          <div class="option-card ${selectedOptId === opt.id ? 'selected' : ''}" onclick="selectAnswer('${q.id}', '${opt.id}')">
            <input type="radio" class="option-radio" name="opt_${q.id}" value="${opt.id}" ${selectedOptId === opt.id ? 'checked' : ''} />
            <span style="font-size:20px; font-weight:600;">${opt.text_vi}</span>
          </div>
        `).join('')}
      </div>

      <div style="display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap;">
        <button class="btn-action btn-secondary" style="flex:1;" ${isFirst ? 'disabled style="opacity:0.4;"' : ''} onclick="prevQuestion()">
          ← CÂU TRƯỚC
        </button>

        ${isLast || allAnswered ? `
          <button class="btn-action btn-primary" style="flex:2;" onclick="submitTest()">
            ✓ NỘP BÀI KIỂM TRA
          </button>
        ` : `
          <button class="btn-action btn-primary" style="flex:2;" onclick="nextQuestion()">
            CÂU TIẾP THEO →
          </button>
        `}
      </div>
    </div>
  `;
}

function selectAnswer(qid, optId) {
  STATE.testAnswers[qid] = optId;
  // Auto-save to server
  api('/api/simple/test/save', 'POST', {
    attempt_id: STATE.testAttemptId,
    answers: STATE.testAnswers
  }).catch(() => {});
  render();
}

function prevQuestion() {
  if (STATE.currentQuestionIndex > 0) {
    STATE.currentQuestionIndex--;
    render();
  }
}

function nextQuestion() {
  if (STATE.currentQuestionIndex + 1 < STATE.testQuestions.length) {
    STATE.currentQuestionIndex++;
    render();
  }
}

async function submitTest() {
  const answeredCount = Object.keys(STATE.testAnswers).length;
  if (answeredCount < 10) {
    alert(`Bạn mới chọn ${answeredCount}/10 câu. Vui lòng trả lời đầy đủ 10 câu trước khi nộp.`);
    return;
  }

  if (!confirm('Bạn có chắc chắn muốn nộp bài kiểm tra không?')) return;

  try {
    const res = await api('/api/simple/test/submit', 'POST', {
      attempt_id: STATE.testAttemptId,
      answers: STATE.testAnswers
    });
    STATE.testResult = res;
    STATE.currentScreen = 'result';
    render();
  } catch (err) {
    alert(err.message);
  }
}

// ---------------- SCREEN 4: KẾT QUẢ ----------------
async function loadLatestResult() {
  try {
    const data = await api('/api/simple/test/result');
    STATE.testResult = data;
    render();
  } catch (err) {
    // If no result yet, fallback to test
    STATE.currentScreen = 'test';
    loadTest();
  }
}

function renderResultScreen(container) {
  if (!STATE.testResult) {
    container.innerHTML = '<div class="box-card"><p>Đang tải kết quả...</p></div>';
    return;
  }

  const res = STATE.testResult;
  const isPass = res.passed;

  container.innerHTML = `
    <div class="box-card">
      ${isPass ? `
        <div class="result-banner-pass">
          <h2 style="font-size:32px; margin-bottom:8px;">✓ BẠN ĐÃ HOÀN THÀNH</h2>
          <p style="font-size:24px; font-weight:700;">
            Chúc mừng ${STATE.learner ? STATE.learner.full_name : ''}! Bạn đạt <strong>${res.score}/10 điểm</strong>.
          </p>
          <small style="font-size:16px;">Thời gian: ${res.submitted_at ? res.submitted_at.replace('T', ' ').substring(0,19) : ''}</small>
        </div>
        <p style="font-size:20px; line-height:1.6; margin-bottom:24px; color:var(--text-muted);">
          Bạn đã hoàn thành phần học lý thuyết và nắm vững quy trình kiểm kê Sản xuất.
        </p>
        <button class="btn-action btn-primary btn-full" onclick="reviewSlidesFromBeginning()">
          📖 XEM LẠI CÁC TRANG SLIDE (ÔN TẬP)
        </button>
      ` : `
        <div class="result-banner-fail">
          <h2 style="font-size:32px; margin-bottom:8px;">⚠ BẠN CẦN ÔN LẠI</h2>
          <p style="font-size:24px; font-weight:700;">
            Điểm của bạn: <strong>${res.score}/10 điểm</strong> (Ngưỡng đạt: 9/10).
          </p>
        </div>
        <p style="font-size:20px; line-height:1.6; margin-bottom:20px; color:var(--text-muted);">
          Dưới đây là các câu trả lời chưa đúng. Vui lòng xem kỹ giải thích và ôn lại các trang liên quan trước khi làm lại:
        </p>

        <!-- Wrong Answers List -->
        <div style="margin-bottom:28px;">
          ${(res.failed_questions || []).map((fq, idx) => `
            <div style="background:#fef7f7; border:2px solid #f5c2c7; border-radius:10px; padding:18px; margin-bottom:16px;">
              <h3 style="font-size:20px; color:#842029; margin-bottom:8px;">
                ${idx + 1}. ${fq.question_vi}
              </h3>
              <p style="font-size:18px; margin-bottom:6px;">
                ❌ Câu bạn chọn: <span style="color:var(--accent-red); font-weight:700;">${fq.your_answer}</span>
              </p>
              <p style="font-size:18px; margin-bottom:8px;">
                ✓ Đáp án đúng: <span style="color:var(--accent-green); font-weight:700;">${fq.correct_answer}</span>
              </p>
              <p style="font-size:18px; background:#ffffff; padding:10px 14px; border-radius:6px; border:1px solid #e0e0e0; color:#333;">
                💡 <strong>Giải thích:</strong> ${fq.explanation_vi}
              </p>
              ${fq.review_slide_ids && fq.review_slide_ids.length > 0 ? `
                <div style="margin-top:10px;">
                  <button class="btn-action btn-secondary" style="min-height:44px; padding:6px 16px; font-size:16px;" onclick="jumpToReviewSlide('${fq.review_slide_ids[0]}')">
                    🔍 Mở trang ${fq.review_slide_ids[0]} để ôn
                  </button>
                </div>
              ` : ''}
            </div>
          `).join('')}
        </div>

        <div style="display:flex; gap:16px; flex-wrap:wrap;">
          <button class="btn-action btn-secondary" style="flex:1;" onclick="reviewSlidesFromBeginning()">
            📖 XEM LẠI PHẦN CẦN ÔN
          </button>
          <button class="btn-action btn-primary" style="flex:1;" onclick="retakeTest()">
            🔄 LÀM LẠI BÀI KIỂM TRA
          </button>
        </div>
      `}
    </div>
  `;
}

function reviewSlidesFromBeginning() {
  STATE.currentScreen = 'slides';
  loadSlides(0);
}

function jumpToReviewSlide(slideId) {
  STATE.currentScreen = 'slides';
  const idx = STATE.slides.findIndex(s => s.id === slideId);
  loadSlides(idx >= 0 ? idx : 0);
}

function retakeTest() {
  STATE.testAttemptId = null;
  STATE.testAnswers = {};
  STATE.testResult = null;
  STATE.currentScreen = 'test';
  loadTest();
}

// ---------------- SCREEN 5: TRANG QUẢN LÝ (ADMIN) ----------------
function renderAdminScreen(container) {
  if (!STATE.adminToken) {
    container.innerHTML = `
      <div class="box-card" style="max-width:480px; margin:40px auto;">
        <h2 style="font-size:26px; margin-bottom:16px; color:var(--accent-green);">Đăng nhập Quản lý</h2>
        <form onsubmit="handleAdminLogin(event)">
          <div class="form-group">
            <label class="form-label">Tài khoản quản trị:</label>
            <input type="text" id="admin-user" class="form-input" placeholder="ADMIN01" required />
          </div>
          <div class="form-group">
            <label class="form-label">Mật khẩu:</label>
            <input type="password" id="admin-pass" class="form-input" placeholder="Nhập mật khẩu" required />
          </div>
          <button type="submit" class="btn-action btn-primary btn-full">Đăng nhập</button>
        </form>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-wrap:wrap; gap:12px;">
      <div>
        <h2 style="font-size:26px;">Báo cáo học viên kiểm kê Sản xuất</h2>
        <p style="color:var(--text-muted); font-size:18px;">Danh sách thực tế những người đã vào học</p>
      </div>
      <div style="display:flex; gap:12px; flex-wrap:wrap;">
        <button class="btn-action btn-primary" onclick="exportAdminCsv()">
          📥 TẢI BÁO CÁO EXCEL / CSV
        </button>
        <button class="btn-action btn-outline-danger" onclick="logoutAdmin()">
          Đăng xuất
        </button>
      </div>
    </div>

    <!-- Google Sheets Integration Box -->
    <div class="box-card" style="padding:20px; margin-bottom:20px; border-left: 8px solid var(--accent-green);">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:12px;">
        <h3 style="color:var(--accent-green); font-size:22px; margin:0;">
          📊 Tích hợp Google Sheets (Lưu dữ liệu vĩnh viễn không phụ thuộc máy chủ Render)
        </h3>
        <button class="btn-action btn-secondary" style="font-size:15px; min-height:38px; padding:4px 14px;" onclick="toggleSheetGuide()">
          📖 Hướng dẫn 3 bước cài đặt
        </button>
      </div>
      <p style="color:var(--text-muted); font-size:16px; margin-bottom:14px;">
        Dán đường link <strong>Google Apps Script Web App</strong> vào đây. Tiến độ học và điểm thi sẽ được tự động lưu thẳng vào file Google Sheet mỗi khi học viên nộp bài.
      </p>

      <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
        <input type="url" id="sheet-webhook-input" class="form-input" style="flex:1; min-width:300px; min-height:46px; font-size:16px;" placeholder="https://script.google.com/macros/s/.../exec" value="${STATE.sheetWebhookUrl || ''}" />
        <button class="btn-action btn-primary" style="min-height:46px; padding:6px 16px; font-size:16px;" onclick="saveSheetConfig()">
          💾 LƯU LINK
        </button>
        <button class="btn-action btn-secondary" style="background:#0b4f2a; border-color:#0b4f2a; color:#fff; min-height:46px; padding:6px 16px; font-size:16px;" onclick="syncAllToSheet()">
          🚀 ĐỒNG BỘ TOÀN BỘ SANG SHEET NGAY
        </button>
      </div>

      <div id="sheet-guide-box" style="display:none; margin-top:16px; background:#f5faf6; border:1px solid #c2e5cf; padding:16px 20px; border-radius:8px; font-size:16px;">
        <h4 style="color:#0b4f2a; margin-bottom:10px; font-size:18px;">3 Bước kết nối Google Sheet cực kỳ đơn giản (Mất 1 phút):</h4>
        <ol style="padding-left:22px; line-height:1.7; margin-bottom:14px;">
          <li>Mở một file <a href="https://sheets.new" target="_blank" style="color:var(--accent-green); font-weight:700; text-decoration:underline;">Google Sheets mới</a> (đặt tên ví dụ: <em>ASV_Kiem_Ke_2026</em>).</li>
          <li>Trên menu của Google Sheet, bấm <strong>Tiện ích mở rộng (Extensions)</strong> → <strong>Apps Script</strong>. Xóa hết code cũ, bấm nút <strong>"Sao chép mã Apps Script"</strong> bên dưới và Dán (Ctrl+V) vào. Bấm biểu tượng <strong>Lưu</strong> (Ctrl+S).</li>
          <li>Góc trên bên phải, bấm <strong>Triển khai (Deploy)</strong> → <strong>Tùy chọn triển khai mới (New deployment)</strong> → Chọn loại <strong>Ứng dụng web (Web app)</strong> → Mục <em>Ai có quyền truy cập (Who has access)</em> chọn <strong>Bất kỳ ai (Anyone)</strong> → Bấm <strong>Triển khai</strong>. Sau đó copy link có đuôi <code>/exec</code> dán vào ô bên trên và bấm <strong>LƯU LINK</strong>.</li>
        </ol>
        <button class="btn-action btn-secondary" style="font-size:15px; min-height:36px; padding:4px 14px;" onclick="copyAppsScriptCode()">
          📋 Sao chép mã Google Apps Script
        </button>
      </div>
    </div>

    <!-- Filter & Search Controls -->
    <div class="box-card" style="padding:16px 20px; margin-bottom:20px;">
      <div style="display:flex; gap:16px; flex-wrap:wrap; align-items:center;">
        <div style="flex:1; min-width:240px;">
          <input type="text" id="admin-search-input" class="form-input" style="min-height:48px;" placeholder="🔍 Tìm theo Mã NV, Họ tên hoặc Vị trí..." value="${STATE.adminSearch}" oninput="searchAdmin(this.value)" />
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          <label style="font-weight:700; font-size:18px;">Vị trí:</label>
          <select class="form-select" style="min-height:48px; width:auto;" onchange="filterAdminPos(this.value)">
            <option value="ALL" ${STATE.adminFilterPos === 'ALL' ? 'selected' : ''}>Tất cả vị trí</option>
            <option value="Line leader" ${STATE.adminFilterPos === 'Line leader' ? 'selected' : ''}>Line leader</option>
            <option value="Group leader" ${STATE.adminFilterPos === 'Group leader' ? 'selected' : ''}>Group leader</option>
            <option value="Feeder" ${STATE.adminFilterPos === 'Feeder' ? 'selected' : ''}>Feeder</option>
            <option value="Dispatcher" ${STATE.adminFilterPos === 'Dispatcher' ? 'selected' : ''}>Dispatcher</option>
            <option value="QD" ${STATE.adminFilterPos === 'QD' ? 'selected' : ''}>QD</option>
            <option value="Workcell manager" ${STATE.adminFilterPos === 'Workcell manager' ? 'selected' : ''}>Workcell manager</option>
          </select>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          <label style="font-weight:700; font-size:18px;">Lọc trạng thái:</label>
          <select class="form-select" style="min-height:48px; width:auto;" onchange="filterAdminStatus(this.value)">
            <option value="ALL" ${STATE.adminFilter === 'ALL' ? 'selected' : ''}>Tất cả</option>
            <option value="Đang học" ${STATE.adminFilter === 'Đang học' ? 'selected' : ''}>Đang học</option>
            <option value="Cần ôn/Chưa đạt" ${STATE.adminFilter === 'Cần ôn/Chưa đạt' ? 'selected' : ''}>Cần ôn/Chưa đạt</option>
            <option value="Đã hoàn thành" ${STATE.adminFilter === 'Đã hoàn thành' ? 'selected' : ''}>Đã hoàn thành</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Data Table Matching Mau_bao_cao.csv -->
    <div class="admin-table-wrapper">
      <table class="admin-table">
        <thead>
          <tr>
            <th>Mã nhân viên</th>
            <th>Họ tên</th>
            <th>Vị trí</th>
            <th>Bắt đầu</th>
            <th>Số trang đã học</th>
            <th>Đã học hết</th>
            <th>Số lần làm bài</th>
            <th>Điểm gần nhất</th>
            <th>Kết quả</th>
            <th>Hoàn tất</th>
          </tr>
        </thead>
        <tbody id="admin-table-body">
          <tr><td colspan="10" style="text-align:center; padding:30px;">Đang tải dữ liệu báo cáo...</td></tr>
        </tbody>
      </table>
    </div>
  `;

  loadAdminReport();
  loadSheetConfig();
}

async function handleAdminLogin(e) {
  e.preventDefault();
  const u = document.getElementById('admin-user').value.trim();
  const p = document.getElementById('admin-pass').value;

  try {
    const res = await api('/api/simple/admin/login', 'POST', { username: u, password: p });
    STATE.adminToken = res.token;
    localStorage.setItem('asv_simple_admin_token', res.token);
    render();
  } catch (err) {
    alert(err.message);
  }
}

function logoutAdmin() {
  STATE.adminToken = '';
  localStorage.removeItem('asv_simple_admin_token');
  render();
}

async function loadAdminReport() {
  try {
    const data = await api(`/api/simple/admin/report?status=${encodeURIComponent(STATE.adminFilter)}&position=${encodeURIComponent(STATE.adminFilterPos)}&q=${encodeURIComponent(STATE.adminSearch)}`, 'GET', null, STATE.adminToken);
    STATE.adminReport = data.learners || [];
    renderAdminTable();
  } catch (err) {
    const tbody = document.getElementById('admin-table-body');
    if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="color:var(--accent-red); padding:20px;">Lỗi: ${err.message}</td></tr>`;
  }
}

function renderAdminTable() {
  const tbody = document.getElementById('admin-table-body');
  if (!tbody) return;

  if (STATE.adminReport.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:30px; color:var(--text-muted);">Không có học viên nào phù hợp bộ lọc.</td></tr>';
    return;
  }

  tbody.innerHTML = STATE.adminReport.map(r => {
    let badgeClass = 'status-learning';
    if (r.result_status === 'Đã hoàn thành') badgeClass = 'status-completed';
    else if (r.result_status === 'Cần ôn/Chưa đạt') badgeClass = 'status-retest';

    return `
      <tr>
        <td><code>${r.employee_id}</code></td>
        <td><strong>${r.full_name}</strong></td>
        <td>${r.position}</td>
        <td style="font-size:15px; color:var(--text-muted);">${r.started_at ? r.started_at.substring(0,16).replace('T', ' ') : '—'}</td>
        <td style="font-weight:700;">${r.slides_viewed_count}</td>
        <td>${r.is_completed_slides === 'Có' ? '<span style="color:var(--accent-green); font-weight:700;">✓ Có</span>' : 'Chưa'}</td>
        <td>${r.attempts_count}</td>
        <td style="font-weight:700;">${r.latest_score}</td>
        <td><span class="badge-status ${badgeClass}">${r.result_status}</span></td>
        <td style="font-size:15px; color:var(--text-muted);">${r.completed_at ? r.completed_at.substring(0,16).replace('T', ' ') : '—'}</td>
      </tr>
    `;
  }).join('');
}

let searchDebounce = null;
function searchAdmin(val) {
  STATE.adminSearch = val;
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(loadAdminReport, 300);
}

function filterAdminStatus(val) {
  STATE.adminFilter = val;
  loadAdminReport();
  loadSheetConfig();
}

function filterAdminPos(val) {
  STATE.adminFilterPos = val;
  loadAdminReport();
  loadSheetConfig();
}

function toggleLogoTheme() {
  STATE.logoTheme = (STATE.logoTheme === 'dark') ? 'light' : 'dark';
  localStorage.setItem('asv_logo_theme', STATE.logoTheme);
  render();
}

function exportAdminCsv() {
  window.location.href = `/api/simple/admin/export-csv?auth=${STATE.adminToken}`;
}

// Google Sheets Integration Helpers
async function loadSheetConfig() {
  try {
    const data = await api('/api/simple/admin/sheet-config', 'GET', null, STATE.adminToken);
    STATE.sheetWebhookUrl = data.webhook_url || '';
    const input = document.getElementById('sheet-webhook-input');
    if (input) input.value = STATE.sheetWebhookUrl;
  } catch (e) {
    console.error('loadSheetConfig error:', e);
  }
}

async function saveSheetConfig() {
  const input = document.getElementById('sheet-webhook-input');
  const url = input ? input.value.trim() : '';
  if (url && !url.startsWith('https://script.google.com/')) {
    alert('Đường dẫn phải bắt đầu bằng: https://script.google.com/macros/s/.../exec');
    return;
  }

  try {
    const res = await api('/api/simple/admin/sheet-config', 'POST', { webhook_url: url }, STATE.adminToken);
    STATE.sheetWebhookUrl = res.webhook_url;
    alert('✅ Đã lưu cấu hình Google Sheet Webhook thành công!');
  } catch (err) {
    alert('❌ Lỗi lưu cấu hình: ' + err.message);
  }
}

async function syncAllToSheet() {
  const input = document.getElementById('sheet-webhook-input');
  const url = input ? input.value.trim() : (STATE.sheetWebhookUrl || '');
  if (!url) {
    alert('Vui lòng nhập đường dẫn Google Sheet Webhook trước khi đồng bộ.');
    return;
  }

  if (!confirm('Bắt đầu đồng bộ toàn bộ danh sách học viên hiện có sang Google Sheet?')) return;

  try {
    const res = await api('/api/simple/admin/sync-sheet', 'POST', { webhook_url: url }, STATE.adminToken);
    alert('🎉 ' + res.message);
  } catch (err) {
    alert('❌ Lỗi đồng bộ: ' + err.message);
  }
}

function toggleSheetGuide() {
  const box = document.getElementById('sheet-guide-box');
  if (box) box.style.display = (box.style.display === 'none') ? 'block' : 'none';
}

function copyAppsScriptCode() {
  const code = `function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var summarySheet = ss.getSheetByName("Ket_Qua_Tong_Hop");
    if (!summarySheet) {
      summarySheet = ss.insertSheet("Ket_Qua_Tong_Hop");
      summarySheet.appendRow(["Mã nhân viên", "Họ và tên", "Vị trí", "Bắt đầu lúc", "Số trang đã học", "Đã học hết", "Số lần làm bài", "Điểm gần nhất", "Kết quả", "Hoàn tất lúc", "Lần cập nhật cuối"]);
      summarySheet.getRange(1, 1, 1, 11).setFontWeight("bold").setBackground("#0b4f2a").setFontColor("#ffffff");
      summarySheet.setFrozenRows(1);
    }
    var logSheet = ss.getSheetByName("Nhat_Ky_Chi_Tiet");
    if (!logSheet) {
      logSheet = ss.insertSheet("Nhat_Ky_Chi_Tiet");
      logSheet.appendRow(["Thời gian ghi nhận", "Mã nhân viên", "Họ và tên", "Vị trí", "Lần thi số", "Điểm số /10", "Kết quả", "Chi tiết câu trả lời"]);
      logSheet.getRange(1, 1, 1, 8).setFontWeight("bold").setBackground("#111111").setFontColor("#ffffff");
      logSheet.setFrozenRows(1);
    }
    var rawContents = "";
    if (e && e.postData && e.postData.contents) {
      rawContents = e.postData.contents;
    } else if (e && e.parameter && e.parameter.data) {
      rawContents = e.parameter.data;
    }
    var data = null;
    if (rawContents) {
      try { data = JSON.parse(rawContents); } catch (errParse) { data = null; }
    } else if (e && e.parameter && e.parameter.employee_id) {
      data = [e.parameter];
    }
    if (!data) {
      return ContentService.createTextOutput(JSON.stringify({ "status": "error", "message": "Không nhận được dữ liệu hợp lệ." })).setMimeType(ContentService.MimeType.JSON);
    }
    var records = Array.isArray(data) ? data : [data];
    var nowStr = Utilities.formatDate(new Date(), "Asia/Ho_Chi_Minh", "yyyy-MM-dd HH:mm:ss");
    var summaryData = summarySheet.getDataRange().getValues();
    var idRowMap = {};
    for (var r = 1; r < summaryData.length; r++) {
      var rawId = String(summaryData[r][0]).replace(/^'/, '').trim();
      if (rawId) idRowMap[rawId] = r + 1;
    }
    for (var i = 0; i < records.length; i++) {
      var item = records[i];
      var cleanEmpId = String(item.employee_id || "").trim();
      var empIdFormatted = "'" + cleanEmpId;
      var rowValues = [
        empIdFormatted, item.full_name || "", item.position || "", 
        item.started_at ? String(item.started_at).substring(0,19).replace('T', ' ') : "",
        item.slides_viewed_count || "", item.is_completed_slides || "", 
        item.attempts_count !== undefined ? item.attempts_count : 0,
        item.latest_score !== undefined ? String(item.latest_score) : "—",
        item.result_status || "", item.completed_at ? String(item.completed_at).substring(0,19).replace('T', ' ') : "—", 
        nowStr
      ];
      var existingRow = idRowMap[cleanEmpId];
      if (existingRow) {
        summarySheet.getRange(existingRow, 1, 1, 11).setValues([rowValues]);
      } else {
        summarySheet.appendRow(rowValues);
        idRowMap[cleanEmpId] = summarySheet.getLastRow();
      }
      if (item.is_test_submit) {
        logSheet.appendRow([nowStr, empIdFormatted, item.full_name || "", item.position || "", item.attempts_count, item.latest_score, item.result_status, JSON.stringify(item.answers || {})]);
      }
    }
    return ContentService.createTextOutput(JSON.stringify({ "status": "success", "synced": records.length })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ "status": "error", "message": err.toString() })).setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}
function doGet(e) {
  if (e && e.parameter && (e.parameter.data || e.parameter.employee_id)) {
    return doPost(e);
  }
  return ContentService.createTextOutput("Ajax Systems Vietnam Webhook OK");
}`;

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(code).then(() => {
      alert('📋 Đã sao chép mã Google Apps Script vào bộ nhớ tạm! Bạn chỉ việc dán (Ctrl+V) vào Apps Script của Google Sheet.');
    }).catch(() => {
      alert('Vui lòng mở file google_apps_script.js trong thư mục dự án để sao chép mã.');
    });
  } else {
    alert('Vui lòng mở file google_apps_script.js trong thư mục dự án để sao chép mã.');
  }
}

// Start on DOM ready
window.addEventListener('DOMContentLoaded', init);
