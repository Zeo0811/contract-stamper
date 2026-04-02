(function () {
    'use strict';

    // ── State ──
    let fileId = null;
    let stampId = null;
    let pdfDoc = null;
    let currentPage = 0;
    let totalPages = 0;
    let detectedPosition = null;
    let manualPosition = null;
    let resultTaskId = null;
    let previewUrls = [];
    let isWordUpload = false;
    let isCompleted = false;
    let history = JSON.parse(localStorage.getItem('stampHistory') || '[]');

    // ── Elements ──
    const pdfInput = document.getElementById('pdfInput');
    const pdfUploadZone = document.getElementById('pdfUploadZone');
    const pdfPlaceholder = document.getElementById('pdfPlaceholder');
    const pdfDone = document.getElementById('pdfDone');
    const pdfFileName = document.getElementById('pdfFileName');
    const pdfClear = document.getElementById('pdfClear');

    const stampGrid = document.getElementById('stampGrid');

    const stampSize = document.getElementById('stampSize');
    const stampSizeVal = document.getElementById('stampSizeVal');
    const seamToggle = document.getElementById('seamToggle');
    const scanSlider = document.getElementById('scanSlider');
    const scanVal = document.getElementById('scanVal');

    const processBtn = document.getElementById('processBtn');
    const processBtnText = document.getElementById('processBtnText');
    const btnProgress = document.getElementById('btnProgress');
    const newTaskBtn = document.getElementById('newTaskBtn');
    const statusBar = document.getElementById('statusBar');
    const statusText = document.getElementById('statusText');

    const canvas = document.getElementById('pdfCanvas');
    const canvasWrap = document.getElementById('canvasWrap');
    const previewTitle = document.getElementById('previewTitle');
    const previewNav = document.getElementById('previewNav');
    const prevPage = document.getElementById('prevPage');
    const nextPage = document.getElementById('nextPage');
    const pageInfo = document.getElementById('pageInfo');
    const stampMarker = document.getElementById('stampMarker');

    const historyList = document.getElementById('historyList');

    // ── API helper ──
    async function api(method, path, body, isFormData) {
        const opts = { method };
        if (isFormData) {
            opts.body = body;
        } else if (body) {
            opts.headers = { 'Content-Type': 'application/json' };
            opts.body = JSON.stringify(body);
        }
        return await fetch(path, opts);
    }

    // ── Upload handlers ──
    function setupUploadZone(zone, input, onFile) {
        zone.addEventListener('click', () => input.click());
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
        lastFileName = file.name;

        showStatus('loading', isWordUpload ? '上传并转换 Word 中...' : '上传合同中...');
        const fd = new FormData();
        fd.append('file', file);
        const resp = await api('POST', '/api/v1/upload', fd, true);
        if (!resp.ok) { showStatus('error', '上传失败'); return; }
        const data = await resp.json();
        fileId = data.file_id;
        totalPages = data.page_count;
        previewUrls = data.previews || [];
        pdfPlaceholder.hidden = true;
        pdfDone.hidden = false;
        pdfFileName.textContent = file.name;

        if (isWordUpload) {
            pdfDoc = null;
            currentPage = 0;
            renderPageFromServer(0);
        } else {
            const pdfData = await file.arrayBuffer();
            pdfDoc = await pdfjsLib.getDocument({ data: pdfData }).promise;
            currentPage = 0;
            renderPage(0);
        }
        previewNav.hidden = false;

        await detectKeywords();
        checkReady();
        hideStatus();
    }

    function renderPageFromServer(num) {
        if (num < 0 || num >= previewUrls.length) return;
        const img = new window.Image();
        img.onload = function () {
            const maxW = canvasWrap.clientWidth - 48;
            const scale = Math.min(maxW / img.width, 2);
            canvas.width = img.width * scale;
            canvas.height = img.height * scale;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            currentPage = num;
            pageInfo.textContent = `${num + 1} / ${totalPages}`;
            previewTitle.textContent = '合同预览';
        };
        img.src = previewUrls[num];
    }

    setupUploadZone(pdfUploadZone, pdfInput, uploadPdf);

    pdfClear.addEventListener('click', e => {
        e.stopPropagation();
        resetContractState();
    });

    function resetContractState() {
        fileId = null; pdfDoc = null; detectedPosition = null; manualPosition = null;
        isWordUpload = false; previewUrls = []; resultTaskId = null; isCompleted = false;
        pdfPlaceholder.hidden = false; pdfDone.hidden = true;
        previewNav.hidden = true;
        canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
        previewTitle.textContent = '上传合同以预览';
        stampMarker.hidden = true;
        newTaskBtn.hidden = true;
        btnProgress.style.width = '0';
        processBtn.classList.remove('download');
        processBtnText.textContent = '开始处理';
        pdfInput.value = '';
        checkReady();
    }

    // ── "Reset" button ──
    newTaskBtn.addEventListener('click', () => {
        resetContractState();
        showStatus('success', '已重置，请上传新合同');
        hideStatus();
    });

    // ── Preset Stamps ──
    async function loadPresetStamps() {
        const resp = await api('GET', '/api/v1/stamps/list');
        const data = await resp.json();
        if (data.stamps.length === 0) {
            stampGrid.innerHTML = '<div class="stamp-empty">暂无印章，请将 PNG 放入 app/static/stamps/</div>';
            return;
        }
        stampGrid.innerHTML = data.stamps.map(s => `
            <div class="stamp-card" data-url="${s.url}" data-name="${s.name}">
                <img src="${s.url}" alt="${s.company || s.name}">
                <div class="stamp-card-name">${s.company || s.name}</div>
            </div>
        `).join('');

        stampGrid.addEventListener('click', async e => {
            const card = e.target.closest('.stamp-card');
            if (!card) return;

            // Deselect all, select this
            stampGrid.querySelectorAll('.stamp-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');

            // Upload the stamp to server
            showStatus('loading', '加载印章中...');
            const imgResp = await fetch(card.dataset.url);
            const blob = await imgResp.blob();
            const fd = new FormData();
            fd.append('file', blob, card.dataset.name + '.png');
            const uploadResp = await api('POST', '/api/v1/upload/stamp', fd, true);
            if (!uploadResp.ok) { showStatus('error', '印章加载失败'); return; }
            const uploadData = await uploadResp.json();
            stampId = uploadData.stamp_id;
            showStatus('success', `已选择印章: ${card.dataset.name}`);
            hideStatus();
            checkReady();
        });
    }

    loadPresetStamps();

    // ── PDF rendering ──
    async function renderPage(num) {
        const page = await pdfDoc.getPage(num + 1);
        const scale = (canvasWrap.clientWidth - 48) / page.getViewport({ scale: 1 }).width;
        const viewport = page.getViewport({ scale: Math.min(scale, 2) });

        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const ctx = canvas.getContext('2d');
        await page.render({ canvasContext: ctx, viewport }).promise;

        currentPage = num;
        pageInfo.textContent = `${num + 1} / ${totalPages}`;
        previewTitle.textContent = '合同预览';
        updateStampMarker(viewport);
    }

    function goToPage(num) {
        if (isWordUpload || !pdfDoc) {
            renderPageFromServer(num);
        } else {
            renderPage(num);
        }
    }

    prevPage.addEventListener('click', () => {
        if (currentPage > 0) goToPage(currentPage - 1);
    });
    nextPage.addEventListener('click', () => {
        if (currentPage < totalPages - 1) goToPage(currentPage + 1);
    });

    // ── Result preview ──
    async function previewResultPdf(taskId) {
        try {
            const resp = await fetch(`/api/v1/download/${taskId}`);
            if (!resp.ok) return;
            const data = await resp.arrayBuffer();
            pdfDoc = await pdfjsLib.getDocument({ data }).promise;
            isWordUpload = false;
            totalPages = pdfDoc.numPages;
            currentPage = 0;
            previewTitle.textContent = '处理结果预览';
            pageInfo.textContent = `1 / ${totalPages}`;
            previewNav.hidden = false;

            const page = await pdfDoc.getPage(1);
            const scale = (canvasWrap.clientWidth - 48) / page.getViewport({ scale: 1 }).width;
            const viewport = page.getViewport({ scale: Math.min(scale, 2) });
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            const ctx = canvas.getContext('2d');
            await page.render({ canvasContext: ctx, viewport }).promise;
            stampMarker.hidden = true;
        } catch (e) {
            console.error('Result preview failed:', e);
        }
    }

    // ── Keyword detection ──
    async function detectKeywords() {
        const resp = await api('POST', '/api/v1/detect', { file_id: fileId });
        const data = await resp.json();
        if (data.found && data.positions.length > 0) {
            detectedPosition = data.positions[0];
            showStatus('success', `已识别: "${detectedPosition.keyword}" 在第 ${detectedPosition.page + 1} 页`);
            if (isWordUpload || !pdfDoc) {
                renderPageFromServer(detectedPosition.page);
            } else {
                renderPage(detectedPosition.page);
            }
        } else {
            showStatus('loading', '未识别到盖章位置，请在预览中点击指定');
            enableManualClick();
        }
    }

    // ── Manual click positioning ──
    function enableManualClick() {
        canvasWrap.style.cursor = 'crosshair';
        canvasWrap.addEventListener('click', onCanvasClick);
    }

    function onCanvasClick(e) {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;

        manualPosition = {
            page: currentPage,
            x: x * scaleX,
            y: y * scaleY,
        };

        stampMarker.hidden = false;
        stampMarker.style.left = (rect.left - canvasWrap.getBoundingClientRect().left + x - 40) + 'px';
        stampMarker.style.top = (rect.top - canvasWrap.getBoundingClientRect().top + y - 40) + 'px';

        showStatus('success', `已指定盖章位置: 第 ${currentPage + 1} 页`);
        canvasWrap.style.cursor = 'default';
        canvasWrap.removeEventListener('click', onCanvasClick);
        checkReady();
    }

    function updateStampMarker(viewport) {
        const pos = detectedPosition;
        if (!pos || pos.page !== currentPage) {
            stampMarker.hidden = true;
            return;
        }
        stampMarker.hidden = false;
        const rect = canvas.getBoundingClientRect();
        const wrapRect = canvasWrap.getBoundingClientRect();
        const scaleX = rect.width / viewport.width;
        const scaleY = rect.height / viewport.height;
        const cx = pos.x * scaleX;
        const cy = pos.y * scaleY;
        stampMarker.style.left = (rect.left - wrapRect.left + cx - 40) + 'px';
        stampMarker.style.top = (rect.top - wrapRect.top + cy - 40) + 'px';
    }

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
    document.addEventListener('mouseup', () => {
        if (!dragging) return;
        dragging = false;
        const rect = canvas.getBoundingClientRect();
        const wrapRect = canvasWrap.getBoundingClientRect();
        const cx = stampMarker.offsetLeft + 40 - (rect.left - wrapRect.left);
        const cy = stampMarker.offsetTop + 40 - (rect.top - wrapRect.top);
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        if (detectedPosition && detectedPosition.page === currentPage) {
            detectedPosition.x = cx * scaleX;
            detectedPosition.y = cy * scaleY;
        } else {
            manualPosition = { page: currentPage, x: cx * scaleX, y: cy * scaleY };
        }
    });

    // ── Settings ──
    stampSize.addEventListener('input', () => {
        stampSizeVal.textContent = stampSize.value + 'mm';
    });

    scanSlider.addEventListener('input', () => {
        const v = parseInt(scanSlider.value);
        if (v === 0) scanVal.textContent = '关闭';
        else if (v >= 80) scanVal.textContent = '轻度';
        else if (v >= 40) scanVal.textContent = '中度';
        else scanVal.textContent = '重度';
    });

    // ── Process / Download (merged button) ──
    function checkReady() {
        if (!isCompleted) {
            processBtn.disabled = !(fileId && stampId && (detectedPosition || manualPosition));
        }
    }

    processBtn.addEventListener('click', async () => {
        // If completed, clicking = download
        if (isCompleted) {
            if (resultTaskId) {
                window.location.href = `/api/v1/download/${resultTaskId}`;
            }
            return;
        }

        processBtn.disabled = true;
        showStatus('loading', '处理中...');

        const pos = detectedPosition || manualPosition;
        let pdfX, pdfY;

        if (pdfDoc) {
            const page = await pdfDoc.getPage(pos.page + 1);
            const viewport = page.getViewport({ scale: 1 });
            const displayScale = canvas.width / viewport.width;
            pdfX = pos.x / displayScale;
            pdfY = pos.y / displayScale;
        } else {
            pdfX = pos.x;
            pdfY = pos.y;
        }

        const body = {
            file_id: fileId,
            stamp_id: stampId,
            party_b_position: { page: pos.page, x: pdfX, y: pdfY },
            riding_seam: seamToggle.checked,
            scan_effect: parseInt(scanSlider.value),
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

            // Switch button to download mode
            isCompleted = true;
            processBtn.disabled = false;
            processBtn.classList.add('download');
            processBtnText.textContent = '下载结果 PDF';
            newTaskBtn.hidden = false;

            // Preview the result PDF
            await previewResultPdf(taskId);

            // Add to history
            addHistory(lastFileName, taskId);

            // Launch fireworks
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
        if (history.length === 0) {
            historyList.innerHTML = '<div class="history-empty">暂无记录</div>';
            return;
        }
        historyList.innerHTML = history.map(h => `
            <div class="history-item">
                <span class="history-name" title="${h.name}">${h.name}</span>
                <span class="history-time">${h.time}</span>
                <button class="history-dl" onclick="window.location.href='/api/v1/download/${h.taskId}'">下载</button>
            </div>
        `).join('');
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
