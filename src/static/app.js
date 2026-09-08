document.getElementById('analyze-btn').addEventListener('click', async () => {
    const container = document.getElementById('results-container');
    const btn = document.getElementById('analyze-btn');
    container.className = 'card loading';
    container.textContent = 'Running governed rights analysis…';
    btn.disabled = true;

    try {
        const response = await fetch('/api/analyze', { method: 'POST' });
        if (!response.ok) throw new Error('Analysis failed.');
        const data = await response.json();

        container.className = `card ${data.overall_status === 'CLEARED' ? 'cleared' : 'not-cleared'}`;
        container.replaceChildren(); // Safely clear

        // Overall Status
        const statusBanner = document.createElement('div');
        statusBanner.className = 'status-banner';
        statusBanner.textContent = data.overall_status;
        container.appendChild(statusBanner);

        // Summary
        const summary = document.createElement('div');
        summary.className = 'summary-metrics';

        const totalCard = document.createElement('div');
        totalCard.className = 'metric-card';
        totalCard.textContent = `Total: ${data.summary.total_usages}`;

        const clearedCard = document.createElement('div');
        clearedCard.className = 'metric-card';
        clearedCard.textContent = `Cleared: ${data.summary.cleared}`;

        const blockedCard = document.createElement('div');
        blockedCard.className = 'metric-card';
        blockedCard.textContent = `Blocked: ${data.summary.not_cleared}`;

        summary.append(totalCard, clearedCard, blockedCard);
        container.appendChild(summary);

        // Decisions
        const list = document.createElement('div');
        list.className = 'decision-list';
        data.decisions.forEach(d => {
            const item = document.createElement('div');
            item.className = `decision-item ${d.status === 'CLEARED' ? 'cleared' : 'not-cleared'}`;

            const title = document.createElement('strong');
            title.textContent = `${d.asset_id} - ${d.asset_title || 'Unknown'}`;

            const details = document.createElement('div');
            details.textContent = `Status: ${d.status}`;

            item.append(title, details);

            if (d.status === 'NOT_CLEARED') {
                const reason = document.createElement('div');
                reason.style.fontWeight = 'bold';
                reason.textContent = `Reason: ${d.reason_codes.join(', ')}`;
                item.appendChild(reason);
            }

            list.appendChild(item);
        });
        container.appendChild(list);

        // Governance Cue & Answer
        const cue = document.createElement('div');
        cue.className = 'governance-cue';
        cue.textContent = 'Authoritative result • Deterministic clearance engine';
        container.appendChild(cue);

        const explanation = document.createElement('div');
        explanation.style.marginTop = '20px';
        const h3 = document.createElement('h3');
        h3.textContent = "Gemini explanation";
        const answerDiv = document.createElement('div');
        answerDiv.textContent = data.answer;
        explanation.append(h3, answerDiv);
        container.appendChild(explanation);

    } catch (e) {
        container.className = 'card error';
        container.textContent = `Rights analysis could not be completed.`;
    } finally {
        btn.disabled = false;
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
