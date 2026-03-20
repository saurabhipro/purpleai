/** @odoo-module **/

export const Filtering = {
    isNodeFilteredOut(node, state) {
        if (!state.filterText && !state.filterType && (!state.ownershipVisibleNodeIds || state.ownershipVisibleNodeIds.length === 0)) return false;
        let match = true;

        if (state.filterText) {
            const search = state.filterText.toLowerCase();
            const nMatch = (node.name || '').toLowerCase().includes(search);
            const jMatch = (node.jurisdiction || '').toLowerCase().includes(search);
            if (!nMatch && !jMatch) match = false;
        }

        if (state.filterType) {
            if (node.type !== state.filterType) match = false;
        }

        if (state.ownershipVisibleNodeIds && state.ownershipVisibleNodeIds.length > 0) {
            if (!state.ownershipVisibleNodeIds.includes(node.id)) match = false;
        }

        return !match;
    },

    isLinkFilteredOut(link, state) {
        const sourceNode = state.nodes.find(n => n.id === link.source);
        const targetNode = state.nodes.find(n => n.id === link.target);
        if (!sourceNode || !targetNode) return true;
        return this.isNodeFilteredOut(sourceNode, state) || this.isNodeFilteredOut(targetNode, state);
    },

    updateOwnershipFilter(state) {
        if (!state.selectedNodeIds || state.selectedNodeIds.length === 0 || !state.showOwnershipMenu) {
            return [];
        }

        const startNodeId = state.selectedNodeIds[0];
        const visibleIds = new Set([startNodeId]);
        const direction = state.ownershipDirection;
        const usePct = state.ownershipFilterEnabled;
        const threshold = parseFloat(state.ownershipPctThreshold) || 0;
        const type = state.ownershipPctType;

        let toVisit = [startNodeId];

        while (toVisit.length > 0) {
            const currentId = toVisit.shift();

            state.links.forEach(l => {
                let nextId = null;
                let isUp = false;
                let isDown = false;

                if (l.target === currentId) {
                    nextId = l.source;
                    isUp = true;
                } else if (l.source === currentId) {
                    nextId = l.target;
                    isDown = true;
                }

                if (!nextId || visibleIds.has(nextId)) return;

                if (direction === 'up' && !isUp) return;
                if (direction === 'down' && !isDown) return;

                let passPct = true;
                const linkPct = parseFloat(l.percent) || 0;

                if (usePct) {
                    if (type === 'more') {
                        passPct = linkPct >= threshold;
                    } else {
                        passPct = linkPct <= threshold;
                    }
                }

                if (passPct) {
                    visibleIds.add(nextId);
                    toVisit.push(nextId);
                }
            });
        }

        return Array.from(visibleIds);
    }
};
