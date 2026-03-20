// ==ClosureCompiler==
// @output_file_name ringover-sdk.js
// @compilation_level SIMPLE_OPTIMIZATIONS
// @language ECMASCRIPT_2015
// ==/ClosureCompiler==

/*jshint esversion: 6 */

(function () {

    const RingoverSDK = (function () {

        const url = 'https://app.ringover.com';
        // const url = 'https://v4.dev157.ringover.dev';
	    // const url = 'https://nico-webapp.dev145.scw.ringover.net';        

        const error = (msg) => {
            console.error('ringover-sdk: ' + msg);
            return false;
        };

        const rulesize = {
            small: {
                height: "500px",
                width: "350px"
            },
            medium: {
                height: "620px",
                width: "380px",
            },
            big: {
                height: "750px",
                width: "1050px",
            },
            auto: {
                height: "100%",
                width: "100%",
            }
        };

        const defaultStyles = _ => JSON.parse(JSON.stringify({
            position: "fixed", 
            display: "inline-block", 
            boxSizing: "border-box",
            zIndex: "9999", 
            boxShadow: "0px 0px 10px #aaa",
            borderRadius: "10px", 
            border: "none",
            transition: "all .5s linear", 
            maxHeight: "0px", 
            opacity: "0"
        }));

        const defaultTrayStyle = _ => JSON.parse(JSON.stringify({
            backgroundImage: "url(https://webcdn.ringover.com/resources/SDK/icon.svg)", 
            backgroundRepeat: "no-repeat", 
            backgroundSize: "contains",
            backgroundPosition: "center center",
            borderRadius: "50%",
            boxSizing: "border-box",
            zIndex: "9999",
            width: "40px", 
            height: "40px",
            cursor: 'pointer',
            boxShadow: "0px 2px 10px rgba(54, 205, 207, 0.4)",
            display: "none"
        }));

        const crossStyle = {
            width: "60px",
            height: "6px",
            backgroundColor: '#eee',
            boxSizing: "border-box",
            backgroundClip: "content-box",
            padding: "7px",
            cursor: 'pointer',
            borderRadius: "12px"
        };

        const crossContainerStyle = {
            height: "20px",
            width: "100%",
            backgroundColor: "white",
            boxSizing: "border-box",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            position: "absolute",
            top: "0"
        };

        const events = _ => JSON.parse(JSON.stringify({
            changePage: [],
            hangupCall: [],
            ringingCall: [],
            answeredCall: [],
            dialerReady: [],
            login: [],
            logout: [],
            smsSent: [],
            smsReceived: []
        }));

        let user_events = events();

        const addUserEvent = (name, fn) => {
            if (user_events[name]) user_events[name].push(fn);
        };

        const generateIframe = (style, id) => {
            const i = document.createElement('IFRAME');
            const d = document.createElement('DIV');
            for (let s in style) d.style[s] = style[s];
            i.style.height = "100%";
            i.style.width = "100%";
            i.style.border = "none";
            i.allow = 'microphone;autoplay;clipboard-read;clipboard-write;';
            i.id = "ringover-iframe-" + id;
            d.id = "ringover-iframe-container-" + id;
            d.appendChild(i);
            return {i: i, d: d};
        };

        const generateTray = (style, id) => {
            const t = document.createElement('DIV');
            for (let s in style) t.style[s] = style[s];
            t.id = "ringover-tray-" +id;
            return t;
        };

        const generateCross = id => {
            const cc = document.createElement('DIV');
            const c = document.createElement('DIV');
            for (let s in crossStyle) c.style[s] = crossStyle[s];
            for (let s in crossContainerStyle) cc.style[s] = crossContainerStyle[s];
            c.id = "ringover-cross-" + id;
            cc.appendChild(c);
            return c;
        };

        const showIframe = i => {
            i.style.opacity = "1";
            i.style.maxHeight = "100%";
            if (i.dataset.animation === "false") i.style.display = 'inline-block';
            return true;
        };
        
        const hideIframe = i => {
            if (i.dataset.animation === "false") i.style.display = 'none';
            i.style.opacity = "0";
            i.style.maxHeight = "0px";
            return false;
        };

        const readEvents = (c, e) => {
            const iframe = c.iframe;
            if (!e.data || !e.data.action) return;
            switch (e.data.action) {
                case 'checkSDK':
                    iframe.contentWindow.postMessage({action: 'presenceSDK', location: window.location.origin}, url);
                    break;
                case 'changePage':
                    if (c.lastPage === e.data.data.page) return;
                    c.lastPage = e.data.data.page;
                    if (user_events[e.data.action]) {
                        for (let fn of user_events[e.data.action]) fn(e.data);
                    }
                    break;
                case 'ringingCall':
                    c.show();
                    if (user_events[e.data.action]) {
                        for (let fn of user_events[e.data.action]) fn(e.data);
                    }
                    break;
                default:
                    if (user_events[e.data.action]) {
                        for (let fn of user_events[e.data.action]) fn(e.data);
                    }
            }
        };

        const setEvents = c => {
            c.iframe.onmessage = (...args) => readEvents(c, ...args);
            window.onmessage = (...args) => readEvents(c, ...args);
        };

        return class {

            // Options:
            //
            //  type:           "fixed"|"relative"|"absolute"                                   default: "fixed" (defined css position)
            //  size:           "big"|"medium"|"small"|"auto"                                   default: "medium"
            //  container:      element.id                                                      default: document.body
            //  position:       {top: "XXpx", left: "XXpx", right: "XXpx", bottom: "XXpx"}      default: size == "big" ||size == "auto" ? {right: 50px, bottom: 50px} : {top: 0px, left: 0px}
            //  border:         true|false                                                      default: true (iframe border)
            //  animation:      true|false                                                      default: true (animation display)
            //  trayicon:       true|false                                                      default: true (button to show iframe)
            //  trayposition:   {top: "XXpx", left: "XXpx", right: "XXpx", bottom: "XXpx"}      default: size == "big" ||size == "auto" ? {right: 10px, bottom: 10px} : {right: -30px, bottom: -30px}
            //
            //
            // Methods:
            //  checkStatus()   => return true/false if iframe SDK is working
            //  - Iframe display methods
            //     generate()      => add iframe on DOM
            //     show()          => show iframe
            //     hide()          => hide iframe
            //     toggle()        => show or hide iframe (optionnal boolean to force: true = show, false = hide)
            //     isDisplay()     => return true if iframe is display
            //     destroy()       => remove iframe of DOM
            //  - Web app methods
            //     dial(numberToDial)   => Insert in dialer or direct call number in params
            //     sendSMS(to_number, message, from_number) => Send directly a SMS
            //     openCallLog(callId)  => Open call-log page on a specific call_id
            //     getCurrentPage()     => Get current page of the web app iframe
            //     changePage(page)     => Change the current page of the web app iframe
            //     reload()             => Reload the web app iframe
            //     logout()             => Logout current user of the web app iframe
            //  - Events Listener
            //     on(event, fn)        => Create event listener
            //     off                  => Remove all events listner
            //
            // Events:
            //
            //  changePage   => return {page: "pageName"}
            //  dialerReady  => return {userId: 123}
            //  login        => return {userId: 123}
            //  logout       => return {userId: 123}
            //  ringingCall  => return {direction: "in"|"out", from_number: "+number", to_number: "+number", internal: true|false, call_id: "123", ringDuration: 0, callDuration: 0}
            //  answeredCall => return {direction: "in"|"out", from_number: "+number", to_number: "+number", internal: true|false, call_id: "123", ringDuration: 0, callDuration: 0}
            //  hangupCall   => return {direction: "in"|"out", from_number: "+number", to_number: "+number", internal: true|false, call_id: "123", ringDuration: 0, callDuration: 0}


            constructor(options = {}) {

                this.id = parseInt((new Date().getTime() + Math.random()).toString().replace('.', '')).toString(16);

                this.status = -1;

                this.display = false;

                this.style = defaultStyles();

                if (typeof options !== 'object' || Array.isArray(options) || options === null) {
                    this.status = 0;
                    return error('Options object not conform. Please referer to documentation!');
                }

                this.container = document.body;
                if (options.container) {
                    const c = document.getElementById(options.container);
                    if (c) {
                        this.container = c;
                    } else {
                        error('Container is not found. Document body used instead');
                    }
                }

                this.style.position = options.type && ['fixed', 'relative', 'absolute'].includes(options.type) ? options.type : (this.container != document.body ? 'relative' : 'fixed');     // "fixed" or "float" or "content"

                this.size = options.size && ['big', 'medium', 'small', 'auto'].includes(options.size) ? options.size : 'medium';     // "small" or "medium" or "big" or "auto"

                this.animation = true;

                this.lastPage = null;

                if (options.border !== undefined && !options.border) {
                    this.style.boxShadow = "none";
                }

                if (options.animation !== undefined && !options.animation) { 
                    this.animation = false;
                    this.style.transition = null;
                }

                if (options.position) {
                    if (options.position.top)       this.style.top       = options.position.top;
                    if (options.position.bottom)    this.style.bottom    = options.position.bottom;
                    if (options.position.left)      this.style.left      = options.position.left;
                    if (options.position.right)     this.style.right     = options.position.right;
                } else if (['auto','big'].includes(this.size) || this.container != document.body) {
                    this.style.top    = "0";
                    this.style.left   = "0";
                } else {
                    this.style.right    = "64px";
                    this.style.bottom   = "0";
                }

                if (options.backgroundColor) {
                    this.style.backgroundColor = options.backgroundColor;
                }


                for (let s in rulesize[this.size])  this.style[s] = rulesize[this.size][s];


                this.tray       = null;
                this.trayicon   = true;
                this.traystyle  = defaultTrayStyle();
                this.cross      = null;
                
                if (options.trayicon !== undefined && !options.trayicon) {
                    this.trayicon = false;
                }
                if (this.trayicon) {
                    if (options.trayposition) {
                        if (options.trayposition.top)       this.traystyle.top       = options.trayposition.top;
                        if (options.trayposition.bottom)    this.traystyle.bottom    = options.trayposition.bottom;
                        if (options.trayposition.left)      this.traystyle.left      = options.trayposition.left;
                        if (options.trayposition.right)     this.traystyle.right     = options.trayposition.right;
                    } else {
                        this.traystyle.bottom   = (this.container != document.body ? "-42px" : "10px");
                        this.traystyle.right    = (this.container != document.body ? "-42px" : "10px");
                    }
                    this.traystyle.position = (this.container != document.body ? 'absolute' : 'fixed');
                    this.tray = generateTray(this.traystyle, this.id);
                    this.tray.onclick = _ => this.show();
                    this.style.paddingTop = '20px';
                    if (this.size == 'auto') this.style.height = "calc(100% - 20px)";
                    this.cross = generateCross(this.id);
                    this.cross.onclick = _ => this.hide();
                }

                const i = generateIframe(this.style, this.id);
                this.iframe = i.i;
                this.iframeContainer = i.d;
                if (this.cross) this.iframeContainer.appendChild(this.cross.parentNode);
                if (this.tray) this.iframe.dataset.tray = this.tray.id;
                if (this.cross) this.iframe.dataset.cross = this.cross.id;
                this.iframe.dataset.animation = this.animation;

                setEvents(this);

                this.iframe.src = url;

            }

            checkStatus (notready = false) {
                if (this.iframe) {
                    switch (this.status) {
                        case 1:
                        case 2:
                            return true;
                        case -1:
                            if (notready) return true;
                            error('Iframe not ready!');
                            break;
                        case 0: 
                            error('Iframe not available!');
                            break;
                        default:
                            error();
                    }
                } else {
                    error('Iframe not found');
                }
                return false;
            }
            
            // Iframe display methods

            generate () {
                if (!this.checkStatus(1)) return; 
                if (this.status === 2) return error('Iframe already present in DOM');

                this.container.style.position = "relative";
                this.container.appendChild(this.iframeContainer);
                if (this.tray) this.container.appendChild(this.tray);

                this.show();
                this.status = 2;

                return this.iframe;
            }

            destroy () {
                this.checkStatus();
                if (this.status === 1) return error('Iframe not found in DOM');
                this.hide();
                if (this.tray && this.tray.parentNode) this.tray.parentNode.removeChild(this.tray);
                if (this.iframeContainer.parentNode) this.iframeContainer.parentNode.removeChild(this.iframeContainer);
                this.status = 1;

                return true;
            }
            
            show () {
                if (!this.checkStatus(1)) return; 
                this.display = showIframe(this.iframeContainer);
                if (this.tray) this.tray.style.display = 'none';
                return this.isDisplay();
            }

            hide () {
                if (!this.checkStatus(1)) return; 
                this.display = hideIframe(this.iframeContainer);
                if (this.tray) this.tray.style.display = 'block';
                return this.isDisplay();
            }
            
            toggle (s = null) {
                this.display = (s === null) ?
                    (this.display ? this.hide() : this.show()) :
                    (s ? this.show() : this.hide())
                ;
                return this.isDisplay();
            }

            isDisplay () {
                return this.display;
            }

            // Web App Methods
    
            dial(number, from_number = null) {
                if (!this.checkStatus()) return false;
                this.iframe.contentWindow.postMessage({action: 'dial', number: number, from_number: from_number}, url);
                this.display = showIframe(this.iframeContainer);
                return true;
            }

            sendSMS(to_number, message, from_number = null) {
                if (!this.checkStatus()) return false;
                let missing_params = null;
                if (!message)       missing_params = 'message';
                if (!to_number)     missing_params = 'to_number';
                if (missing_params) {
                    console.error("Cannot send a SMS if the " + missing_params + " is not specified");
                    return false;
                }
                this.iframe.contentWindow.postMessage({action: 'sendSMS', to_number: to_number, message: message, from_number: from_number}, url);
                this.display = showIframe(this.iframeContainer);
                return true;
            }

            openCallLog(call_id) {
                console.log(call_id);
                if (!this.checkStatus()) return false;
                if (!call_id) return console.error("Cannot open a specific calllog if the call_id is not given")  && false;
                console.log("sent event");
                this.iframe.contentWindow.postMessage({action: 'openCallLog', call_id: call_id}, url);
                this.display = showIframe(this.iframeContainer);
                return true; 
            }

            changePage(page) {
                if (!this.checkStatus()) return false; 
                this.iframe.contentWindow.postMessage({action: 'changePage', page: page}, url);
                return true;
            }

            reload() {
                if (!this.checkStatus()) return false; 
                this.iframe.contentWindow.postMessage({action: 'reload'}, url);
                return true;
            }

            logout() {
                if (!this.checkStatus()) return false; 
                this.iframe.contentWindow.postMessage({action: 'changePage', page: 'logout'}, url);
                return true;
            }
            
            getCurrentPage() {
                if (!this.checkStatus()) return false; 
                return this.lastPage;
            }

            // Events listeners

            on (name, fn) {
                if (!this.checkStatus(1)) return false; 
                addUserEvent(name, fn);
                return true;
            }

            off() {
                if (!this.checkStatus(1)) return false;  
                user_events = events();
                return true;
            }
        };
    })();

    if (typeof define === "function" && define.amd) {
        Object.defineProperty(exports, '__esModule', { value: true });
        define(function () {
            return RingoverSDK;
        });
    } else if (typeof module !== "undefined" && module.exports) {
        module.exports = RingoverSDK;
    } else if (typeof __exports !== "undefined") {
        __exports.RingoverSDK = RingoverSDK;
    } else {
        this.RingoverSDK = RingoverSDK;
    }
})();