/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useBus } from "@web/core/utils/hooks";
import { ensureJQuery } from '@web/core/ensure_jquery';

import { Component, onMounted, useRef, onWillStart, onWillUnmount } from  "@odoo/owl";

const defaultDiagramXML = `
<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:omgdc="http://www.omg.org/spec/DD/20100524/DC" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" targetNamespace="" xsi:schemaLocation="http://www.omg.org/spec/BPMN/20100524/MODEL http://www.omg.org/spec/BPMN/2.0/20100501/BPMN20.xsd">
  <process id="Process_1ljiddg" />
  <bpmndi:BPMNDiagram id="sid-74620812-92c4-44e5-949c-aa47393d3830">
    <bpmndi:BPMNPlane id="sid-cdcae759-2af7-4a6d-bd02-53f3352a731d" bpmnElement="Process_1ljiddg" />
    <bpmndi:BPMNLabelStyle id="sid-e0502d32-f8d1-41cf-9c4a-cbb49fecf581">
      <omgdc:Font name="Arial" size="11" isBold="false" isItalic="false" isUnderline="false" isStrikeThrough="false" />
    </bpmndi:BPMNLabelStyle>
    <bpmndi:BPMNLabelStyle id="sid-84cb49fd-2f7c-44fb-8950-83c3fa153d3b">
      <omgdc:Font name="Arial" size="12" isBold="false" isItalic="false" isUnderline="false" isStrikeThrough="false" />
    </bpmndi:BPMNLabelStyle>
  </bpmndi:BPMNDiagram>
</definitions>`

export class BpmnViewField extends Component {
    static template = "rmt_bpmn.BpmnField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.root = useRef("root");
        this.fileInput = useRef('fileInput')
        this.downloadButton = useRef('downloadButton')
        this.imageButton = useRef('imageButton')
        this.diagramXML = defaultDiagramXML;

        this.isDirty = false;
        const { model } = this.props.record;
        useBus(model.bus, "WILL_SAVE_URGENTLY", () =>
            this.commitChanges({ urgent: true })
        );
        useBus(model.bus, "NEED_LOCAL_CHANGES", ({ detail }) =>
            detail.proms.push(this.commitChanges({ urgent: true }))
        );

        onWillStart(this.onWillStart)
        onMounted(this.onMounted);
        onWillUnmount(this.onWillUnmount)
    }

    async onWillStart() {
        await ensureJQuery()
    }

    async onMounted() {
        if (!this.props.readonly)
            this.modeler = new BpmnJS({
                container: this.root.el,
                additionalModules: [
                  BpmnComments, 
                  {
                    __init__: [ 'colorContextPadProvider', 'colorPopupProvider' ],
                    colorContextPadProvider: [ 'type', window.BpmnColorPicker.ColorContextPadProvider ],
                    colorPopupProvider: [ 'type', window.BpmnColorPicker.ColorPopupProvider ]
                  }
                ],
                colorPicker: {
                    colors: [
                    // Your custom colors, or just use the default ones from the extension
                    { label: 'My Custom Blue', fill: '#E3F2FD', stroke: '#1565C0' },
                    ...window.BpmnColorPicker.COLORS // You can merge with the default ones
                  ]
                },
                keyboard: {
                    bindTo: window
                }
            });
        else
            this.modeler = new BpmnViewer({
                container: this.root.el,
                keyboard: {
                    bindTo: window
                }
            });
        const bpmnData = this.formatData(this.props.record.data[this.props.name]);
        if (bpmnData != '')
            this.diagramXML = bpmnData;

        await this.openDiagram(this.diagramXML);
        await this.setupListener()

    }

    async onWillUnmount() {
        if (!this.props.readonly && this.isDirty) {
            await this.commitChanges();
        }
    };

    openFile() {
        this.fileInput.el.click();
    }

    async commitChanges(urgent) {
        if (this.isDirty || (urgent)) {
            const { xml } = await this.modeler.saveXML({ format: true });
            const bpmnData = encodeURIComponent(xml)
            await this.props.record.update({ [this.props.name]: bpmnData }, true);
            this.props.record.model.bus.trigger("FIELD_IS_DIRTY", false);
            this.isDirty = false;
            console.log('commit changes')
        }
    }

    formatData(bpmnData) {
        return decodeURIComponent(bpmnData.toString().substring(0, 3) == '<p>' ? bpmnData.toString().substring(3, bpmnData.length - 4) : bpmnData);
    }

    debounce(fn, timeout) {
        var timer;
        return function() {
            if (timer) {
            clearTimeout(timer);
            }

            timer = setTimeout(fn, timeout);
        };
    }

    async setupListener() {
        let self = this;
        if (!self.props.readonly)
            await self.encoded();

        var eventListener = this.debounce(async function() {
            self.isDirty = true;
            self.props.record.model.bus.trigger("FIELD_IS_DIRTY", true);
            self.props.record.resetFieldValidity(self.props.name);

            if (!self.props.readonly)
                await self.encoded();
        }, 500);
        this.modeler.on('commandStack.changed', eventListener);
    }

    async encoded() {
        this.handleFileSelectCallback = this.handleFileSelect.bind(this);
        this.fileInput.el.addEventListener('change', this.handleFileSelectCallback);
        try {
            const { svg } = await this.modeler.saveSVG();
            this.setEncoded($(this.imageButton.el), 'diagram.svg', svg);
        } catch (err) {
            console.error('Error happened saving svg: ', err);
            this.setEncoded($(this.imageButton.el), 'diagram.svg', null);
        }

        try {
            const { xml } = await this.modeler.saveXML({ format: true });
            this.setEncoded($(this.downloadButton.el), 'diagram.bpmn', xml);
        } catch (err) {
            console.error('Error happened saving XML: ', err);
            this.setEncoded($(this.downloadButton.el), 'diagram.bpmn', null);
        }
    }

    setEncoded(link, name, data) {
        var encodedData = encodeURIComponent(data);

        if (data) {
            link.attr({
                'href': 'data:application/bpmn20-xml;charset=UTF-8,' + encodedData,
                'download': name
            });
        }
    }

    async openDiagram(xml) {
        try {
            await this.modeler.importXML(xml);
            var canvas = this.modeler.get('canvas');
            canvas.zoom('fit-viewport');
        } catch (err) {
            console.error(err);
        }
    }

    validateFile(file) {
        const allowedExtensions = ['bpmn', 'xml'];
        const { name: fileName } = file;
        const fileExtension = fileName.split('.').pop();
        if (!allowedExtensions.includes(fileExtension)) {
            return false;
        }
        return true
    }

    handleFileSelect(e) {
        e.stopPropagation();
        e.preventDefault();

        const self = this;
        var files;
        if (e.dataTransfer != null)
            files = e.dataTransfer.files;
        else if (e.target != null)
            files = e.target.files;

        var file = files[0];
        if (!this.validateFile(file)) {
            alert("File type not allowed");
            return
        }
        var reader = new FileReader();
        reader.onload = function(e) {
            var xml = e.target.result;
            this.diagramXML = xml;
            self.openDiagram(xml);
            self.props.record.model.bus.trigger("FIELD_IS_DIRTY", true);
            self.props.record.resetFieldValidity(self.props.name);
            self.dirty = true
        };
        reader.readAsText(file);
    }
}

export const bpmnViewField = {
    component: BpmnViewField,
    displayName: _t("BPMN Viewer"),
    supportedTypes: ["html", "text"]
};

registry.category("fields").add("bpmn_widget", bpmnViewField);