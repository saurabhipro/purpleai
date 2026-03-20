/** @odoo-module **/

export const Export = {
    exportExcel(state, isNodeFilteredOut) {
        if (!state.nodes || !state.nodes.length) return;

        const rows = [
            ["Entity Name", "Type", "Jurisdiction", "Registration Number", "Subtype", "Entity ID (External)", "Country"]
        ];

        for (const node of state.nodes) {
            if (isNodeFilteredOut(node, state)) continue;
            const arr = [
                node.name || '',
                node.type || '',
                node.jurisdiction || '',
                node.registration_no || '',
                node.subtype || '',
                node.entity_id_external || '',
                node.country || ''
            ];
            // Escape quotes inside fields and wrap in quotes
            rows.push(arr.map(col => `"${String(col).replace(/"/g, '""')}"`).join(","));
        }

        const csvContent = "data:text/csv;charset=utf-8," + rows.join("\n");
        const encodedUri = encodeURI(csvContent);

        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", "Entity_Data_Export.csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
};
