(function () {
    'use strict';

    let fileId = null;
    let stampId = null;
    let pdfDoc = null;
    let currentPage = 0;
    let totalPages = 0;
    let detectedPosition = null;
    let manualPosition = null;
    let resultTaskId = null;

    const pdfInput = document.getElementById('pdfInput');
    const pdfUploadZone = document.getElementById('pdfUploadZone');
    const pdfPlaceholder = document.getElementById('pdfPlaceholder');
    const pdfDone = document.getElementById('pdfDone');
    const pdfFileName = document.getElementById('pdfFileName');
    const pdfClear = document.getElementById('pdfClear');

    const stampInput = document.getElementById('stampInput');
    const stampUploadZone = document.getElementById('stampUploadZone');
    const stampPlaceholder = document.getElementById('stampPlaceholder');
    const stampDone = document.getElementById('stampDone');
    const stampPreview = document.getElementById('stampPreview');
    const stampClear = document.getElementById('stampClear');

    const stampSize = document.getElementById('stampSize');
    const stampSizeVal = document.getElementById('stampSizeVal');
    const seamToggle = document.getElementById('seamToggle');
    const scanSlider = document.getElementById('scanSlider');
    const scanVal = document.getElementById('scanVal');

    const processBtn = document.getElementById('processBtn');
    const btnProgress = document.getElementById('btnProgress');
    const downloadBtn = document.getElementById('downloadBtn');
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

    let previewUrls = []; // server-side preview URLs (used for Word uploads)
    let isWordUpload = false;

    async function uploadPdf(file) {
        const ext = file.name.split('.').pop().toLowerCase();
        isWordUpload = (ext === 'docx' || ext === 'doc');

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
            // Word file: use server-side preview images
            pdfDoc = null;
            currentPage = 0;
            renderPageFromServer(0);
        } else {
            // PDF file: use PDF.js for client-side rendering
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

    async function uploadStamp(file) {
        showStatus('loading', '上传印章中...');
        const fd = new FormData();
        fd.append('file', file);
        const resp = await api('POST', '/api/v1/upload/stamp', fd, true);
        if (!resp.ok) { showStatus('error', '上传失败'); return; }
        const data = await resp.json();
        stampId = data.stamp_id;
        stampPlaceholder.hidden = true;
        stampDone.hidden = false;
        stampPreview.src = URL.createObjectURL(file);
        checkReady();
        hideStatus();
    }

    setupUploadZone(pdfUploadZone, pdfInput, uploadPdf);
    setupUploadZone(stampUploadZone, stampInput, uploadStamp);

    pdfClear.addEventListener('click', e => {
        e.stopPropagation();
        fileId = null; pdfDoc = null; detectedPosition = null; manualPosition = null;
        isWordUpload = false; previewUrls = [];
        pdfPlaceholder.hidden = false; pdfDone.hidden = true;
        previewNav.hidden = true;
        canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
        previewTitle.textContent = '上传合同以预览';
        stampMarker.hidden = true;
        checkReady();
    });

    stampClear.addEventListener('click', e => {
        e.stopPropagation();
        stampId = null;
        stampPlaceholder.hidden = false; stampDone.hidden = true;
        checkReady();
    });

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

    async function detectKeywords() {
        const resp = await api('POST', '/api/v1/detect', { file_id: fileId });
        const data = await resp.json();
        if (data.found && data.positions.length > 0) {
            detectedPosition = data.positions[0];
            showStatus('success', `已识别: "${detectedPosition.keyword}" 在第 ${detectedPosition.page + 1} 页`);
            renderPage(detectedPosition.page);
        } else {
            showStatus('loading', '未识别到盖章位置，请在预览中点击指定');
            enableManualClick();
        }
    }

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
            canvasX: x,
            canvasY: y,
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

    function checkReady() {
        processBtn.disabled = !(fileId && stampId && (detectedPosition || manualPosition));
    }

    processBtn.addEventListener('click', async () => {
        processBtn.disabled = true;
        downloadBtn.hidden = true;
        showStatus('loading', '处理中...');

        const pos = detectedPosition || manualPosition;
        let pdfX, pdfY;

        if (pdfDoc) {
            // PDF mode: convert canvas coords to PDF coords via PDF.js
            const page = await pdfDoc.getPage(pos.page + 1);
            const viewport = page.getViewport({ scale: 1 });
            const displayScale = canvas.width / viewport.width;
            pdfX = pos.x / displayScale;
            pdfY = pos.y / displayScale;
        } else {
            // Word mode: detected positions are already in PDF coords from server
            pdfX = pos.x;
            pdfY = pos.y;
        }

        const body = {
            file_id: fileId,
            stamp_id: stampId,
            party_b_position: { page: pos.page, x: pdfX, y: pdfY },
            riding_seam: seamToggle.checked,
            scan_effect: parseInt(scanSlider.value),
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
            downloadBtn.hidden = false;
            processBtn.disabled = false;
            setTimeout(() => { btnProgress.style.width = '0'; }, 500);
        } else if (data.status === 'error') {
            showStatus('error', '处理失败: ' + (data.error || '未知错误'));
            processBtn.disabled = false;
            btnProgress.style.width = '0';
        } else {
            btnProgress.style.width = (data.progress || 0) + '%';
            setTimeout(() => pollResult(taskId), 800);
        }
    }

    downloadBtn.addEventListener('click', () => {
        if (resultTaskId) {
            window.location.href = `/api/v1/download/${resultTaskId}`;
        }
    });

    function showStatus(type, msg) {
        statusBar.hidden = false;
        statusBar.className = 'status-bar ' + type;
        statusText.textContent = msg;
    }

    function hideStatus() {
        setTimeout(() => { statusBar.hidden = true; }, 3000);
    }
})();
