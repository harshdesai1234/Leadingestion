(function () {
  'use strict';

  function csrfToken() {
    var cookie = document.cookie.split(';').find(function (item) {
      return item.trim().indexOf('csrftoken=') === 0;
    });
    return cookie ? cookie.trim().split('=')[1] : '';
  }

  function setIndicator(message, tone) {
    var indicator = document.getElementById('saveIndicator');
    if (!indicator) return;
    indicator.textContent = message || '';
    indicator.style.color = tone === 'error' ? 'var(--danger)' : 'var(--muted)';
  }

  function collectSections(canvas) {
    return Array.from(canvas.querySelectorAll('.editor-section')).map(function (section) {
      var heading = section.querySelector('.section-heading');
      var content = section.querySelector('.section-content');
      return {
        id: Number(section.dataset.sectionId),
        title: heading ? heading.textContent.trim() : '',
        content_html: content ? content.innerHTML : '',
      };
    }).filter(function (section) {
      return section.id;
    });
  }

  function initSave() {
    var canvas = document.getElementById('editorCanvas');
    var button = document.getElementById('saveAllBtn');
    if (!canvas || !button || !canvas.dataset.saveAllUrl) return;

    function saveAll() {
      button.disabled = true;
      setIndicator('Saving...');

      fetch(canvas.dataset.saveAllUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
        },
        body: JSON.stringify({ sections: collectSections(canvas) }),
      })
        .then(function (response) {
          if (!response.ok) throw new Error('Save failed');
          return response.json();
        })
        .then(function () {
          setIndicator('Saved');
          window.setTimeout(function () { setIndicator(''); }, 1800);
        })
        .catch(function () {
          setIndicator('Save failed', 'error');
        })
        .finally(function () {
          button.disabled = false;
        });
    }

    button.addEventListener('click', saveAll);
    document.addEventListener('keydown', function (event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        saveAll();
      }
    });
  }

  function initExportModal() {
    var modal = document.getElementById('exportModal');
    var open = document.getElementById('exportToggle');
    var close = document.getElementById('exportClose');
    if (!modal || !open) return;

    open.addEventListener('click', function () {
      modal.hidden = false;
    });

    if (close) {
      close.addEventListener('click', function () {
        modal.hidden = true;
      });
    }

    modal.addEventListener('click', function (event) {
      if (event.target === modal) modal.hidden = true;
    });
  }

  function initProgress() {
    var canvas = document.getElementById('editorCanvas');
    if (!canvas || !canvas.dataset.jobStatusUrl) return;

    var wrap = document.getElementById('generationProgressWrap');
    var text = document.getElementById('generationProgressText');
    var bar = document.getElementById('generationProgressBar');
    if (wrap) wrap.hidden = false;

    var timer = window.setInterval(function () {
      fetch(canvas.dataset.jobStatusUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (response) { return response.json(); })
        .then(function (data) {
          var pct = data.percent || 0;
          if (bar) {
            bar.style.width = pct + '%';
            bar.setAttribute('aria-valuenow', String(pct));
          }
          if (text) {
            text.textContent = data.current_section_title || (pct + '% complete');
          }
          if (data.is_complete) {
            window.clearInterval(timer);
            window.location.href = window.location.pathname;
          }
          if (data.is_failed) {
            window.clearInterval(timer);
            if (text) text.textContent = data.error_message || 'Generation failed';
          }
        })
        .catch(function () {
          window.clearInterval(timer);
        });
    }, 3000);
  }

  document.addEventListener('DOMContentLoaded', function () {
    initSave();
    initExportModal();
    initProgress();
  });
})();
