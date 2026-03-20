/** @odoo-module **/

/**
 * Ringover Configuration and UI Constants.
 * Optimized for Odoo 18.
 */

export const RINGOVER_URL = 'https://app.ringover.com';

export const RULE_SIZES = {
    small: { height: "500px", width: "350px" },
    medium: { height: "620px", width: "380px" },
    big: { height: "750px", width: "1050px" },
    auto: { height: "100%", width: "100%" }
};

export const DEFAULT_STYLES = {
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
};

export const DEFAULT_TRAY_STYLE = {
    backgroundImage: "url(/spiffy_theme_backend/static/description/vertical-unpinned-menu-logo.png)",
    backgroundRepeat: "no-repeat",
    backgroundSize: "28px", // Logo size
    backgroundPosition: "center",
    borderRadius: "50%",
    backgroundColor: "#583885", // Explicit GT Purple from Spiffy to ensure it's not 'still black' or white-on-white
    boxSizing: "border-box",
    zIndex: "9999",
    width: "48px",
    height: "48px",
    cursor: 'pointer',
    boxShadow: "0px 4px 12px rgba(0,0,0,0.3)", // Stronger shadow
    display: "none"
};

export const CROSS_STYLE = {
    width: "60px",
    height: "6px",
    backgroundColor: 'var(--biz-theme-primary-color)', // Theme color for the handle
    boxSizing: "border-box",
    backgroundClip: "content-box",
    padding: "7px",
    cursor: 'pointer',
    borderRadius: "12px",
    opacity: "0.8"
};

export const CROSS_CONTAINER_STYLE = {
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

export const DEFAULT_EVENTS = {
    changePage: [],
    hangupCall: [],
    ringingCall: [],
    answeredCall: [],
    dialerReady: [],
    login: [],
    logout: [],
    smsSent: [],
    smsReceived: []
};
