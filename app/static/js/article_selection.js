let allArticles = [];
let selectedArticles = [];
let socket = io();

document.addEventListener('DOMContentLoaded', function() {
    const apiKey = Cookies.get('omnivoreApiKey');
    const settingsWarning = document.getElementById('settingsWarning');
    const articleSelectionContainer = document.getElementById('articleSelectionContainer');

    if (!apiKey) {
        settingsWarning.style.display = 'block';
        articleSelectionContainer.style.display = 'none';
    } else {
        fetchArticles();
    }

    socket.on('connect', function() {
        console.log('Connected to server');
    });

    socket.on('pdf_progress', function(data) {
        updateProgressBar(data.progress, data.status);
    });

    document.getElementById('generatePdf').addEventListener('click', generatePdf);
    document.getElementById('searchInput').addEventListener('input', handleSearch);
});

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
    articleList.innerHTML = ''; // Clear existing articles
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
    if (!apiKey) {
        alert('Please set your API key in the settings.');
        return;
    }

    const generateButton = document.getElementById('generatePdf');
    generateButton.disabled = true;
    generateButton.textContent = 'Generating...';

    // Show progress bar immediately
    updateProgressBar(0, 'Waiting for server...');

    fetch('/generate_pdf', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            api_key: apiKey, 
            article_slugs: selectedArticles
        }),
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw err; });
        }
        return response.blob();
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = 'Omnivore_Selected_Articles.pdf';
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

function updateProgressBar(progress, status) {
    let progressContainer = document.getElementById('progressContainer');
    let progressBar = document.getElementById('progressBar');
    let statusText = document.getElementById('statusText');
    
    if (!progressContainer) {
        progressContainer = document.createElement('div');
        progressContainer.id = 'progressContainer';
        document.getElementById('generatePdf').insertAdjacentElement('afterend', progressContainer);
        
        progressBar = document.createElement('progress');
        progressBar.id = 'progressBar';
        progressBar.max = 100;
        progressContainer.appendChild(progressBar);
        
        statusText = document.createElement('p');
        statusText.id = 'statusText';
        progressContainer.appendChild(statusText);
    }
    
    progressBar.value = progress;
    statusText.innerHTML = `<span class="status-icon">➡️</span> <span class="status-message">${status}</span>`;
    progressContainer.style.display = 'block';
    
    if (progress === 100) {
        setTimeout(() => {
            progressContainer.style.display = 'none';
        }, 5000);  // Display for 5 seconds after completion
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