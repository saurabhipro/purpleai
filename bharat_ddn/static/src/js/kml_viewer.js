/** @odoo-module **/

import { Component, onWillStart, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class KMLViewerComponent extends Component {
    setup() {
        this.mapRef = useRef("map");
        onWillStart(async () => {
            await this.loadLeaflet();
        });
    }

    async loadLeaflet() {
        if (!window.L) {
            await this.loadScript("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js");
            await this.loadStyle("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css");
        }
        // Remove the problematic toGeoJSON and omnivore libraries
        // We'll use a simpler approach
    }

    async loadScript(url) {
        return new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = url;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    async loadStyle(url) {
        return new Promise((resolve, reject) => {
            const link = document.createElement("link");
            link.rel = "stylesheet";
            link.href = url;
            link.onload = resolve;
            link.onerror = reject;
            document.head.appendChild(link);
        });
    }

    mounted() {
        const waitForReady = () => {
            if (!this.mapRef || !this.mapRef.el) {
                setTimeout(waitForReady, 100);
                return;
            }
            if (!window.L) {
                setTimeout(waitForReady, 100);
                return;
            }
            // Debug logs
            console.log("Map container:", this.mapRef.el);
            console.log("Leaflet loaded:", !!window.L);

            // Initialize map
            const map = L.map(this.mapRef.el).setView([22.7196, 75.8577], 12);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
            }).addTo(map);
            L.marker([22.7196, 75.8577]).addTo(map)
                .bindPopup('Indore, Madhya Pradesh')
                .openPopup();
        };
        waitForReady();
    }
}

KMLViewerComponent.template = "bharat_ddn.KMLViewerComponent";

registry.category("actions").add("kml_viewer_component", KMLViewerComponent);