const DOMAIN = document.currentScript.getAttribute('data-domain');
let allArticles = [];
let selectedArticles = [];
let socket;

function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}

document.addEventListener('DOMContentLoaded', function() {
    const apiKey = Cookies.get('readeckApiKey');
    const readeckUrl = Cookies.get('readeckUrl');
    const settingsWarning = document.getElementById('settingsWarning');
    const recentLastSection = document.getElementById('recentLastSection');
    const customSelectionSection = document.getElementById('customSelectionSection');


    document.getElementById('settingsBtn').addEventListener('click', function () {
        window.location.href = '/settings';
    });

    if (!apiKey || !readeckUrl) {
        settingsWarning.style.display = 'block';
        recentLastSection.style.display = 'none';
        customSelectionSection.style.display = 'none';
    }

    document.getElementById('recentLastBtn').addEventListener('click', showRecentLast);
    document.getElementById('customSelectionBtn').addEventListener('click', showCustomSelection);
    document.getElementById('pdfForm').addEventListener('submit', function(e) {
        e.preventDefault();
        fetchArticlesAndGenerateDocument();
    });
    document.getElementById('generateDocument').addEventListener('click', generateDocument);
    document.getElementById('searchInput').addEventListener('input', handleSearch);

    if (typeof io !== 'undefined') {
        socket = io({
            auth: {
                csrf_token: getCsrfToken()
            }
        });
        socket.on('connect', function() {
            console.log('Connected to server');
        });
        socket.on('document_progress', function(data) {
            updateProgressBar(data.progress, data.status);
        });
    } else {
        console.warn('Socket.IO is not available. Real-time updates will not work.');
    }

    updateGenerateButton();
});

function showRecentLast() {
    document.getElementById('recentLastSection').classList.remove('hidden');
    document.getElementById('customSelectionSection').classList.add('hidden');
    fetchArticles();
}

function showCustomSelection() {
    document.getElementById('recentLastSection').classList.add('hidden');
    document.getElementById('customSelectionSection').classList.remove('hidden');
    if (allArticles.length === 0) {
        fetchArticles();
    }
}

function fetchArticles() {
    const apiKey = Cookies.get('readeckApiKey');
    const readeckUrl = Cookies.get('readeckUrl');

    if (!apiKey || !readeckUrl) {
        alert('Please set your API key and Readeck URL in the settings.');
        return;
    }

    fetch('/fetch_articles', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        credentials: 'same-origin',
        body: JSON.stringify({
            api_key: apiKey,
            readeck_url: readeckUrl,
            page_type: 'article_selection',
            emit_progress: false
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
            <input type="checkbox" id="${article.id}" ${selectedArticles.includes(article.id) ? 'checked' : ''}>
            <label for="${article.id}">${article.title}</label>
        `;
        articleElement.querySelector('input').addEventListener('change', (e) => toggleArticle(article.id, e.target.checked));
        articleList.appendChild(articleElement);
    });
}

function toggleArticle(id, isSelected) {
    if (isSelected && !selectedArticles.includes(id)) {
        if (selectedArticles.length < 10) {
            selectedArticles.push(id);
        } else {
            alert("You can only select up to 10 articles.");
            document.getElementById(id).checked = false;
            return;
        }
    } else {
        const index = selectedArticles.indexOf(id);
        if (index > -1) {
            selectedArticles.splice(index, 1);
        }
    }
    updateGenerateButton();
}

function updateGenerateButton() {
    const button = document.getElementById('generateDocument');
    const outputFormat = 'pdf';
    button.textContent = `Generate ${outputFormat.toUpperCase()} (${selectedArticles.length} selected)`;
    button.disabled = selectedArticles.length === 0;
}

function fetchArticlesAndGenerateDocument() {
    const apiKey = Cookies.get('readeckApiKey');
    const readeckUrl = Cookies.get('readeckUrl');
    const twoColumnLayout = Cookies.get('readeckTwoColumnLayout') === 'true';
    const tag = document.getElementById('tag').value;

    let sortInput = document.getElementById('sort').value;
    let sort = sortInput === 'asc' ? 'created' : '-created';    
    const outputFormat = 'pdf';

    if (!apiKey || !readeckUrl) {
        alert('Please set your API key and Readeck URL in the settings.');
        return;
    }

    updateProgressBar(0, 'Initiating article fetch...');

    fetch('/fetch_articles', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        credentials: 'same-origin',
        body: JSON.stringify({
            api_key: apiKey,
            readeck_url: readeckUrl,
            tag: tag,
            sort: sort
        }),
    })
    .then(response => response.json())
    .then(data => {
        updateProgressBar(25, `Articles fetched. Initiating PDF generation...`);
        return fetch('/generate_document', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                api_key: apiKey,
                readeck_url: readeckUrl,
                article_ids: data.articles.map(article => article.id),
                two_column_layout: twoColumnLayout,
                output_format: outputFormat
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
        updateProgressBar(100, `PDF generated and downloaded successfully!`);
    })
    .catch(error => {
        console.error('Error:', error);
        updateProgressBar(100, `Error: ${error.error || 'An unexpected error occurred. Is your API key correct?'}`);
    });
}

function generateDocument() {
    const apiKey = Cookies.get('readeckApiKey');
    const readeckUrl = Cookies.get('readeckUrl');
    const twoColumnLayout = Cookies.get('readeckTwoColumnLayout') === 'true';

    if (!apiKey || !readeckUrl) {
        alert('Please set your API key and Readeck URL in the settings.');
        return;
    }

    const generateButton = document.getElementById('generateDocument');
    generateButton.disabled = true;
    generateButton.textContent = 'Generating...';

    updateProgressBar(0, 'Waiting for server...');

    fetch('/generate_document', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        credentials: 'same-origin',
        body: JSON.stringify({
            api_key: apiKey,
            readeck_url: readeckUrl,
            article_ids: selectedArticles,
            outputFormat: 'pdf',
            two_column_layout: twoColumnLayout,
            emit_progress: true,
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
        updateProgressBar(100, `PDF generated and downloaded successfully!`);
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
        }, 5000);
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
