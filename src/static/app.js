document.getElementById('analyze-btn').addEventListener('click', async () => {
    const container = document.getElementById('results-container');
    container.className = 'card loading';
    container.textContent = 'Analyzing rights...';

    try {
        const response = await fetch('/api/analyze', { method: 'POST' });
        if (!response.ok) throw new Error('Analysis failed.');
        const data = await response.json();
        container.className = 'card neutral';
        container.textContent = data.answer;
    } catch (e) {
        container.className = 'card error';
        container.textContent = `Error: ${e.message}`;
    }
});

document.getElementById('ask-btn').addEventListener('click', async () => {
    const container = document.getElementById('answer-container');
    const question = document.getElementById('question').value;

    if (!question.trim()) {
        alert('Please enter a question.');
        return;
    }

    container.textContent = 'Thinking...';
    try {
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        if (!response.ok) throw new Error('Question processing failed.');
        const data = await response.json();
        container.textContent = data.answer;
    } catch (e) {
        container.textContent = `Error: ${e.message}`;
    }
});
