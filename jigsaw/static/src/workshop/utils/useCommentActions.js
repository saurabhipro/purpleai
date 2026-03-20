/** @odoo-module **/

/**
 * useCommentActions — handles all comment state and interactions
 * for the Jigsaw workshop canvas.
 *
 * @param {object} state - OWL reactive state from the parent component
 */
export function useCommentActions(state) {

    function hasComments(nodeId) {
        return state.comments.some((c) => c.nodeId === nodeId);
    }

    function onCommentKeydown(ev) {
        if (ev.key === "Enter") {
            submitComment();
        }
    }

    function submitComment() {
        if (!state.newCommentText || !state.showCommentInputForNode) return;

        state.comments.push({
            id: Date.now(),
            text: state.newCommentText,
            author: "Brinn MacRae",
            initials: "BM",
            time: "just now",
            resolved: false,
            replies: 0,
            nodeId: state.showCommentInputForNode,
        });

        state.newCommentText = "";
        state.showCommentInputForNode = null;
        state.activeSidebar = "comments";
    }

    return {
        hasComments,
        onCommentKeydown,
        submitComment,
    };
}
