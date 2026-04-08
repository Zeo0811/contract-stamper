(function () {
    'use strict';

    // ── State ──
    let fileId = null;
    let stampId = null;
    let pdfDoc = null;
    let totalPages = 0;
    let detectedPosition = null;
    let isExcelUpload = false;
    let manualPosition = null;
    let resultTaskId = null;
    let previewUrls = [];
    let isWordUpload = false;
    let isCompleted = false;
    let history = JSON.parse(localStorage.getItem('stampHistory') || '[]');

    // ── Elements: Welcome ──
    const welcomeScreen = document.getElementById('welcomeScreen');
    const welcomeUploadZone = document.getElementById('welcomeUploadZone');
    const welcomeStatusText = document.getElementById('welcomeStatusText');

    // ── Elements: Workspace ──
    const workspace = document.getElementById('workspace');
    const pdfInput = document.getElementById('pdfInput');
    const pdfFileName = document.getElementById('pdfFileName');
    const pdfClear = document.getElementById('pdfClear');

    const stampGrid = document.getElementById('stampGrid');

    const stampSize = document.getElementById('stampSize');
    const stampSizeVal = document.getElementById('stampSizeVal');
    const seamToggle = document.getElementById('seamToggle');
    const seamPosition = document.getElementById('seamPosition');
    const agingSlider = document.getElementById('agingSlider');
    const agingVal = document.getElementById('agingVal');
    const scanSlider = document.getElementById('scanSlider');
    const scanVal = document.getElementById('scanVal');

    const processBtn = document.getElementById('processBtn');
    const processBtnText = document.getElementById('processBtnText');
    const btnProgress = document.getElementById('btnProgress');
    const newTaskBtn = document.getElementById('newTaskBtn');
    const statusBar = document.getElementById('statusBar');
    const statusText = document.getElementById('statusText');

    const previewScroll = document.getElementById('previewScroll');
    const pagesContainer = document.getElementById('pagesContainer');
    const previewTitle = document.getElementById('previewTitle');
    const pageCount = document.getElementById('pageCount');
    const stampMarker = document.getElementById('stampMarker');

    // ── API helper ──
    async function api(method, path, body, isFormData) {
        const opts = { method, headers: {} };
        const token = localStorage.getItem('token');
        if (token) {
            opts.headers['Authorization'] = 'Bearer ' + token;
        }
        if (isFormData) {
            opts.body = body;
        } else if (body) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        }
        return await fetch(path, opts);
    }

    // ══════════════════════════════════════
    // WELCOME / WORKSPACE TRANSITIONS
    // ══════════════════════════════════════
    function showWorkspace() {
        welcomeScreen.classList.add('leaving');
        setTimeout(() => {
            welcomeScreen.style.display = 'none';
            workspace.classList.add('visible');
        }, 400);
    }

    function showWelcome() {
        workspace.classList.remove('visible');
        welcomeScreen.style.display = '';
        welcomeScreen.classList.remove('leaving');
    }

    // ── Upload zone setup ──
    function setupUploadZone(zone, input, onFile) {
        zone.addEventListener('click', (e) => {
            if (e.target.closest('button') || e.target.closest('a')) return;
            input.click();
        });
        zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
        zone.addEventListener('drop', e => {
            e.preventDefault();
            zone.classList.remove('dragover');
            if (e.dataTransfer.files.length) onFile(e.dataTransfer.files[0]);
        });
        input.addEventListener('change', () => {
            if (input.files.length) onFile(input.files[0]);
        });
    }

    let lastFileName = '';

    async function uploadPdf(file) {
        const ext = file.name.split('.').pop().toLowerCase();
        isWordUpload = (ext === 'docx' || ext === 'doc');
        isExcelUpload = (ext === 'xlsx' || ext === 'xls');
        lastFileName = file.name;

        // Show uploading state on welcome screen
        welcomeUploadZone.classList.add('uploading');
        const statusMsg = isExcelUpload ? '上传并转换 Excel 中...' : isWordUpload ? '上传并转换 Word 中...' : '上传合同中...';
        welcomeStatusText.textContent = statusMsg;

        const fd = new FormData();
        fd.append('file', file);
        const resp = await api('POST', '/api/v1/upload', fd, true);
        if (!resp.ok) {
            welcomeUploadZone.classList.remove('uploading');
            showStatus('error', '上传失败');
            return;
        }
        const data = await resp.json();
        fileId = data.file_id;
        totalPages = data.page_count;
        previewUrls = data.previews || [];
        pdfFileName.textContent = file.name;

        // Transition to workspace
        showWorkspace();

        // Render preview after a small delay to let workspace appear
        setTimeout(async () => {
            if (isWordUpload || isExcelUpload) {
                pdfDoc = null;
                await renderAllPagesFromServer();
            } else {
                const pdfData = await file.arrayBuffer();
                pdfDoc = await pdfjsLib.getDocument({ data: pdfData }).promise;
                totalPages = pdfDoc.numPages;
                await renderAllPages();
            }

            if (isExcelUpload) {
                // Excel: no auto-detection, user places stamp manually
                seamToggle.checked = false;
                seamToggle.dispatchEvent(new Event('change'));
                previewWarning.classList.add('visible');
            } else {
                await detectKeywords();
            }
            checkReady();
        }, 500);
    }

    // Set up the welcome upload zone
    setupUploadZone(welcomeUploadZone, pdfInput, uploadPdf);

    // ── Multi-page rendering ──
    async function renderAllPages() {
        pagesContainer.innerHTML = '';
        pageCount.textContent = `${totalPages} 页`;
        previewTitle.textContent = '合同预览';

        for (let i = 0; i < totalPages; i++) {
            const page = await pdfDoc.getPage(i + 1);
            const maxW = previewScroll.clientWidth - 48;
            const scale = Math.min(maxW / page.getViewport({ scale: 1 }).width, 2);
            const viewport = page.getViewport({ scale });

            const wrapper = document.createElement('div');
            wrapper.className = 'page-wrapper';
            wrapper.dataset.pageNum = i;

            const label = document.createElement('div');
            label.className = 'page-label';
            label.textContent = `第 ${i + 1} 页`;

            const canvas = document.createElement('canvas');
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            canvas.dataset.pageNum = i;

            const ctx = canvas.getContext('2d');
            await page.render({ canvasContext: ctx, viewport }).promise;

            wrapper.appendChild(label);
            wrapper.appendChild(canvas);
            pagesContainer.appendChild(wrapper);
        }

        enableCanvasClicks();
    }

    function renderAllPagesFromServer() {
        pagesContainer.innerHTML = '';
        pageCount.textContent = `${totalPages} 页`;
        previewTitle.textContent = '合同预览';

        const loadPromises = [];
        for (let i = 0; i < previewUrls.length; i++) {
            const wrapper = document.createElement('div');
            wrapper.className = 'page-wrapper';
            wrapper.dataset.pageNum = i;

            const label = document.createElement('div');
            label.className = 'page-label';
            label.textContent = `第 ${i + 1} 页`;

            const canvas = document.createElement('canvas');
            canvas.dataset.pageNum = i;

            const p = new Promise(resolve => {
                const img = new window.Image();
                img.onload = function () {
                    const maxW = previewScroll.clientWidth - 48;
                    const scale = Math.min(maxW / img.width, 2);
                    canvas.width = img.width * scale;
                    canvas.height = img.height * scale;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    resolve();
                };
                img.onerror = resolve;
                img.src = previewUrls[i];
            });
            loadPromises.push(p);

            wrapper.appendChild(label);
            wrapper.appendChild(canvas);
            pagesContainer.appendChild(wrapper);
        }

        enableCanvasClicks();
        return Promise.all(loadPromises);
    }

    // ── Result preview ──
    async function previewResultPdf(taskId) {
        try {
            const resp = await api('GET', `/api/v1/download/${taskId}`);
            if (!resp.ok) return;
            const data = await resp.arrayBuffer();
            pdfDoc = await pdfjsLib.getDocument({ data }).promise;
            isWordUpload = false;
            totalPages = pdfDoc.numPages;
            previewTitle.textContent = '处理结果预览';
            stampMarker.hidden = true;

            pagesContainer.innerHTML = '';
            pageCount.textContent = `${totalPages} 页`;

            for (let i = 0; i < totalPages; i++) {
                const page = await pdfDoc.getPage(i + 1);
                const maxW = previewScroll.clientWidth - 48;
                const scale = Math.min(maxW / page.getViewport({ scale: 1 }).width, 2);
                const viewport = page.getViewport({ scale });

                const wrapper = document.createElement('div');
                wrapper.className = 'page-wrapper';

                const label = document.createElement('div');
                label.className = 'page-label';
                label.textContent = `第 ${i + 1} 页`;

                const canvas = document.createElement('canvas');
                canvas.width = viewport.width;
                canvas.height = viewport.height;

                const ctx = canvas.getContext('2d');
                await page.render({ canvasContext: ctx, viewport }).promise;

                wrapper.appendChild(label);
                wrapper.appendChild(canvas);
                pagesContainer.appendChild(wrapper);
            }

            previewScroll.scrollTop = 0;
        } catch (e) {
            console.error('Result preview failed:', e);
        }
    }

    // ── Clear / Reset ──
    pdfClear.addEventListener('click', e => {
        e.stopPropagation();
        resetContractState();
    });

    function resetContractState() {
        fileId = null; pdfDoc = null; detectedPosition = null; manualPosition = null;
        isWordUpload = false; isExcelUpload = false; previewUrls = []; resultTaskId = null; isCompleted = false;
        pagesContainer.innerHTML = '';
        pageCount.textContent = '';
        previewTitle.textContent = '合同预览';
        stampMarker.hidden = true;
        newTaskBtn.hidden = true;
        btnProgress.style.width = '0';
        processBtn.classList.remove('download');
        processBtnText.textContent = '开始处理';
        document.getElementById('processBtnIcon').innerHTML = '<polygon points="5 3 19 12 5 21 5 3"/>';
        pdfInput.value = '';
        welcomeUploadZone.classList.remove('uploading');
        previewWarning.classList.remove('visible');
        checkReady();

        // Go back to welcome screen
        showWelcome();
    }

    newTaskBtn.addEventListener('click', () => {
        resetContractState();
    });

    // ── Preset Stamps ──
    async function loadPresetStamps() {
        const resp = await api('GET', '/api/v1/stamps/list');
        const data = await resp.json();
        if (data.stamps.length === 0) {
            stampGrid.innerHTML = '<div class="stamp-empty">暂无印章，请在管理后台添加</div>';
            return;
        }
        stampGrid.innerHTML = data.stamps.map(s => `
            <div class="stamp-card" data-url="${s.url}" data-name="${s.name}" data-stamp-id="">
                <img src="${s.url}" alt="${s.company || s.name}">
                <div class="stamp-card-name">${s.company || s.name}</div>
            </div>
        `).join('');

        // Pre-upload stamps one by one in background (sequential to avoid overloading server)
        (async () => {
            const cards = stampGrid.querySelectorAll('.stamp-card');
            for (const card of cards) {
                try {
                    const imgResp = await fetch(card.dataset.url);
                    if (!imgResp.ok) continue;
                    const blob = await imgResp.blob();
                    const fd = new FormData();
                    fd.append('file', blob, card.dataset.name + '.png');
                    const uploadResp = await api('POST', '/api/v1/upload/stamp', fd, true);
                    if (uploadResp.ok) {
                        const d = await uploadResp.json();
                        card.dataset.stampId = d.stamp_id;
                        card.classList.add('preloaded');
                    }
                } catch (e) { /* ignore preload failures */ }
            }
        })();

        stampGrid.addEventListener('click', async e => {
            const card = e.target.closest('.stamp-card');
            if (!card) return;

            stampGrid.querySelectorAll('.stamp-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');

            if (card.dataset.stampId) {
                // Already preloaded — instant
                stampId = card.dataset.stampId;
                showStatus('success', `已选择: ${card.dataset.name}`);
                hideStatus();
                checkReady();
            } else {
                // Fallback: preload hasn't finished yet
                showStatus('loading', '加载印章中...');
                try {
                    const imgResp = await fetch(card.dataset.url);
                    if (!imgResp.ok) { showStatus('error', '印章图片加载失败'); return; }
                    const blob = await imgResp.blob();
                    const fd = new FormData();
                    fd.append('file', blob, card.dataset.name + '.png');
                    const uploadResp = await api('POST', '/api/v1/upload/stamp', fd, true);
                    if (!uploadResp.ok) { showStatus('error', '印章加载失败'); return; }
                    const uploadData = await uploadResp.json();
                    stampId = uploadData.stamp_id;
                    card.dataset.stampId = stampId;
                    showStatus('success', `已选择: ${card.dataset.name}`);
                    hideStatus();
                    checkReady();
                } catch (err) {
                    showStatus('error', '印章加载出错');
                }
            }
        });
    }

    loadPresetStamps();

    // ── Party toggle ──
    let currentParty = '乙方';
    const partyToggle = document.getElementById('partyToggle');
    partyToggle.addEventListener('click', async e => {
        const btn = e.target.closest('.party-btn');
        if (!btn || btn.classList.contains('active')) return;
        partyToggle.querySelectorAll('.party-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentParty = btn.dataset.party;
        if (fileId) {
            detectedPosition = null;
            manualPosition = null;
            stampMarker.hidden = true;
            await detectKeywords();
            checkReady();
        }
    });

    // ── Keyword detection ──
    const previewWarning = document.getElementById('previewWarning');

    async function detectKeywords() {
        const resp = await api('POST', '/api/v1/detect', { file_id: fileId, party: currentParty });
        const data = await resp.json();
        if (data.found && data.positions.length > 0) {
            const pos = data.positions[0];
            // Store normalized 0-1 coords directly; convert at point of use
            detectedPosition = {
                keyword: pos.keyword,
                page: pos.page,
                x_norm: pos.x_norm,
                y_norm: pos.y_norm,
            };

            showMarkerByNorm(detectedPosition.page, detectedPosition.x_norm, detectedPosition.y_norm);
            showStatus('success', `已识别: "${detectedPosition.keyword}" 在第 ${detectedPosition.page + 1} 页`);
            const wrapper = pagesContainer.querySelector(`[data-page-num="${detectedPosition.page}"]`);
            if (wrapper) wrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
            previewWarning.classList.remove('visible');
        } else {
            previewWarning.classList.add('visible');
        }
    }

    // ── Click-to-place ──
    function enableCanvasClicks() {
        pagesContainer.querySelectorAll('canvas').forEach(canvas => {
            canvas.style.cursor = 'crosshair';
            canvas.addEventListener('click', e => {
                const rect = canvas.getBoundingClientRect();
                const cssX = e.clientX - rect.left;
                const cssY = e.clientY - rect.top;
                const pageNum = parseInt(canvas.dataset.pageNum);

                // Convert CSS click → normalized 0-1 coords
                manualPosition = {
                    page: pageNum,
                    x_norm: cssX / rect.width,
                    y_norm: cssY / rect.height,
                };

                showMarkerByNorm(pageNum, manualPosition.x_norm, manualPosition.y_norm);
                showStatus('success', `已指定盖章位置: 第 ${pageNum + 1} 页`);
                previewWarning.classList.remove('visible');
                checkReady();
            });
        });
    }

    function showMarkerByNorm(pageNum, xNorm, yNorm) {
        const canvas = pagesContainer.querySelector(`canvas[data-page-num="${pageNum}"]`);
        if (!canvas) return;
        const rect = canvas.getBoundingClientRect();
        const scrollRect = previewScroll.getBoundingClientRect();
        const cx = xNorm * rect.width;
        const cy = yNorm * rect.height;
        stampMarker.hidden = false;
        stampMarker.style.left = (rect.left - scrollRect.left + previewScroll.scrollLeft + cx - 40) + 'px';
        stampMarker.style.top = (rect.top - scrollRect.top + previewScroll.scrollTop + cy - 40) + 'px';
    }

    // Reposition marker on window resize so it stays on the correct spot
    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            const pos = manualPosition || detectedPosition;
            if (pos && !stampMarker.hidden) {
                showMarkerByNorm(pos.page, pos.x_norm, pos.y_norm);
            }
        }, 150);
    });

    // ── Draggable stamp marker ──
    let dragging = false, dragStartX, dragStartY, markerStartX, markerStartY;
    stampMarker.addEventListener('mousedown', e => {
        dragging = true;
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        markerStartX = stampMarker.offsetLeft;
        markerStartY = stampMarker.offsetTop;
        e.preventDefault();
    });
    document.addEventListener('mousemove', e => {
        if (!dragging) return;
        stampMarker.style.left = (markerStartX + e.clientX - dragStartX) + 'px';
        stampMarker.style.top = (markerStartY + e.clientY - dragStartY) + 'px';
    });
    document.addEventListener('mouseup', () => { finishDrag(); });

    // ── Touch events for mobile ──
    stampMarker.addEventListener('touchstart', e => {
        dragging = true;
        const touch = e.touches[0];
        dragStartX = touch.clientX;
        dragStartY = touch.clientY;
        markerStartX = stampMarker.offsetLeft;
        markerStartY = stampMarker.offsetTop;
        e.preventDefault();
    }, { passive: false });

    document.addEventListener('touchmove', e => {
        if (!dragging) return;
        const touch = e.touches[0];
        stampMarker.style.left = (markerStartX + touch.clientX - dragStartX) + 'px';
        stampMarker.style.top = (markerStartY + touch.clientY - dragStartY) + 'px';
        e.preventDefault();
    }, { passive: false });

    document.addEventListener('touchend', () => { finishDrag(); });

    function finishDrag() {
        if (!dragging) return;
        dragging = false;
        const markerCx = stampMarker.offsetLeft + 40;
        const markerCy = stampMarker.offsetTop + 40;
        const canvases = pagesContainer.querySelectorAll('canvas');
        for (const canvas of canvases) {
            const scrollRect = previewScroll.getBoundingClientRect();
            const rect = canvas.getBoundingClientRect();
            const relLeft = rect.left - scrollRect.left + previewScroll.scrollLeft;
            const relTop = rect.top - scrollRect.top + previewScroll.scrollTop;
            if (markerCx >= relLeft && markerCx <= relLeft + rect.width &&
                markerCy >= relTop && markerCy <= relTop + rect.height) {
                const cx = markerCx - relLeft;
                const cy = markerCy - relTop;
                const pageNum = parseInt(canvas.dataset.pageNum);
                // Store as normalized coords
                const newPos = { page: pageNum, x_norm: cx / rect.width, y_norm: cy / rect.height };
                if (detectedPosition && detectedPosition.page === pageNum) {
                    detectedPosition.x_norm = newPos.x_norm;
                    detectedPosition.y_norm = newPos.y_norm;
                } else {
                    manualPosition = newPos;
                }
                break;
            }
        }
    }

    // ── Settings ──
    const seamPositionRow = document.getElementById('seamPositionRow');
    seamToggle.addEventListener('change', () => {
        seamPositionRow.style.display = seamToggle.checked ? '' : 'none';
    });

    stampSize.addEventListener('input', () => {
        stampSizeVal.textContent = stampSize.value + 'mm';
    });

    agingSlider.addEventListener('input', () => {
        const v = parseInt(agingSlider.value);
        if (v === 0) agingVal.textContent = '关闭';
        else if (v <= 25) agingVal.textContent = '轻度';
        else if (v <= 55) agingVal.textContent = '中度';
        else agingVal.textContent = '重度';
    });

    scanSlider.addEventListener('input', () => {
        const v = parseInt(scanSlider.value);
        if (v === 0) scanVal.textContent = '关闭';
        else if (v <= 30) scanVal.textContent = '轻度';
        else if (v <= 70) scanVal.textContent = '中度';
        else scanVal.textContent = '重度';
    });

    // Convert slider value (0=off, higher=stronger) to API value (higher=lighter)
    function scanSliderToApi(v) {
        return v > 0 ? (101 - v) : 0;
    }

    // ── Process / Download ──
    function checkReady() {
        if (!isCompleted) {
            processBtn.disabled = !(fileId && stampId && (detectedPosition || manualPosition));
        }
    }

    processBtn.addEventListener('click', async () => {
        if (isCompleted) {
            if (resultTaskId) {
                window.location.href = `/api/v1/download/${resultTaskId}`;
            }
            return;
        }

        processBtn.disabled = true;
        showStatus('loading', '处理中...');

        const pos = manualPosition || detectedPosition;
        let pdfX, pdfY;

        if (pdfDoc && !isWordUpload) {
            // Normalized coords → PDF points
            const page = await pdfDoc.getPage(pos.page + 1);
            const viewport = page.getViewport({ scale: 1 });
            pdfX = pos.x_norm * viewport.width;
            pdfY = pos.y_norm * viewport.height;
        } else {
            // Word upload: use page dimensions from preview
            const canvas = pagesContainer.querySelector(`canvas[data-page-num="${pos.page}"]`);
            pdfX = pos.x_norm * 595.276;  // A4 width in points
            pdfY = pos.y_norm * 841.89;   // A4 height in points
        }

        const body = {
            file_id: fileId,
            stamp_id: stampId,
            party_b_position: { page: pos.page, x: pdfX, y: pdfY },
            riding_seam: seamToggle.checked,
            seam_position: seamPosition.value,
            scan_effect: scanSliderToApi(parseInt(scanSlider.value)),
            stamp_aging: parseInt(agingSlider.value),
            original_filename: lastFileName,
        };

        const resp = await api('POST', '/api/v1/stamp', body);
        const data = await resp.json();
        resultTaskId = data.task_id;
        pollResult(resultTaskId);
    });

    async function pollResult(taskId) {
        const resp = await api('GET', `/api/v1/result/${taskId}`);
        const data = await resp.json();
        if (data.status === 'completed') {
            btnProgress.style.width = '100%';
            showStatus('success', '处理完成');
            setTimeout(() => { btnProgress.style.width = '0'; }, 500);

            isCompleted = true;
            processBtn.disabled = false;
            processBtn.classList.add('download');
            processBtnText.textContent = '下载结果 PDF';
            document.getElementById('processBtnIcon').innerHTML = '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>';
            newTaskBtn.hidden = false;

            await previewResultPdf(taskId);
            addHistory(lastFileName, taskId);
            launchFireworks();
        } else if (data.status === 'error') {
            showStatus('error', '处理失败: ' + (data.error || '未知错误'));
            processBtn.disabled = false;
            btnProgress.style.width = '0';
        } else {
            btnProgress.style.width = (data.progress || 0) + '%';
            setTimeout(() => pollResult(taskId), 800);
        }
    }

    // ── Status ──
    function showStatus(type, msg) {
        statusBar.hidden = false;
        statusBar.className = 'status-bar ' + type;
        statusText.textContent = msg;
    }

    function hideStatus() {
        setTimeout(() => { statusBar.hidden = true; }, 3000);
    }

    // ── History ──
    function addHistory(name, taskId) {
        const now = new Date();
        const time = `${now.getMonth()+1}/${now.getDate()} ${now.getHours()}:${String(now.getMinutes()).padStart(2,'0')}`;
        history.unshift({ name, taskId, time });
        if (history.length > 20) history.pop();
        localStorage.setItem('stampHistory', JSON.stringify(history));
        renderHistory();
    }

    function renderHistory() {
        const html = history.length === 0
            ? '<div class="history-empty">暂无记录</div>'
            : history.map(h => `
                <div class="history-item">
                    <span class="history-name" title="${h.name}">${h.name}</span>
                    <span class="history-time">${h.time}</span>
                    <button class="history-dl" onclick="window.location.href='/api/v1/download/${h.taskId}'"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>下载</button>
                </div>
            `).join('');

        const sidebarList = document.getElementById('sidebarHistoryList');
        if (sidebarList) sidebarList.innerHTML = html;
    }

    renderHistory();

    // ── Fireworks ──
    let fwAnimId = null;
    let fwParticles = [];
    let fwRunning = false;

    window.launchFireworks = function () {
        const cvs = document.getElementById('fireworks');
        const ctx = cvs.getContext('2d');
        cvs.width = window.innerWidth;
        cvs.height = window.innerHeight;
        cvs.classList.add('active');
        fwParticles = [];
        fwRunning = true;

        const colors = [
            '#ff6b6b','#ff3e3e','#ffd93d','#ffb347','#6bcb77','#2ecc71',
            '#4d96ff','#3b7dff','#ff6bff','#e84393','#00cec9','#fdcb6e',
            '#407600','#a29bfe','#fd79a8','#fab1a0','#55efc4','#74b9ff'
        ];

        function addBurst() {
            if (!fwRunning) return;
            const cx = Math.random() * cvs.width * 0.8 + cvs.width * 0.1;
            const cy = Math.random() * cvs.height * 0.5 + cvs.height * 0.05;
            const count = 60 + Math.random() * 60;
            const palette = [colors[Math.floor(Math.random() * colors.length)]];
            for (let c = 0; c < 2; c++) palette.push(colors[Math.floor(Math.random() * colors.length)]);
            for (let i = 0; i < count; i++) {
                const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.5;
                const speed = 3 + Math.random() * 7;
                fwParticles.push({
                    x: cx, y: cy,
                    vx: Math.cos(angle) * speed,
                    vy: Math.sin(angle) * speed - 1,
                    life: 1,
                    decay: 0.006 + Math.random() * 0.012,
                    color: palette[Math.floor(Math.random() * palette.length)],
                    size: 2.5 + Math.random() * 3.5,
                });
            }
        }

        for (let i = 0; i < 4; i++) setTimeout(() => addBurst(), i * 200);
        const burstInterval = setInterval(() => {
            if (!fwRunning) { clearInterval(burstInterval); return; }
            addBurst();
            if (Math.random() > 0.5) setTimeout(addBurst, 150);
        }, 600 + Math.random() * 600);

        function animate() {
            if (!fwRunning) {
                ctx.clearRect(0, 0, cvs.width, cvs.height);
                cvs.classList.remove('active');
                return;
            }
            ctx.clearRect(0, 0, cvs.width, cvs.height);
            for (let i = fwParticles.length - 1; i >= 0; i--) {
                const p = fwParticles[i];
                p.life -= p.decay;
                if (p.life <= 0) { fwParticles.splice(i, 1); continue; }
                p.vy += 0.04;
                p.vx *= 0.985;
                p.x += p.vx;
                p.y += p.vy;
                const glow = p.size * p.life * 2;
                ctx.globalAlpha = p.life * 0.3;
                ctx.fillStyle = p.color;
                ctx.beginPath();
                ctx.arc(p.x, p.y, glow, 0, Math.PI * 2);
                ctx.fill();
                ctx.globalAlpha = Math.min(1, p.life * 1.5);
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.size * p.life, 0, Math.PI * 2);
                ctx.fill();
                if (Math.random() > 0.92 && p.life > 0.3) {
                    ctx.globalAlpha = p.life;
                    ctx.fillStyle = '#fff';
                    ctx.beginPath();
                    ctx.arc(p.x + (Math.random() - 0.5) * 4, p.y + (Math.random() - 0.5) * 4, 1, 0, Math.PI * 2);
                    ctx.fill();
                }
            }
            ctx.globalAlpha = 1;
            fwAnimId = requestAnimationFrame(animate);
        }
        animate();
        setTimeout(() => { if (fwRunning) stopFireworks(); }, 5000);
    };

    window.stopFireworks = function () {
        fwRunning = false;
        if (fwAnimId) cancelAnimationFrame(fwAnimId);
        const cvs = document.getElementById('fireworks');
        const ctx = cvs.getContext('2d');
        ctx.clearRect(0, 0, cvs.width, cvs.height);
        cvs.classList.remove('active');
        fwParticles = [];
    };

})();
