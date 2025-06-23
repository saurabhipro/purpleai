/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class PropertyMapView extends Component {
    static template = "ddn.PropertyMapView";
    static components = {};

    setup() {
        this.state = useState({
            selectedZone: '',
            selectedWard: '',
            selectedStatus: '',
            searchCoords: '',
            dateFrom: '',
            dateTo: '',
            upicNo: '',
            loading: false,
            error: null,
            zones: [],
            wards: [],
            statuses: [
                { value: '', label: 'All Statuses' },
                { value: 'uploaded', label: 'Uploaded' },
                { value: 'pdf_downloaded', label: 'PDF Downloaded' },
                // { value: 'plate_installed', label: 'Plate Installed' },
                { value: 'surveyed', label: 'Surveyed' },
                { value: 'unlocked', label: 'Unlocked' },
                { value: 'discovered', label: 'Discovered' },
            ],
            filteredWards: [],
        });
        
        this.mapRef = useRef('mapRef');
        this.markers = [];
        this.map = null;
        this.bounds = null;
        this.orm = useService("orm");

        onMounted(async () => {
            try {
                await this.loadFilters();
                await this.loadGoogleMaps();
                await this.initMap();
            } catch (error) {
                console.error("Error in onMounted:", error);
                this.state.error = error.message;
            }
        });
    }

    async loadGoogleMaps() {
        return new Promise((resolve, reject) => {
            if (window.google && window.google.maps) {
                resolve();
                return;
            }
            const script = document.createElement('script');
            script.src = `https://maps.googleapis.com/maps/api/js?key=AIzaSyCQ1XvoKRmX1qqo2XwlLj2C2gCIiCjtgFE`;
            script.async = true;
            script.defer = true;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    async loadFilters() {
        try {
            const zones = await this.orm.call('ddn.zone', 'search_read', [[]], { fields: ['id', 'name'] });
            this.state.zones = zones;
            // Find ZK7 zone
            const zk7 = zones.find(z => z.name === 'ZK7');
            if (zk7) {
                this.state.selectedZone = zk7.id;
            }
            const wards = await this.orm.call('ddn.ward', 'search_read', [[]], { fields: ['id', 'name', 'zone_id'] });
            this.state.wards = wards;
            this.state.filteredWards = wards; // Always show all wards
            // Find K16 ward
            const k16 = wards.find(w => w.name === 'K16');
            if (k16) {
                this.state.selectedWard = k16.id;
            } else {
                this.state.selectedWard = '';
            }
            // Trigger filter after setting defaults
            setTimeout(() => this.onFilter(), 0);
        } catch (error) {
            console.error("Error loading filters:", error);
            throw error;
        }
    }

    async initMap() {
        try {
            if (!(window.google && window.google.maps)) {
                this.state.error = "Google Maps failed to load. Please check your internet connection and API key.";
                return;
            }
            const mapElement = this.mapRef.el;
            if (!mapElement) {
                throw new Error("Map element not found");
            }
            this.map = new google.maps.Map(mapElement, {
                center: { lat: 16.863890, lng: 74.622479 },
                zoom: 12,
                mapTypeControl: true,
                streetViewControl: true,
                fullscreenControl: true,
            });
            this.bounds = new google.maps.LatLngBounds();
        } catch (error) {
            console.error("Error in initMap:", error);
            this.state.error = "Failed to initialize the map. Please try refreshing the page.";
            throw error;
        }
    }

    onZoneChange(ev) {
        const zoneId = ev.target.value;
        this.state.selectedZone = zoneId;
        this.state.filteredWards = this.state.wards; // Always show all wards
        // If K16 exists, select it, else reset to empty
        const k16 = this.state.filteredWards.find(w => w.name === 'K16');
        if (k16) {
            this.state.selectedWard = k16.id;
        } else {
            this.state.selectedWard = '';
        }
    }

    onWardChange(ev) {
        this.state.selectedWard = ev.target.value;
    }

    onStatusChange(ev) {
        this.state.selectedStatus = ev.target.value;
    }

    onSearchCoords(ev) {
        this.state.searchCoords = ev.target.value;
    }

    onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value;
    }

    onDateToChange(ev) {
        this.state.dateTo = ev.target.value;
    }

    onUpicNoInput(ev) {
        this.state.upicNo = ev.target.value;
        this.onFilter();
    }

    onUpicNoChange(ev) {
        this.state.upicNo = ev.target.value;
    }

    async onFilter() {
        try {
            this.state.loading = true;
            this.clearMarkers();
            const domain = [];
            if (this.state.selectedZone) {
                domain.push(['zone_id', '=', parseInt(this.state.selectedZone)]);
            }
            if (this.state.selectedWard) {
                domain.push(['ward_id', '=', parseInt(this.state.selectedWard)]);
            }
            if (this.state.selectedStatus) {
                domain.push(['property_status', '=', this.state.selectedStatus]);
            }
            if (this.state.upicNo) {
                domain.push(['upic_no', 'ilike', this.state.upicNo]);
            }
            if (this.state.dateFrom) {
                domain.push(['create_date', '>=', this.state.dateFrom]);
            }
            if (this.state.dateTo) {
                domain.push(['create_date', '<=', this.state.dateTo + ' 23:59:59']);
            }
            if (this.state.searchCoords) {
                // Optionally, add logic to filter by coordinates
            }
            console.log('Filter domain:', domain);
            console.log('Selected values:', {
                selectedZone: this.state.selectedZone,
                selectedWard: this.state.selectedWard,
                selectedStatus: this.state.selectedStatus,
                upicNo: this.state.upicNo,
                dateFrom: this.state.dateFrom,
                dateTo: this.state.dateTo
            });
            const properties = await this.orm.call('ddn.property.info', 'search_read', [domain], {
                fields: [
                    'id', 'upic_no', 'zone_id', 'ward_id', 'property_status', 'latitude', 'longitude'
                ]
            });
            console.log('Properties returned:', properties.length, properties);
            const bounds = new google.maps.LatLngBounds();
            for (const prop of properties) {
                if (prop.latitude && prop.longitude) {
                    const lat = parseFloat(prop.latitude);
                    const lng = parseFloat(prop.longitude);
                    if (!isNaN(lat) && !isNaN(lng)) {
                        // Pin color logic
                        let pinColor = '#1976d2'; // blue default
                        let barColor = '#1976d2';
                        if (prop.property_status === 'plate_installed') {
                            pinColor = '#43a047'; // green
                            barColor = '#43a047';
                        } else if (prop.property_status === 'uploaded' || prop.property_status === 'pdf_downloaded') {
                            pinColor = '#e53935'; // red
                            barColor = '#e53935';
                        }
                        const markerIcon = {
                            path: "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z",
                            fillColor: pinColor,
                            fillOpacity: 1,
                            strokeWeight: 1,
                            strokeColor: '#fff',
                            scale: 2,
                            anchor: new google.maps.Point(12, 24),
                        };
                        const position = { lat, lng };
                        const marker = new google.maps.Marker({
                            position,
                            map: this.map,
                            title: prop.upic_no,
                            icon: markerIcon,
                        });
                        // Only create InfoWindow on click
                        marker.addListener('click', () => {
                            const shareText = encodeURIComponent(
                                `UPIC: ${prop.upic_no}\nZone: ${prop.zone_id ? prop.zone_id[1] : ''}\nWard: ${prop.ward_id ? prop.ward_id[1] : ''}\nStatus: ${prop.property_status || ''}\n}`
                            );
                            const whatsappLink = `https://wa.me/?text=${shareText}`;
                            const emailLink = `mailto:?subject=Property%20Details%20-%20${prop.upic_no}&body=${shareText}`;
                            const gmapsLink = `https://www.google.com/maps?q=${lat},${lng}`;
                            const upicCopyId = `upic_copy_${prop.id}`;
                            const infowindow = new google.maps.InfoWindow({
                                content: `
                                    <div style="min-width:270px;max-width:350px;background:#fff;border-radius:14px;box-shadow:0 4px 24px rgba(0,0,0,0.13);overflow:hidden;font-family:'Segoe UI',Arial,sans-serif;">
                                        <div style="background:${barColor};color:#fff;padding:14px 16px 14px 18px;font-weight:600;font-size:1.15em;display:flex;align-items:center;justify-content:space-between;">
                                            <span style="display:flex;align-items:center;gap:8px;">
                                                <b>UPIC:</b> <span id='${upicCopyId}_val'>${prop.upic_no}</span>
                                                <span style="cursor:pointer;display:inline-flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.18);border-radius:50%;width:28px;height:28px;" title='Copy UPIC' onclick="navigator.clipboard.writeText('${prop.upic_no}');var el=document.getElementById('${upicCopyId}_msg');if(el){el.style.display='inline';setTimeout(function(){el.style.display='none';},1200);}">
                                                    <svg width='16' height='16' fill='#fff' viewBox='0 0 24 24'><path d='M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z'/></svg>
                                                </span>
                                                <span id='${upicCopyId}_msg' style="display:none;margin-left:6px;font-size:0.95em;color:#fff;background:#222;padding:2px 8px;border-radius:6px;">Copied!</span>
                                            </span>
                                            <span style='cursor:pointer;font-size:1.4em;font-weight:normal;line-height:1;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.18);border-radius:50%;width:32px;height:32px;' onclick='this.closest(\".gm-style-iw\").parentElement.style.display=\"none\";'>
                                                <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M6 6L14 14M14 6L6 14" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>
                                            </span>
                                        </div>
                                        <div style="padding:16px 18px 10px 18px;">
                                            <div style="margin-bottom:6px;"><b>Zone:</b> ${prop.zone_id ? prop.zone_id[1] : ''}</div>
                                            <div style="margin-bottom:6px;"><b>Ward:</b> ${prop.ward_id ? prop.ward_id[1] : ''}</div>
                                            <div style="margin-bottom:6px;"><b>Status:</b> ${prop.property_status || ''}</div>
                                            <div style="margin-bottom:6px;"><b>Coordinates:</b> ${prop.latitude}, ${prop.longitude}</div>
                                            <div style="display:flex;gap:10px;margin-bottom:10px;">
                                                <a href="${gmapsLink}" target="_blank" style="flex:1;text-align:center;background:#4285F4;color:#fff;padding:8px 0;border-radius:6px;font-weight:500;text-decoration:none;display:flex;align-items:center;justify-content:center;gap:6px;transition:background 0.2s;">
                                                    <svg width="18" height="18" fill="#fff" viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
                                                    View on Google Maps
                                                </a>
                                            </div>
                                            <div style="display:flex;gap:10px;">
                                                <a href="${whatsappLink}" target="_blank" title="Share on WhatsApp" style="flex:1;text-align:center;background:#25d366;color:#fff;padding:8px 0;border-radius:6px;font-weight:500;text-decoration:none;display:flex;align-items:center;justify-content:center;gap:6px;transition:background 0.2s;">
                                                    <svg width="18" height="18" fill="#fff" viewBox="0 0 24 24"><path d="M20.52 3.48A12.07 12.07 0 0 0 12 0C5.37 0 0 5.37 0 12c0 2.12.55 4.19 1.6 6.01L0 24l6.18-1.62A11.94 11.94 0 0 0 12 24c6.63 0 12-5.37 12-12 0-3.21-1.25-6.23-3.48-8.52zM12 22c-1.85 0-3.68-.5-5.25-1.44l-.38-.22-3.67.96.98-3.58-.25-.37A9.94 9.94 0 0 1 2 12c0-5.52 4.48-10 10-10s10 4.48 10 10-4.48 10-10 10zm5.2-7.6c-.28-.14-1.65-.81-1.9-.9-.25-.09-.43-.14-.61.14-.18.28-.7.9-.86 1.08-.16.18-.32.2-.6.07-.28-.14-1.18-.44-2.25-1.4-.83-.74-1.39-1.65-1.55-1.93-.16-.28-.02-.43.12-.57.12-.12.28-.32.42-.48.14-.16.18-.28.28-.46.09-.18.05-.34-.02-.48-.07-.14-.61-1.47-.84-2.01-.22-.53-.45-.46-.61-.47-.16-.01-.34-.01-.52-.01-.18 0-.48.07-.73.34-.25.27-.96.94-.96 2.3 0 1.36.99 2.68 1.13 2.87.14.18 1.95 2.98 4.74 4.06.66.28 1.18.45 1.58.58.66.21 1.26.18 1.73.11.53-.08 1.65-.67 1.89-1.32.23-.65.23-1.2.16-1.32-.07-.12-.25-.18-.53-.32z"/></svg>
                                                    WhatsApp
                                                </a>
                                                <a href="${emailLink}" target="_blank" title="Share by Email" style="flex:1;text-align:center;background:#1976d2;color:#fff;padding:8px 0;border-radius:6px;font-weight:500;text-decoration:none;display:flex;align-items:center;justify-content:center;gap:6px;transition:background 0.2s;">
                                                    <svg width="18" height="18" fill="#fff" viewBox="0 0 24 24"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 2v.01L12 13 4 6.01V6h16zM4 20V8.99l8 6.99 8-6.99V20H4z"/></svg>
                                                    Email
                                                </a>
                                            </div>
                                        </div>
                                    </div>
                                `
                            });
                            infowindow.open(this.map, marker);
                        });
                        this.markers.push(marker);
                        bounds.extend(position);
                    }
                }
            }

            if (this.markers.length === 1) {
                this.map.setCenter(this.markers[0].getPosition());
                this.map.setZoom(18); // Zoom in close for a single property
            } else if (this.markers.length > 1) {
                this.map.fitBounds(bounds); // Adjust map to show all markers
            }

        } catch (error) {
            console.error("Error during filter:", error);
            this.state.error = "An error occurred while filtering properties.";
        } finally {
            this.state.loading = false;
        }
    }

    clearMarkers() {
        for (const marker of this.markers) {
            marker.setMap(null);
        }
        this.markers = [];
        this.bounds = new google.maps.LatLngBounds();
    }

    onClearFilters() {
        this.state.selectedZone = '';
        this.state.selectedWard = '';
        this.state.selectedStatus = '';
        this.state.dateFrom = '';
        this.state.dateTo = '';
        this.state.upicNo = '';
        this.state.searchCoords = '';
        this.state.filteredWards = this.state.wards;
        this.onFilter();
    }
}

registry.category("actions").add("property_map_view", PropertyMapView);

// Add this CSS to hide the default Google Maps InfoWindow close button
document.head.insertAdjacentHTML('beforeend', '<style>.gm-ui-hover-effect{display:none!important;}</style>');

