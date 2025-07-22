
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
            propertyTypes: [],
            properties: [],
            map: null,
            markers: [],
            selectedZones: [],
            selectedWards: [],
            selectedStatuses: [],
            selectedPropertyTypes: [],
            loading: false
        });
        onMounted(() => this.initMapAndFilters());
    }

    async initMapAndFilters() {
        await this.loadGoogleMaps();
        this.initMap();
        await this.loadFilters();
    }

    initMap() {
        const container = this.mapRef.el;
        this.state.map = new google.maps.Map(container, {
            center: { lat: 22.7196, lng: 75.8577 },
            zoom: 12,
            mapTypeId: google.maps.MapTypeId.ROADMAP
        });
    }

    onZoneChange(ev) {
        const value = ev.target.value;
        if (ev.target.checked) {
            if (!this.state.selectedZones.includes(value)) {
                this.state.selectedZones.push(value);
            }
        } else {
            this.state.selectedZones = this.state.selectedZones.filter(z => z !== value);
        }
    }

    onWardChange(ev) {
        const value = ev.target.value;
        if (ev.target.checked) {
            if (!this.state.selectedWards.includes(value)) {
                this.state.selectedWards.push(value);
            }
        } else {
            this.state.selectedWards = this.state.selectedWards.filter(w => w !== value);
        }
    }

    onStatusChange(ev) {
        const value = ev.target.value;
        if (ev.target.checked) {
            if (!this.state.selectedStatuses.includes(value)) {
                this.state.selectedStatuses.push(value);
            }
        } else {
            this.state.selectedStatuses = this.state.selectedStatuses.filter(s => s !== value);
        }
    }

    onPropertyTypeChange(ev) {
        const value = ev.target.value;
        console.log("Property type changed:", value, ev.target.checked);
        if (ev.target.checked) {
            if (!this.state.selectedPropertyTypes.includes(value)) {
                this.state.selectedPropertyTypes.push(value);
            }
        } else {
            this.state.selectedPropertyTypes = this.state.selectedPropertyTypes.filter(pt => pt !== value);
        }
        console.log("Selected property types:", this.state.selectedPropertyTypes);
    }

    async loadFilters() {
        console.log("Loading filters only");
        
        try {
            const filterResult = await rpc('/ddn/kml/get_filters', {});
            console.log("Filter result:", filterResult);
            
            if (filterResult.success) {
                this.state.zones = filterResult.zones || [];
                this.state.wards = filterResult.wards || [];
                this.state.statuses = filterResult.statuses || [];
                this.state.propertyTypes = filterResult.property_types || [];
                console.log("Filters loaded:", {
                    zones: this.state.zones.length,
                    wards: this.state.wards.length,
                    statuses: this.state.statuses.length,
                    propertyTypes: this.state.propertyTypes.length,
                    propertyTypesData: this.state.propertyTypes
                });
            }
        } catch (error) {
            console.error('Error loading filters:', error);
        }
    }

    async loadProperties() {
        console.log("Loading properties with filters:", {
            zones: this.state.selectedZones,
            wards: this.state.selectedWards,
            statuses: this.state.selectedStatuses,
            propertyTypes: this.state.selectedPropertyTypes
        });
        
        this.state.loading = true;
        
        try {
            const propertyResult = await rpc('/ddn/kml/get_properties', {
                zone_ids: this.state.selectedZones.length > 0 ? this.state.selectedZones : null,
                ward_ids: this.state.selectedWards.length > 0 ? this.state.selectedWards : null,
                status_ids: this.state.selectedStatuses.length > 0 ? this.state.selectedStatuses : null,
                property_type_ids: this.state.selectedPropertyTypes.length > 0 ? this.state.selectedPropertyTypes : null,
            });

            console.log("Property result:", propertyResult);

            if (propertyResult.success) {
                this.state.properties = propertyResult.properties || [];
                console.log("Properties loaded:", this.state.properties.length);
            }

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
                    animation: google.maps.Animation.DROP
                });

                // Create compact info window
                const infoWindow = new google.maps.InfoWindow({
                    content: this.createCompactInfoWindowContent(property),
                    maxWidth: 320,
                    pixelOffset: new google.maps.Size(0, -10)
                });

                // Store info window reference on marker
                marker.infoWindow = infoWindow;

                marker.addListener('click', () => {
                    // Close all other info windows first
                    this.state.markers.forEach(m => {
                        if (m.infoWindow && m.infoWindow !== infoWindow) {
                            m.infoWindow.close();
                        }
                    });
                    infoWindow.open(this.state.map, marker);
                    
                    // Set up the close function for this specific info window
                    window.closeInfoWindow = () => {
                        infoWindow.close();
                    };
                });

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
            
            this.state.map.fitBounds(bounds);
            
            // Add a small delay to ensure bounds are set, then open first property
            setTimeout(() => {
                if (firstInfoWindow && firstMarker) {
                    firstInfoWindow.open(this.state.map, firstMarker);
                    // Set up close function for first info window
                    window.closeInfoWindow = () => {
                        firstInfoWindow.close();
                    };
                }
            }, 500);
        } else {
            // If no properties found, center on Indore
            this.state.map.setCenter({ lat: 22.7196, lng: 75.8577 });
            this.state.map.setZoom(12);
        }
    }

    createCompactInfoWindowContent(property) {
        const lat = parseFloat(property.latitude);
        const lng = parseFloat(property.longitude);
        const googleMapsUrl = `https://www.google.com/maps?q=${lat},${lng}`;
        const whatsappText = encodeURIComponent(
            `Property: ${property.upic_no || 'N/A'}\n` +
            `ID: ${property.id} | Owner: ${property.owner_name || 'N/A'}\n` +
            `Status: ${property.property_status || 'N/A'}\n` +
            `Zone: ${property.zone_name || 'N/A'} | Ward: ${property.ward_name || 'N/A'}\n` +
            `Location: ${lat}, ${lng}\n` +
            `Maps: ${googleMapsUrl}`
        );
        const whatsappUrl = `https://wa.me/?text=${whatsappText}`;

        // Only show address if it exists
        const address = `${property.address_line_1 || ''} ${property.address_line_2 || ''}`.trim();
        const showAddress = address.length > 0;

        return `
            <div style="padding: 12px; max-width: 320px; font-family: Arial, sans-serif; font-size: 13px;">
                <div style="position: relative;">
                    <button onclick="window.closeInfoWindow();" 
                            style="position: absolute; top: 2px; right: 2px; background: #ff4444; color: white; border: none; border-radius: 50%; width: 18px; height: 18px; cursor: pointer; font-size: 10px; line-height: 1; z-index: 1000;">×</button>
                    
                    <h4 style="margin: 0 0 8px 0; color: #333; font-size: 15px; border-bottom: 1px solid #007bff; padding-bottom: 4px;">
                        ${property.upic_no || 'No UPIC'}
                    </h4>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 8px;">
                        <div><strong style="color: #555;">ID:</strong> ${property.id}</div>
                        <div><strong style="color: #555;">Status:</strong> <span style="background: #e9ecef; padding: 1px 4px; border-radius: 2px; font-size: 11px;">${property.property_status || 'N/A'}</span></div>
                    </div>
                    
                    <div style="margin-bottom: 6px;">
                        <strong style="color: #555;">Owner:</strong> ${property.owner_name || 'N/A'}
                    </div>
                    
                    ${showAddress ? `
                        <div style="margin-bottom: 6px;">
                            <strong style="color: #555;">Address:</strong> ${address}
                        </div>
                    ` : ''}
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 8px;">
                        <div><strong style="color: #555;">Zone:</strong> ${property.zone_name || 'N/A'}</div>
                        <div><strong style="color: #555;">Ward:</strong> ${property.ward_name || 'N/A'}</div>
                    </div>
                    
                    <div style="margin-bottom: 8px; font-family: monospace; font-size: 12px;">
                        <strong style="color: #555;">📍</strong> ${lat.toFixed(6)}, ${lng.toFixed(6)}
                    </div>
                    
                    ${property.survey_image1 || property.survey_image2 ? `
                        <div style="margin-bottom: 8px;">
                            <div style="display: flex; gap: 4px;">
                                ${property.survey_image1 ? `<img src="${property.survey_image1}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 3px; border: 1px solid #ddd;" alt="Photo 1">` : ''}
                                ${property.survey_image2 ? `<img src="${property.survey_image2}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 3px; border: 1px solid #ddd;" alt="Photo 2">` : ''}
                            </div>
                        </div>
                    ` : ''}
                    
                    <div style="display: flex; gap: 6px;">
                        <a href="${googleMapsUrl}" target="_blank" 
                           style="flex: 1; padding: 6px 8px; background: #007bff; color: white; text-decoration: none; border-radius: 3px; text-align: center; font-size: 11px;">
                            📍 Maps
                        </a>
                        <a href="${whatsappUrl}" target="_blank" 
                           style="flex: 1; padding: 6px 8px; background: #25d366; color: white; text-decoration: none; border-radius: 3px; text-align: center; font-size: 11px;">
                            📱 Share
                        </a>
                    </div>
                </div>
            </div>
        `;
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