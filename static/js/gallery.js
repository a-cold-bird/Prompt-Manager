/**
 * static/js/gallery.js
 * 画廊页面核心交互逻辑：详情弹窗、统计打点、剪贴板复制。
 * (Fixed: 修复字段名与后端 to_dict() 不匹配的问题)
 */

document.addEventListener("DOMContentLoaded", function() {
    // 1. 初始化主题
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
});

// --- 主题切换 ---
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const target = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', target);
    localStorage.setItem('theme', target);
    updateThemeIcon(target);
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('themeIcon');
    if(icon) icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
}

// --- 详情弹窗逻辑 ---
window.showDetail = function(el) {
    try {
        const scriptTag = el.querySelector('.img-data');
        if (!scriptTag) return;
        const data = JSON.parse(scriptTag.textContent);

        // 填充基本信息
        const modalImg = document.getElementById('modalImg');
        // ✨ [修复 1] 使用 file_path 替代 src
        modalImg.src = data.file_path;

        document.getElementById('modalTitle').innerText = data.title;
        document.getElementById('modalAuthor').innerText = data.author ? 'by ' + data.author : '';
        document.getElementById('modalPrompt').innerText = data.prompt;

        // 记录当前 ID 用于复制统计
        window.currentImgId = data.id;

        // 填充描述
        const descSection = document.getElementById('modalDescSection');
        // ✨ [修复 2] 使用 description 替代 desc
        if (data.description && data.description.trim() !== '') {
            descSection.classList.remove('d-none');
            document.getElementById('modalDesc').innerText = data.description;
        } else {
            descSection.classList.add('d-none');
        }

        // 填充标签
        const tagsContainer = document.getElementById('modalTags');
        tagsContainer.innerHTML = '';
        data.tags.forEach(tag => {
            tagsContainer.innerHTML += `<span class="badge rounded-pill fw-normal border me-1" style="background:var(--btn-bg); color:var(--text-primary); border-color: rgba(128,128,128,0.2) !important;">${tag}</span>`;
        });

        // 填充参考图
        const refsSection = document.getElementById('modalRefsSection');
        const refsContainer = document.getElementById('modalRefs');
        refsContainer.innerHTML = '';
        if (data.refs.length > 0) {
            refsSection.classList.remove('d-none');
            // 添加原图缩略 (点击切换回原图)
            // ✨ [修复 3] 这里的 onclick 事件中也要用 data.file_path
            refsContainer.innerHTML += `
            <div class="d-flex flex-column align-items-center cursor-pointer me-2" onclick="document.getElementById('modalImg').src='${data.file_path}'">
                <img src="${data.file_path}" class="rounded border mb-1" style="width:60px;height:60px;object-fit:cover;">
                <span style="font-size:0.6rem;color:var(--text-secondary);">Original</span>
            </div>`;

            // 添加参考图 (点击切换为参考图)
            data.refs.forEach((rSrc, idx) => {
                refsContainer.innerHTML += `
                <div class="d-flex flex-column align-items-center cursor-pointer me-1" onclick="document.getElementById('modalImg').src='${rSrc}'">
                    <img src="${rSrc}" class="rounded border mb-1" style="width:60px;height:60px;object-fit:cover;">
                    <span style="font-size:0.6rem;color:var(--text-secondary);">Ref ${idx+1}</span>
                </div>`;
            });
        } else {
            refsSection.classList.add('d-none');
        }

        // 发送浏览打点 (Beacon API 优先)
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        if (navigator.sendBeacon && csrfToken) {
            const formData = new FormData();
            formData.append('csrf_token', csrfToken);
            navigator.sendBeacon(`/api/stats/view/${data.id}`, formData);
        } else {
            // 降级方案
            fetch(`/api/stats/view/${data.id}`, {
                method: 'POST',
                headers: {'X-CSRFToken': csrfToken}
            }).catch(() => {});
        }

        // 管理员操作按钮
        const adminSection = document.getElementById('admin-actions');
        if (window.UserContext && window.UserContext.isAdmin) {
            adminSection.classList.remove('d-none');
            const currentPath = window.location.pathname + window.location.search + window.location.hash;
            const encodedPath = encodeURIComponent(currentPath);
            document.getElementById('btn-edit-art').href = `/admin/edit/${data.id}?next=${encodedPath}`;
            document.getElementById('form-delete-art').action = `/admin/delete/${data.id}?next=${encodedPath}`;
        } else {
            adminSection.classList.add('d-none');
        }

        // 显示模态框
        if (typeof bootstrap !== 'undefined') {
            new bootstrap.Modal(document.getElementById('detailModal')).show();
        }
    } catch(e) {
        console.error("Detail Error:", e);
    }
}

// --- 复制 Prompt 逻辑 ---
window.copyModalPrompt = function() {
    const node = document.getElementById('modalPrompt');
    const text = node.innerText || node.textContent;
    const btn = document.querySelector('#detailModal button[onclick="copyModalPrompt()"]');

    const onSuccess = () => {
        // UI 反馈
        if(btn) {
            const originalContent = btn.innerHTML;
            btn.innerHTML = '<i class="bi bi-check-lg me-1"></i> Copied';
            btn.classList.remove('btn-link');
            btn.classList.add('text-success', 'fw-bold');
            setTimeout(() => {
                btn.innerHTML = originalContent;
                btn.classList.remove('text-success', 'fw-bold');
                btn.classList.add('btn-link');
            }, 2000);
        }
        // 复制统计打点
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        if (window.currentImgId && csrfToken) {
            fetch(`/api/stats/copy/${window.currentImgId}`, {
                method: 'POST',
                headers: {'X-CSRFToken': csrfToken}
            }).catch(() => {});
        }
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(onSuccess).catch(err => {
            fallbackCopy(text, btn, onSuccess);
        });
    } else {
        fallbackCopy(text, btn, onSuccess);
    }
}

// 降级复制方案 (兼容性)
function fallbackCopy(text, parentBtn, callback) {
    try {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.setAttribute("readonly", "readonly");
        textArea.style.position = "absolute";
        textArea.style.left = "-9999px";
        document.body.appendChild(textArea);

        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);

        if (callback) callback();
    } catch (err) {
        console.error("Copy failed:", err);
        prompt("请手动复制:", text);
    }
}