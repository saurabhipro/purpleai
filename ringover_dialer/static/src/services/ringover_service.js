/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";
import { RingoverSDK } from "../js/lib/ringover_sdk";

/**
 * Ringover Management Service
 * 
 * Optimized Odoo 18 Service that utilizes the modular Ringover SDK.
 */
export const ringoverService = {
    // orm is the Odoo 18 service to call ir.config_parameter
    dependencies: ["orm"],
    
    /**
     * @param {Object} env
     * @param {Object} services
     */
    start(env, { orm }) {
        const state = reactive({
            isInitialized: false,
            isCompatible: !/iPhone|iPod/i.test(browser.navigator.userAgent),
            error: null,
            initializing: false
        });

        let sdkInstance = null;

        const _fetchConfig = async () => {
            const params = ['ringover.size', 'ringover.bottom', 'ringover.right', 'ringover.show_tray'];
            try {
                const results = await Promise.all(
                    params.map(p => orm.call('ir.config_parameter', 'get_param', [p]))
                );

                return {
                    type: 'fixed',
                    size: results[0] || 'medium',
                    container: null,
                    position: { 
                        top: 'auto', 
                        bottom: results[1] || '0px', 
                        left: 'auto', 
                        right: results[2] || '0px' 
                    },
                    animation: false,
                    trayicon: results[3] !== 'False'
                };
            } catch (e) {
                console.warn("Ringover Service: Failed to fetch backend config, using defaults.", e);
                return {
                    type: 'fixed',
                    size: 'medium',
                    container: null,
                    position: { top: 'auto', bottom: '0px', left: 'auto', right: '0px' },
                    animation: false,
                    trayicon: true
                };
            }
        };

        const init = async () => {
            if (!state.isCompatible || state.isInitialized || state.initializing) return;
            state.initializing = true;

            try {
                const config = await _fetchConfig();
                
                // Using the imported class for predictable, module-safe behavior
                sdkInstance = new RingoverSDK(config);
                sdkInstance.generate();

                if (sdkInstance.checkStatus()) {
                    sdkInstance.hide();
                    
                    // Hook into incoming calls
                    sdkInstance.on('ringingCall', () => this.show());

                    state.isInitialized = true;
                    console.log("Ringover Service: Initialized with modular SDK.");
                } else {
                    state.error = "SDK initialization failed status check.";
                }
            } catch (e) {
                state.error = e.message;
                console.error("Ringover Service: Fatal initialization error:", e);
            } finally {
                state.initializing = false;
            }
        };

        const show = () => {
            if (sdkInstance) sdkInstance.show();
        };

        return {
            state,
            init,
            show,
            
            dial(number) {
                if (!sdkInstance) {
                    init().then(() => {
                        if (sdkInstance && number) {
                            const cleanNumber = number.replace(/[^0-9+]/g, '');
                            sdkInstance.dial(cleanNumber || number);
                            show();
                        }
                    });
                    return;
                }

                if (number) {
                    const cleanNumber = number.replace(/[^0-9+]/g, '');
                    sdkInstance.dial(cleanNumber || number);
                    show();
                }
            },

            hide() { if (sdkInstance) sdkInstance.hide(); },
            toggle() { if (sdkInstance) sdkInstance.toggle(); },

            sendSMS(toNumber, message, fromNumber = null) {
                if (sdkInstance) sdkInstance.sendSMS(toNumber, message, fromNumber);
            },

            openCallLog(callId) {
                if (sdkInstance) sdkInstance.openCallLog(callId);
            },

            changePage(page) {
                if (sdkInstance) sdkInstance.changePage(page);
            },

            logout() {
                if (sdkInstance) sdkInstance.logout();
            },

            reload() {
                if (sdkInstance) sdkInstance.reload();
            }
        };
    }
};

registry.category("services").add("ringover_dialer", ringoverService);
