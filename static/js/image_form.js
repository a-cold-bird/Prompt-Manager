/**
 * static/js/image_form.js
 * 负责上传和编辑页面的表单交互逻辑：
 * 1. 拖拽排序 (SortableJS)
 * 2. 多图上传预览
 * 3. 标签输入交互
 * 4. 表单提交预处理
 */

document.addEventListener('DOMContentLoaded', function() {
    'use strict';

    const form = document.getElementById('imageForm');
    if (!form) return;

    // --- DOM Elements ---
    const mode = form.getAttribute('data-mode'); // 'create' or 'edit'
    const submitBtn = document.getElementById('submitBtn');

    // Type Selection
    const cardTxt2Img = document.querySelector('.type-selector-card[data-type="txt2img"]');
    const cardImg2Img = document.querySelector('.type-selector-card[data-type="img2img"]');

    // Reference Image Area
    const refUploadArea = document.getElementById('refUploadArea');
    const refContainer = document.getElementById('refContainer');
    const refEmptyMsg = document.getElementById('refEmptyMsg');
    const tempRefInput = document.getElementById('tempRefInput');
    const finalRefInput = document.getElementById('finalRefInput');
    const btnAddRef = document.getElementById('btnAddRef');
    const refLayoutInput = document.getElementById('refLayoutInput');

    // Tag Input
    const tagInput = document.getElementById('tagInput');
    const tagContainer = document.getElementById('tagWrapper');
    const realTagsInput = document.getElementById('realTagsInput');

    // State
    let newRefFiles = [];
    let deletedRefIds = [];
    let tags = [];

    // --- Initialization ---
    function init() {
        if (mode === 'edit') {
            try {
                // Restore tags
                tags = JSON.parse(form.getAttribute('data-existing-tags') || '[]');
                renderTags();

                // Restore reference images
                const existingRefs = JSON.parse(form.getAttribute('data-existing-refs') || '[]');
                const existingRefIds = JSON.parse(form.getAttribute('data-existing-ref-ids') || '[]');

                existingRefs.forEach((url, idx) => {
                    appendExistingRef(url, existingRefIds[idx]);
                });
            } catch (e) { console.error('Data restore failed:', e); }
        } else if (realTagsInput.value) {
            tags = realTagsInput.value.split(',').filter(t => t.trim());
            renderTags();
        }

        checkRefEmptyState();
        initSortable();
        updateIndices();
    }

    // --- Type Toggling ---
    function toggleType(type) {
        if (type === 'txt2img') {
            cardTxt2Img.classList.add('active');
            cardImg2Img.classList.remove('active');
            cardTxt2Img.querySelector('input').checked = true;
            refUploadArea.classList.add('d-none');
        } else {
            cardImg2Img.classList.add('active');
            cardTxt2Img.classList.remove('active');
            cardImg2Img.querySelector('input').checked = true;
            refUploadArea.classList.remove('d-none');
            // Animation
            refUploadArea.animate([
                { opacity: 0, transform: 'translateY(-10px)' },
                { opacity: 1, transform: 'translateY(0)' }
            ], { duration: 300, easing: 'ease-out', fill: 'forwards' });
            setTimeout(initSortable, 100);
        }
    }
    if(cardTxt2Img) cardTxt2Img.addEventListener('click', () => toggleType('txt2img'));
    if(cardImg2Img) cardImg2Img.addEventListener('click', () => toggleType('img2img'));

    // --- Main Image Preview ---
    const mainInput = document.getElementById('mainImageInput');
    if (mainInput) {
        mainInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    document.getElementById('mainPlaceholder').classList.add('d-none');
                    const img = document.getElementById('mainPreview');
                    img.src = e.target.result;
                    img.classList.remove('d-none');
                }
                reader.readAsDataURL(this.files[0]);
            }
        });
    }

    // --- Reference Images Logic ---
    if (btnAddRef && tempRefInput) {
        btnAddRef.addEventListener('click', () => tempRefInput.click());

        tempRefInput.addEventListener('change', function() {
            if (!this.files.length) return;

            Array.from(this.files).forEach(file => {
                // Assign temporary UID for tracking
                file._uid = Date.now() + Math.random().toString(36).substr(2, 9);
                newRefFiles.push(file);
                const imgUrl = URL.createObjectURL(file);
                appendRefPreview(imgUrl, file._uid);
            });

            checkRefEmptyState();
            syncNewFilesInput();
            updateIndices();
            this.value = '';
        });
    }

    function appendExistingRef(url, id) {
        const div = createRefElement(url, 'existing');
        div.setAttribute('data-ref-id', id);
        div.innerHTML += `<div class="index-badge"></div>`;
        refContainer.insertBefore(div, refEmptyMsg);
    }

    function appendRefPreview(url, uid) {
        const div = createRefElement(url, 'new');
        div.setAttribute('data-uid', uid);
        div.innerHTML += `<div class="index-badge"></div>`;
        refContainer.insertBefore(div, refEmptyMsg);
    }

    function createRefElement(src, type) {
        const div = document.createElement('div');
        div.className = 'draggable-item position-relative d-inline-block rounded-3 overflow-hidden shadow-sm';
        div.style.width = '100px'; div.style.height = '100px';
        div.setAttribute('data-type', type);
        div.innerHTML = `
            <img src="${src}" class="w-100 h-100 object-fit-cover">
            <div class="btn-remove-ref" title="移除"><i class="bi bi-x pointer-events-none"></i></div>
        `;
        return div;
    }

    // Remove Event Delegation
    if (refContainer) {
        refContainer.addEventListener('click', function(e) {
            const btn = e.target.closest('.btn-remove-ref');
            if (!btn) return;

            const item = btn.closest('.draggable-item');
            const type = item.getAttribute('data-type');

            if (type === 'existing') {
                deletedRefIds.push(item.getAttribute('data-ref-id'));
                document.getElementById('deletedRefIds').value = deletedRefIds.join(',');
            } else {
                const uid = item.getAttribute('data-uid');
                const img = item.querySelector('img');
                if(img && img.src.startsWith('blob:')) URL.revokeObjectURL(img.src);
                newRefFiles = newRefFiles.filter(f => f._uid !== uid);
                syncNewFilesInput();
            }
            item.remove();
            checkRefEmptyState();
            updateIndices();
        });
    }

    // Update Visual Indices (1, 2, 3...)
    function updateIndices() {
        const items = Array.from(refContainer.querySelectorAll('.draggable-item'))
                           .filter(el => el.style.display !== 'none');

        items.forEach((el, idx) => {
            const badge = el.querySelector('.index-badge');
            if(badge) badge.innerText = (idx + 1);
        });
    }

    // Sync DataTransfer for Input[type=file]
    function syncNewFilesInput() {
        if (!finalRefInput) return;
        const newOrder = [];
        refContainer.querySelectorAll('.draggable-item[data-type="new"]').forEach(el => {
            const uid = el.getAttribute('data-uid');
            const file = newRefFiles.find(f => f._uid === uid);
            if (file) newOrder.push(file);
        });
        newRefFiles = newOrder;

        // Reconstruct FileList
        const dt = new DataTransfer();
        newRefFiles.forEach(f => dt.items.add(f));
        finalRefInput.files = dt.files;
    }

    function checkRefEmptyState() {
        const items = refContainer.querySelectorAll('.draggable-item');
        if (items.length > 0) refEmptyMsg.classList.add('d-none');
        else refEmptyMsg.classList.remove('d-none');
    }

    function initSortable() {
        if (typeof Sortable !== 'undefined' && refContainer && !refContainer._sortable) {
            refContainer._sortable = new Sortable(refContainer, {
                animation: 200,
                ghostClass: 'sortable-ghost',
                draggable: ".draggable-item",
                delay: 100,
                delayOnTouchOnly: true,
                onEnd: function() {
                    updateIndices();
                    syncNewFilesInput();
                }
            });
        }
    }

    // --- Tag Logic ---
    function renderTags() {
        tagContainer.querySelectorAll('.tag-pill').forEach(el => el.remove());
        tags.forEach((tag, index) => {
            const span = document.createElement('span');
            span.className = 'tag-pill';
            span.innerHTML = `${tag} <i class="bi bi-x-lg" data-idx="${index}"></i>`;
            tagContainer.insertBefore(span, tagInput);
        });
        realTagsInput.value = tags.join(',');
    }

    if (tagContainer && tagInput) {
        tagContainer.addEventListener('click', (e) => {
            if(e.target === tagContainer) tagInput.focus();
            if(e.target.classList.contains('bi-x-lg')) {
                tags.splice(e.target.getAttribute('data-idx'), 1); renderTags();
            }
        });
        tagInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                const val = this.value.replace(/,|，/g, '').trim();
                if (val && !tags.includes(val)) { tags.push(val); renderTags(); }
                this.value = '';
            } else if (e.key === 'Backspace' && !this.value && tags.length) {
                tags.pop(); renderTags();
            }
        });
        tagInput.addEventListener('blur', function() {
             const val = this.value.replace(/,|，/g, '').trim();
             if (val && !tags.includes(val)) { tags.push(val); renderTags(); this.value = ''; }
        });
    }

    // --- Form Submission ---
    form.addEventListener('submit', function() {
        if (submitBtn) {
            setTimeout(() => {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>处理中...';
            }, 0);
        }

        // Calculate final layout for backend
        const layout = [];
        refContainer.querySelectorAll('.draggable-item').forEach(el => {
            const type = el.getAttribute('data-type');
            if (type === 'existing') {
                layout.push(`existing:${el.getAttribute('data-ref-id')}`);
            } else {
                layout.push('new');
            }
        });

        if(refLayoutInput) refLayoutInput.value = JSON.stringify(layout);
        syncNewFilesInput();
    });

    // Run
    init();
});