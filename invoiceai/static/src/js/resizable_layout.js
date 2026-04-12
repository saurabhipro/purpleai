/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";
import { onMounted } from "@odoo/owl";

patch(FormRenderer.prototype, {
    setup() {
        super.setup();
        onMounted(() => {
            this._setupResizer();
        });
    },

    _setupResizer() {
        const root = this.el || document.querySelector('.o_form_renderer');
        const resizer = root?.querySelector('.o_audit_resizer');
        if (!resizer) return;

        const leftPanel = resizer.previousElementSibling;
        const container = resizer.parentElement;

        let isResizing = false;

        resizer.addEventListener('mousedown', (e) => {
            isResizing = true;
            document.body.style.cursor = 'col-resize';
            resizer.classList.add('active');
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;

            const containerRect = container.getBoundingClientRect();
            const relativeX = e.clientX - containerRect.left;
            const containerWidth = containerRect.width;

            // Calculate percentage (min 20%, max 60%)
            let percentage = (relativeX / containerWidth) * 100;
            percentage = Math.max(20, Math.min(60, percentage));

            leftPanel.style.width = `${percentage}%`;
            leftPanel.style.flex = `0 0 ${percentage}%`;
        });

        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = '';
                resizer.classList.remove('active');
                // Trigger resize to let PDF viewer adjust
                window.dispatchEvent(new Event('resize'));
            }
        });
    }
});
