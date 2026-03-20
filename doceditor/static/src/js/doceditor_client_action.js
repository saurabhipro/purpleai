/** @odoo-module **/

import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

/**
 * DocEditor Client Action - CKEditor 5 implementation with Track Changes support.
 */
export class DocEditor extends Component {
    static template = "doceditor.Editor";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.editorRef = useRef("editor_area");
        this.toolbarRef = useRef("toolbar_container");
        this.documentId = this.props.action.context.active_id || this.props.action.params.document_id;
        this.state = useState({
            document: null,
            isTrackChanges: true,
            trackedChanges: [
                { id: 1, type: 'remove', author: 'Michael West', date: '03-18-2022 04:18PM', comment: 'Remove: "the"' },
                { id: 2, type: 'replace', author: 'John Smith', date: 'Today 11:17AM', comment: 'Insert: "dsdsdsdsd"' },
                { id: 3, type: 'comment', author: 'Michael West', date: 'Today 11:16AM', comment: 'This might be Mr. Lafleur\'s address. Can we double-check?' },
            ],
        });

        onMounted(() => {
            this.initCKEditor5();
            if (this.documentId) {
                this.loadDocument();
            }
        });
    }

    async initCKEditor5() {
        if (typeof DecoupledEditor === 'undefined') {
            const script = document.createElement('script');
            script.src = 'https://cdn.ckeditor.com/ckeditor5/41.2.1/decoupled-document/ckeditor.js';
            script.onload = () => this._startCKEditor5();
            document.head.appendChild(script);
        } else {
            this._startCKEditor5();
        }
    }

    async _startCKEditor5() {
        if (this.ckInstance || !this.editorRef.el) return;

        try {
            const Editor = window.DecoupledEditor || (window.CKSource && window.CKSource.DecoupledEditor);
            if (!Editor) {
                throw new Error("CKEditor 5 DecoupledEditor not found.");
            }

            this.ckInstance = await Editor.create(this.editorRef.el, {
                toolbar: [
                    'undo', 'redo', '|',
                    'heading', '|',
                    'fontFamily', 'fontSize', 'fontColor', 'fontBackgroundColor', '|',
                    'bold', 'italic', 'underline', 'strikethrough', '|',
                    'alignment', '|',
                    'bulletedList', 'numberedList', 'outdent', 'indent', '|',
                    'link', 'insertTable', 'blockQuote'
                ],
                placeholder: 'Type document content here...',
            });

            if (this.toolbarRef.el) {
                this.toolbarRef.el.appendChild(this.ckInstance.ui.view.toolbar.element);
            }

            this.ckInstance.model.document.on('change:data', () => {
                if (this.state.isTrackChanges) { this.updateTrackLog(); }
            });

            if (this.state.document) {
                this.ckInstance.setData(this.state.document.content || "");
            }

            this.ckInstance.editing.view.focus();
        } catch (error) {
            console.error("CKEditor error:", error);
            this.notification.add(`CKEditor Error: ${error.message}`, { type: 'danger' });
        }
    }

    updateTrackLog() {
        if (!this.state.isTrackChanges) return;
        // Efficient mock logging
        const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        this.state.trackedChanges.unshift({
            id: Date.now(),
            type: 'replace',
            author: session.name,
            date: now,
            comment: 'Updating document...'
        });
        if (this.state.trackedChanges.length > 3) this.state.trackedChanges.pop();
    }

    async loadDocument() {
        try {
            const doc = await this.orm.read("doc.document", [parseInt(this.documentId)], ["name", "content"]);
            if (doc && doc.length > 0) {
                this.state.document = doc[0];
                if (this.ckInstance) {
                    this.ckInstance.setData(doc[0].content || "");
                }
            }
        } catch (error) {
            console.error("Failed to load document:", error);
        }
    }

    resolveChange(id, action) {
        this.state.trackedChanges = this.state.trackedChanges.filter(c => c.id !== id);
        this.notification.add(`Change ${action === 'accept' ? 'accepted' : 'rejected'}.`, { type: 'info' });
    }

    async saveDocument() {
        if (!this.ckInstance || !this.documentId) return;
        const content = this.ckInstance.getData();
        try {
            await this.orm.write("doc.document", [parseInt(this.documentId)], { content });
            this.notification.add("Document saved successfully.", { type: 'success' });
        } catch (error) {
            this.notification.add("Error saving document.", { type: 'danger' });
        }
    }

    downloadDocument() {
        if (!this.ckInstance) return;
        const html = this.ckInstance.getData();
        const blob = new Blob([html], { type: 'application/msword' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = (this.state.document?.name || 'document') + '.doc';
        link.click();
    }
}

registry.category("actions").add("doceditor.Editor", DocEditor);
