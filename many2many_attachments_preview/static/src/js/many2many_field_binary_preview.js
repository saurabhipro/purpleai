/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { Many2ManyBinaryField, many2ManyBinaryField } from '@web/views/fields/many2many_binary/many2many_binary_field';
import { FileViewer } from "@web/core/file_viewer/file_viewer";
import { useService } from "@web/core/utils/hooks";

let fileViewerId = 0;

patch(Many2ManyBinaryField.prototype, {
    setup() {
        super.setup();
        this.store = useService("mail.store");
    },
    onGlobalClickPreview(ev) {
        const viewerId = `web.file_viewer${fileViewerId++}`;
        const files = [];

        this.props.record.data[this.props.name].records.forEach(rec => {
            files.push({
                id: rec.evalContext.active_id,
                filename: rec.data.name,
                name: rec.data.name,
                mimetype: rec.data.mimetype,
            })
        });
        const attachment = this.store.Attachment.insert(files)
        const viewableFiles = attachment.filter((file) => file.isViewable);
        const index = parseInt(ev.currentTarget.getAttribute('rec-id'));
        registry.category("main_components").add(viewerId, {
            Component: FileViewer,
            props: {
                files: attachment,
                startIndex: index,
                close: () => {
                    registry.category('main_components').remove(viewerId);
                },
            },
        });
    },

});
many2ManyBinaryField.relatedFields = [
    ...many2ManyBinaryField.relatedFields,
    { name: "create_date", type: "char" },
]
