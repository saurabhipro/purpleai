
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
            markers: [],
            selectedZone: '',
            selectedWard: '',
            selectedStatus: 'surveyed', // Default to surveyed
            loading: false
        });
        onMounted(() => this.initMapAndFilters());
    }

    async initMapAndFilters() {
        await this.loadGoogleMaps();
        this.initMap();
        await this.loadFilters(); // Only load filters, not properties
    }

    initMap() {
        const container = this.mapRef.el;
        this.state.map = new google.maps.Map(container, {
            center: { lat: 22.688804, lng: 75.833185 },
            zoom: 14
        });
    }

    onZoneChange(ev) {
        this.state.selectedZone = ev.target.value;
        this.state.selectedWard = ''; // Reset ward when zone changes
        // Don't auto-load properties - wait for refresh button
    }

    onWardChange(ev) {
        this.state.selectedWard = ev.target.value;
        // Don't auto-load properties - wait for refresh button
    }

    onStatusChange(ev) {
        this.state.selectedStatus = ev.target.value;
        // Don't auto-load properties - wait for refresh button
    }

    async loadFilters() {
        console.log("Loading filters only");
        
        try {
            const filterResult = await rpc('/ddn/kml/get_filters', {});
            
            if (filterResult.success) {
                this.state.zones = filterResult.zones || [];
                this.state.wards = filterResult.wards || [];
                this.state.statuses = filterResult.statuses || [];
                console.log("Filters loaded:", {
                    zones: this.state.zones.length,
                    wards: this.state.wards.length,
                    statuses: this.state.statuses.length
                });
            }
        } catch (error) {
            console.error('Error loading filters:', error);
        }
    }

    async loadProperties() {
        console.log("Loading properties with filters:", {
            zone: this.state.selectedZone,
            ward: this.state.selectedWard,
            status: this.state.selectedStatus
        });
        
        this.state.loading = true;
        
        try {
            const propertyResult = await rpc('/ddn/kml/get_properties', {
                zone_id: this.state.selectedZone || null,
                ward_id: this.state.selectedWard || null,
                status: this.state.selectedStatus || 'surveyed',
            });

            console.log("Property result:", propertyResult);

            if (propertyResult.success) {
                this.state.properties = propertyResult.properties || [];
                console.log("Properties loaded:", this.state.properties.length);
            }

            // Render markers after loading properties
            this.renderMarkers();

        } catch (error) {
            console.error('Error loading properties:', error);
        } finally {
            this.state.loading = false;
        }
    }

    renderMarkers() {
        console.log("Rendering markers for", this.state.properties.length, "properties");
        
        // Remove old markers
        this.state.markers.forEach(marker => marker.setMap(null));
        this.state.markers = [];

        if (!this.state.map || !this.state.properties.length) {
            console.log("No map or properties to render");
            return;
        }

        this.state.properties.forEach(property => {
            try {
                const lat = parseFloat(property.latitude);
                const lng = parseFloat(property.longitude);
                
                if (isNaN(lat) || isNaN(lng) || lat === 0 || lng === 0) {
                    console.log("Invalid coordinates for property:", property.id);
                    return;
                }

                const marker = new google.maps.Marker({
                    position: { lat: lat, lng: lng },
                    map: this.state.map,
                    title: `${property.upic_no || 'No UPIC'} - ${property.owner_name || 'No Owner'}`,
                });

                const infoWindow = new google.maps.InfoWindow({
                    content: `<b>${property.upic_no || 'No UPIC'}</b><br>${property.owner_name || 'No Owner'}<br>${lat}, ${lng}`
                });
                marker.addListener('click', () => infoWindow.open(this.state.map, marker));

                this.state.markers.push(marker);
            } catch (error) {
                console.error("Error creating marker for property:", property.id, error);
            }
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