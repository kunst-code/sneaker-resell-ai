/**
 * SneakerAI - 스니커즈 리셀 AI 분석 프론트엔드
 */

const API_BASE = window.location.origin + '/api';

// ========== 페이지 라우팅 (SPA) ==========
function navigateTo(pageName) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    
    const page = document.getElementById(`page-${pageName}`);
    if (page) page.classList.add('active');
    
    document.querySelectorAll(`[data-page="${pageName}"]`).forEach(l => l.classList.add('active'));
    window.scrollTo(0, 0);

    // 페이지 진입 시 데이터 로드
    if (pageName === 'home') loadWordCloud();
    if (pageName === 'trending') loadTrendingSneakers();
    if (pageName === 'recommendations') loadRecommendations();
    if (pageName === 'analyzer') renderSearchHistory();
}

// 네비게이션 클릭 이벤트
document.addEventListener('click', (e) => {
    const link = e.target.closest('[data-page]');
    if (link) {
        e.preventDefault();
        navigateTo(link.dataset.page);
    }
});

// ========== 워드클라우드 (D3.js) ==========
let trendKeywordsCache = null;

async function loadWordCloud() {
    const container = document.getElementById('wordcloud-container');
    if (!container) return;

    try {
        let keywords;
        if (trendKeywordsCache) {
            keywords = trendKeywordsCache;
        } else {
            const response = await fetch(`${API_BASE}/trending/keywords`);
            const data = await response.json();
            keywords = data.keywords || [];
            trendKeywordsCache = keywords;
        }

        if (keywords.length > 0) {
            renderWordCloud(keywords);
        }
    } catch (e) {
        // 실패해도 무시 (홈페이지 로딩에 영향 없음)
        console.log('WordCloud load skipped:', e.message);
    }
}

function renderWordCloud(keywords) {
    const container = document.getElementById('wordcloud-container');
    const width = container.clientWidth || 900;
    const height = container.clientHeight || 400;

    // 기존 SVG 초기화
    d3.select('#wordcloud-svg').selectAll('*').remove();

    const colors = ['#6366f1', '#8b5cf6', '#ec4899', '#10b981', '#f59e0b', '#06b6d4', '#f472b6', '#a78bfa'];

    const layout = d3.layout.cloud()
        .size([width, height])
        .words(keywords.map(d => ({ text: d.text, size: d.size * 0.45 })))
        .padding(6)
        .rotate(() => (Math.random() > 0.7 ? 90 : 0))
        .font('Inter')
        .fontSize(d => d.size)
        .on('end', draw);

    layout.start();

    function draw(words) {
        const svg = d3.select('#wordcloud-svg')
            .attr('width', width)
            .attr('height', height);

        const g = svg.append('g')
            .attr('transform', `translate(${width / 2},${height / 2})`);

        const text = g.selectAll('text')
            .data(words)
            .enter().append('text')
            .style('font-size', d => `${d.size}px`)
            .style('font-family', 'Inter, sans-serif')
            .style('font-weight', d => d.size > 30 ? '700' : '500')
            .style('fill', (d, i) => colors[i % colors.length])
            .attr('text-anchor', 'middle')
            .attr('transform', d => `translate(${d.x},${d.y})rotate(${d.rotate})`)
            .style('opacity', 0)
            .text(d => d.text);

        // 모션 애니메이션: 순차적으로 페이드인
        text.transition()
            .duration(800)
            .delay((d, i) => i * 80)
            .style('opacity', 1);

        // 지속적 미세 움직임 (floating)
        function floatAnimation() {
            text.transition()
                .duration(3000 + Math.random() * 2000)
                .attr('transform', d => {
                    const dx = d.x + (Math.random() - 0.5) * 4;
                    const dy = d.y + (Math.random() - 0.5) * 4;
                    return `translate(${dx},${dy})rotate(${d.rotate})`;
                })
                .on('end', function() {
                    d3.select(this).transition()
                        .duration(3000 + Math.random() * 2000)
                        .attr('transform', d => `translate(${d.x},${d.y})rotate(${d.rotate})`)
                        .on('end', floatAnimation);
                });
        }

        // 초기 애니메이션 후 floating 시작
        setTimeout(floatAnimation, keywords.length * 80 + 1000);

        // 클릭 시 검색 (서버에 새로 조회)
        text.on('click', function(event, d) {
            const input = document.getElementById('style-code-input');
            if (input) input.value = d.text;
            addToHistory({ sku: d.text, title: d.text });
            navigateTo('analyzer');
            // 자동으로 분석 실행
            setTimeout(() => btnAnalyze.click(), 300);
        });
    }
}

// 홈 페이지 진입 시 워드클라우드 로드
setTimeout(loadWordCloud, 500);

// ========== DOM 요소 ==========
const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');
const previewContainer = document.getElementById('preview-container');
const btnAnalyze = document.getElementById('btn-analyze');
const styleCodeInput = document.getElementById('style-code-input');
const resultPanel = document.getElementById('result-panel');
const loadingOverlay = document.getElementById('loading-overlay');
const loadingSteps = document.getElementById('loading-steps');

let selectedFiles = [];  // 다중 파일
let analysisResults = []; // 다중 분석 결과
let currentResultPage = 0; // 현재 페이지

// ========== 이미지 업로드 (다중) ==========
uploadArea.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
    if (files.length > 0) handleFilesSelect(files);
});

fileInput.addEventListener('change', (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) handleFilesSelect(files);
});

function handleFilesSelect(files) {
    selectedFiles = [...selectedFiles, ...files];
    renderPreviews();
}

function renderPreviews() {
    if (selectedFiles.length === 0) {
        previewContainer.classList.add('hidden');
        uploadArea.querySelector('.upload-placeholder').classList.remove('hidden');
        return;
    }
    previewContainer.classList.remove('hidden');
    uploadArea.querySelector('.upload-placeholder').classList.add('hidden');

    previewContainer.innerHTML = selectedFiles.map((file, idx) => {
        const url = URL.createObjectURL(file);
        return `<div class="preview-thumb">
            <img src="${url}" alt="${file.name}">
            <button class="preview-remove" onclick="removeFile(${idx})">×</button>
        </div>`;
    }).join('') + `<div class="preview-count">${selectedFiles.length}장</div>`;
}

function removeFile(idx) {
    selectedFiles.splice(idx, 1);
    renderPreviews();
}

// ========== 빠른 선택 버튼 ==========
document.querySelectorAll('.sample-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const current = styleCodeInput.value.trim();
        const code = btn.dataset.code;
        if (current && !current.includes(code)) {
            styleCodeInput.value = current + ', ' + code;
        } else {
            styleCodeInput.value = code;
        }
    });
});

// ========== 통합 분석 실행 (다중) ==========
btnAnalyze.addEventListener('click', async () => {
    const codes = styleCodeInput.value.trim().split(/[,，]+/).map(c => c.trim()).filter(c => c.length > 0);
    const size = document.getElementById('analyze-size').value;

    if (selectedFiles.length === 0 && codes.length === 0) {
        alert('이미지를 업로드하거나 품번을 입력해주세요.');
        return;
    }

    // 이전 결과 리셋
    resetAnalyzer();

    showLoading();
    analysisResults = [];
    currentResultPage = 0;

    // 이미지 분석
    for (const file of selectedFiles) {
        updateLoadingStep(1);
        const result = await analyzeImageSingle(file);
        if (result) analysisResults.push(result);
    }

    // 품번 분석
    for (const code of codes) {
        updateLoadingStep(2);
        const result = await analyzeCodeSingle(code, size);
        if (result) analysisResults.push(result);
    }

    hideLoading();

    if (analysisResults.length > 0) {
        renderPaginatedResults();

        // 결과를 히스토리에 저장
        let idx = 0;
        // 이미지 분석 결과
        const imageCount = selectedFiles.length;
        for (let i = 0; i < imageCount && idx < analysisResults.length; i++, idx++) {
            const r = analysisResults[idx];
            const sneaker = r.step1_identification || {};
            addToHistory({
                sku: sneaker.style_code || sneaker.model_name || '',
                title: sneaker.model_name || '이미지 분석',
                image: sneaker.image || '',
            }, r);
        }
        // 품번 분석 결과
        for (let i = 0; i < codes.length && idx < analysisResults.length; i++, idx++) {
            addToHistory({ sku: codes[i], title: codes[i] }, analysisResults[idx]);
        }

        // 결과 나온 후 검색창 리셋
        styleCodeInput.value = '';
        selectedFiles = [];
        renderPreviews();
    } else {
        showError('분석 결과를 가져올 수 없습니다.');
    }
});

// 엔터키로도 분석
styleCodeInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') btnAnalyze.click();
});

// ========== 개별 분석 함수 ==========
async function analyzeImageSingle(file) {
    const formData = new FormData();
    formData.append('image', file);
    try {
        const response = await fetch(`${API_BASE}/recommend/analyze`, { method: 'POST', body: formData });
        const data = await response.json();
        if (data.success) return data.pipeline;
    } catch (e) { console.error(e); }
    return null;
}

async function analyzeCodeSingle(code, size) {
    const body = { style_code: code };
    if (size) body.size = size;
    // AI 분석 포함
    body.use_ai = true;
    try {
        const response = await fetch(`${API_BASE}/recommend/analyze-by-code`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await response.json();
        if (data.success) return data.pipeline;
    } catch (e) { console.error(e); }
    return null;
}

// ========== 페이지네이션 결과 렌더링 ==========
function renderPaginatedResults() {
    const total = analysisResults.length;
    const pipeline = analysisResults[currentResultPage];

    // 페이지네이션 바
    const paginationHtml = total > 1 ? `
        <div class="result-pagination">
            <button class="btn btn-outline btn-sm" onclick="prevResult()" ${currentResultPage === 0 ? 'disabled' : ''}>◀ 이전</button>
            <span class="pagination-info">${currentResultPage + 1} / ${total}</span>
            <button class="btn btn-outline btn-sm" onclick="nextResult()" ${currentResultPage === total - 1 ? 'disabled' : ''}>다음 ▶</button>
        </div>
    ` : '';

    // 결과 HTML 생성
    resultPanel.innerHTML = paginationHtml + buildResultHTML(pipeline) + paginationHtml;
}

function prevResult() {
    if (currentResultPage > 0) {
        currentResultPage--;
        renderPaginatedResults();
        resultPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function nextResult() {
    if (currentResultPage < analysisResults.length - 1) {
        currentResultPage++;
        renderPaginatedResults();
        resultPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function buildResultHTML(pipeline) {
    const { step1_identification, step2_price_data, step3_forecast, step4_recommendation } = pipeline;
    const rec = step4_recommendation;
    const priceData = step2_price_data;
    const forecast = step3_forecast;
    const sneaker = step1_identification;
    const selectedSize = sneaker.selected_size || priceData?.selected_size || '';

    const recClass = (rec.recommendation || 'HOLD').toLowerCase();
    const recLabel = {
        'buy': '🟢 매수 (BUY)',
        'sell': '🔴 매도 (SELL)',
        'hold': '🟡 보유 (HOLD)'
    }[recClass] || '🟡 보유 (HOLD)';
    const sizeDisplay = selectedSize ? `US ${selectedSize}` : '전체 (최저가)';

    // 이미지: sneaker.image → priceData.sneaker.image → priceData.current_price 어디든 찾기
    const productImage = sneaker.image || priceData?.sneaker?.image || priceData?.image || '';

    return `
        <div class="product-info-card">
            ${productImage ? `<div class="product-info-image"><img src="${productImage}" alt="${sneaker.model_name || ''}" onerror="this.parentElement.style.display='none'"></div>` : ''}
            <h3 class="product-info-title">${sneaker.model_name || 'N/A'}</h3>
            <p class="product-info-subtitle">${sneaker.colorway || sneaker.nickname || ''}</p>
            <div class="product-info-table">
                <div class="product-info-row"><span class="product-info-label">모델 번호</span><span class="product-info-value">${sneaker.style_code || 'N/A'}</span></div>
                <div class="product-info-row"><span class="product-info-label">브랜드</span><span class="product-info-value">${sneaker.brand || 'N/A'}</span></div>
                <div class="product-info-row"><span class="product-info-label">사이즈</span><span class="product-info-value">${sizeDisplay}</span></div>
                <div class="product-info-row"><span class="product-info-label">출시일</span><span class="product-info-value">${sneaker.release_date || sneaker.release_year || 'N/A'}</span></div>
                <div class="product-info-row"><span class="product-info-label">발매가</span><span class="product-info-value">${sneaker.retail_price ? (sneaker.retail_price > 1000 ? sneaker.retail_price.toLocaleString() + '원' : '$' + sneaker.retail_price) : 'N/A'}</span></div>
            </div>
        </div>
        <div class="result-section">
            <h3>🎯 AI 투자 추천</h3>
            ${rec.recommendation === 'N/A' ? `
                <p style="color:var(--text-muted);text-align:center;margin:16px 0;">AI 분석을 사용하지 않았습니다</p>
                <div style="text-align:center;">
                    <button class="btn btn-primary" onclick="runAiAnalysis(this.dataset.sku)" data-sku="${(sneaker.style_code || sneaker.model_name || '').replace(/"/g, '&quot;')}">🤖 AI 투자 분석 실행</button>
                </div>
            ` : `
                <div style="text-align:center;margin:20px 0;"><span class="recommendation-badge ${recClass}">${recLabel}</span></div>
                <p class="report-text">${rec.detailed_report || rec.summary || ''}</p>
            `}
        </div>
        <div class="result-section">
            <h3>💰 현재 시세</h3>
            <div class="info-grid">
                ${priceData?.current_price?.kream ? `<div class="info-item"><div class="label">KREAM</div><div class="value">${formatPrice(priceData.current_price.kream)}</div></div>` : ''}
                <div class="info-item"><div class="label">StockX 최저가</div><div class="value">${priceData?.current_price?.stockx_usd ? '$' + priceData.current_price.stockx_usd : 'N/A'}</div></div>
                <div class="info-item"><div class="label">StockX 평균가</div><div class="value">${priceData?.current_price?.avg_price_usd ? '$' + Math.round(priceData.current_price.avg_price_usd) : 'N/A'}</div></div>
                <div class="info-item"><div class="label">원화환산</div><div class="value">${formatPrice(priceData?.current_price?.stockx_krw)}</div></div>
                <div class="info-item"><div class="label">주간 거래량</div><div class="value">${priceData?.statistics?.weekly_orders ? priceData.statistics.weekly_orders.toLocaleString() + '건' : 'N/A'}</div></div>
            </div>
        </div>
        <div class="result-section">
            <h3>📈 가격 예측 (30일)</h3>
            <div class="info-grid">
                <div class="info-item"><div class="label">현재가</div><div class="value">${forecast?.current_price ? (forecast.current_price > 1000 ? formatPrice(forecast.current_price) : '$' + forecast.current_price) : 'N/A'}</div></div>
                <div class="info-item"><div class="label">30일 후</div><div class="value ${(forecast?.summary?.change_pct || 0) > 0 ? 'positive' : 'negative'}">${formatPrice(forecast?.summary?.predicted_30d_price)}</div></div>
                <div class="info-item"><div class="label">변동률</div><div class="value ${(forecast?.summary?.change_pct || 0) > 0 ? 'positive' : 'negative'}">${forecast?.summary?.change_pct > 0 ? '+' : ''}${forecast?.summary?.change_pct || 0}%</div></div>
                <div class="info-item"><div class="label">추세</div><div class="value">${forecast?.summary?.trend || 'N/A'} ${forecast?.summary?.trend === '상승' ? '📈' : '📉'}</div></div>
            </div>
            <div class="chart-container"><canvas id="forecast-chart"></canvas></div>
        </div>
        <div class="result-section">
            <h3>📋 판단 근거</h3>
            <ul class="key-factors">${(rec.key_factors || []).map(f => '<li>' + f + '</li>').join('')}</ul>
            ${rec.arbitrage_opportunity ? '<div class="report-text" style="margin-top:16px;"><strong>💱 차익 거래:</strong><br>' + rec.arbitrage_opportunity + '</div>' : ''}
        </div>
    `;
}
async function analyzeByImage(file) {
    showLoading();
    
    const formData = new FormData();
    formData.append('image', file);

    try {
        updateLoadingStep(1);
        await delay(500);
        
        const response = await fetch(`${API_BASE}/recommend/analyze`, {
            method: 'POST',
            body: formData,
        });

        updateLoadingStep(2);
        await delay(300);
        updateLoadingStep(3);
        await delay(300);
        updateLoadingStep(4);

        const data = await response.json();
        
        if (data.success) {
            hideLoading();
            renderResults(data.pipeline);
        } else {
            hideLoading();
            showError(data.error || '분석에 실패했습니다.');
        }
    } catch (error) {
        hideLoading();
        showError('서버 연결에 실패했습니다. 서버가 실행 중인지 확인해주세요.');
        console.error(error);
    }
}

// ========== API 호출: 품번 분석 ==========
async function analyzeByCode(styleCode, size = '') {
    showLoading();

    try {
        updateLoadingStep(2);
        
        const body = { style_code: styleCode };
        if (size) body.size = size;

        const response = await fetch(`${API_BASE}/recommend/analyze-by-code`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        updateLoadingStep(3);
        await delay(400);
        updateLoadingStep(4);

        const data = await response.json();

        if (data.success) {
            hideLoading();
            renderResults(data.pipeline);
        } else {
            hideLoading();
            showError(data.error || '분석에 실패했습니다.');
        }
    } catch (error) {
        hideLoading();
        showError('서버 연결에 실패했습니다. 서버가 실행 중인지 확인해주세요.');
        console.error(error);
    }
}

// ========== 결과 렌더링 ==========
function renderResults(pipeline) {
    analysisResults = [pipeline];
    currentResultPage = 0;
    renderPaginatedResults();
}

// ========== 차트 렌더링 ==========
function renderForecastChart(forecast, priceData) {
    const canvas = document.getElementById('forecast-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    
    // 과거 데이터
    const historyData = (priceData?.price_history?.kream || []).reverse();
    const historyLabels = historyData.map(p => p.recorded_date?.slice(5) || '');
    const historyPrices = historyData.map(p => p.price);

    // 예측 데이터
    const predictions = forecast.predictions || [];
    const forecastLabels = predictions.map(p => p.date?.slice(5) || '');
    const forecastPrices = predictions.map(p => p.predicted_price);
    const upperBound = predictions.map(p => p.upper_bound);
    const lowerBound = predictions.map(p => p.lower_bound);

    const allLabels = [...historyLabels, ...forecastLabels];
    const allHistory = [...historyPrices, ...Array(forecastLabels.length).fill(null)];
    const allForecast = [...Array(historyLabels.length).fill(null), ...forecastPrices];
    const allUpper = [...Array(historyLabels.length).fill(null), ...upperBound];
    const allLower = [...Array(historyLabels.length).fill(null), ...lowerBound];

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: allLabels,
            datasets: [
                {
                    label: '실제 가격 (KREAM)',
                    data: allHistory,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                },
                {
                    label: '예측 가격',
                    data: allForecast,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                },
                {
                    label: '상한선',
                    data: allUpper,
                    borderColor: 'rgba(16, 185, 129, 0.3)',
                    backgroundColor: 'rgba(16, 185, 129, 0.05)',
                    borderWidth: 1,
                    fill: '+1',
                    tension: 0.3,
                    pointRadius: 0,
                },
                {
                    label: '하한선',
                    data: allLower,
                    borderColor: 'rgba(16, 185, 129, 0.3)',
                    backgroundColor: 'rgba(16, 185, 129, 0.05)',
                    borderWidth: 1,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#94a3b8',
                        font: { size: 11 },
                        boxWidth: 12,
                    }
                },
                tooltip: {
                    backgroundColor: '#1e293b',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8',
                    borderColor: '#334155',
                    borderWidth: 1,
                    callbacks: {
                        label: (ctx) => {
                            if (ctx.parsed.y === null) return '';
                            return `${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString()}원`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(51, 65, 85, 0.5)' },
                    ticks: {
                        color: '#64748b',
                        font: { size: 10 },
                        maxTicksLimit: 12,
                    }
                },
                y: {
                    grid: { color: 'rgba(51, 65, 85, 0.5)' },
                    ticks: {
                        color: '#64748b',
                        font: { size: 10 },
                        callback: (val) => (val / 10000).toFixed(0) + '만'
                    }
                }
            }
        }
    });
}

// ========== 유틸리티 함수 ==========
function formatPrice(price) {
    if (!price && price !== 0) return 'N/A';
    return Math.round(price).toLocaleString() + '원';
}

function showLoading() {
    loadingOverlay.classList.remove('hidden');
    document.querySelectorAll('.loading-step').forEach(s => {
        s.classList.remove('active', 'done');
    });
}

function hideLoading() {
    loadingOverlay.classList.add('hidden');
}

function updateLoadingStep(step) {
    document.querySelectorAll('.loading-step').forEach(s => {
        const stepNum = parseInt(s.dataset.step);
        if (stepNum < step) {
            s.classList.remove('active');
            s.classList.add('done');
            s.textContent = '✅ ' + s.textContent.replace(/^[^\s]+\s/, '');
        } else if (stepNum === step) {
            s.classList.add('active');
        }
    });
}

function showError(message) {
    resultPanel.innerHTML = `
        <div class="result-placeholder" style="color: var(--danger);">
            <div class="placeholder-icon">⚠️</div>
            <p>${message}</p>
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 12px;">
                서버 실행: <code>cd backend && python app.py</code>
            </p>
        </div>
    `;
}

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// ========== 초기화 ==========
console.log('🚀 SneakerAI 프론트엔드 로드 완료');

// ========== 실시간 인기 스니커즈 ==========
const trendingList = document.getElementById('trending-list');
const trendingSearchInput = document.getElementById('trending-search-input');
const btnTrendingSearch = document.getElementById('btn-trending-search');
const filterBrand = document.getElementById('filter-brand');
const filterSize = document.getElementById('filter-size');
const filterGender = document.getElementById('filter-gender');
const filterSort = document.getElementById('filter-sort');
const btnApplyFilters = document.getElementById('btn-apply-filters');

// 페이지 로드 시 인기 스니커즈 목록 로드
// (navigateTo에서 트리거됨)

btnTrendingSearch.addEventListener('click', () => {
    const query = trendingSearchInput.value.trim();
    if (query) {
        searchTrendingSneakers(query);
    } else {
        loadTrendingSneakers();
    }
});

trendingSearchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        const query = trendingSearchInput.value.trim();
        if (query) {
            searchTrendingSneakers(query);
        } else {
            loadTrendingSneakers();
        }
    }
});

// 필터 적용
btnApplyFilters.addEventListener('click', () => loadTrendingSneakers());
filterBrand.addEventListener('change', () => loadTrendingSneakers());
filterSize.addEventListener('change', () => loadTrendingSneakers());
filterGender.addEventListener('change', () => loadTrendingSneakers());
filterSort.addEventListener('change', () => loadTrendingSneakers());

async function loadTrendingSneakers() {
    trendingList.innerHTML = `
        <div class="trending-loading">
            <div class="spinner"></div>
            <p>인기 스니커즈 목록을 불러오는 중...</p>
        </div>
    `;

    try {
        // 필터 파라미터 구성
        const params = new URLSearchParams({ limit: 15 });
        const brand = filterBrand.value;
        const size = filterSize.value;
        const gender = filterGender.value;
        const sortValue = filterSort.value; // "rank:asc" 형태

        if (brand) params.set('brand', brand);
        if (size) params.set('size', size);
        if (gender) params.set('gender', gender);
        if (sortValue) {
            const [sort, order] = sortValue.split(':');
            params.set('sort', sort);
            params.set('order', order);
        }

        const response = await fetch(`${API_BASE}/trending/popular?${params.toString()}`);
        const data = await response.json();

        if (data.success && data.trending && data.trending.length > 0) {
            if (data.exchange_rate) window._exchangeRate = data.exchange_rate;
            renderTrendingList(data.trending);
        } else if (data.message || data.error) {
            trendingList.innerHTML = `
                <div class="trending-empty">
                    <div class="empty-icon">📭</div>
                    <p>${data.message || data.error}</p>
                    <button class="btn btn-primary" onclick="triggerCollection()" style="margin-top: 16px;">
                        📦 데이터 수집하기
                    </button>
                </div>
            `;
        } else {
            trendingList.innerHTML = `
                <div class="trending-empty">
                    <div class="empty-icon">📭</div>
                    <p>인기 스니커즈 데이터를 가져올 수 없습니다</p>
                    <button class="btn btn-primary" onclick="triggerCollection()" style="margin-top: 16px;">
                        📦 데이터 수집하기
                    </button>
                </div>
            `;
        }
    } catch (error) {
        trendingList.innerHTML = `
            <div class="trending-empty">
                <div class="empty-icon">🔌</div>
                <p>서버에 연결할 수 없습니다</p>
                <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 8px;">
                    서버 실행: <code>cd backend && python app.py</code>
                </p>
            </div>
        `;
        console.error(error);
    }
}

async function searchTrendingSneakers(query) {
    trendingList.innerHTML = `
        <div class="trending-loading">
            <div class="spinner"></div>
            <p>"${query}" 검색 중...</p>
        </div>
    `;

    try {
        const response = await fetch(`${API_BASE}/trending/search?q=${encodeURIComponent(query)}&limit=20`);
        const data = await response.json();

        if (data.success && data.products && data.products.length > 0) {
            const formatted = data.products.map(p => ({
                id: p.id || '',
                title: p.title || '',
                brand: p.brand || '',
                model: p.model || '',
                sku: p.sku || '',
                image: p.image || '',
                release_date: p.release_date || '',
                release_year: (p.release_date || '').slice(0, 4) || 'N/A',
                gender: p.gender || '',
                min_price: p.min_price,
                max_price: p.max_price,
                avg_price: p.avg_price,
                weekly_orders: p.weekly_orders || 0,
                colorway: p.colorway || p.secondary_title || '',
            }));
            renderTrendingList(formatted);
        } else if (data.error) {
            trendingList.innerHTML = `
                <div class="trending-empty">
                    <div class="empty-icon">⚠️</div>
                    <p>${data.error}</p>
                </div>
            `;
        } else {
            trendingList.innerHTML = `
                <div class="trending-empty">
                    <div class="empty-icon">🔍</div>
                    <p>"${query}"에 대한 검색 결과가 없습니다</p>
                </div>
            `;
        }
    } catch (error) {
        trendingList.innerHTML = `
            <div class="trending-empty">
                <div class="empty-icon">🔌</div>
                <p>서버에 연결할 수 없습니다</p>
            </div>
        `;
        console.error(error);
    }
}

function renderTrendingList(items) {
    if (!items || items.length === 0) {
        trendingList.innerHTML = `
            <div class="trending-empty">
                <div class="empty-icon">📭</div>
                <p>조건에 맞는 스니커즈가 없습니다</p>
            </div>
        `;
        return;
    }

    // 전역 저장 (클릭 시 데이터 전달용)
    window._trendingItems = items;

    trendingList.innerHTML = items.map((item, idx) => {
        const title = item.title || item.model_name || '';
        const sku = item.sku || item.style_code || '';
        const brand = item.brand || '';
        const minPrice = item.min_price || item.stockx_price_usd || null;
        const avgPrice = item.avg_price || null;
        const maxPrice = item.max_price || null;
        const year = item.release_year || (item.release_date ? item.release_date.slice(0, 4) : 'N/A');
        const orders = item.weekly_orders ? item.weekly_orders.toLocaleString() : '';
        const rank = item.rank || (idx + 1);
        const imageUrl = item.image || item.image_url || 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAiIGhlaWdodD0iODAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjgwIiBoZWlnaHQ9IjgwIiBmaWxsPSIjMWUyOTNiIi8+PHRleHQgeD0iNDAiIHk9IjQ1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjNjQ3NDhiIiBmb250LXNpemU9IjMwIj7wn5GLPC90ZXh0Pjwvc3ZnPg==';

        // 가격 표시 (StockX 기준)
        const priceMain = minPrice ? `$${minPrice}` : 'N/A';
        const priceKRW = minPrice ? `₩${Math.round(minPrice * (window._exchangeRate || 1380)).toLocaleString()}` : '';
        const priceAvg = avgPrice ? `평균 $${Math.round(avgPrice)}` : '';

        return `
            <div class="trending-card" onclick="analyzeTrendingSneaker('${sku || title}', window._trendingItems[${idx}])">
                <img class="trending-card-image" src="${imageUrl}" alt="${title}" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAiIGhlaWdodD0iODAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjgwIiBoZWlnaHQ9IjgwIiBmaWxsPSIjMWUyOTNiIi8+PHRleHQgeD0iNDAiIHk9IjQ1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjNjQ3NDhiIiBmb250LXNpemU9IjMwIj7wn5GLPC90ZXh0Pjwvc3ZnPg=='">
                <div class="trending-card-info">
                    <div class="trending-card-title">${title}</div>
                    <div class="trending-card-meta">
                        <span class="meta-tag">${brand}</span>
                        ${sku ? `<span class="meta-tag sku">${sku}</span>` : ''}
                        <span class="meta-tag year">📅 ${year}</span>
                        ${item.gender ? `<span class="meta-tag">${item.gender}</span>` : ''}
                    </div>
                </div>
                <div class="trending-card-prices">
                    <div class="trending-card-price">${priceMain}</div>
                    ${priceKRW ? `<div class="trending-card-price-range">${priceKRW}</div>` : ''}
                    ${priceAvg ? `<div class="trending-card-price-range">${priceAvg}</div>` : ''}
                    ${orders ? `<div class="trending-card-orders">🔥 주간 ${orders}건</div>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// ========== 검색 히스토리 ==========
let searchHistory = JSON.parse(localStorage.getItem('sneaker_search_history') || '[]');

function addToHistory(item, resultData) {
    const entry = {
        sku: item.sku || item.style_code || '',
        title: item.title || item.model_name || '',
        price: item.min_price || item.price_usd || 0,
        image: item.image || '',
        timestamp: Date.now(),
        result: resultData || null,  // 분석 결과 저장
    };
    if (!entry.sku && !entry.title) return;

    // 중복 제거
    searchHistory = searchHistory.filter(h => h.sku !== entry.sku);
    searchHistory.unshift(entry);
    searchHistory = searchHistory.slice(0, 10); // 최대 10개
    localStorage.setItem('sneaker_search_history', JSON.stringify(searchHistory));
    renderSearchHistory();
}

function renderSearchHistory() {
    const container = document.getElementById('search-history');
    if (!container || searchHistory.length === 0) {
        if (container) container.innerHTML = '';
        return;
    }

    container.innerHTML = `
        <h4>🕐 최근 검색</h4>
        <div class="history-list">
            ${searchHistory.map(h => `
                <div class="history-item" onclick="reSearchHistory('${h.sku || h.title}')">
                    <span>${h.title || h.sku}</span>
                    ${h.price ? `<span class="history-price">$${h.price}</span>` : ''}
                </div>
            `).join('')}
        </div>
    `;
}

function resetAnalyzer() {
    // 결과 패널 리셋
    resultPanel.innerHTML = `
        <div class="result-placeholder">
            <div class="placeholder-icon">🎯</div>
            <p>분석 결과가 여기에 표시됩니다</p>
        </div>
    `;
    analysisResults = [];
    currentResultPage = 0;
}

function reSearchHistory(query) {
    // 최근 검색 클릭 시 — 저장된 결과 바로 표시 (서버 재호출 없음)
    const cached = searchHistory.find(h => (h.sku === query || h.title === query));
    if (cached && cached.result) {
        analysisResults = [cached.result];
        currentResultPage = 0;
        renderPaginatedResults();
    } else {
        // 캐시 없으면 서버 호출
        styleCodeInput.value = query;
        btnAnalyze.click();
    }
    // 결과 영역 최상단으로 스크롤
    resultPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function analyzeTrendingSneaker(skuOrName, itemData) {
    // 이전 결과 리셋
    resetAnalyzer();

    // 히스토리에 추가
    if (itemData) {
        addToHistory(itemData);
    } else {
        addToHistory({ sku: skuOrName, title: skuOrName });
    }

    // 데이터가 있으면 AI 없이 바로 표시
    if (itemData) {
        navigateTo('analyzer');
        renderQuickResult(itemData);
    } else {
        styleCodeInput.value = skuOrName;
        navigateTo('analyzer');
    }
}

// 페이지 로드 시 히스토리 렌더링
setTimeout(renderSearchHistory, 100);

async function runAiAnalysis(styleCode) {
    if (!styleCode) {
        styleCode = styleCodeInput.value.trim();
    }
    if (!styleCode) return;

    // 버튼 비활성화
    const btns = document.querySelectorAll('[onclick*="runAiAnalysis"]');
    btns.forEach(b => { b.disabled = true; b.textContent = '🔄 AI 분석 중...'; });

    try {
        const response = await fetch(`${API_BASE}/recommend/analyze-by-code`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ style_code: styleCode, use_ai: true }),
        });
        const data = await response.json();
        if (data.success) {
            analysisResults = [data.pipeline];
            currentResultPage = 0;
            renderPaginatedResults();
            // 히스토리 업데이트 (AI 결과 포함)
            addToHistory({ sku: styleCode, title: styleCode }, data.pipeline);
        } else {
            btns.forEach(b => { b.textContent = '❌ 분석 실패'; });
        }
    } catch (e) {
        btns.forEach(b => { b.textContent = '❌ 서버 오류'; });
    }
}

function renderQuickResult(item) {
    const title = item.title || item.model_name || '';
    const brand = item.brand || '';
    const sku = item.sku || item.style_code || '';
    const minPrice = item.min_price || item.price_usd || null;
    const avgPrice = item.avg_price || item.avg_price_usd || null;
    const maxPrice = item.max_price || null;
    const weeklyOrders = item.weekly_orders || 0;
    const image = item.image || '';
    const colorway = item.colorway || '';
    const year = item.release_year || (item.release_date ? item.release_date.slice(0, 4) : 'N/A');
    const releaseDate = item.release_date || '';
    const retailPrice = item.retail_price || 0;
    const priceKRW = item.price_krw || (minPrice ? Math.round(minPrice * (window._exchangeRate || 1380)) : 0);
    const signal = item.buy_signal || '';
    const reason = item.reason || '';
    const trend = item.price_trend || '';

    resultPanel.innerHTML = `
        <div class="product-info-card">
            ${image ? `<div class="product-info-image"><img src="${image}" alt="${title}" onerror="this.parentElement.style.display='none'"></div>` : ''}
            <h3 class="product-info-title">${title}</h3>
            <p class="product-info-subtitle">${colorway}</p>
            <div class="product-info-table">
                <div class="product-info-row"><span class="product-info-label">모델 번호</span><span class="product-info-value">${sku}</span></div>
                <div class="product-info-row"><span class="product-info-label">브랜드</span><span class="product-info-value">${brand}</span></div>
                ${releaseDate ? `<div class="product-info-row"><span class="product-info-label">출시일</span><span class="product-info-value">${releaseDate}</span></div>` : ''}
                ${retailPrice ? `<div class="product-info-row"><span class="product-info-label">출시가</span><span class="product-info-value">$${retailPrice}</span></div>` : ''}
            </div>
        </div>
        <div class="result-section">
            <h3>💰 현재 시세</h3>
            <div class="info-grid">
                ${minPrice ? `<div class="info-item"><div class="label">StockX 최저가</div><div class="value">$${minPrice}</div></div>` : ''}
                ${avgPrice ? `<div class="info-item"><div class="label">StockX 평균가</div><div class="value">$${Math.round(avgPrice)}</div></div>` : ''}
                ${maxPrice ? `<div class="info-item"><div class="label">StockX 최고가</div><div class="value">$${maxPrice}</div></div>` : ''}
                ${priceKRW ? `<div class="info-item"><div class="label">원화 환산 (최저)</div><div class="value">₩${priceKRW.toLocaleString()}<br><span style="font-size:0.7rem;color:var(--text-muted)">환율 ${Math.round(window._exchangeRate || 1380)}원/USD</span></div></div>` : ''}
                ${weeklyOrders ? `<div class="info-item"><div class="label">주간 거래량</div><div class="value">${weeklyOrders.toLocaleString()}건</div></div>` : ''}
            </div>
            ${minPrice && maxPrice ? `<p style="font-size:0.75rem; color:var(--text-muted); margin-top:8px;">사이즈별 가격 범위: $${minPrice} ~ $${maxPrice}</p>` : ''}
        </div>
        ${signal || trend || reason ? `
        <div class="result-section">
            <h3>📊 분석 요약</h3>
            ${signal ? `<div style="text-align:center;margin:12px 0;"><span class="recommendation-badge ${signal === 'BUY' ? 'buy' : 'hold'}">${signal === 'BUY' ? '🟢 매수 (BUY)' : '🟡 보유 (HOLD)'}</span></div>` : ''}
            ${trend ? `<p style="color:var(--text-secondary);">추세: ${trend} ${trend === '상승' ? '📈' : trend === '하락' ? '📉' : '➡️'}</p>` : ''}
            ${reason ? `<p class="report-text">${reason}</p>` : ''}
        </div>` : ''}
        <div style="text-align:center; margin-top:20px;">
            <button class="btn btn-primary" onclick="styleCodeInput.value='${sku}'; btnAnalyze.click();">🔍 AI 상세 분석 실행</button>
        </div>
    `;
}

async function triggerCollection() {
    trendingList.innerHTML = `
        <div class="trending-loading">
            <div class="spinner"></div>
            <p>RapidAPI에서 데이터 수집 중... (30초 정도 소요)</p>
        </div>
    `;

    try {
        const response = await fetch(`${API_BASE}/trending/collect?force=true`, { method: 'POST' });
        const data = await response.json();

        if (data.status === 'success') {
            // 수집 후 목록 다시 로드
            loadTrendingSneakers();
        } else {
            trendingList.innerHTML = `
                <div class="trending-empty">
                    <div class="empty-icon">⚠️</div>
                    <p>${data.error || data.message || '수집에 실패했습니다'}</p>
                </div>
            `;
        }
    } catch (error) {
        trendingList.innerHTML = `
            <div class="trending-empty">
                <div class="empty-icon">🔌</div>
                <p>서버에 연결할 수 없습니다</p>
            </div>
        `;
        console.error(error);
    }
}

// ========== 트렌드 구매 추천 Top 10 ==========
const btnLoadRecs = document.getElementById('btn-load-recommendations');
const recsList = document.getElementById('recommendations-list');

// 페이지 전환 시 자동 로드 (navigateTo에서 트리거됨)
// loadRecommendations();

btnLoadRecs.addEventListener('click', loadRecommendations);

async function loadRecommendations() {
    btnLoadRecs.disabled = true;
    btnLoadRecs.textContent = '🔄 트렌드 분석 중... (30초 소요)';
    recsList.innerHTML = `
        <div class="trending-loading">
            <div class="spinner"></div>
            <p>유튜브/구글 트렌드 분석 + 실시간 가격 조회 중...</p>
        </div>
    `;

    try {
        const response = await fetch(`${API_BASE}/trending/recommendations`);
        const data = await response.json();

        if (data.success && data.recommendations) {
            renderRecommendations(data);
        } else {
            recsList.innerHTML = `
                <div class="trending-empty">
                    <div class="empty-icon">⚠️</div>
                    <p>${data.error || '추천 생성에 실패했습니다'}</p>
                </div>
            `;
        }
    } catch (error) {
        recsList.innerHTML = `
            <div class="trending-empty">
                <div class="empty-icon">🔌</div>
                <p>서버에 연결할 수 없습니다</p>
            </div>
        `;
        console.error(error);
    } finally {
        btnLoadRecs.disabled = false;
        btnLoadRecs.textContent = '🔄 트렌드 새로고침';
    }
}

function renderRecommendations(data) {
    const { trend_analysis, recommendations, generated_at, from_cache } = data;

    // 전역 저장 (클릭 시 데이터 전달용)
    window._recItems = recommendations;

    let html = `
        <div class="result-section" style="margin-bottom: 20px;">
            <h3>📊 시장 트렌드 분석</h3>
            <p class="report-text">${trend_analysis}</p>
            <p style="font-size: 0.7rem; color: var(--text-muted); margin-top: 8px;">
                업데이트: ${generated_at || 'N/A'} ${from_cache ? '(캐시)' : '(신규 생성)'} · 1시간 단위 갱신
            </p>
        </div>
        <div class="trending-list">
    `;

    html += recommendations.map((item, idx) => {
        const priceMain = item.price_usd ? `$${item.price_usd}` : 'N/A';
        const priceKRW = item.price_krw ? `₩${item.price_krw.toLocaleString()}` : '';
        const avgPrice = item.avg_price_usd ? `평균 $${Math.round(item.avg_price_usd)}` : '';
        const signal = item.buy_signal || 'HOLD';
        const signalClass = signal === 'BUY' ? 'positive' : '';
        const signalEmoji = signal === 'BUY' ? '🟢' : '🟡';
        const trendEmoji = item.price_trend === '상승' ? '📈' : (item.price_trend === '하락' ? '📉' : '➡️');
        const imageUrl = item.image || 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAiIGhlaWdodD0iODAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjgwIiBoZWlnaHQ9IjgwIiBmaWxsPSIjMWUyOTNiIi8+PHRleHQgeD0iNDAiIHk9IjQ1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjNjQ3NDhiIiBmb250LXNpemU9IjMwIj7wn5GLPC90ZXh0Pjwvc3ZnPg==';

        return `
            <div class="trending-card" onclick="analyzeTrendingSneaker('${item.style_code || item.model_name}', window._recItems[${idx}])">
                <img class="trending-card-image" src="${imageUrl}" alt="${item.model_name}" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAiIGhlaWdodD0iODAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjgwIiBoZWlnaHQ9IjgwIiBmaWxsPSIjMWUyOTNiIi8+PHRleHQgeD0iNDAiIHk9IjQ1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjNjQ3NDhiIiBmb250LXNpemU9IjMwIj7wn5GLPC90ZXh0Pjwvc3ZnPg=='">
                <div class="trending-card-info">
                    <div class="trending-card-title">
                        <span style="color: var(--accent); font-weight: 700;">#${item.rank}</span> ${item.model_name}
                    </div>
                    <div class="trending-card-meta">
                        <span class="meta-tag">${item.brand}</span>
                        ${item.style_code ? `<span class="meta-tag sku">${item.style_code}</span>` : ''}
                        <span class="meta-tag ${signalClass}">${signalEmoji} ${signal}</span>
                        <span class="meta-tag">${trendEmoji} ${item.price_trend}</span>
                    </div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">
                        ${item.reason}
                    </div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 2px;">
                        출처: ${item.trend_source}
                    </div>
                </div>
                <div class="trending-card-prices">
                    <div class="trending-card-price">${priceMain}</div>
                    ${priceKRW ? `<div class="trending-card-price-range">${priceKRW}</div>` : ''}
                    ${avgPrice ? `<div class="trending-card-price-range">${avgPrice}</div>` : ''}
                    ${item.weekly_orders ? `<div class="trending-card-orders">🔥 주간 ${item.weekly_orders.toLocaleString()}건</div>` : ''}
                </div>
            </div>
        `;
    }).join('');

    html += '</div>';
    recsList.innerHTML = html;
}
