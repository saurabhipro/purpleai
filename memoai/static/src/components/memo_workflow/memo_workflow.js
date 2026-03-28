/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * MemoWorkflow — An OWL widget embedded in the Session form.
 * Displays a visual step tracker and handles async AI step execution with loading states.
 * Registered as a form field widget: widget="memo_workflow"
 */
export class MemoWorkflowWidget extends Component {
    static template = "memoai.MemoWorkflow";
    static props = {
        sessionId: { type: Number, optional: true },
        currentState: { type: String, optional: true },
    };

    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");

        this.steps = [
            { id: 1, label: "Summarize",      icon: "📋", color: "#6366f1" },
            { id: 2, label: "Issues",          icon: "🔍", color: "#f59e0b" },
            { id: 3, label: "Regulations",     icon: "📚", color: "#10b981" },
            { id: 4, label: "Analysis",        icon: "🧠", color: "#ef4444" },
            { id: 5, label: "Export Word",     icon: "📄", color: "#3b82f6" },
        ];

        this.stateToStep = {
            'draft': 0,
            'step1_done': 1,
            'step2_done': 2,
            'step3_done': 3,
            'step4_done': 4,
            'done': 5,
        };

        this.state = useState({
            loading: false,
            activeStep: null,
            currentStepIndex: this.stateToStep[this.props.currentState] || 0,
        });
    }

    get completedStepIndex() {
        return this.stateToStep[this.props.currentState] || 0;
    }

    isStepComplete(stepId) {
        return stepId <= this.completedStepIndex;
    }

    isStepActive(stepId) {
        return stepId === this.completedStepIndex + 1;
    }

    getStepClass(stepId) {
        if (this.isStepComplete(stepId)) return "memo-step-complete";
        if (this.isStepActive(stepId)) return "memo-step-active";
        return "memo-step-pending";
    }
}

registry.add("memo_workflow_widget", MemoWorkflowWidget);
