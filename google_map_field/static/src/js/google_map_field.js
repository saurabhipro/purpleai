/** @odoo-module **/
/* global google */

import { registry } from "@web/core/registry";
import { CharField } from "@web/views/fields/char/char_field";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { loadGoogleMapLibWithApi } from "./google_api_services";
import { _t } from "@web/core/l10n/translation";

const { onMounted, onWillStart, onWillUnmount, useRef, useState } = owl;

export class GoogleMapField extends CharField {
    static template = "google_map_field.GoogleMapField";
    static components = { ...CharField.components };
    static props = {
        ...standardFieldProps,
        autocomplete: { type: String, optional: true },
        isPassword: { type: Boolean, optional: true },
        placeholder: { type: String, optional: true },
        dynamicPlaceholder: { type: Boolean, optional: true },
        default_lt: { type: Number, optional: true },
        default_lg: { type: Number, optional: true },
    };

    setup() {
        super.setup();
        this.mapRef = useRef("geomap_ref");
        this.inputRef = useRef("input");
        this.apiInputRef = useRef("api_input");
        this.notificationService = useService("notification");
        this.orm = useService("orm");

        const { default_lt, default_lg, options, record } = this.props;
        const latField = options?.latitude;
        const longField = options?.longitude;
        const recordLat = latField ? record.data[latField] : null;
        const recordLong = longField ? record.data[longField] : null;

        const lat = parseFloat(recordLat) || default_lt || 22.7196;
        const long = parseFloat(recordLong) || default_lg || 75.8577;

        this.state = useState({
            isShowingApiInput: false,
            lat: lat,
            long: long,
        });

        onWillStart(() => this.ensureGoogleMapLibLoaded());

        onMounted(() => {
            if (this.googleMapLoaded) {
                this.initMap();
            }
        });

        onWillUnmount(() => {
            if (this.googleMapLoaded) {
                this.removeMapEvents();
            }
        });
    }

    showApiInput() {
        this.state.isShowingApiInput = true;
    }

    hideApiInput() {
        this.state.isShowingApiInput = false;
    }

    inputApiKey(event) {
        event.preventDefault();
        this.apiKey = this.apiInputRef.el.value;
        this.hideApiInput();
        this.loadGoogleMapLib(true);
    }

    saveApiKey() {
        try {
            this.orm.call("google.api.key.manager", "set_google_api_key", [this.apiKey]);
        } catch (error) {
            this.notificationService.add(
                _t("Could not save Google Map API key in System Parameters"),
                {
                    title: _t("API KEY not saved!"),
                    sticky: true,
                }
            );
        }
    }

    closePopup(event) {
        event.preventDefault();
        this.hideApiInput();
    }

    ensureGoogleMapLibLoaded() {
        if (typeof google !== "undefined" && google.maps) {
            this.googleMapLoaded = true;
        } else {
            this.loadGoogleMapLib();
        }
    }

    async getGoogleMapApiKey() {
        try {
            const apiKey = await this.orm.call("google.api.key.manager", "get_google_api_key", []);
            if (!apiKey) throw new Error("No GoogleMap API Key found");

            return apiKey;
        } catch (error) {
            this.showApiInput();
            this.notificationService.add(
                _t("Could not found Google Map API key in System Parameters"),
                {
                    title: _t("API KEY not found!"),
                    sticky: true,
                }
            );
            return false;
        }
    }

    async loadGoogleMapLib(isReload = false) {
        try {
            if (!this.apiKey) this.apiKey = await this.getGoogleMapApiKey();
            if (!this.apiKey) return;

            await loadGoogleMapLibWithApi(this.apiKey);
            this.googleMapLoaded = true;
            if (isReload)
                this.notificationService.add(_t("Google Map API loaded successfully."), {
                    title: _t("Google Map API loaded, please reload the page."),
                    type: "success",
                });
        } catch (error) {
            this.googleMapLoaded = false;
            const errorMessage = error.message || "An unknown error occurred.";
            this.notificationService.add(
                _t("Could not load the Google Maps library. The map and autocomplete will not function. Please check the browser console (F12) for specific error details from Google. Common issues are an invalid API key, missing billing information, or incorrect API restrictions. Error: %s", errorMessage),
                {
                    title: _t("Google Map Loading Failed"),
                    type: "danger",
                    sticky: true,
                }
            );
            console.error("Failed Loading Google Map API.", error);
        }
    }

    initMap() {
        if (!this.mapRef.el) return;

        const center = new google.maps.LatLng(this.state.lat, this.state.long);
        const mapOptions = {
            center,
            zoom: 15,
            mapTypeId: google.maps.MapTypeId.ROADMAP,
            mapTypeControl: !this.props.readonly,
            streetViewControl: !this.props.readonly,
            fullscreenControl: true,
            zoomControl: !this.props.readonly,
            draggable: !this.props.readonly,
        };
        this.map = new google.maps.Map(this.mapRef.el, mapOptions);

        google.maps.event.addListenerOnce(this.map, "idle", () => {
            google.maps.event.trigger(this.map, "resize");
            this.map.setCenter(center);
        });

        if (this.props.readonly) {
            new google.maps.Marker({ position: center, map: this.map });
        } else {
            this.geocoder = new google.maps.Geocoder();
            this.initAutocomplete();
            this.initMarkerAndInfoWindow();
            this.handleInputAddressChanged(this.props.record.data[this.props.name]);
        }
    }

    initAutocomplete() {
        if (!this.map || !this.inputRef.el) return;
        this.autocomplete = new google.maps.places.Autocomplete(this.inputRef.el);
        this.autocomplete.addListener("place_changed", () => {
            const place = this.autocomplete.getPlace();
            if (place.geometry) {
                this.map.setCenter(place.geometry.location);
                this.marker.setPosition(place.geometry.location);
                this.updateAddressFromLocation(place.geometry.location);
                this.updateStatePosition();
            }
        });
    }

    initMarkerAndInfoWindow() {
        const position = new google.maps.LatLng(this.state.lat, this.state.long);
        this.marker = new google.maps.Marker({
            map: this.map,
            position,
            draggable: true,
        });

        this.infoWindow = new google.maps.InfoWindow({
            content: this.props.record.data[this.props.name] || "Current Location",
        });
        if (this.props.record.data[this.props.name]) {
             this.infoWindow.open(this.map, this.marker);
        }

        this.marker.addListener("dragend", () => {
            this.updateAddressFromLocation(this.marker.getPosition());
            this.updateStatePosition();
        });
    }

    handleInputAddressChanged(address) {
        if (!address || !this.geocoder) return;
        this.geocoder.geocode({ address }, (results, status) => {
            if (status === "OK") {
                this.map.setCenter(results[0].geometry.location);
                this.marker.setPosition(results[0].geometry.location);
                this.updateStatePosition();
                this.updateCurrentAddress(results[0].formatted_address);
            }
        });
    }

    async updateAddressFromLocation(latLng) {
        this.geocoder.geocode({ location: latLng }, async (results, status) => {
            if (status === "OK" && results[0]) {
                await this.updateCurrentAddress(results[0].formatted_address);
                await this.updateAddressFieldValue(results[0].formatted_address);
            }
        });
    }
    
    removeAutocomplete() {
        if (this.autocomplete) {
            google.maps.event.clearInstanceListeners(this.autocomplete);
        }
    }

    removeMapEvents() {
        if (this.map) {
            google.maps.event.clearInstanceListeners(this.map);
        }
        if (this.marker) {
            google.maps.event.clearInstanceListeners(this.marker);
        }
        this.removeAutocomplete();
    }

    updateStatePosition() {
        this.state.lat = this.marker.getPosition().lat();
        this.state.long = this.marker.getPosition().lng();
    }

    async updateCurrentAddress(formatted_address) {
        this.infoWindow.setContent(formatted_address);
        this.infoWindow.open(this.map, this.marker);
    }

    async updateAddressFieldValue(value) {
        await this.props.record.update({ [this.props.name]: value });
    }
}

export const googleMapField = {
    ...CharField,
    component: GoogleMapField,
    extractProps: ({ attrs, options }) => ({
        default_lt: options.default_lt,
        default_lg: options.default_lg,
    }),
};

registry.category("fields").add("google_map_field", googleMapField);
