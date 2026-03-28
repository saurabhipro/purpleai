/** @odoo-module **/

// A global, capture-phase event listener is the most robust way to intercept 
// keystrokes in Odoo, surviving any dynamic form state changes or re-renders.
document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') {
        const activeEl = document.activeElement;
        if (!activeEl) return;

        // Verify we are inside one of the chat input areas
        const isChatInput = activeEl.closest('.chat-input-area') || 
            (activeEl.getAttribute('name') && activeEl.getAttribute('name').includes('_chat_input'));

        if (isChatInput) {
            ev.preventDefault();
            ev.stopPropagation();
            ev.stopImmediatePropagation(); // Supercede any Odoo-bound events

            // Find the corresponding 'Send' button purely via DOM traversal
            const stepCard = activeEl.closest('.card');
            if (stepCard) {
                const sendBtn = stepCard.querySelector('button[name="action_chat_step"]');
                if (sendBtn) {
                    sendBtn.click();
                }
            }
        }
    }
}, true);

