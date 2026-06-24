/**
 * Lead Ingestion — Premium UI JavaScript
 * Handles AJAX requeuing, toast notifications, and dynamic filtering.
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Auto-submit filter form when select values change
    const filterForm = document.getElementById('filters-form');
    if (filterForm) {
        const selects = filterForm.querySelectorAll('select');
        selects.forEach(select => {
            select.addEventListener('change', () => {
                document.body.style.cursor = 'wait';
                filterForm.submit();
            });
        });
    }

    // 2. AJAX Requeue Logic
    const requeueForms = document.querySelectorAll('.ajax-requeue-form');
    
    requeueForms.forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const btn = form.querySelector('.requeue-btn');
            const leadId = btn.dataset.leadId;
            const row = document.getElementById(`failed-row-${leadId}`);
            
            // Set loading state
            btn.innerHTML = `<svg class="spin-anim" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="4.93" x2="19.07" y2="7.76"></line></svg> Queuing...`;
            btn.disabled = true;
            row.classList.add('requeueing');

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: new FormData(form),
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    }
                });

                const data = await response.json();

                if (data.success) {
                    showToast(`Lead #${leadId} requeued successfully`, 'success');
                    
                    row.style.transition = 'all 0.4s ease-out';
                    row.style.opacity = '0';
                    row.style.transform = 'translateX(20px)';
                    
                    setTimeout(() => {
                        row.remove();
                        updateFailedBadgeCount(-1);
                    }, 400);
                } else {
                    showToast(data.error || data.message || 'Failed to requeue lead', 'error');
                    resetRequeueBtn(btn, row);
                }
            } catch (err) {
                showToast('Network error occurred', 'error');
                resetRequeueBtn(btn, row);
            }
        });
    });

    // 3. Toast Notification System
    function showToast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icon = type === 'success' 
            ? `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`
            : `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;

        toast.innerHTML = `
            ${icon}
            <span>${message}</span>
        `;
        
        container.appendChild(toast);
        
        setTimeout(() => toast.classList.add('show'), 10);
        
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    function resetRequeueBtn(btn, row) {
        btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"></polyline><polyline points="23 20 23 14 17 14"></polyline><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"></path></svg> Requeue`;
        btn.disabled = false;
        row.classList.remove('requeueing');
    }

    function updateFailedBadgeCount(change) {
        const badges = document.querySelectorAll('.badge-error');
        badges.forEach(badge => {
            let current = parseInt(badge.textContent, 10);
            if (!isNaN(current)) {
                let next = current + change;
                if (next <= 0) {
                    badge.style.display = 'none';
                } else {
                    badge.textContent = next;
                }
            }
        });
        
        const metricValue = document.querySelector('.error-card .metric-value');
        if (metricValue) {
            let current = parseInt(metricValue.textContent, 10);
            if (!isNaN(current)) {
                metricValue.textContent = Math.max(0, current + change);
            }
        }
    }
    
    if (!document.getElementById('spin-anim-style')) {
        const style = document.createElement('style');
        style.id = 'spin-anim-style';
        style.textContent = `
            @keyframes spin { 100% { transform: rotate(360deg); } }
            .spin-anim { animation: spin 1s linear infinite; }
        `;
        document.head.appendChild(style);
    }
});
