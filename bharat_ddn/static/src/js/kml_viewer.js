
/** @odoo-module **/

import { Component, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class KmlMapView extends Component {
    setup() {
        this.mapRef = useRef("map");
        onMounted(() => this.renderMap());
    }

    async renderMap() {
        try {
            await this.loadGoogleMaps();
            console.log("Google Maps API loaded");

            const container = this.mapRef.el;
            if (!container) {
                console.error("Map container div not found.");
                return;
            }

            const map = new google.maps.Map(container, {
                center: { lat: 22.688804, lng: 75.833185 },
                zoom: 15,
            });

            const marker = new google.maps.Marker({
                position: { lat: 22.688804, lng: 75.833185 },
                map: map,
                title: "My Location",
            });

            const kmlLayer = new google.maps.KmlLayer({
                url: window.location.origin + "/bharat_ddn/static/kml/jangpura_radial_parcels.kml",
                map: map,
            });
        } catch (err) {
            console.error("Failed to load Google Maps API:", err);
        }
    }

    async loadGoogleMaps() {
        if (window.google && window.google.maps) {
            return;
        }

        return new Promise((resolve, reject) => {
            const existingScript = document.querySelector("script[src*='maps.googleapis.com']");
            if (existingScript) {
                existingScript.addEventListener("load", resolve);
                existingScript.addEventListener("error", reject);
                return;
            }

            const script = document.createElement("script");
            script.src = `https://maps.googleapis.com/maps/api/js?key=AIzaSyCQ1XvoKRmX1qqo2XwlLj2C2gCIiCjtgFE`;
            script.async = true;
            script.defer = true;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }



    // renderMap() {
    //     if (!window.L) {
    //         console.error("Leaflet is not loaded. Check your assets configuration.");
    //         return;
    //     }

    //     const container = this.mapRef.el;
    //     if (!container) {
    //         console.error("Map container div not found.");
    //         return;
    //     }

    //     const map = window.L.map(container).setView([22.688804, 75.833185], 5);

    //     window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    //         attribution: '&copy; OSM contributors',
    //         maxZoom: 18,
    //     }).addTo(map);

    //     if (window.omnivore) {
    //         const kmlLayer = window.omnivore.kml("/bharat_ddn/static/kml/imc.kmz");

    //         kmlLayer.on("ready", () => {
    //             map.fitBounds(kmlLayer.getBounds());
    //         });

    //         kmlLayer.addTo(map);
    //     } else {
    //         console.error("Omnivore is not loaded.");
    //     }
    // }

}

KmlMapView.template = "bharat_ddn.KMLViewerComponent";
registry.category("actions").add("kml_viewer_component", KmlMapView);






// /** @odoo-module **/

// import { Component, onWillStart, useRef } from "@odoo/owl";
// import { registry } from "@web/core/registry";

// export class KMLViewerComponent extends Component {
//     setup() {
//         this.mapRef = useRef("map");
//         onWillStart(async () => {
//             await this.loadLeaflet();
//         });
//     }

//     async loadLeaflet() {
//         if (!window.L) {
//             await this.loadScript("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js");
//             await this.loadStyle("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css");
//         }
//         // Remove the problematic toGeoJSON and omnivore libraries
//         // We'll use a simpler approach
//     }

//     async loadScript(url) {
//         return new Promise((resolve, reject) => {
//             const script = document.createElement("script");
//             script.src = url;
//             script.onload = resolve;
//             script.onerror = reject;
//             document.head.appendChild(script);
//         });
//     }

//     async loadStyle(url) {
//         return new Promise((resolve, reject) => {
//             const link = document.createElement("link");
//             link.rel = "stylesheet";
//             link.href = url;
//             link.onload = resolve;
//             link.onerror = reject;
//             document.head.appendChild(link);
//         });
//     }

//     mounted() {
//         const waitForReady = () => {
//             if (!this.mapRef || !this.mapRef.el) {
//                 setTimeout(waitForReady, 100);
//                 return;
//             }
//             if (!window.L) {
//                 setTimeout(waitForReady, 100);
//                 return;
//             }
//             // Debug logs
//             console.log("Map container:", this.mapRef.el);
//             console.log("Leaflet loaded:", !!window.L);

//             // Initialize map
//             const map = L.map(this.mapRef.el).setView([22.7196, 75.8577], 12);
//             L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
//                 maxZoom: 19,
//             }).addTo(map);
//             L.marker([22.7196, 75.8577]).addTo(map)
//                 .bindPopup('Indore, Madhya Pradesh')
//                 .openPopup();
//         };
//         waitForReady();
//     }
// }

// KMLViewerComponent.template = "bharat_ddn.KMLViewerComponent";

// registry.category("actions").add("kml_viewer_component", KmlMapView);