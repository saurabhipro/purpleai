
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
        // Set default center to Indore, India
        this.state.map = new google.maps.Map(container, {
            center: { lat: 22.7196, lng: 75.8577 }, // Indore coordinates
            zoom: 12, // Closer zoom to show Indore city
            mapTypeId: google.maps.MapTypeId.ROADMAP
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

        let firstInfoWindow = null;
        let firstMarker = null;

        this.state.properties.forEach((property, index) => {
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
                    content: `<div style="padding: 10px; max-width: 300px;">
                        <h4 style="margin: 0 0 10px 0; color: #333;">${property.upic_no || 'No UPIC'}</h4>
                        <p style="margin: 5px 0;"><strong>Owner:</strong> ${property.owner_name || 'No Owner'}</p>
                        <p style="margin: 5px 0;"><strong>Coordinates:</strong> ${lat.toFixed(6)}, ${lng.toFixed(6)}</p>
                        <p style="margin: 5px 0; font-size: 12px; color: #666;">Property ID: ${property.id}</p>
                    </div>`
                });

                marker.addListener('click', () => {
                    // Close all other info windows first
                    this.state.markers.forEach(m => {
                        if (m.infoWindow && m.infoWindow !== infoWindow) {
                            m.infoWindow.close();
                        }
                    });
                    infoWindow.open(this.state.map, marker);
                });

                // Store info window reference on marker
                marker.infoWindow = infoWindow;

                this.state.markers.push(marker);

                // Store first marker and info window for auto-opening
                if (index === 0) {
                    firstMarker = marker;
                    firstInfoWindow = infoWindow;
                }

            } catch (error) {
                console.error("Error creating marker for property:", property.id, error);
            }
        });

        // Fit map to markers with padding
        if (this.state.markers.length > 0) {
            const bounds = new google.maps.LatLngBounds();
            this.state.markers.forEach(marker => bounds.extend(marker.getPosition()));
            
            // Add padding to bounds
            this.state.map.fitBounds(bounds);
            
            // Add a small delay to ensure bounds are set, then open first property
            setTimeout(() => {
                if (firstInfoWindow && firstMarker) {
                    firstInfoWindow.open(this.state.map, firstMarker);
                }
            }, 500);
        } else {
            // If no properties found, center on Indore
            this.state.map.setCenter({ lat: 22.7196, lng: 75.8577 });
            this.state.map.setZoom(12);
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