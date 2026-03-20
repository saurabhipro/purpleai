/** @odoo-module **/

import {
    RINGOVER_URL,
    RULE_SIZES,
    DEFAULT_STYLES,
    DEFAULT_TRAY_STYLE,
    CROSS_STYLE,
    CROSS_CONTAINER_STYLE,
    DEFAULT_EVENTS
} from "./ringover_constants";

/**
 * Optimized Ringover SDK for Odoo 18.
 * 
 * Logic split into independent modules for better scalability and maintainability.
 */
export class RingoverSDK {
    constructor(options = {}) {
        this.options = {
            type: options.type || 'fixed',
            size: options.size || 'medium',
            container: options.container,
            position: options.position || { top: 'auto', bottom: '0px', left: 'auto', right: '0px' },
            animation: options.animation !== undefined ? options.animation : true,
            trayicon: options.trayicon !== undefined ? options.trayicon : true,
            invite_token: options.invite_token,
            lang: options.lang
        };

        this.initialized = false;
        this.events = { ...DEFAULT_EVENTS };
        this._bindPostMessage();
    }

    /**
     * SDK Generators
     */
    generate() {
        if (this.initialized) return;

        this.iframe = this._createIframe();
        this.tray = this._createTray();
        this.header = this._createHeader();

        if (this.options.type === "fixed") {
            this._setupFixedLayout();
        } else if (this.options.container) {
            this._setupContainerLayout();
        }

        this.initialized = true;
    }

    _createIframe() {
        const iframe = document.createElement('iframe');
        iframe.src = this._getIframeSrc();
        iframe.setAttribute("allow", "microphone; clipboard-read; clipboard-write;");
        Object.assign(iframe.style, DEFAULT_STYLES);
        return iframe;
    }

    _createTray() {
        if (!this.options.trayicon) return null;
        const tray = document.createElement('div');
        tray.id = 'ringover-sdk-tray';
        Object.assign(tray.style, DEFAULT_TRAY_STYLE);

        // Dynamic positioning from config
        tray.style.position = 'fixed';
        tray.style.bottom = `calc(${this.options.position.bottom} + 20px)`;
        tray.style.right = `calc(${this.options.position.right} + 20px)`;
        tray.style.display = 'block';

        tray.onclick = () => this.toggle();
        return tray;
    }

    _createHeader() {
        const container = document.createElement('div');
        Object.assign(container.style, CROSS_CONTAINER_STYLE);

        const bar = document.createElement('div');
        bar.id = 'ringover-sdk-cross';
        Object.assign(bar.style, CROSS_STYLE);

        container.appendChild(bar);
        container.onclick = () => this.hide();
        return container;
    }

    _setupFixedLayout() {
        const container = document.createElement('div');
        container.id = "ringover-sdk-container";
        Object.assign(container.style, {
            position: 'fixed',
            zIndex: '9999',
            ...this.options.position,
            width: RULE_SIZES[this.options.size].width,
            height: RULE_SIZES[this.options.size].height,
            pointerEvents: 'none', // Allow clicking through if hidden
            transition: 'all 0.3s ease-out'
        });

        // The Iframe actually occupies the space
        Object.assign(this.iframe.style, {
            width: '100%',
            height: '100%',
            opacity: '1',
            maxHeight: '100%',
            pointerEvents: 'auto'
        });

        container.appendChild(this.header);
        container.appendChild(this.iframe);

        document.body.appendChild(container);
        if (this.tray) document.body.appendChild(this.tray);

        this.container = container;
        this.hide(); // Start hidden
    }

    /**
     * Core API Methods
     */
    dial(number, from_number = null) {
        if (!this.checkStatus()) return false;
        this._postAction('dial', { number, from_number });
        return true;
    }

    sendSMS(to_number, message, from_number = null) {
        if (!this.checkStatus()) return false;
        if (!message || !to_number) {
            console.error("Ringover SDK: Cannot send SMS without message or number.");
            return false;
        }
        this._postAction('sendSMS', { to_number, message, from_number });
        this.show();
        return true;
    }

    openCallLog(call_id) {
        if (!this.checkStatus()) return false;
        if (!call_id) {
            console.error("Ringover SDK: call_id is required to open call log.");
            return false;
        }
        this._postAction('openCallLog', { call_id });
        this.show();
        return true;
    }

    changePage(page) {
        if (!this.checkStatus()) return false;
        this._postAction('changePage', { page });
        return true;
    }

    reload() {
        if (!this.checkStatus()) return false;
        this._postAction('reload');
        return true;
    }

    logout() {
        if (!this.checkStatus()) return false;
        this._postAction('changePage', { page: 'logout' });
        return true;
    }

    destroy() {
        if (!this.initialized) return;
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
        if (this.tray && this.tray.parentNode) {
            this.tray.parentNode.removeChild(this.tray);
        }
        this.initialized = false;
        this.iframe = null;
    }

    show() {
        if (!this.initialized) return;
        this.container.style.display = 'block';
        this.container.style.opacity = '1';
        this.container.style.pointerEvents = 'auto';
        this.container.style.transform = 'translateY(0)';
        if (this.tray) this.tray.style.display = 'none';
    }

    hide() {
        if (!this.initialized) return;
        this.container.style.opacity = '0';
        this.container.style.pointerEvents = 'none';
        this.container.style.transform = 'translateY(20px)';
        if (this.tray) this.tray.style.display = 'block';
        // Delay display none for animation
        setTimeout(() => {
            if (this.container.style.opacity === '0') {
                this.container.style.display = 'none';
            }
        }, 300);
    }

    toggle() {
        this.isDisplay() ? this.hide() : this.show();
    }

    isDisplay() {
        return this.container && this.container.style.display !== 'none' && this.container.style.opacity !== '0';
    }

    checkStatus() {
        return !!this.iframe;
    }

    on(event, callback) {
        if (this.events[event]) {
            this.events[event].push(callback);
        }
    }

    off(event = null) {
        if (event) {
            if (this.events[event]) {
                this.events[event] = [];
            }
        } else {
            this.events = { ...DEFAULT_EVENTS };
        }
    }

    /**
     * Internal Helpers
     */
    _getIframeSrc() {
        let src = `${RINGOVER_URL}/sdk`;
        const params = [];
        if (this.options.invite_token) params.push(`invite_token=${this.options.invite_token}`);
        if (this.options.lang) params.push(`lang=${this.options.lang}`);

        // Attempt to match Spiffy's theme (force light if user thinks it's 'still black')
        params.push('theme=light');

        return params.length ? `${src}?${params.join('&')}` : src;
    }

    _postAction(action, data = {}) {
        this.iframe.contentWindow.postMessage({ action, ...data }, RINGOVER_URL);
    }

    _bindPostMessage() {
        window.addEventListener('message', (event) => {
            if (event.origin !== RINGOVER_URL) return;
            const { action, data } = event.data;

            // Handle SDK handshake
            if (action === 'checkSDK') {
                this._postAction('presenceSDK', { location: window.location.origin });
            }

            // Route standard events to callbacks
            if (this.events[action]) {
                this.events[action].forEach(cb => cb(data));
            }

            // Specific internal logic
            if (action === 'ringingCall') {
                this.show();
            }
        });
    }
}
