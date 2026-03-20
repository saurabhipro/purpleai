/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class AIEvidenceViewer extends Component {
    static template = "purpleai.AIEvidenceViewer";
    static props = { ...standardFieldProps };

    setup() {
        this.state = useState({
            data: {},
            selectedKey: null,
            editingKey: null,
            editValue: "",
            commentingKey: null,
            commentValue: "",
            hoveredKey: null,
        });
        this._updateData(this.props);
        this.pdfApp = null;
        this.scrollRequested = false;

        onWillStart(async () => {
            // Pre-process data if needed
        });

        onWillUpdateProps(nextProps => {
            this._updateData(nextProps);
        });
    }

    _updateData(props) {
        const rawValue = props.record.data[props.name];
        if (rawValue) {
            try {
                this.state.data = JSON.parse(rawValue);
            } catch (e) {
                console.error("Failed to parse extracted_data", e);
                this.state.data = {};
            }
        } else {
            this.state.data = {};
        }
    }

    selectRow(key, ev) {
        if (ev) {
            ev.stopPropagation();
            this.scrollRequested = true; // Trigger precision scroll only from table clicks
        }
        if (this.state.editingKey) return; // Don't switch while editing

        this.state.selectedKey = key;
        const val_data = this.state.data[key];
        const val = (val_data && typeof val_data === 'object') ? val_data.value : val_data;
        const page = (val_data && typeof val_data === 'object') ? val_data.page_number : null;

        this.onVerify(val, page);
        this._applyMultiHighlights();
    }

    startEdit(key, val, ev) {
        if (ev) ev.stopPropagation();
        this.state.editingKey = key;
        this.state.editValue = val || "";
        this.state.selectedKey = key;
        this.state.commentingKey = null;
    }

    startComment(key, comment, ev) {
        if (ev) ev.stopPropagation();
        this.state.commentingKey = key;
        this.state.commentValue = comment || "";
        this.state.selectedKey = key;
        this.state.editingKey = null;
    }

    async saveComment() {
        if (!this.state.commentingKey) return;

        const key = this.state.commentingKey;
        const comment = this.state.commentValue;

        const success = await this.props.record.model.orm.call(
            "purple_ai.invoice_processor",
            "update_evidence_comment",
            [this.props.record.resId, key, comment]
        );

        if (success) {
            if (this.state.data[key] && typeof this.state.data[key] === 'object') {
                this.state.data[key].comment = comment;
            } else {
                this.state.data[key] = { value: this.state.data[key], comment: comment, page_number: 1 };
            }
            this.state.commentingKey = null;
            this._applyMultiHighlights();
        }
    }

    cancelComment() {
        this.state.commentingKey = null;
    }

    async saveEdit() {
        if (!this.state.editingKey) return;

        const key = this.state.editingKey;
        const newValue = this.state.editValue;

        // Call backend for persistent save and audit trail
        const success = await this.props.record.model.orm.call(
            "purple_ai.invoice_processor",
            "update_extracted_evidence",
            [[this.props.record.resId], key, newValue]
        );

        if (success) {
            // Update local state for immediate feedback
            if (this.state.data[key] && typeof this.state.data[key] === 'object') {
                this.state.data[key].value = newValue;
            } else {
                this.state.data[key] = newValue;
            }
            this.state.editingKey = null;
            this._applyMultiHighlights();
        }
    }

    cancelEdit() {
        this.state.editingKey = null;
    }

    getFieldIcon(key) {
        const icons = {
            'vendor_name': 'fa-building-o',
            'invoice_number': 'fa-hashtag',
            'invoice_date': 'fa-calendar-o',
            'untaxed_amount': 'fa-money',
            'gst_amount': 'fa-percent',
            'total_amount': 'fa-bank',
            'supplier_gstin': 'fa-id-card-o',
            'vendor_bank_account': 'fa-credit-card',
            'po_number': 'fa-file-text-o',
            'service_type': 'fa-cog'
        };
        return icons[key] || 'fa-tag';
    }

    onMouseEnterRow(key) {
        if (this.state.hoveredKey === key) return;
        this.state.hoveredKey = key;

        const val_data = this.state.data[key];
        const page = (val_data && typeof val_data === 'object') ? val_data.page_number : null;

        // Instant Hover Navigation
        const pdfIframe = document.querySelector('.o_field_pdf_viewer iframe, iframe.o_pdfview_iframe');
        if (pdfIframe && pdfIframe.contentWindow && pdfIframe.contentWindow.PDFViewerApplication) {
            const app = pdfIframe.contentWindow.PDFViewerApplication;
            if (app.initialized && page && app.page !== page) {
                app.page = parseInt(page);
            }
        }

        this.scrollRequested = true; // Signal for the custom scroller to center view
        this._applyMultiHighlights();
    }

    onMouseLeaveRow() {
        if (!this.state.hoveredKey) return;
        this.state.hoveredKey = null;
        this._applyMultiHighlights();
    }

    _applyMultiHighlights() {
        const pdfIframe = document.querySelector('.o_field_pdf_viewer iframe, iframe.o_pdfview_iframe');
        if (!pdfIframe || !pdfIframe.contentDocument) return;

        const app = pdfIframe.contentWindow.PDFViewerApplication;
        if (!app || !app.initialized) return;

        this._injectHighlightStyle(pdfIframe);

        // Listen for page changes/renders to re-apply
        if (!this.auditHooked) {
            app.eventBus.on('pagerendered', () => this._applyMultiHighlights());
            this.auditHooked = true;
        }

        const textLayers = pdfIframe.contentDocument.querySelectorAll('.textLayer');
        textLayers.forEach(layer => {
            const pageDiv = layer.closest('.page');
            const pageNum = pageDiv ? parseInt(pageDiv.dataset.pageNumber) : null;
            if (!pageNum) return;

            // Clear previous overlays and highlights
            const existingOverlay = layer.querySelector('.audit-precision-overlay');
            if (existingOverlay) existingOverlay.innerHTML = '';

            // CRITICAL: Disable PDF.js native search results to prevent "2 yellow shades"
            // This force-hides the internal yellow blobs that PDF.js adds
            const nativeHighlights = layer.querySelectorAll('.highlight');
            nativeHighlights.forEach(nh => {
                nh.style.backgroundColor = 'transparent';
                nh.style.boxShadow = 'none';
                nh.classList.add('native-hidden'); // CSS class to keep it hidden
            });

            // Re-create or find overlay container
            let overlay = layer.querySelector('.audit-precision-overlay');
            if (!overlay) {
                overlay = pdfIframe.contentDocument.createElement('div');
                overlay.className = 'audit-precision-overlay';
                overlay.style.position = 'absolute';
                overlay.style.top = '0';
                overlay.style.left = '0';
                overlay.style.width = '100%';
                overlay.style.height = '100%';
                overlay.style.pointerEvents = 'none';
                overlay.style.zIndex = '10';
                layer.appendChild(overlay);
            }

            const spans = layer.querySelectorAll('span');
            spans.forEach(span => {
                // Remove old direct span highlights to prevent "labels being highlighted"
                span.style.backgroundColor = '';
                span.classList.remove('audit-pink-highlight', 'audit-yellow-highlight');
                const oldTag = span.querySelector('.audit-comment-tag');
                if (oldTag) oldTag.remove();
            });

            // Apply Precision Bounding Boxes
            Object.entries(this.state.data).forEach(([key, val_data]) => {
                if (key === 'validations') return;

                const valObj = (val_data && typeof val_data === 'object');
                // Try preferred 'raw' text if available, fallback to normalized 'value'
                const textToFind = valObj ? (val_data.raw || val_data.value) : val_data;
                const targetPage = valObj ? val_data.page_number : null;

                // Safeguard: Skip empty, whitespace, or placeholder data (like ---)
                if (!textToFind) return;
                const searchStr = textToFind.toString().trim();
                const placeholders = ['---', '--', 'n/a', 'null', 'none', 'not found', 'undefined', '---'];

                if (searchStr.length < 2 ||
                    placeholders.includes(searchStr.toLowerCase()) ||
                    /^[^a-zA-Z0-9]+$/.test(searchStr)) {
                    return;
                }

                if (targetPage && pageNum && targetPage !== pageNum) return;

                const isSelected = this.state.selectedKey === key;
                const isHovered = this.state.hoveredKey === key;
                const friendlyName = key.replace(/_/g, ' ').toUpperCase();

                spans.forEach(span => {
                    const textContent = span.textContent; // Do NOT trim, helps preserve indices
                    if (!textContent || !textContent.trim()) return;

                    const searchStr = textToFind.toString();

                    // Match Strategy: EXACT
                    let idx = textContent.toLowerCase().indexOf(searchStr.toLowerCase());

                    // Match Strategy: FUZZY NUMBER (handles "21 185,60" vs "21185.01")
                    if (idx === -1 && !isNaN(parseFloat(searchStr.replace(/,/g, '')))) {
                        const normContent = textContent.replace(/[^0-9]/g, '');
                        // Match first 5 digits to handle rounding (.01 vs .00)
                        const normSearch = searchStr.replace(/[^0-9]/g, '').slice(0, 5);
                        if (normSearch && normContent && normContent.includes(normSearch)) {
                            const firstDigit = textContent.match(/\d/);
                            if (firstDigit) idx = textContent.indexOf(firstDigit[0]);
                        }
                    }

                    // Match Strategy: FUZZY DATE (handles "2023-06-26" vs "26.06.2023")
                    if (idx === -1 && key.includes('date')) {
                        const dateParts = searchStr.split(/[-./]/);
                        if (dateParts.length === 3) {
                            // Find the most unique part (usually year or day)
                            const day = dateParts[2];
                            const year = dateParts[0];
                            if (textContent.includes(day) && (textContent.includes(year) || textContent.includes(year.slice(-2)))) {
                                idx = textContent.indexOf(day) !== -1 ? textContent.indexOf(day) : 0;
                            }
                        }
                    }

                    if (idx !== -1) {
                        // Create a Range to get the EXACT bounding box of the matching text only
                        const range = pdfIframe.contentDocument.createRange();
                        const textNode = span.firstChild;
                        if (textNode && textNode.nodeType === 3) {
                            try {
                                range.setStart(textNode, idx);
                                range.setEnd(textNode, Math.min(idx + searchStr.length, textContent.length));

                                const rect = range.getBoundingClientRect();
                                const layerRect = layer.getBoundingClientRect();

                                // Calculate position relative to the text layer
                                const top = ((rect.top - layerRect.top) / layerRect.height) * 100;
                                const left = ((rect.left - layerRect.left) / layerRect.width) * 100;
                                const width = (rect.width / layerRect.width) * 100;
                                const height = (rect.height / layerRect.height) * 100;

                                // Create the Precision Bounding Box
                                const box = pdfIframe.contentDocument.createElement('div');
                                box.className = 'audit-box';
                                if (isSelected) box.classList.add('pink-box', 'blink');
                                if (isHovered) box.classList.add('hover-box');
                                if (!isSelected && !isHovered) box.classList.add('yellow-box');

                                box.style.position = 'absolute';
                                box.style.top = `${top}%`;
                                box.style.left = `${left}%`;
                                box.style.width = `calc(${width}% + 4px)`;
                                box.style.height = `calc(${height}% + 4px)`;
                                box.style.marginTop = '-2px';
                                box.style.marginLeft = '-2px';
                                box.style.borderRadius = '3px';
                                box.style.pointerEvents = 'auto'; // Allow interaction
                                box.style.cursor = 'pointer';

                                const comment = valObj ? val_data.comment : null;
                                let hoverTitle = `${friendlyName}: ${searchStr}`;
                                if (comment) hoverTitle += `\nNote: ${comment}`;
                                box.title = hoverTitle;

                                // Bidirectional linking: click box to select row
                                box.onclick = (e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    this.selectRow(key);
                                };

                                if (isSelected || isHovered) {
                                    // Add the Field Tag to the box itself for 100% accuracy
                                    const tag = pdfIframe.contentDocument.createElement('div');
                                    tag.className = 'audit-comment-tag';
                                    tag.textContent = friendlyName;
                                    tag.style.position = 'absolute';
                                    tag.style.top = '-18px';
                                    tag.style.left = '50%';
                                    tag.style.transform = 'translateX(-50%)';
                                    tag.style.backgroundColor = '#db2777';
                                    tag.style.color = '#fff';
                                    tag.style.fontSize = '8px';
                                    tag.style.padding = '1px 6px';
                                    tag.style.borderRadius = '4px';
                                    tag.style.whiteSpace = 'nowrap';
                                    tag.style.zIndex = '110';
                                    box.appendChild(tag);

                                    // Precision Scroller: Bring the selected evidence into the viewport
                                    if (this.scrollRequested) {
                                        this.scrollRequested = false;
                                        setTimeout(() => {
                                            box.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                        }, 100);
                                    }
                                }

                                // Show comment icon if present
                                if (valObj && val_data.comment) {
                                    const commentIcon = pdfIframe.contentDocument.createElement('div');
                                    commentIcon.className = 'audit-comment-icon';
                                    commentIcon.innerHTML = '<i class="fa fa-commenting" style="font-family: FontAwesome; font-size: 8px;"></i>';
                                    commentIcon.style.position = 'absolute';
                                    commentIcon.style.top = '-8px';
                                    commentIcon.style.right = '-8px';
                                    commentIcon.style.backgroundColor = '#2563eb';
                                    commentIcon.style.color = '#fff';
                                    commentIcon.style.borderRadius = '50%';
                                    commentIcon.style.width = '14px';
                                    commentIcon.style.height = '14px';
                                    commentIcon.style.display = 'flex';
                                    commentIcon.style.alignItems = 'center';
                                    commentIcon.style.justifyContent = 'center';
                                    commentIcon.style.boxShadow = '0 2px 4px rgba(0,0,0,0.2)';
                                    commentIcon.style.zIndex = '120';
                                    box.appendChild(commentIcon);
                                }

                                overlay.appendChild(box);
                            } catch (e) {
                                // Fallback to span-level if range fails
                                span.classList.add(isSelected ? 'audit-pink-highlight' : 'audit-yellow-highlight');
                            }
                        }
                    }
                });
            });
        });
    }

    _injectHighlightStyle(pdfIframe) {
        try {
            const doc = pdfIframe.contentDocument;
            if (!doc || doc.getElementById('purple-ai-highlight-style')) return;

            const style = doc.createElement('style');
            style.id = 'purple-ai-highlight-style';
            style.textContent = `
                .textLayer .audit-precision-overlay {
                    pointer-events: none;
                }
                .audit-box {
                    transition: all 0.2s;
                    border: 1px solid transparent;
                }
                .audit-box.yellow-box {
                    background-color: rgba(255, 235, 59, 0.35) !important;
                    border-color: rgba(255, 235, 59, 0.5);
                }
                .audit-box.hover-box {
                    background-color: rgba(99, 102, 241, 0.4) !important;
                    border-color: #6366f1 !important;
                    border-width: 2px !important;
                    z-index: 150 !important;
                    transform: scale(1.05);
                    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
                }
                .audit-box.pink-box {
                    background-color: rgba(255, 0, 127, 0.45) !important;
                    border-color: rgba(255, 0, 127, 0.8);
                    box-shadow: 0 0 10px rgba(255, 0, 127, 0.4);
                    z-index: 100;
                }
                .audit-box.blink {
                    animation: blinkBox 1.5s infinite;
                }
                @keyframes blinkBox {
                    0% { opacity: 1; transform: scale(1); }
                    50% { opacity: 0.7; transform: scale(1.02); }
                    100% { opacity: 1; transform: scale(1); }
                }
                .audit-box.yellow-box:hover {
                    background-color: rgba(255, 235, 59, 0.6) !important;
                    border-color: rgba(255, 235, 59, 1);
                    z-index: 50;
                }
                .audit-comment-tag {
                    animation: popIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                    pointer-events: none;
                    z-index: 110;
                }
                @keyframes popIn {
                    from { transform: scale(0.5) translateX(-50%); opacity: 0; }
                    to { transform: scale(1) translateX(-50%); opacity: 1; }
                }
                .native-hidden {
                    background-color: transparent !important;
                    box-shadow: none !important;
                }
            `;
            doc.head.appendChild(style);
        } catch (e) {
            console.warn("Could not inject custom highlight styles", e);
        }
    }

    async onVerify(searchTerm, page) {
        if (!searchTerm) return;

        // Use a more robust selector for the PDF viewer iframe in Odoo 18
        const pdfIframe = document.querySelector('.o_field_pdf_viewer iframe, iframe.o_pdfview_iframe');

        if (pdfIframe && pdfIframe.contentWindow && pdfIframe.contentWindow.PDFViewerApplication) {
            const app = pdfIframe.contentWindow.PDFViewerApplication;

            if (app.initialized) {
                this._injectHighlightStyle(pdfIframe);

                // Maintain current zoom level instead of forcing page-fit every click
                // This respects the auditor's preferred viewing size
                if (app.pdfViewer && !app.pdfViewer.currentScaleValue) {
                    app.pdfViewer.currentScaleValue = 'page-fit';
                }

                // Change page
                if (page) {
                    app.page = parseInt(page);
                }

                // Execute find command via eventBus
                if (app.eventBus) {
                    app.eventBus.dispatch('find', {
                        caseSensitive: false,
                        findPrevious: false,
                        highlightAll: false,
                        phraseSearch: true,
                        query: searchTerm,
                    });
                }

                // Re-apply custom auditor highlights to ensure the pink tag is synced
                // after the built-in search centers the view
                setTimeout(() => this._applyMultiHighlights(), 300);
            }

            // Visual feedback on the viewer container
            const container = pdfIframe.closest('.o_audit_right_panel') || pdfIframe.closest('.col-lg-7');
            if (container) {
                container.classList.add('highlight-viewer');
                setTimeout(() => container.classList.remove('highlight-viewer'), 1000);
            }
        } else {
            // Fallback for unexpected environments
            console.warn("PDF Viewer iframe not found or inaccessible. Falling back to window.find()");
            window.find(searchTerm);
        }
    }
}

registry.category("fields").add("ai_evidence_viewer", {
    component: AIEvidenceViewer,
});
