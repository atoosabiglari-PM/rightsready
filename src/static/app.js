document.getElementById('analyze-btn').addEventListener('click', async () => {
    const container = document.getElementById('results-container');
    const btn = document.getElementById('analyze-btn');
    // Loading State
    container.className = 'card loading';
    container.replaceChildren();
    const loadingText = document.createElement('p');
    loadingText.textContent = 'Running governed rights analysis…';
    const subLoadingText = document.createElement('p');
    subLoadingText.style.fontSize = '0.9em';
    subLoadingText.textContent = 'Gemini is orchestrating. Deterministic rules remain authoritative.';
    container.append(loadingText, subLoadingText);
    btn.disabled = true;

    try {
        const response = await fetch('/api/analyze', { method: 'POST' });
        if (!response.ok) throw new Error('Analysis failed.');
        const data = await response.json();

        container.className = `card ${data.overall_status === 'CLEARED' ? 'cleared' : 'not-cleared'}`;
        container.replaceChildren();

        // Overall Status
        const statusBanner = document.createElement('div');
        statusBanner.className = 'status-banner';
        statusBanner.textContent = data.overall_status;
        container.appendChild(statusBanner);

        // Governance Designation
        const govCue = document.createElement('div');
        govCue.style.textAlign = 'center';
        govCue.style.fontWeight = 'bold';
        govCue.style.marginBottom = '10px';
        govCue.textContent = 'Authoritative deterministic result';
        container.appendChild(govCue);

        // Summary...
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

        // Decisions...
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

        // Explanation...
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
        container.replaceChildren();
        const heading = document.createElement('div');
        heading.className = 'error-heading';
        heading.textContent = 'Analysis unavailable';
        const msg = document.createElement('div');
        msg.className = 'error-message';
        msg.textContent = 'RightsReady could not complete the governed rights analysis. Please try again.';
        container.append(heading, msg);
    } finally {
        btn.disabled = false;
    }
});

document.getElementById('ask-btn').addEventListener('click', async () => {
    const container = document.getElementById('answer-container');
    const questionInput = document.getElementById('question');
    const question = questionInput.value;
    const btn = document.getElementById('ask-btn');
    const validationMsg = document.getElementById('validation-msg');

    // Validation
    if (!question.trim()) {
        validationMsg.style.display = 'block';
        return;
    }
    validationMsg.style.display = 'none';

    // Loading State
    container.replaceChildren();
    const loadingText = document.createElement('p');
    loadingText.textContent = 'Querying governed rights warehouse…';
    const subLoadingText = document.createElement('p');
    subLoadingText.style.fontSize = '0.9em';
    subLoadingText.textContent = 'Gemini may query ClickHouse through governed MCP.';
    container.append(loadingText, subLoadingText);
    btn.disabled = true;

    try {
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        if (!response.ok) throw new Error('RightsReady could not complete this query.');
        const data = await response.json();

        container.replaceChildren(); // Clear 'Querying...'

        if (data.warehouse_evidence) {
            // Display Evidence Panel
            const panel = document.createElement('div');
            panel.className = 'evidence-panel';

            const header = document.createElement('h3');
            header.textContent = 'Live ClickHouse result';
            panel.appendChild(header);

            const badge = document.createElement('span');
            badge.className = 'source-badge';
            badge.textContent = 'ClickHouse • MCP';
            panel.appendChild(badge);

            // Handle data content (columns/rows rendering)...
            const dataDiv = document.createElement('div');
            dataDiv.className = 'evidence-data';

            if (data.warehouse_evidence.rows.length === 1 && data.warehouse_evidence.rows[0].length === 1) {
                // Scalar result
                const label = document.createElement('div');
                label.style.fontWeight = 'bold';
                label.textContent = data.warehouse_evidence.columns[0];
                const value = document.createElement('div');
                value.style.fontSize = '1.5em';
                value.textContent = data.warehouse_evidence.rows[0][0];
                dataDiv.append(label, value);
            } else {
                // Tabular result
                const table = document.createElement('table');
                table.style.width = '100%';
                const thead = document.createElement('thead');
                const headerRow = document.createElement('tr');
                data.warehouse_evidence.columns.forEach(col => {
                    const th = document.createElement('th');
                    th.textContent = col;
                    headerRow.appendChild(th);
                });
                thead.appendChild(headerRow);
                table.appendChild(thead);

                const tbody = document.createElement('tbody');
                data.warehouse_evidence.rows.forEach(row => {
                    const tr = document.createElement('tr');
                    row.forEach(cell => {
                        const td = document.createElement('td');
                        td.textContent = cell;
                        tr.appendChild(td);
                    });
                    tbody.appendChild(tr);
                });
                table.appendChild(tbody);
                dataDiv.appendChild(table);
            }
            panel.appendChild(dataDiv);
            container.appendChild(panel);

            const govCue = document.createElement('div');
            govCue.className = 'governance-cue';
            govCue.textContent = 'Live data • ClickHouse queried through governed MCP';
            container.appendChild(govCue);
        }

        // Gemini explanation
        const explanation = document.createElement('div');
        explanation.style.marginTop = '20px';
        const h3 = document.createElement('h3');
        h3.textContent = "Gemini explanation";
        const answerDiv = document.createElement('div');
        answerDiv.textContent = data.answer;
        explanation.append(h3, answerDiv);
        container.appendChild(explanation);

    } catch (e) {
        container.replaceChildren();
        const heading = document.createElement('div');
        heading.className = 'error-heading';
        heading.textContent = 'Warehouse query unavailable';
        const msg = document.createElement('div');
        msg.className = 'error-message';
        msg.textContent = 'RightsReady could not complete this query. Please try again.';
        container.append(heading, msg);
    } finally {
        btn.disabled = false;
    }
});
