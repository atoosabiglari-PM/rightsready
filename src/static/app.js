document.getElementById('analyze-btn').addEventListener('click', () => {
    const container = document.getElementById('results-container');
    container.className = 'card loading';
    container.innerHTML = '<p>Analyzing rights...</p>';
});

document.getElementById('ask-btn').addEventListener('click', () => {
    const container = document.getElementById('answer-container');
    container.innerHTML = '<p>Thinking...</p>';
});
