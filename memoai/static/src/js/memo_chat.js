/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";
import { onMounted } from "@odoo/owl";

/**
 * Patching FormRenderer to add Enter key support for AI chat inputs.
 * Uses a much simpler and more direct approach to ensure it works in all conditions.
 */
patch(FormRenderer.prototype, {
    setup() {
        super.setup();
        onMounted(() => {
            const el = this.root && this.root.el;
            if (el) {
                // Attach a single listener to the form root
                el.addEventListener('keydown', (ev) => {
                    if (ev.key === 'Enter') {
                        // Check if focused element is a chat input
                        const activeEl = document.activeElement;
                        if (!activeEl) return;

                        // Identify the chat input area specifically
                        const isChat = activeEl.closest('.chat-input-area') ||
                            activeEl.getAttribute('name')?.includes('_chat_input');

                        if (isChat) {
                            ev.preventDefault();
                            ev.stopPropagation();

                            // Find the button within the same section and click it
                            const stepCard = activeEl.closest('.card');
                            if (stepCard) {
                                const btn = stepCard.querySelector('button[name="action_chat_step"]');
                                if (btn) {
                                    btn.click();
                                }
                            }
                        }
                    }
                }, true); // Capture phase is critical
            }
        });
    }
});
