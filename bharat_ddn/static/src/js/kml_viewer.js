
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
            loading: false,
            currentViewport: null,
            currentZoom: 12,
            totalCount: 0
        });
        
        this.kmlLayers = []; // Array to store multiple KML layers
        this.currentInfoWindow = null;
        this.loadTimeout = null;
        onMounted(() => this.initMapAndFilters());
    }

    async initMapAndFilters() {
        await this.loadGoogleMaps();
        this.initMap();
        await this.loadFilters();
    }

    initMap() {
        // Initialize map centered on Indore
        this.state.map = new google.maps.Map(this.mapRef.el, {
            center: { lat: 22.7196, lng: 75.8577 }, // Indore coordinates
            zoom: 12,
            mapTypeId: google.maps.MapTypeId.HYBRID,
            maxZoom: 22, // Allow deeper zoom
            minZoom: 8,
            styles: [
                {
                    featureType: "poi",
                    elementType: "labels",
                    stylers: [{ visibility: "off" }]
                }
            ]
        });

        // Load KML layers automatically when map is ready
        google.maps.event.addListenerOnce(this.state.map, 'idle', () => {
            this.loadKmlLayers();
        });

        // Add map event listeners
        this.state.map.addListener('bounds_changed', () => {
            this.debouncedLoadPropertiesForViewport();
        });

        this.state.map.addListener('zoom_changed', () => {
            this.debouncedLoadPropertiesForViewport();
        });
    }

    debouncedLoadPropertiesForViewport() {
        if (this.loadTimeout) {
            clearTimeout(this.loadTimeout);
        }
        
        this.loadTimeout = setTimeout(() => {
            this.loadPropertiesForViewport();
        }, 500);
    }

    async loadPropertiesForViewport() {
        if (!this.state.map) return;

        const bounds = this.state.map.getBounds();
        if (!bounds) return;

        const ne = bounds.getNorthEast();
        const sw = bounds.getSouthWest();
        const viewportBounds = [sw.lat(), sw.lng(), ne.lat(), ne.lng()];
        const zoomLevel = this.state.map.getZoom();

        if (this.state.currentViewport && 
            this.arraysEqual(this.state.currentViewport, viewportBounds, 0.01) &&
            Math.abs(this.state.currentZoom - zoomLevel) < 1) {
            return;
        }

        this.state.currentViewport = viewportBounds;
        this.state.currentZoom = zoomLevel;

        console.log("Loading properties for viewport:", {
            bounds: viewportBounds,
            zoom: zoomLevel,
            filters: {
                zones: this.state.selectedZones,
                wards: this.state.selectedWards,
                statuses: this.state.selectedStatuses,
                propertyTypes: this.state.selectedPropertyTypes
            }
        });

        this.state.loading = true;
        
        try {
            const propertyResult = await rpc('/ddn/kml/get_properties', {
                zone_ids: this.state.selectedZones.length > 0 ? this.state.selectedZones : null,
                ward_ids: this.state.selectedWards.length > 0 ? this.state.selectedWards : null,
                status_ids: this.state.selectedStatuses.length > 0 ? this.state.selectedStatuses : null,
                property_type_ids: this.state.selectedPropertyTypes.length > 0 ? this.state.selectedPropertyTypes : null,
                bounds: viewportBounds,
                zoom_level: zoomLevel
            });

            if (propertyResult.success) {
                this.state.properties = propertyResult.properties || [];
                this.state.totalCount = propertyResult.total_count || 0;
                
                console.log(`Loaded ${this.state.properties.length} properties for current viewport (zoom: ${zoomLevel})`);
                
                this.renderMarkers();
            }

        } catch (error) {
            console.error('Error loading properties for viewport:', error);
        } finally {
            this.state.loading = false;
        }
    }

    arraysEqual(a, b, tolerance = 0) {
        if (a.length !== b.length) return false;
        for (let i = 0; i < a.length; i++) {
            if (Math.abs(a[i] - b[i]) > tolerance) return false;
        }
        return true;
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
        if (ev.target.checked) {
            if (!this.state.selectedPropertyTypes.includes(value)) {
                this.state.selectedPropertyTypes.push(value);
            }
        } else {
            this.state.selectedPropertyTypes = this.state.selectedPropertyTypes.filter(pt => pt !== value);
        }
    }

    async loadFilters() {
        console.log("Loading filters only");
        
        try {
            const filterResult = await rpc('/ddn/kml/get_filters', {});
            
            if (filterResult.success) {
                this.state.zones = filterResult.zones || [];
                this.state.wards = filterResult.wards || [];
                this.state.statuses = filterResult.statuses || [];
                this.state.propertyTypes = filterResult.property_types || [];
                console.log("Filters loaded:", {
                    zones: this.state.zones.length,
                    wards: this.state.wards.length,
                    statuses: this.state.statuses.length,
                    propertyTypes: this.state.propertyTypes.length
                });
            }
        } catch (error) {
            console.error('Error loading filters:', error);
        }
    }

    async loadProperties() {
        this.state.currentViewport = null;
        await this.loadPropertiesForViewport();
    }

    renderMarkers() {
        console.log("Rendering markers for", this.state.properties.length, "properties");
        
        this.clearMarkers();

        if (!this.state.map || !this.state.properties.length) {
            console.log("No map or properties to render");
            return;
        }

        this.createMarkersInBatches(this.state.properties, 100);
    }

    clearMarkers() {
        if (this.currentInfoWindow) {
            this.currentInfoWindow.close();
            this.currentInfoWindow = null;
        }
        this.state.markers.forEach(marker => marker.setMap(null));
        this.state.markers = [];
    }

    createMarkersInBatches(properties, batchSize) {
        const totalBatches = Math.ceil(properties.length / batchSize);
        let currentBatch = 0;

        const processBatch = () => {
            const start = currentBatch * batchSize;
            const end = Math.min(start + batchSize, properties.length);
            const batch = properties.slice(start, end);

            batch.forEach((property, index) => {
                try {
                    const lat = parseFloat(property.latitude);
                    const lng = parseFloat(property.longitude);
                    
                    if (isNaN(lat) || isNaN(lng) || lat === 0 || lng === 0) {
                        return;
                    }

                    // Use default Google Maps marker with only color change for visit again
                    const marker = new google.maps.Marker({
                        position: { lat, lng },
                        map: this.state.map,
                        title: property.upic_no || property.ddn_number || 'Property',
                        zIndex: 10, // Higher z-index to appear above KML layer
                        // Use green marker for visit again, default red for others
                        icon: property.property_status === 'visit again' ? 
                            'http://maps.google.com/mapfiles/ms/icons/green-dot.png' : 
                            'http://maps.google.com/mapfiles/ms/icons/red-dot.png'
                    });

                    // Add click event
                    marker.addListener('click', () => {
                        this.showInfoWindow(marker, property);
                    });

                    this.state.markers.push(marker);
                } catch (error) {
                    console.error('Error creating marker for property:', property.id, error);
                }
            });

            currentBatch++;
            if (currentBatch < totalBatches) {
                setTimeout(processBatch, 10);
            }
        };

        processBatch();
    }

    showInfoWindow(marker, property) {
        if (this.currentInfoWindow) {
            this.currentInfoWindow.close();
        }

        const content = this.createEnhancedInfoWindowContent(property);
        
        this.currentInfoWindow = new google.maps.InfoWindow({
            content: content,
            maxWidth: 350,
            pixelOffset: new google.maps.Size(0, -10)
        });

        this.currentInfoWindow.open(this.state.map, marker);
        
        window.closeInfoWindow = () => {
            if (this.currentInfoWindow) {
                this.currentInfoWindow.close();
            }
        };
    }

    createEnhancedInfoWindowContent(property) {
        const lat = parseFloat(property.latitude);
        const lng = parseFloat(property.longitude);
        const googleMapsUrl = `https://www.google.com/maps?q=${lat},${lng}`;
        const whatsappText = encodeURIComponent(
            `Property: ${property.upic_no || 'N/A'}\n` +
            `Property ID: ${property.property_id || 'N/A'}\n` +
            `Owner: ${property.owner_name || 'N/A'}\n` +
            `Mobile: ${property.mobile_no || 'N/A'}\n` +
            `Status: ${property.property_status || 'N/A'}\n` +
            `Zone: ${property.zone_name || 'N/A'} | Ward: ${property.ward_name || 'N/A'}\n` +
            `Address: ${property.address_line_1 || ''} ${property.address_line_2 || ''}\n` +
            `Location: ${lat}, ${lng}\n` +
            `Maps: ${googleMapsUrl}`
        );
        const whatsappUrl = `https://wa.me/?text=${whatsappText}`;

        const address = `${property.address_line_1 || ''} ${property.address_line_2 || ''}`.trim();
        const showAddress = address.length > 0;
        const showMobile = property.mobile_no && property.mobile_no.trim() !== '';
        const showPropertyId = property.property_id && property.property_id.trim() !== '';
        const hasSurveyImages = property.survey_image1 || property.survey_image2;

        return `
            <div style="padding: 12px; max-width: 350px; font-family: Arial, sans-serif; font-size: 13px;">
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
                    
                    ${showPropertyId ? `
                        <div style="margin-bottom: 6px;">
                            <strong style="color: #555;">Property ID:</strong> ${property.property_id}
                        </div>
                    ` : ''}
                    
                    <div style="margin-bottom: 6px;">
                        <strong style="color: #555;">Owner:</strong> ${property.owner_name || 'N/A'}
                    </div>
                    
                    ${showMobile ? `
                        <div style="margin-bottom: 6px;">
                            <strong style="color: #555;">Mobile:</strong> <a href="tel:${property.mobile_no}" style="color: #007bff; text-decoration: none;">${property.mobile_no}</a>
                        </div>
                    ` : ''}
                    
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
                    
                    ${hasSurveyImages ? `
                        <div style="margin-bottom: 8px;">
                            <strong style="color: #555; display: block; margin-bottom: 4px;">Survey Photos:</strong>
                            <div style="display: flex; gap: 4px;">
                                ${property.survey_image1 ? `<img src="${property.survey_image1}" style="width: 60px; height: 60px; object-fit: cover; border-radius: 3px; border: 1px solid #ddd; cursor: pointer;" onclick="window.open('${property.survey_image1}', '_blank')" alt="Survey Photo 1" title="Click to view full size">` : ''}
                                ${property.survey_image2 ? `<img src="${property.survey_image2}" style="width: 60px; height: 60px; object-fit: cover; border-radius: 3px; border: 1px solid #ddd; cursor: pointer;" onclick="window.open('${property.survey_image2}', '_blank')" alt="Survey Photo 2" title="Click to view full size">` : ''}
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

    loadKmlLayers() {
        try {
            console.log("Loading KML layers automatically...");
            
            // Load IMC KMZ file
            const imcKmlUrl = '/bharat_ddn/static/kml/imc.kmz';
            const imcLayer = new google.maps.KmlLayer({
                url: imcKmlUrl,
                map: this.state.map,
                preserveViewport: false,
                suppressInfoWindows: false, // Allow KML info windows
                zIndex: 1
            });
            
            // Load Jangpura Radial Parcels KML file
            const jangpuraKmlUrl = '/bharat_ddn/static/kml/jangpura_radial_parcels.kml';
            const jangpuraLayer = new google.maps.KmlLayer({
                url: jangpuraKmlUrl,
                map: this.state.map,
                preserveViewport: false,
                suppressInfoWindows: false, // Allow KML info windows
                zIndex: 2
            });
            
            // Store both layers
            this.kmlLayers = [imcLayer, jangpuraLayer];
            
            // Add event listeners for both layers
            this.kmlLayers.forEach((layer, index) => {
                const layerName = index === 0 ? 'IMC' : 'Jangpura';
                
                google.maps.event.addListener(layer, 'status_changed', () => {
                    const status = layer.getStatus();
                    console.log(`${layerName} KML Layer Status:`, status);
                    
                    switch(status) {
                        case google.maps.KmlLayerStatus.OK:
                            console.log(`✅ ${layerName} KML layer loaded successfully`);
                            // Fit map to KML bounds when first layer loads
                            if (index === 0) {
                                this.fitMapToKmlBounds();
                            }
                            break;
                        case google.maps.KmlLayerStatus.UNKNOWN_DOCUMENT:
                            console.error(`❌ ${layerName} KML document not found or invalid`);
                            break;
                        case google.maps.KmlLayerStatus.DOCUMENT_NOT_FOUND:
                            console.error(`❌ ${layerName} KML document not found`);
                            break;
                        case google.maps.KmlLayerStatus.TIMED_OUT:
                            console.error(`❌ ${layerName} KML document load timed out`);
                            break;
                        case google.maps.KmlLayerStatus.UNSUPPORTED_DOCUMENT:
                            console.error(`❌ ${layerName} KML document format not supported`);
                            break;
                        case google.maps.KmlLayerStatus.INVALID_DOCUMENT:
                            console.error(`❌ ${layerName} KML document is invalid`);
                            break;
                        default:
                            console.log(`${layerName} KML layer status:`, status);
                    }
                });

                google.maps.event.addListener(layer, 'defaultviewport_changed', () => {
                    console.log(`${layerName} KML default viewport changed`);
                    this.fitMapToKmlBounds();
                });
            });

        } catch (error) {
            console.error('Error loading KML layers:', error);
        }
    }

    clearKmlLayers() {
        if (this.kmlLayers && this.kmlLayers.length > 0) {
            this.kmlLayers.forEach(layer => {
                if (layer) {
                    layer.setMap(null);
                }
            });
            this.kmlLayers = [];
        }
    }

    fitMapToKmlBounds() {
        try {
            if (this.kmlLayers && this.kmlLayers.length > 0) {
                // Try to fit to the first layer's bounds
                const firstLayer = this.kmlLayers[0];
                if (firstLayer && firstLayer.getDefaultViewport) {
                    const bounds = firstLayer.getDefaultViewport();
                    if (bounds) {
                        console.log('Fitting map to KML bounds');
                        this.state.map.fitBounds(bounds);
                    }
                }
            }
        } catch (error) {
            console.error('Error fitting map to KML bounds:', error);
        }
    }

    exportToKML() {
        if (this.state.properties.length === 0) {
            console.log('No properties to export');
            return;
        }

        console.log(`Exporting ${this.state.properties.length} properties to KML`);
        
        const kmlContent = this.generateKMLContent(this.state.properties);
        const blob = new Blob([kmlContent], { type: 'application/vnd.google-earth.kml+xml' });
        const url = URL.createObjectURL(blob);
        
        // Create download link
        const a = document.createElement('a');
        a.href = url;
        a.download = `properties_export_${new Date().toISOString().split('T')[0]}.kml`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        // Clean up
        URL.revokeObjectURL(url);
        
        console.log('KML export completed');
    }

    generateKMLContent(properties) {
        const kmlHeader = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
    <name>DDN Properties Export</name>
    <description>Properties exported from DDN system on ${new Date().toLocaleString()}</description>
    <Style id="visitAgainStyle">
        <IconStyle>
            <Icon>
                <href>http://maps.google.com/mapfiles/ms/icons/green-dot.png</href>
            </Icon>
        </IconStyle>
        <LabelStyle>
            <scale>0</scale>
        </LabelStyle>
    </Style>
    <Style id="defaultStyle">
        <IconStyle>
            <Icon>
                <href>http://maps.google.com/mapfiles/ms/icons/red-dot.png</href>
            </Icon>
        </IconStyle>
        <LabelStyle>
            <scale>0</scale>
        </LabelStyle>
    </Style>`;

        const kmlFooter = `
</Document>
</kml>`;

        const placemarks = properties.map(property => {
            try {
                const lat = parseFloat(property.latitude);
                const lng = parseFloat(property.longitude);
                
                if (isNaN(lat) || isNaN(lng) || lat === 0 || lng === 0) {
                    return '';
                }

                const address = `${property.address_line_1 || ''} ${property.address_line_2 || ''}`.trim();
                const styleId = property.property_status === 'visit again' ? 'visitAgainStyle' : 'defaultStyle';
                
                // Create rich description with HTML - this will only show when clicked
                const description = `
                    <![CDATA[
                    <div style="font-family: Arial, sans-serif; max-width: 300px;">
                        <h3 style="color: #007bff; margin: 0 0 10px 0; border-bottom: 1px solid #007bff; padding-bottom: 5px;">
                            ${property.upic_no || 'No UPIC'}
                        </h3>
                        <table style="width: 100%; font-size: 12px;">
                            <tr><td><strong>Property ID:</strong></td><td>${property.property_id || 'N/A'}</td></tr>
                            <tr><td><strong>Owner:</strong></td><td>${property.owner_name || 'N/A'}</td></tr>
                            <tr><td><strong>Mobile:</strong></td><td>${property.mobile_no || 'N/A'}</td></tr>
                            <tr><td><strong>Status:</strong></td><td style="background: #e9ecef; padding: 2px 4px; border-radius: 2px;">${property.property_status || 'N/A'}</td></tr>
                            <tr><td><strong>Zone:</strong></td><td>${property.zone_name || 'N/A'}</td></tr>
                            <tr><td><strong>Ward:</strong></td><td>${property.ward_name || 'N/A'}</td></tr>
                            <tr><td><strong>Address:</strong></td><td>${address || 'N/A'}</td></tr>
                            <tr><td><strong>Coordinates:</strong></td><td style="font-family: monospace;">${lat.toFixed(6)}, ${lng.toFixed(6)}</td></tr>
                        </table>
                        ${property.survey_image1 || property.survey_image2 ? `
                        <div style="margin-top: 10px;">
                            <strong>Survey Photos:</strong><br/>
                            ${property.survey_image1 ? `<a href="${property.survey_image1}" target="_blank">View Photo 1</a>` : ''}
                            ${property.survey_image1 && property.survey_image2 ? ' | ' : ''}
                            ${property.survey_image2 ? `<a href="${property.survey_image2}" target="_blank">View Photo 2</a>` : ''}
                        </div>
                        ` : ''}
                        <div style="margin-top: 10px;">
                            <a href="https://www.google.com/maps?q=${lat},${lng}" target="_blank" style="color: #007bff;">📍 Open in Google Maps</a>
                        </div>
                    </div>
                    ]]>`;

                return `
    <Placemark>
        <name></name>
        <description>${description}</description>
        <styleUrl>#${styleId}</styleUrl>
        <Point>
            <coordinates>${lng},${lat},0</coordinates>
        </Point>
        <ExtendedData>
            <Data name="upic_no">
                <value>${property.upic_no || ''}</value>
            </Data>
            <Data name="property_id">
                <value>${property.property_id || ''}</value>
            </Data>
            <Data name="owner_name">
                <value>${property.owner_name || ''}</value>
            </Data>
            <Data name="mobile_no">
                <value>${property.mobile_no || ''}</value>
            </Data>
            <Data name="property_status">
                <value>${property.property_status || ''}</value>
            </Data>
            <Data name="zone_name">
                <value>${property.zone_name || ''}</value>
            </Data>
            <Data name="ward_name">
                <value>${property.ward_name || ''}</value>
            </Data>
            <Data name="address">
                <value>${address}</value>
            </Data>
        </ExtendedData>
    </Placemark>`;
            } catch (error) {
                console.error('Error creating placemark for property:', property.id, error);
                return '';
            }
        }).filter(placemark => placemark !== '');

        return kmlHeader + placemarks.join('') + kmlFooter;
    }
}

KmlMapView.template = "bharat_ddn.KMLViewerComponent";
registry.category("actions").add("kml_viewer_component", KmlMapView);