const DOMAIN = document.currentScript.getAttribute('data-domain');
let allArticles = [];
let selectedArticles = [];
let socket;

document.addEventListener('DOMContentLoaded', function() {
    const apiKey = Cookies.get('omnivoreApiKey');
    const settingsWarning = document.getElementById('settingsWarning');
    const recentLastSection = document.getElementById('recentLastSection');
    const customSelectionSection = document.getElementById('customSelectionSection');

    if (!apiKey) {
        settingsWarning.style.display = 'block';
        recentLastSection.style.display = 'none';
        customSelectionSection.style.display = 'none';
    }

    document.getElementById('recentLastBtn').addEventListener('click', showRecentLast);
    document.getElementById('customSelectionBtn').addEventListener('click', showCustomSelection);
    document.getElementById('pdfForm').addEventListener('submit', function(e) {
        e.preventDefault();
        fetchArticlesAndGeneratePDF();
    });
    document.getElementById('generatePdf').addEventListener('click', generatePdf);
    document.getElementById('searchInput').addEventListener('input', handleSearch);

    // Initialize Socket.IO if it's available
    if (typeof io !== 'undefined') {
        socket = io();
        socket.on('connect', function() {
            console.log('Connected to server');
        });
        socket.on('pdf_progress', function(data) {
            updateProgressBar(data.progress, data.status);
        });
    } else {
        console.warn('Socket.IO is not available. Real-time updates will not work.');
    }
});

function showRecentLast() {
    document.getElementById('recentLastSection').classList.remove('hidden');
    document.getElementById('customSelectionSection').classList.add('hidden');
}

function showCustomSelection() {
    document.getElementById('recentLastSection').classList.add('hidden');
    document.getElementById('customSelectionSection').classList.remove('hidden');
    if (allArticles.length === 0) {
        fetchArticles();
    }
}

function fetchArticles() {
    const apiKey = Cookies.get('omnivoreApiKey');
    if (!apiKey) {
        alert('Please set your API key in the settings.');
        return;
    }

    fetch('/fetch_articles', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            api_key: apiKey,
            page_type: 'article_selection'
        }),
    })
    .then(response => response.json())
    .then(data => {
        allArticles = data.articles;
        displayArticles(allArticles);
    })
    .catch(error => console.error('Error:', error));
}

function displayArticles(articles) {
    const articleList = document.getElementById('articleList');
    articleList.innerHTML = '';
    articles.forEach(article => {
        const articleElement = document.createElement('div');
        articleElement.className = 'article-item';
        articleElement.innerHTML = `
            <input type="checkbox" id="${article.slug}" ${selectedArticles.includes(article.slug) ? 'checked' : ''}>
            <label for="${article.slug}">${article.title}</label>
        `;
        articleElement.querySelector('input').addEventListener('change', (e) => toggleArticle(article.slug, e.target.checked));
        articleList.appendChild(articleElement);
    });
}

function toggleArticle(slug, isSelected) {
    if (isSelected && !selectedArticles.includes(slug)) {
        if (selectedArticles.length < 10) {
            selectedArticles.push(slug);
        } else {
            alert("You can only select up to 10 articles.");
            document.getElementById(slug).checked = false;
            return;
        }
    } else {
        const index = selectedArticles.indexOf(slug);
        if (index > -1) {
            selectedArticles.splice(index, 1);
        }
    }
    updateGenerateButton();
}

function updateGenerateButton() {
    const button = document.getElementById('generatePdf');
    button.textContent = `Generate PDF (${selectedArticles.length} selected)`;
    button.disabled = selectedArticles.length === 0;
}

function generatePdf() {
    const apiKey = Cookies.get('omnivoreApiKey');
    const archive = Cookies.get('omnivoreArchive') === 'true';
    if (!apiKey) {
        alert('Please set your API key in the settings.');
        return;
    }

    const generateButton = document.getElementById('generatePdf');
    generateButton.disabled = true;
    generateButton.textContent = 'Generating...';

    updateProgressBar(0, 'Waiting for server...');

    fetch('/generate_pdf', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            api_key: apiKey, 
            article_slugs: selectedArticles,
            archive: archive
        }),
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw err; });
        }
        const filename = response.headers.get('Content-Disposition').split('filename=')[1].replace(/"/g, '');
        return response.blob().then(blob => ({ blob, filename }));
    })
    .then(({ blob, filename }) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        updateProgressBar(100, 'PDF generated and downloaded successfully!');
    })
    .catch(error => {
        console.error('Error:', error);
        updateProgressBar(100, `Error generating PDF: ${error.error || 'An unexpected error occurred'}`);
    })
    .finally(() => {
        generateButton.disabled = false;
        updateGenerateButton();
    });
}

function fetchArticlesAndGeneratePDF() {
    const apiKey = Cookies.get('omnivoreApiKey');
    const archive = Cookies.get('omnivoreArchive') === 'true';
    const tag = document.getElementById('tag').value;
    const sort = document.getElementById('sort').value;

    updateProgressBar(0, 'Fetching articles...');

    // First, fetch articles
    fetch('/fetch_articles', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            api_key: apiKey, 
            tag: tag, 
            sort: sort
        }),
    })
    .then(response => response.json())
    .then(data => {
        // Now generate PDF with the fetched articles
        return fetch(`${DOMAIN}/generate_pdf`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                api_key: apiKey,
                archive: archive,
                article_slugs: data.articles.map(article => article.slug)
            }),
        });
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw err; });
        }
        const filename = response.headers.get('Content-Disposition').split('filename=')[1].replace(/"/g, '');
        return response.blob().then(blob => ({ blob, filename }));
    })
    .then(({ blob, filename }) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        updateProgressBar(100, 'PDF generated successfully!');
    })
    .catch(error => {
        console.error('Error:', error);
        updateProgressBar(100, `Error: ${error.error || 'An unexpected error occurred. Is your API key correct?'}`);
    });
}

function updateProgressBar(progress, status) {
    let progressContainer = document.getElementById('progressContainer');
    let progressBar = document.getElementById('progressBar');
    let statusText = document.getElementById('statusText');
    
    progressContainer.classList.remove('hidden');
    progressBar.value = progress;
    statusText.innerHTML = `<span class="status-icon">➡️</span> <span class="status-message">${status}</span>`;
    
    if (progress === 100) {
        setTimeout(() => {
            progressContainer.classList.add('hidden');
        }, 5000);  // Hide after 5 seconds
    }
}

function handleSearch(e) {
    const searchTerm = e.target.value.toLowerCase();
    const filteredArticles = allArticles.filter(article => 
        article.title.toLowerCase().includes(searchTerm) || 
        (article.author && article.author.toLowerCase().includes(searchTerm))
    );
    displayArticles(filteredArticles);
}