/**
 * Markdown Search Functionality
 * Highlights text matches in the markdown container
 */

window.highlightSearchText = function(searchText) {
    const container = document.getElementById('markdown_container');
    const countSpan = document.getElementById('search_count');
    
    if (!container) return;
    
    // Remove previous highlights
    const previousHighlights = container.querySelectorAll('mark[data-search-highlight]');
    previousHighlights.forEach(mark => {
        const parent = mark.parentNode;
        while (mark.firstChild) {
            parent.insertBefore(mark.firstChild, mark);
        }
        parent.removeChild(mark);
        parent.normalize();
    });
    
    if (!searchText.trim()) {
        countSpan.textContent = '';
        return;
    }
    
    let count = 0;
    const regex = new RegExp(searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    const walker = document.createTreeWalker(
        container,
        NodeFilter.SHOW_TEXT,
        null,
        false
    );
    
    const nodesToReplace = [];
    let node;
    while (node = walker.nextNode()) {
        if (regex.test(node.textContent)) {
            nodesToReplace.push(node);
        }
    }
    
    regex.lastIndex = 0;
    nodesToReplace.forEach(node => {
        const fragment = document.createDocumentFragment();
        let lastIndex = 0;
        let match;
        
        while ((match = regex.exec(node.textContent)) !== null) {
            count++;
            fragment.appendChild(document.createTextNode(node.textContent.substring(lastIndex, match.index)));
            
            const mark = document.createElement('mark');
            mark.setAttribute('data-search-highlight', 'true');
            mark.style.backgroundColor = '#FFFF00';
            mark.style.color = '#000';
            mark.style.padding = '2px 4px';
            mark.style.borderRadius = '3px';
            mark.textContent = match[0];
            fragment.appendChild(mark);
            
            lastIndex = regex.lastIndex;
        }
        
        fragment.appendChild(document.createTextNode(node.textContent.substring(lastIndex)));
        node.parentNode.replaceChild(fragment, node);
    });
    
    countSpan.textContent = count > 0 ? count + ' match' + (count !== 1 ? 'es' : '') : 'no matches';
    countSpan.style.color = count > 0 ? '#28a745' : '#dc3545';
};

/**
 * Highlight field value in markdown when clicked in AI Evidence Viewer
 * Called from the AI Evidence Viewer when a field row is clicked
 */
window.highlightFieldInMarkdown = function(fieldValue) {
    const searchInput = document.getElementById('markdown_search');
    if (searchInput) {
        searchInput.value = String(fieldValue || '').substring(0, 200);  // Truncate long values
        window.highlightSearchText(searchInput.value);
        
        // Scroll to first match
        const container = document.getElementById('markdown_container');
        const firstHighlight = container ? container.querySelector('mark[data-search-highlight]') : null;
        if (firstHighlight) {
            firstHighlight.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
};

// Listen for evidence viewer row clicks
document.addEventListener('DOMContentLoaded', function() {
    // Set up mutation observer to watch for dynamically added evidence rows
    const evidenceContainer = document.querySelector('.ai-evidence-container');
    if (evidenceContainer) {
        const observer = new MutationObserver(() => {
            setupEvidenceRowListeners();
        });
        observer.observe(evidenceContainer, { childList: true, subtree: true });
    }
    setupEvidenceRowListeners();
});

function setupEvidenceRowListeners() {
    const rows = document.querySelectorAll('tr.evidence-row');
    rows.forEach(row => {
        // Only add listener once
        if (!row.hasAttribute('data-listener-attached')) {
            row.addEventListener('click', function(e) {
                // Extract field value from the row
                const cells = this.querySelectorAll('td, th');
                if (cells.length >= 3) {
                    // Third cell contains the value
                    const valueCell = cells[2];
                    const valueText = valueCell.textContent.trim();
                    
                    if (valueText) {
                        window.highlightFieldInMarkdown(valueText);
                    }
                }
            });
            row.setAttribute('data-listener-attached', 'true');
        }
    });
}

