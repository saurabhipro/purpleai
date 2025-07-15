
/** @odoo-module **/

import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export class KmlMapView extends Component {
    setup() {
        this.mapRef = useRef("map");
        this.state = useState({
            zones: [],
            wards: [],
            statuses: [],
            properties: [],
            map: null,
            markers: []
        });
        onMounted(() => this.initMapAndMarkers());
    }

    async initMapAndMarkers() {
        await this.loadGoogleMaps();
        this.initMap();
        await this.loadProperties();
    }

    initMap() {
        const container = this.mapRef.el;
        this.state.map = new google.maps.Map(container, {
            center: { lat: 22.688804, lng: 75.833185 },
            zoom: 14
        });
    }

    async loadProperties() {
        // You can add filters here if you want (zone_id, ward_id, status)
        const result = await rpc('/ddn/kml/get_properties', {});
        if (result.success) {
            this.state.properties = result.properties;
            this.renderMarkers();
        }
    }

    renderMarkers() {
        // Remove old markers
        this.state.markers.forEach(marker => marker.setMap(null));
        this.state.markers = [];

        if (!this.state.map || !this.state.properties.length) return;

        this.state.properties.forEach(property => {
            const marker = new google.maps.Marker({
                position: { lat: parseFloat(property.latitude), lng: parseFloat(property.longitude) },
                map: this.state.map,
                title: `${property.upic_no} - ${property.owner_name}`,
            });

            const infoWindow = new google.maps.InfoWindow({
                content: `<b>${property.upic_no}</b><br>${property.owner_name}<br>${property.latitude}, ${property.longitude}`
            });
            marker.addListener('click', () => infoWindow.open(this.state.map, marker));

            this.state.markers.push(marker);
        });

        // Fit map to markers
        if (this.state.markers.length > 0) {
            const bounds = new google.maps.LatLngBounds();
            this.state.markers.forEach(marker => bounds.extend(marker.getPosition()));
            this.state.map.fitBounds(bounds);
        }
    }

    async loadGoogleMaps() {
        if (window.google && window.google.maps) return;
        return new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = "https://maps.googleapis.com/maps/api/js?key=AIzaSyCQ1XvoKRmX1qqo2XwlLj2C2gCIiCjtgFE";
            script.async = true;
            script.defer = true;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }
}

KmlMapView.template = "bharat_ddn.KMLViewerComponent";
registry.category("actions").add("kml_viewer_component", KmlMapView);