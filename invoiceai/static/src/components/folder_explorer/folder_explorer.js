/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class FolderExplorer extends Component {
    static template = "invoiceai.FolderExplorer";
    static components = {};

    setup() {
        this.state = useState({
            currentPath: "",
            contents: [],
            breadcrumbs: [],
            isLoading: true,
            isDragging: false,
            selectedFile: null,
            error: null,
            rootName: "Home",
            selectedPaths: new Set(),
        });
        this.notification = useService("notification");
        this.dialogService = useService("dialog");
        this.companyService = useService("company");

        // onWillStart: first paint
        onWillStart(async () => {
            try {
                await this.loadFolder("");
            } catch (err) {
                console.error("Critical error in FolderExplorer onWillStart:", err);
                this.state.error = "Failed to initialize: " + err.message;
                this.state.isLoading = false;
            }
        });

        // onMounted: always reload root when the view becomes active
        // This ensures a company switch is picked up immediately
        onMounted(async () => {
            try {
                await this.loadFolder("");
            } catch (err) {
                console.error("FolderExplorer onMounted reload error:", err);
            }
        });
    }

    async loadFolder(path) {
        this.state.isLoading = true;
        this.state.error = null;
        this.state.selectedFile = null; // Clear preview on navigation
        this.state.selectedPaths.clear(); // Clear selections on navigation
        try {
            const result = await rpc("/purple_ai/list_folder", {
                folder_path: path,
                active_company_ids: this.companyService.activeCompanyIds,
            });
            if (result.status === "success") {
                this.state.contents = result.contents;
                this.state.currentPath = result.current_path;
                this.state.rootName = result.root_name;
                this._updateBreadcrumbs(result.current_path, result.root_name);
            } else {
                this.state.error = result.message;
            }
        } catch (err) {
            console.error("Folder Explorer RPC Error:", err);
            this.state.error = "Failed to communicate with server. Check console for details.";
        } finally {
            this.state.isLoading = false;
        }
    }

    _updateBreadcrumbs(path, rootName) {
        const parts = path.split("/").filter(p => p);
        const crumbs = [{ name: rootName, path: "" }];
        let current = "";
        for (const p of parts) {
            current += (current ? "/" : "") + p;
            crumbs.push({ name: p, path: current });
        }
        this.state.breadcrumbs = crumbs;
    }

    onItemClick(item) {
        if (item.is_dir) {
            this.loadFolder(item.path);
        } else {
            this.state.selectedFile = item;
        }
    }

    onDownload(item) {
        window.open(`/purple_ai/download_file?file_path=${encodeURIComponent(item.path)}`, "_blank");
    }

    async onFileDrop(ev) {
        this.state.isDragging = false;
        const files = ev.dataTransfer.files;
        if (!files.length) return;

        this.state.isLoading = true;
        for (const file of files) {
            const formData = new FormData();
            formData.append("ufile", file);
            formData.append("folder_path", this.state.currentPath);

            try {
                const response = await fetch("/purple_ai/upload_file", {
                    method: "POST",
                    body: formData,
                });
                if (response.ok) {
                    this.notification.add(`Uploaded ${file.name} successfully`, { type: "success" });
                } else {
                    this.notification.add(`Failed to upload ${file.name}`, { type: "danger" });
                }
            } catch (err) {
                this.notification.add(`Error uploading ${file.name}`, { type: "danger" });
            }
        }
        await this.loadFolder(this.state.currentPath);
    }

    async onDelete(item) {
        const confirmed = await new Promise((resolve) => {
            this.dialogService.add(ConfirmationDialog, {
                body: `Are you sure you want to delete ${item.name}? This action cannot be undone.`,
                confirm: () => resolve(true),
                cancel: () => resolve(false),
            });
        });

        if (!confirmed) return;

        try {
            this.state.isLoading = true;
            const result = await rpc("/purple_ai/delete_file", {
                file_path: item.path
            });
            if (result.status === "success") {
                this.notification.add("Deleted successfully", { type: "success" });
                await this.loadFolder(this.state.currentPath);
            } else {
                this.notification.add(result.message, { type: "danger" });
            }
        } catch (err) {
            this.notification.add("Failed to delete file", { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }

    toggleSelectItem(item, ev) {
        if (ev) ev.stopPropagation();
        if (this.state.selectedPaths.has(item.path)) {
            this.state.selectedPaths.delete(item.path);
        } else {
            this.state.selectedPaths.add(item.path);
        }
    }

    toggleSelectAll() {
        if (this.state.selectedPaths.size === this.state.contents.length && this.state.contents.length > 0) {
            this.state.selectedPaths.clear();
        } else {
            this.state.contents.forEach(item => this.state.selectedPaths.add(item.path));
        }
    }

    async onDeleteSelected() {
        if (this.state.selectedPaths.size === 0) return;

        const confirmed = await new Promise((resolve) => {
            this.dialogService.add(ConfirmationDialog, {
                body: `Are you sure you want to delete ${this.state.selectedPaths.size} selected items? This action cannot be undone.`,
                confirm: () => resolve(true),
                cancel: () => resolve(false),
            });
        });

        if (!confirmed) return;

        try {
            this.state.isLoading = true;
            const result = await rpc("/purple_ai/delete_file", {
                file_paths: Array.from(this.state.selectedPaths)
            });
            if (result.status === "success") {
                this.notification.add(result.message, { type: "success" });
                await this.loadFolder(this.state.currentPath);
            } else {
                this.notification.add(result.message, { type: "danger" });
            }
        } catch (err) {
            this.notification.add("Failed to delete files", { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }

    onBreadcrumbClick(path) {
        this.loadFolder(path);
    }

    isImage(item) {
        if (!item || item.is_dir) return false;
        const extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg'];
        return extensions.some(ext => item.name.toLowerCase().endsWith(ext));
    }

    getPreviewSrc(item) {
        if (!item) return "";
        const fileUrl = `/purple_ai/download_file?file_path=${encodeURIComponent(item.path)}`;
        if (this.isImage(item)) {
            return fileUrl;
        }
        return `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(fileUrl)}`;
    }

    formatSize(bytes) {
        if (!bytes) return "0 B";
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    }

    formatDate(mtime) {
        const date = new Date(mtime * 1000);
        return date.toLocaleString();
    }
}

registry.category("actions").add("invoiceai.action_folder_explorer", FolderExplorer);
registry.category("actions").add("purpleai_invoices.action_folder_explorer", FolderExplorer);
