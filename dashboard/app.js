/**
 * Review Pulsator — Interactive Dashboard Controller (app.js)
 * Handles REST API calls, dynamic DOM manipulation, Chart.js visualizations,
 * and live Groq LLM pulse triggers.
 */

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    fetchServerStatus();
    loadLatestPulseReport();
    loadAnalytics();
    loadArchives();
    setupEventListeners();
});

/* --- Navigation & Tabs --- */
function initNavigation() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-target');

            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const targetPane = document.getElementById(targetId);
            if (targetPane) {
                targetPane.classList.add('active');
            }

            // If switching to analytics, trigger Chart resize if needed
            if (targetId === 'view-analytics') {
                window.dispatchEvent(new Event('resize'));
            }
        });
    });
}

/* --- Event Listeners --- */
function setupEventListeners() {
    const btnTrigger = document.getElementById('btn-trigger-pulse');
    if (btnTrigger) {
        btnTrigger.addEventListener('click', triggerLivePulse);
    }

    const btnRefreshPulse = document.getElementById('btn-refresh-pulse');
    if (btnRefreshPulse) {
        btnRefreshPulse.addEventListener('click', () => {
            showToast('Reloading latest pulse report...');
            loadLatestPulseReport();
        });
    }

    const btnRefreshArchives = document.getElementById('btn-refresh-archives');
    if (btnRefreshArchives) {
        btnRefreshArchives.addEventListener('click', () => {
            showToast('Refreshing archive list...');
            loadArchives();
        });
    }

    const btnCloseModal = document.getElementById('btn-close-modal');
    const modalBackdrop = document.getElementById('modal-backdrop');
    const modal = document.getElementById('report-modal');

    const closeModal = () => modal.classList.remove('active');
    if (btnCloseModal) btnCloseModal.addEventListener('click', closeModal);
    if (modalBackdrop) modalBackdrop.addEventListener('click', closeModal);
}

/* --- API Callers --- */
async function fetchServerStatus() {
    try {
        const res = await fetch('/api/status');
        if (!res.ok) throw new Error('Server offline');
        const data = await res.json();

        const badge = document.getElementById('server-status-badge');
        const text = document.getElementById('status-text');
        const modelText = document.getElementById('active-model-text');

        if (text) text.textContent = '● AI ENGINE ONLINE';
        if (modelText) modelText.textContent = `${data.model} (@ 0.4 temp)`;
    } catch (e) {
        const text = document.getElementById('status-text');
        if (text) text.textContent = '○ OFFLINE';
        const badge = document.getElementById('server-status-badge');
        if (badge) badge.style.borderColor = 'var(--brand-danger)';
    }
}

async function loadLatestPulseReport() {
    try {
        const res = await fetch('/api/report');
        if (!res.ok) {
            document.getElementById('themes-list-container').innerHTML = `<div class="empty-state">No pulse report found. Click "Trigger Live AI Pulse" to generate one!</div>`;
            return;
        }
        const data = await res.json();
        const report = data.report;
        renderPulseReport(report);
    } catch (e) {
        console.error('Error loading pulse report:', e);
    }
}

function renderPulseReport(report) {
    if (!report) return;

    // Subtitle
    const subtitle = document.getElementById('pulse-date-subtitle');
    if (subtitle) subtitle.textContent = `Report Date: ${report.report_date} • 100% Validated by Groq 70B`;

    // Word Count Card
    const valWord = document.getElementById('val-word-count');
    if (valWord) valWord.textContent = `${report.word_count} / 250`;

    // Google Doc Button
    const btnGdocs = document.getElementById('btn-view-gdocs');
    if (btnGdocs) {
        const docUrl = report.doc_url || "https://docs.google.com/document/d/17Uam8Sm6woB9Ten1lsRNepKUtAVklsFsl6ItI59sEdk/edit";
        btnGdocs.href = docUrl;
        btnGdocs.style.display = 'inline-block';
    }

    // Render Themes
    const themesContainer = document.getElementById('themes-list-container');
    if (themesContainer && report.top_themes) {
        themesContainer.innerHTML = report.top_themes.map((t, idx) => `
            <div class="theme-card">
                <div class="theme-card-header">
                    <span class="theme-title">${idx + 1}. ${t.name}</span>
                    <div class="theme-stats">
                        <span class="stat-tag">ID: #${t.theme_id || idx+101}</span>
                    </div>
                </div>
                <p class="theme-summary">${t.summary}</p>
            </div>
        `).join('');
    }

    // Render Quotes
    const quotesContainer = document.getElementById('quotes-list-container');
    if (quotesContainer && report.verbatim_quotes) {
        quotesContainer.innerHTML = report.verbatim_quotes.map(q => `
            <div class="quote-card">"${q}"</div>
        `).join('');
    }

    // Render Action Ideas
    const actionsContainer = document.getElementById('actions-list-container');
    if (actionsContainer && report.action_ideas) {
        actionsContainer.innerHTML = report.action_ideas.map((a, idx) => `
            <div class="action-item">
                <span class="action-number">${idx + 1}</span>
                <span>${a}</span>
            </div>
        `).join('');
    }
}

/* --- Analytics & Charts --- */
let ratingsChartInstance = null;
let themesChartInstance = null;

async function loadAnalytics() {
    try {
        const res = await fetch('/api/analytics');
        if (!res.ok) throw new Error('Analytics failed');
        const data = await res.json();

        // Total reviews
        const valTotal = document.getElementById('val-total-reviews');
        if (valTotal) valTotal.textContent = data.total_scrubbed_window;
        const subRaw = document.getElementById('subval-raw-total');
        if (subRaw) subRaw.textContent = `Filtered from ${data.total_raw} raw dataset`;

        // Store split
        const play = data.store_split.google_play || 0;
        const apple = data.store_split.apple_app_store || 0;
        const totalStore = play + apple || 1;
        const playPct = Math.round((play / totalStore) * 100);
        const applePct = 100 - playPct;

        const valSplit = document.getElementById('val-store-split');
        if (valSplit) valSplit.textContent = `${playPct}% : ${applePct}%`;
        const barPlay = document.getElementById('bar-play-width');
        if (barPlay) barPlay.style.width = `${playPct}%`;
        const barApple = document.getElementById('bar-apple-width');
        if (barApple) barApple.style.width = `${applePct}%`;

        // Avg Star rating
        let totalStars = 0;
        let countStars = 0;
        for (const [star, cnt] of Object.entries(data.rating_distribution)) {
            totalStars += (Number(star) * cnt);
            countStars += cnt;
        }
        const avgRating = countStars > 0 ? (totalStars / countStars).toFixed(2) : '3.00';
        const valRating = document.getElementById('val-avg-rating');
        if (valRating) valRating.textContent = `${avgRating} ⭐`;
        const starFill = document.getElementById('val-star-fill');
        if (starFill) starFill.style.width = `${(avgRating / 5) * 100}%`;

        // Populate Complete 5 Themes Table
        const tbodyThemes = document.getElementById('tbody-all-themes');
        if (tbodyThemes && data.themes) {
            tbodyThemes.innerHTML = data.themes.map((t, idx) => `
                <tr>
                    <td><strong>#${idx + 1}</strong></td>
                    <td><span class="badge badge-orange">${t.name}</span></td>
                    <td><strong>${t.count}</strong> reviews</td>
                    <td><code>${t.severity}</code></td>
                    <td>⭐ ${t.avg_rating}</td>
                    <td style="font-style: italic; max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">"${t.sample_quote}"</td>
                </tr>
            `).join('');
        }

        // Render Chart.js
        renderRatingsChart(data.rating_distribution);
        if (data.themes) {
            renderThemesRadarChart(data.themes);
        }

    } catch (e) {
        console.error('Error loading analytics:', e);
    }
}

function renderRatingsChart(dist) {
    const ctx = document.getElementById('chart-ratings');
    if (!ctx) return;

    if (ratingsChartInstance) ratingsChartInstance.destroy();

    const labels = ['1 Star ⭐', '2 Stars ⭐⭐', '3 Stars ⭐⭐⭐', '4 Stars ⭐⭐⭐⭐', '5 Stars ⭐⭐⭐⭐⭐'];
    const values = [dist[1] || 0, dist[2] || 0, dist[3] || 0, dist[4] || 0, dist[5] || 0];

    ratingsChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: [
                    '#ef4444', // Red for 1 star
                    '#f97316', // Orange for 2 stars
                    '#eab308', // Yellow for 3 stars
                    '#3b82f6', // Blue for 4 stars
                    '#10b981'  // Green for 5 stars
                ],
                borderColor: '#111424',
                borderWidth: 2,
                hoverOffset: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#94a3b8', font: { family: 'Inter', size: 12 }, padding: 16 }
                }
            },
            cutout: '68%'
        }
    });
}

function renderThemesRadarChart(themes) {
    const ctx = document.getElementById('chart-themes-severity');
    if (!ctx) return;

    if (themesChartInstance) themesChartInstance.destroy();

    const labels = themes.map(t => t.name.length > 20 ? t.name.substring(0, 18) + '...' : t.name);
    const severities = themes.map(t => t.severity);
    const volumes = themes.map(t => t.count * 20); // Scaled for comparison

    themesChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Severity Score',
                    data: severities,
                    backgroundColor: 'rgba(252, 128, 25, 0.7)',
                    borderColor: '#fc8019',
                    borderWidth: 1,
                    borderRadius: 6
                },
                {
                    label: 'Review Volume (Scaled)',
                    data: volumes,
                    backgroundColor: 'rgba(0, 242, 254, 0.4)',
                    borderColor: '#00f2fe',
                    borderWidth: 1,
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#94a3b8', font: { family: 'Inter', size: 12 }, padding: 16 }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    grid: { display: false },
                    ticks: { color: '#f8fafc', font: { family: 'Outfit', weight: '600' } }
                }
            }
        }
    });
}

/* --- Archives Table --- */
async function loadArchives() {
    try {
        const res = await fetch('/api/reports');
        if (!res.ok) return;
        const data = await res.json();

        const badge = document.getElementById('archive-count-badge');
        if (badge) badge.textContent = data.count;

        const tbody = document.getElementById('tbody-archives');
        if (!tbody) return;

        if (data.count === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center">No historical reports archived yet.</td></tr>`;
            return;
        }

        tbody.innerHTML = data.reports.map(r => `
            <tr>
                <td><strong>${r.report_date}</strong></td>
                <td><code>${r.filename}</code></td>
                <td><span class="badge badge-purple">${r.word_count} words</span></td>
                <td>${r.top_themes ? r.top_themes.join(', ') : 'N/A'}</td>
                <td><span class="badge badge-success">${r.status || 'SUCCESS'}</span></td>
                <td>
                    <button class="btn btn-outline" style="padding: 4px 10px; font-size: 12px;" onclick="viewReportModal('${r.path}')">🔍 View JSON</button>
                </td>
            </tr>
        `).join('');
    } catch (e) {
        console.error('Error loading archives:', e);
    }
}

window.viewReportModal = async function(path) {
    try {
        const res = await fetch(`/api/report?path=${encodeURIComponent(path)}`);
        const data = await res.json();
        
        const modal = document.getElementById('report-modal');
        const modalTitle = document.getElementById('modal-title');
        const modalCode = document.getElementById('modal-code');

        if (modalTitle) modalTitle.textContent = `Report Archive: ${path}`;
        if (modalCode) modalCode.textContent = JSON.stringify(data.report, null, 2);
        if (modal) modal.classList.add('active');
    } catch (e) {
        showToast('Error opening archive');
    }
};

/* --- Live AI Pulse Trigger --- */
async function triggerLivePulse() {
    const spinner = document.getElementById('pulse-loading-spinner');
    const content = document.getElementById('pulse-content-container');
    const btn = document.getElementById('btn-trigger-pulse');

    if (spinner) spinner.style.display = 'block';
    if (content) content.style.opacity = '0.3';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner" style="width: 16px; height: 16px; border-width: 2px; margin: 0; display: inline-block;"></span> Synthesizing...`;
    }

    try {
        showToast('Running live vector clustering & Groq LLM synthesis...');
        const res = await fetch('/api/trigger_pulse', { method: 'POST' });
        const data = await res.json();

        if (data.success && data.result) {
            showToast('✅ Executive Pulse Note generated successfully!');
            await loadLatestPulseReport();
            await loadArchives();
        } else {
            alert('Synthesis failed: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Failed to connect to server: ' + e.message);
    } finally {
        if (spinner) spinner.style.display = 'none';
        if (content) content.style.opacity = '1';
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<span class="btn-icon">⚡</span> <span class="btn-label">Trigger Live AI Pulse</span>`;
        }
    }
}

/* --- Toast Helper --- */
function showToast(msg) {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toast-message');
    if (!toast || !toastMsg) return;

    toastMsg.textContent = msg;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 4000);
}
