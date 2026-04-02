(function () {
    'use strict';

    const token = localStorage.getItem('token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = 'Bearer ' + token;

    const adminDenied = document.getElementById('adminDenied');
    const adminContent = document.getElementById('adminContent');

    // Check admin access
    async function checkAccess() {
        try {
            const resp = await fetch('/api/v1/me', { headers });
            if (!resp.ok) {
                adminDenied.hidden = false;
                return;
            }
            const data = await resp.json();
            if (data.role !== 'admin') {
                adminDenied.hidden = false;
                return;
            }
            adminContent.hidden = false;
            loadUsers();
            loadStamps();
        } catch (e) {
            adminDenied.hidden = false;
        }
    }

    // ── User Management ──
    async function loadUsers() {
        const resp = await fetch('/api/v1/admin/users', { headers });
        const data = await resp.json();
        const list = document.getElementById('userList');
        if (data.users.length === 0) {
            list.innerHTML = '<div class="admin-list-empty">暂无用户</div>';
            return;
        }
        list.innerHTML = data.users.map(u => `
            <div class="admin-list-item">
                <div class="admin-list-info">
                    <span class="admin-list-name">${u.username}</span>
                    <span class="admin-role-badge ${u.role === 'admin' ? 'role-admin' : 'role-user'}">${u.role === 'admin' ? '管理员' : '用户'}</span>
                </div>
                ${u.username === 'admin' ? '<span class="admin-list-hint">默认管理员</span>' : `<button class="btn-danger" onclick="deleteUser('${u.username}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>删除</button>`}
            </div>
        `).join('');
    }

    window.deleteUser = async function (username) {
        if (!confirm(`确定删除用户 "${username}" 吗？`)) return;
        await fetch(`/api/v1/admin/users/${username}`, { method: 'DELETE', headers });
        loadUsers();
    };

    document.getElementById('addUserBtn').addEventListener('click', async () => {
        const username = document.getElementById('newUsername').value.trim();
        const password = document.getElementById('newPassword').value;
        const role = document.getElementById('newRole').value;
        if (!username || !password) { alert('请填写用户名和密码'); return; }
        const resp = await fetch('/api/v1/admin/users', {
            method: 'POST',
            headers,
            body: JSON.stringify({ username, password, role }),
        });
        if (resp.ok) {
            document.getElementById('newUsername').value = '';
            document.getElementById('newPassword').value = '';
            loadUsers();
        } else {
            const err = await resp.json();
            alert(err.detail || '添加失败');
        }
    });

    // ── Stamp Management ──
    let selectedStampFile = null;

    document.getElementById('stampFileBtn').addEventListener('click', () => {
        document.getElementById('stampFileInput').click();
    });

    document.getElementById('stampFileInput').addEventListener('change', (e) => {
        if (e.target.files.length) {
            selectedStampFile = e.target.files[0];
            document.getElementById('stampFileName').textContent = selectedStampFile.name;
        }
    });

    async function loadStamps() {
        const resp = await fetch('/api/v1/admin/stamps', { headers });
        const data = await resp.json();
        const list = document.getElementById('stampList');
        if (data.stamps.length === 0) {
            list.innerHTML = '<div class="admin-list-empty">暂无印章</div>';
            return;
        }
        list.innerHTML = data.stamps.map(s => `
            <div class="admin-list-item">
                <div class="admin-list-info">
                    <img src="${s.url}" class="admin-stamp-thumb" alt="${s.company}">
                    <span class="admin-list-name">${s.company}</span>
                </div>
                <button class="btn-danger" onclick="deleteStamp('${s.filename}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>删除</button>
            </div>
        `).join('');
    }

    window.deleteStamp = async function (filename) {
        if (!confirm('确定删除此印章吗？')) return;
        await fetch(`/api/v1/admin/stamps/${filename}`, { method: 'DELETE', headers });
        loadStamps();
    };

    document.getElementById('addStampBtn').addEventListener('click', async () => {
        const company = document.getElementById('newCompany').value.trim();
        if (!company) { alert('请填写公司主体名称'); return; }
        if (!selectedStampFile) { alert('请选择印章图片'); return; }

        const fd = new FormData();
        fd.append('file', selectedStampFile);
        fd.append('company', company);

        const uploadHeaders = {};
        if (token) uploadHeaders['Authorization'] = 'Bearer ' + token;

        const resp = await fetch('/api/v1/admin/stamps', {
            method: 'POST',
            headers: uploadHeaders,
            body: fd,
        });
        if (resp.ok) {
            document.getElementById('newCompany').value = '';
            document.getElementById('stampFileName').textContent = '未选择文件';
            document.getElementById('stampFileInput').value = '';
            selectedStampFile = null;
            loadStamps();
        } else {
            const err = await resp.json();
            alert(err.detail || '添加失败');
        }
    });

    // ── Logout ──
    document.getElementById('logoutBtn').addEventListener('click', async () => {
        await fetch('/api/v1/logout', { method: 'POST' });
        localStorage.removeItem('token');
        localStorage.removeItem('username');
        window.location.href = '/';
    });

    checkAccess();
})();
