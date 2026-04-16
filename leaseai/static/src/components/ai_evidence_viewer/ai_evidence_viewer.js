/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Normalise box_2d to [ymin, xmin, ymax, xmax] in 0–1000.
 * Models sometimes emit [xmin, ymin, xmax, ymax]; pick the interpretation that
 * looks like a text run (aligned with extraction prompt + React viewer).
 */
function resolveBox2d(raw) {
    if (!Array.isArray(raw) || raw.length !== 4) {
        return null;
    }
    let a = Number(raw[0]);
    let b = Number(raw[1]);
    let c = Number(raw[2]);
    let d = Number(raw[3]);
    if ([a, b, c, d].some((v) => Number.isNaN(v))) {
        return null;
    }
    if ([a, b, c, d].every((v) => v >= 0 && v <= 1)) {
        a *= 1000;
        b *= 1000;
        c *= 1000;
        d *= 1000;
    }
    function pack(y0, x0, y1, x1) {
        if ([y0, x0, y1, x1].some((v) => v < 0 || v > 1000)) {
            return null;
        }
        if (x1 <= x0 || y1 <= y0) {
            return null;
        }
        if (x1 - x0 > 700 || y1 - y0 > 700) {
            return null;
        }
        const aspect = (x1 - x0) / (y1 - y0);
        return { y0, x0, y1, x1, aspect };
    }
    const optA = pack(a, b, c, d);
    const optB = pack(b, a, d, c);
    function score(o) {
        if (!o) {
            return -1;
        }
        const r = o.aspect;
        if (r >= 0.35 && r <= 10) {
            return 3;
        }
        if (r >= 0.18 && r <= 16) {
            return 2;
        }
        if (r >= 0.06 && r <= 40) {
            return 1;
        }
        return 0;
    }
    const sA = score(optA);
    const sB = score(optB);
    if (optA && !optB) {
        return [optA.y0, optA.x0, optA.y1, optA.x1];
    }
    if (optB && !optA) {
        return [optB.y0, optB.x0, optB.y1, optB.x1];
    }
    if (!optA && !optB) {
        return null;
    }
    if (sB > sA) {
        return [optB.y0, optB.x0, optB.y1, optB.x1];
    }
    if (sA > sB) {
        return [optA.y0, optA.x0, optA.y1, optA.x1];
    }
    return [optA.y0, optA.x0, optA.y1, optA.x1];
}

export class AIEvidenceViewer extends Component {
    static template = "leaseai.AIEvidenceViewer";
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
            hoveredBox2d: null,
            activeTab: 'main',
            editedKeys: [],  // Track which rows have been edited (stay red)\n        });
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

    formatFieldLabel(key) {
        return (key || "").replace(/_/g, " ").toUpperCase();
    }

    getMainSections() {
        return [
            { id: "general", title: "Extracted Lease Data", entries: [] },
            { id: "other", title: "Other Fields", entries: [] },
        ];
    }

    getSectionIdForKey(key) {
        const sectionMap = {
            general: new Set([
                "tenant_name", "landlord_name", "property_address", "unit_number",
                "lease_start_date", "lease_end_date", "lease_term", "rent_amount",
                "deposit_amount", "security_deposit", "payment_frequency",
            ]),
        };
        if (sectionMap.general.has(key)) return "general";
        return "other";
    }

    getGroupedTabEntries() {
        const sections = this.getMainSections();
        const byId = {};
        sections.forEach((section) => {
            byId[section.id] = section;
        });
        Object.entries(this.state.data).forEach(([key, val]) => {
            if (key === "validations") return;
            const sectionId = this.getSectionIdForKey(key);
            byId[sectionId].entries.push([key, val]);
        });
        return sections.filter((section) => section.entries.length);
    }

    setActiveTab(tab) {
        this.state.activeTab = tab;
        this.state.selectedKey = null;
    }

    selectRow(key, ev) {
        if (ev) {
            ev.stopPropagation();
            this.scrollRequested = true;
        }
        if (this.state.editingKey) return;

        this.state.selectedKey = key;
        const val_data = this.state.data[key];
        const val = (val_data && typeof val_data === 'object' && !Array.isArray(val_data)) ? val_data.value : val_data;
        const page = (val_data && typeof val_data === 'object' && !Array.isArray(val_data)) ? val_data.page_number : null;
        const box2d = (val_data && typeof val_data === 'object' && !Array.isArray(val_data)) ? val_data.box_2d : null;

        if (box2d && box2d.length === 4) {
            this._navigateToPage(page);
        } else {
            this.onVerify(val, page);
        }
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
        // For leaseai, comments are optional - just update local state
        const key = this.state.commentingKey;
        const comment = this.state.commentValue;
        if (this.state.data[key] && typeof this.state.data[key] === 'object') {
            this.state.data[key].comment = comment;
        } else {
            this.state.data[key] = { value: this.state.data[key], comment: comment, page_number: 1 };
        }
        this.state.commentingKey = null;
        this._applyMultiHighlights();
    }

    cancelComment() {
        this.state.commentingKey = null;
    }

    async saveEdit() {
        if (!this.state.editingKey) return;
        
        try {
            // For leaseai, edits are local only - no backend persistence
            const key = this.state.editingKey;
            const newValue = this.state.editValue;
            
            if (this.state.data[key] && typeof this.state.data[key] === 'object') {
                this.state.data[key].value = newValue;
            } else {
                this.state.data[key] = newValue;
            }
            
            // Track this row as edited - keep it red permanently
            if (!this.state.editedKeys.includes(key)) {
                this.state.editedKeys.push(key);
            }
            
            // Exit edit mode + keep row visible with red color
            this.state.editingKey = null;
            this.state.selectedKey = key;
            this._applyMultiHighlights();
        } catch (e) {
            console.error('Save failed:', e);
            // Always exit edit mode even if save failed
            this.state.editingKey = null;
        }
    }

    cancelEdit() {
        this.state.editingKey = null;
    }

    getFieldIcon(key) {
        const icons = {
            'tenant_name': 'fa-user',
            'landlord_name': 'fa-building-o',
            'property_address': 'fa-map-marker',
            'unit_number': 'fa-hashtag',
            'lease_start_date': 'fa-calendar-o',
            'lease_end_date': 'fa-calendar-o',
            'lease_term': 'fa-clock-o',
            'rent_amount': 'fa-money',
            'deposit_amount': 'fa-bank',
            'security_deposit': 'fa-shield',
            'payment_frequency': 'fa-repeat',
        };
        return icons[key] || 'fa-tag';
    }

    formatValue(val) {
        if (val === null || val === undefined) return '---';
        if (Array.isArray(val)) {
            return val.join(', ');
        }
        if (typeof val === 'object') return JSON.stringify(val);
        return String(val);
    }

    itemToString(item) {
        if (item === null || item === undefined) return '—';
        if (typeof item !== 'object') return String(item);
        try {
            return Object.entries(item).map(([k, v]) => `${k}:${v}`).join(' ');
        } catch (e) {
            return String(item);
        }
    }

    getBooleanState(val) {
        if (typeof val === "boolean") {
            return val ? "true" : "false";
        }
        const text = String(val ?? "").trim().toLowerCase();
        if (["true", "1", "yes", "y"].includes(text)) {
            return "true";
        }
        if (["false", "0", "no", "n"].includes(text)) {
            return "false";
        }
        return null;
    }

    onMouseEnterRow(key) {
        if (this.state.hoveredKey === key) return;
        this.state.hoveredKey = key;

        const val_data = this.state.data[key];
        const page = (val_data && typeof val_data === 'object' && !Array.isArray(val_data)) ? val_data.page_number : null;

        this._navigateToPage(page);
        this.scrollRequested = true;
        this._applyMultiHighlights();
    }

    onMouseLeaveRow() {
        if (!this.state.hoveredKey) return;
        this.state.hoveredKey = null;
        this._applyMultiHighlights();
    }

    _navigateToPage(page) {
        if (!page) return;
        const pdfIframe = document.querySelector('.o_field_pdf_viewer iframe, iframe.o_pdfview_iframe');
        if (!pdfIframe || !pdfIframe.contentWindow) return;
        const app = pdfIframe.contentWindow.PDFViewerApplication;
        if (app && app.initialized && app.page !== parseInt(page)) {
            app.page = parseInt(page);
        }
    }

    _applyMultiHighlights() {
        const pdfIframe = document.querySelector('.o_field_pdf_viewer iframe, iframe.o_pdfview_iframe');
        if (!pdfIframe || !pdfIframe.contentDocument) return;

        const app = pdfIframe.contentWindow.PDFViewerApplication;
        if (!app || !app.initialized) return;

        this._injectHighlightStyle(pdfIframe);

        if (!this.auditHooked) {
            app.eventBus.on('pagerendered', () => this._applyMultiHighlights());
            this.auditHooked = true;
        }

        const textLayers = pdfIframe.contentDocument.querySelectorAll('.textLayer');
        textLayers.forEach(layer => {
            const pageDiv = layer.closest('.page');
            const pageNum = pageDiv ? parseInt(pageDiv.dataset.pageNumber) : null;
            if (!pageNum) return;

            const existingOverlay = layer.querySelector('.audit-precision-overlay');
            if (existingOverlay) existingOverlay.innerHTML = '';

            const nativeHighlights = layer.querySelectorAll('.highlight');
            nativeHighlights.forEach(nh => {
                nh.style.backgroundColor = 'transparent';
                nh.style.boxShadow = 'none';
                nh.classList.add('native-hidden');
            });

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
                span.style.backgroundColor = '';
                span.classList.remove('audit-pink-highlight', 'audit-yellow-highlight');
                const oldTag = span.querySelector('.audit-comment-tag');
                if (oldTag) oldTag.remove();
            });

            Object.entries(this.state.data).forEach(([key, val_data]) => {
                if (key === 'validations') return;

                const valObj = (val_data && typeof val_data === 'object' && !Array.isArray(val_data));
                const rawValue = valObj ? (val_data.raw || val_data.value) : val_data;

                if (Array.isArray(rawValue)) return;
                
                // SKIP PLACEHOLDER VALUES - Don't highlight missing/empty data
                const PLACEHOLDER_VALUES = [
                    '', '--', '—', '–', 'n/a', 'na', 'not applicable',
                    'not found', 'not available', 'not mentioned',
                    'none', 'null', 'nil'
                ];
                const valueStr = (rawValue || '').toString().trim().toLowerCase();
                if (PLACEHOLDER_VALUES.includes(valueStr)) {
                    return; // Skip highlighting for placeholder values
                }

                const isSelected = this.state.selectedKey === key;
                const isHovered = this.state.hoveredKey === key;
                const targetPage = valObj ? val_data.page_number : null;
                const box2d = valObj ? val_data.box_2d : null;
                const friendlyName = key.replace(/_/g, ' ').toUpperCase();

                if (box2d && Array.isArray(box2d) && box2d.length === 4) {
                    if (targetPage && targetPage !== pageNum) return;

                    const resolved = resolveBox2d(box2d);
                    if (!resolved) {
                        return;
                    }
                    const [y0, x0, y1, x1] = resolved;

                    const box = pdfIframe.contentDocument.createElement('div');
                    box.className = 'audit-box';
                    if (isSelected) box.classList.add('pink-box', 'blink');
                    if (isHovered) box.classList.add('hover-box');
                    if (!isSelected && !isHovered) box.classList.add('yellow-box');

                    box.style.position = 'absolute';
                    box.style.top = `calc(${y0 / 10}% - 2px)`;
                    box.style.left = `calc(${x0 / 10}% - 3px)`;
                    box.style.width = `calc(${(x1 - x0) / 10}% + 6px)`;
                    box.style.height = `calc(${(y1 - y0) / 10}% + 4px)`;
                    box.style.borderRadius = '3px';
                    box.style.pointerEvents = 'auto';
                    box.style.cursor = 'pointer';
                    box.title = `${friendlyName}: ${rawValue || ''}`;

                    box.onclick = (e) => { e.preventDefault(); e.stopPropagation(); this.selectRow(key); };

                    if (isSelected || isHovered) {
                        const tag = pdfIframe.contentDocument.createElement('div');
                        tag.className = 'audit-comment-tag';
                        tag.textContent = friendlyName;
                        tag.style.cssText = 'position:absolute;top:-18px;left:50%;transform:translateX(-50%);background:#db2777;color:#fff;font-size:8px;padding:1px 6px;border-radius:4px;white-space:nowrap;z-index:110;pointer-events:none;';
                        box.appendChild(tag);

                        if (this.scrollRequested) {
                            this.scrollRequested = false;
                            setTimeout(() => box.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100);
                        }
                    }

                    overlay.appendChild(box);
                    return;
                }

                const textToFind = rawValue;

                if (!textToFind) return;
                const searchStr = textToFind.toString().trim();
                const placeholders = ['---', '--', 'n/a', 'null', 'none', 'not found', 'undefined', '---'];

                if (searchStr.length < 2 ||
                    placeholders.includes(searchStr.toLowerCase()) ||
                    /^[^a-zA-Z0-9]+$/.test(searchStr)) {
                    return;
                }

                if (targetPage && pageNum && targetPage !== pageNum) return;

                spans.forEach(span => {
                    const textContent = span.textContent;
                    if (!textContent || !textContent.trim()) return;

                    const searchStr = textToFind.toString();

                    let idx = textContent.toLowerCase().indexOf(searchStr.toLowerCase());

                    if (idx === -1 && !isNaN(parseFloat(searchStr.replace(/,/g, '')))) {
                        const normContent = textContent.replace(/[^0-9]/g, '');
                        const normSearch = searchStr.replace(/[^0-9]/g, '').slice(0, 5);
                        if (normSearch.length >= 4 && normContent && normContent.includes(normSearch)) {
                            const firstDigit = textContent.match(/\d/);
                            if (firstDigit) idx = textContent.indexOf(firstDigit[0]);
                        }
                    }

                    if (idx === -1 && key.includes('date')) {
                        const dateParts = searchStr.split(/[-./]/);
                        if (dateParts.length === 3) {
                            const day = dateParts[2];
                            const year = dateParts[0];
                            if (textContent.includes(day) && (textContent.includes(year) || textContent.includes(year.slice(-2)))) {
                                idx = textContent.indexOf(day) !== -1 ? textContent.indexOf(day) : 0;
                            }
                        }
                    }

                    if (idx !== -1) {
                        const range = pdfIframe.contentDocument.createRange();
                        const textNode = span.firstChild;
                        if (textNode && textNode.nodeType === 3) {
                            try {
                                range.setStart(textNode, idx);
                                range.setEnd(textNode, Math.min(idx + searchStr.length, textContent.length));

                                const rect = range.getBoundingClientRect();
                                const layerRect = layer.getBoundingClientRect();

                                const isNumericMatch = !isNaN(parseFloat(searchStr.replace(/[,\u20b9$\s]/g, '')));
                                const finalRect = isNumericMatch ? span.getBoundingClientRect() : rect;

                                const top = ((finalRect.top - layerRect.top) / layerRect.height) * 100;
                                const left = ((finalRect.left - layerRect.left) / layerRect.width) * 100;
                                const width = (finalRect.width / layerRect.width) * 100;
                                const height = (finalRect.height / layerRect.height) * 100;

                                const box = pdfIframe.contentDocument.createElement('div');
                                box.className = 'audit-box';
                                if (isSelected) box.classList.add('pink-box', 'blink');
                                if (isHovered) box.classList.add('hover-box');
                                if (!isSelected && !isHovered) box.classList.add('yellow-box');

                                box.style.position = 'absolute';
                                box.style.top = `${top}%`;
                                box.style.left = `${left}%`;
                                box.style.width = `calc(${width}% + 10px)`;
                                box.style.height = `calc(${height}% + 8px)`;
                                box.style.marginTop = '-4px';
                                box.style.marginLeft = '-5px';
                                box.style.borderRadius = '3px';
                                box.style.pointerEvents = 'auto';
                                box.style.cursor = 'pointer';

                                const comment = valObj ? val_data.comment : null;
                                let hoverTitle = `${friendlyName}: ${searchStr}`;
                                if (comment) hoverTitle += `\nNote: ${comment}`;
                                box.title = hoverTitle;

                                box.onclick = (e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    this.selectRow(key);
                                };

                                if (isSelected || isHovered) {
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

                                    if (this.scrollRequested) {
                                        this.scrollRequested = false;
                                        setTimeout(() => {
                                            box.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                        }, 100);
                                    }
                                }

                                overlay.appendChild(box);
                            } catch (e) {
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

        const pdfIframe = document.querySelector('.o_field_pdf_viewer iframe, iframe.o_pdfview_iframe');

        if (pdfIframe && pdfIframe.contentWindow && pdfIframe.contentWindow.PDFViewerApplication) {
            const app = pdfIframe.contentWindow.PDFViewerApplication;

            if (app.initialized) {
                this._injectHighlightStyle(pdfIframe);

                if (app.pdfViewer && !app.pdfViewer.currentScaleValue) {
                    app.pdfViewer.currentScaleValue = 'page-fit';
                }

                if (page) {
                    app.page = parseInt(page);
                }

                if (app.eventBus) {
                    app.eventBus.dispatch('find', {
                        caseSensitive: false,
                        findPrevious: false,
                        highlightAll: false,
                        phraseSearch: true,
                        query: searchTerm,
                    });
                }

                setTimeout(() => this._applyMultiHighlights(), 300);
            }

            const container = pdfIframe.closest('.o_audit_right_panel') || pdfIframe.closest('.col-lg-7');
            if (container) {
                container.classList.add('highlight-viewer');
                setTimeout(() => container.classList.remove('highlight-viewer'), 1000);
            }
        } else {
            console.warn("PDF Viewer iframe not found or inaccessible. Falling back to window.find()");
            window.find(searchTerm);
        }
    }
}

registry.category("fields").add("ai_evidence_viewer", {
    component: AIEvidenceViewer,
});
