const API_BASE_URL = "http://localhost:8000";
let currentCategory = "전체";

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
});

// ── 뉴스 카드 렌더링 ────────────────────────────────────────────────────────

async function fetchNews(category = "전체") {
    currentCategory = category;

    // 카테고리 탭 활성화
    document.querySelectorAll(".cat-link").forEach(a => {
        const label = a.textContent.trim();
        a.classList.toggle("active", label === category);
    });

    const gridContainer = document.getElementById("news-grid-container");
    gridContainer.innerHTML = '<div class="loading">뉴스를 불러오는 중입니다...</div>';

    try {
        const res = await fetch(`${API_BASE_URL}/news?category=${encodeURIComponent(category)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        gridContainer.innerHTML = "";

        if (!data.articles || data.articles.length === 0) {
            gridContainer.innerHTML =
                '<div style="grid-column:1/-1;text-align:center;padding:50px;color:#888;">해당 카테고리의 뉴스가 없습니다.</div>';
            return;
        }

        data.articles.forEach(article => {
            const item = {
                title:      article.title,
                link:       article.link,
                category:   article.category,
                source:     "연합뉴스",
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
                    <span class="news-category">${item.category}</span>
                    <h4 class="news-title">${item.title}</h4>
                    <p class="news-summary">${item.summary}</p>
                    <div class="news-meta">
                        <span class="news-source">${item.source}</span>
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
                <button onclick="fetchNews('${currentCategory}')"
                    style="margin-top:15px;padding:8px 20px;background:#1c7ed6;color:#fff;
                           border:none;border-radius:6px;cursor:pointer;font-size:0.9rem;">
                    다시 시도
                </button>
            </div>`;
    }
}

function filterCategory(category) {
    fetchNews(category);
}

// ── 모달 ────────────────────────────────────────────────────────────────────

function openModal(item) {
    document.getElementById("modal-source").innerText = item.source || "연합뉴스";
    document.getElementById("modal-date").innerText   = item.date;
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
