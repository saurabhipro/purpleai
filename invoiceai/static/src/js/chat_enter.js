/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";
import { onMounted, onExternalListener } from "@odoo/owl";

// Simple global listener for Enter key on chat inputs
document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        const activeElement = document.activeElement;
        const placeholder = (activeElement.getAttribute('placeholder') || '').toLowerCase();
        if (activeElement && activeElement.tagName === 'INPUT' &&
            (placeholder.includes('message') || placeholder.includes('question'))) {

            // Find the nearest send button
            const container = activeElement.closest('.o_quick_chat_form, .o_form_view');
            if (container) {
                const sendBtn = container.querySelector('button[name="action_send_message"], button[name="action_doc_chat"]');
                if (sendBtn && !sendBtn.disabled && sendBtn.offsetParent !== null) {
                    e.preventDefault();
                    sendBtn.click();
                }
            }
        }
    }
});
