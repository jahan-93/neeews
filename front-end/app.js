const API_BASE_URL = "http://localhost:8000";
let currentSource = "전체";

// ── 유틸 ────────────────────────────────────────────────────────────────────

function timeAgo(pubDateStr) {
    const date = new Date(pubDateStr);
    if (isNaN(date)) return "";
    const diff = Math.floor((Date.now() - date.getTime()) / 1000);
    if (diff < 60)    return "방금 전";
    if (diff < 3600)  return `${Math.floor(diff / 60)}분 전`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
    return `${Math.floor(diff / 86400)}일 전`;
}

// ── 초기화 ─────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    fetchNews("전체");
    fetchKeywords("전체");
});

// ── 뉴스 카드 렌더링 ────────────────────────────────────────────────────────

async function fetchNews(source = "전체") {
    currentSource = source;

    document.querySelectorAll(".src-link").forEach(a => {
        a.classList.toggle("active", a.textContent.trim() === source);
    });

    const gridContainer = document.getElementById("news-grid-container");
    gridContainer.innerHTML = '<div class="loading">뉴스를 불러오는 중입니다...</div>';

    try {
        const res = await fetch(`${API_BASE_URL}/news?source=${encodeURIComponent(source)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        gridContainer.innerHTML = "";

        if (!data.articles || data.articles.length === 0) {
            gridContainer.innerHTML =
                '<div style="grid-column:1/-1;text-align:center;padding:50px;color:#888;">해당 언론사의 뉴스가 없습니다.</div>';
            return;
        }

        data.articles.forEach(article => {
            const item = {
                title:      article.title,
                link:       article.link,
                source:     article.source,
                category:   article.category,
                date:       timeAgo(article.pub_date),
                img:        article.image_url || "",
                summary:    article.description,
                paragraphs: article.paragraphs,
            };

            const card = document.createElement("div");
            card.className = "news-card";
            card.onclick = () => openModal(item);

            const imgHtml = item.img
                ? `<img src="${item.img}" alt="뉴스 이미지" class="news-img" loading="lazy">`
                : `<div class="news-img" style="background:linear-gradient(135deg,#e7f5ff,#d0ebff);"></div>`;

            card.innerHTML = `
                ${imgHtml}
                <div class="news-content">
                    <span class="news-category">${item.source}</span>
                    <h4 class="news-title">${item.title}</h4>
                    <p class="news-summary">${item.summary}</p>
                    <div class="news-meta">
                        <span class="news-date">${item.date}</span>
                    </div>
                </div>`;

            gridContainer.appendChild(card);
        });

    } catch (e) {
        gridContainer.innerHTML = `
            <div style="grid-column:1/-1;text-align:center;padding:50px;color:#888;">
                <p style="font-size:1rem;">뉴스를 불러오지 못했습니다.</p>
                <p style="font-size:0.85rem;margin-top:5px;color:#adb5bd;">
                    백엔드 서버(http://localhost:8000)가 실행 중인지 확인해주세요.
                </p>
                <button onclick="fetchNews('${currentSource}')"
                    style="margin-top:15px;padding:8px 20px;background:#1c7ed6;color:#fff;
                           border:none;border-radius:6px;cursor:pointer;font-size:0.9rem;">
                    다시 시도
                </button>
            </div>`;
    }
}

function filterSource(source) {
    fetchNews(source);
    fetchKeywords(source);
}

// ── 키워드 랭킹 ─────────────────────────────────────────────────────────────

async function fetchKeywords(source = "전체") {
    const listEl = document.getElementById("keyword-ranking");
    listEl.innerHTML = '<li><span class="rank">—</span> <span class="kw-text">분석 중...</span></li>';

    try {
        const res = await fetch(`${API_BASE_URL}/keywords?source=${encodeURIComponent(source)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!data.keywords || data.keywords.length === 0) {
            listEl.innerHTML = '<li><span class="rank">—</span> <span class="kw-text">키워드 없음</span></li>';
            return;
        }

        listEl.innerHTML = data.keywords
            .map((item, i) => `
                <li>
                    <span class="rank">${i + 1}</span>
                    <span class="kw-text">${item.keyword}</span>
                    <span class="kw-count">${item.count}</span>
                </li>`)
            .join("");
    } catch {
        listEl.innerHTML = '<li><span class="rank">—</span> <span class="kw-text">불러오기 실패</span></li>';
    }
}

// ── 모달 ────────────────────────────────────────────────────────────────────

function openModal(item) {
    document.getElementById("modal-source").innerText = item.source;
    const catEl = document.getElementById("modal-category");
    catEl.textContent = item.category || "";
    catEl.style.display = item.category ? "inline-block" : "none";
    document.getElementById("modal-date").innerText = item.date;
    document.getElementById("modal-title").innerText  = item.title;
    document.getElementById("modal-summary").innerText = item.summary;

    const fullTextEl = document.getElementById("modal-full-text");
    if (item.paragraphs && item.paragraphs.length > 0) {
        fullTextEl.innerHTML = item.paragraphs
            .map(p => `<p style="margin-bottom:14px;line-height:1.8;">${p}</p>`)
            .join("");
    } else {
        fullTextEl.innerText = item.summary || "본문 내용이 없습니다.";
    }

    document.getElementById("modal-link").href = item.link || "#";
    document.getElementById("news-modal").classList.add("active");
    document.body.style.overflow = "hidden";
}

function closeModal() {
    document.getElementById("news-modal").classList.remove("active");
    document.body.style.overflow = "";
}

window.onclick = function (event) {
    const modal = document.getElementById("news-modal");
    if (event.target === modal) closeModal();
};
