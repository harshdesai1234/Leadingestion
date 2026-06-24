/* ═══════════════════════════════════════════════════════════════
   AGENTYNE ASOC — PREMIUM JS
   Vanilla JavaScript · No Dependencies
   ═══════════════════════════════════════════════════════════════ */

(function() {
  'use strict';

  /* ── ANIMATED COUNTERS ── */
  function animateCount(el) {
    const target = parseFloat(el.dataset.target);
    if (isNaN(target)) return;

    const duration = 1400;
    const isFloat = target % 1 !== 0;
    const step = target / (duration / 16);
    let current = 0;

    const timer = setInterval(function() {
      current += step;
      if (current >= target) {
        current = target;
        clearInterval(timer);
      }
      if (isFloat) {
        el.textContent = current.toFixed(1);
      } else {
        el.textContent = Math.floor(current).toLocaleString();
      }
    }, 16);
  }

  function initCounters() {
    document.querySelectorAll('.count-up').forEach(function(el) {
      setTimeout(function() { animateCount(el); }, 300);
    });
  }

  /* ── NAV ACTIVE STATE ── */
  function initNav() {
    // Highlight current nav item based on URL
    var navItems = document.querySelectorAll('.nav-item');
    var currentPath = window.location.pathname;

    navItems.forEach(function(item) {
      var href = item.getAttribute('href');
      if (href && currentPath.indexOf(href) === 0 && href !== '/') {
        item.classList.add('active');
      } else if (href === '/' && currentPath === '/') {
        item.classList.add('active');
      }
    });

    // Click handler for nav items
    navItems.forEach(function(item) {
      item.addEventListener('click', function() {
        navItems.forEach(function(n) { n.classList.remove('active'); });
        this.classList.add('active');
      });
    });
  }

  /* ── SEARCH INPUT FOCUS ANIMATION ── */
  function initSearch() {
    var searchInputs = document.querySelectorAll('.search-input');
    searchInputs.forEach(function(input) {
      input.addEventListener('focus', function() {
        this.style.width = '240px';
      });
      input.addEventListener('blur', function() {
        this.style.width = '';
      });
    });
  }

  /* ── ALERT AUTO-DISMISS ── */
  function initAlerts() {
    // Auto-dismiss Django messages after 5 seconds
    var alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
      setTimeout(function() {
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-8px)';
        alert.style.transition = 'all 0.4s ease';
        setTimeout(function() {
          alert.remove();
        }, 400);
      }, 5000);
    });

    // Close button handler
    document.querySelectorAll('.alert-close').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var alert = this.closest('.alert');
        if (alert) {
          alert.style.opacity = '0';
          alert.style.transform = 'translateY(-8px)';
          alert.style.transition = 'all 0.3s ease';
          setTimeout(function() { alert.remove(); }, 300);
        }
      });
    });
  }

  /* ── TOOLTIPS ── */
  // Handled purely via CSS [data-tip] attribute

  /* ── TAB SWITCHING ── */
  function initTabs() {
    document.querySelectorAll('.tabs').forEach(function(tabContainer) {
      var buttons = tabContainer.querySelectorAll('.tab-btn');
      buttons.forEach(function(btn) {
        btn.addEventListener('click', function() {
          // Remove active from all tabs in this container
          buttons.forEach(function(b) { b.classList.remove('active'); });
          this.classList.add('active');

          // Show/hide tab content panels
          var targetId = this.dataset.tab;
          if (targetId) {
            var parent = tabContainer.parentElement;
            parent.querySelectorAll('.tab-panel').forEach(function(panel) {
              panel.style.display = 'none';
            });
            var targetPanel = parent.querySelector('#' + targetId);
            if (targetPanel) {
              targetPanel.style.display = 'block';
            }
          }
        });
      });
    });
  }

  /* ── DROPDOWN TOGGLE (lightweight) ── */
  function initDropdowns() {
    document.addEventListener('click', function(e) {
      var toggle = e.target.closest('[data-dropdown]');
      if (toggle) {
        e.stopPropagation();
        var menu = toggle.nextElementSibling;
        if (menu && menu.classList.contains('dropdown-menu')) {
          var isOpen = menu.classList.contains('open');
          // Close all other dropdowns
          document.querySelectorAll('.dropdown-menu.open').forEach(function(m) {
            m.classList.remove('open');
          });
          if (!isOpen) {
            menu.classList.add('open');
          }
        }
      } else {
        // Close all dropdowns on outside click
        document.querySelectorAll('.dropdown-menu.open').forEach(function(m) {
          m.classList.remove('open');
        });
      }
    });
  }

  /* ── CONFIRM DELETE ── */
  function initConfirmActions() {
    document.querySelectorAll('[data-confirm]').forEach(function(el) {
      el.addEventListener('click', function(e) {
        var message = this.dataset.confirm || 'Are you sure?';
        if (!confirm(message)) {
          e.preventDefault();
        }
      });
    });
  }

  /* ── FORM VALIDATION HELPER ── */
  function initFormValidation() {
    document.querySelectorAll('form[data-validate]').forEach(function(form) {
      form.addEventListener('submit', function(e) {
        var isValid = true;
        this.querySelectorAll('[required]').forEach(function(field) {
          if (!field.value.trim()) {
            isValid = false;
            field.style.borderColor = 'var(--accent)';
            field.style.boxShadow = '0 0 0 3px rgba(212,0,0,0.08)';
          } else {
            field.style.borderColor = '';
            field.style.boxShadow = '';
          }
        });
        if (!isValid) {
          e.preventDefault();
        }
      });
    });
  }

  /* ── TOPBAR TITLE FROM PAGE ── */
  function initTopbarTitle() {
    var topbarTitle = document.querySelector('.topbar-title');
    var pageTitle = document.querySelector('[data-page-title]');
    if (topbarTitle && pageTitle) {
      topbarTitle.textContent = pageTitle.dataset.pageTitle;
    }

    // Set date in topbar
    var topbarSub = document.querySelector('.topbar-sub');
    if (topbarSub && !topbarSub.textContent.trim()) {
      var now = new Date();
      var days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
      var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      topbarSub.textContent = days[now.getDay()] + ', ' + now.getDate() + ' ' + months[now.getMonth()] + ' ' + now.getFullYear();
    }
  }

  /* ── INIT ALL ── */
  function init() {
    initCounters();
    initNav();
    initSearch();
    initAlerts();
    initTabs();
    initDropdowns();
    initConfirmActions();
    initFormValidation();
    initTopbarTitle();
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
