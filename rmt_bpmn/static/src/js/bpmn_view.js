/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { ensureJQuery } from "@web/core/ensure_jquery";

import {
  Component,
  onMounted,
  useRef,
  useState,
  onWillStart,
  onWillDestroy,
} from "@odoo/owl";

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
</definitions>`;

export class BPMNViewerAction extends Component {
  setup() {
    this.root = useRef("root");
    this.propertiesPanel = useRef("properties");
    this.orm = useService("orm");
    this.action = useService("action");
    this.notificationService = useService("notification");
    this.modelId =
      this.props.action.context.active_id == null
        ? parseInt(browser.localStorage.getItem("rmt_bpmn_model_id"))
        : this.props.action.context.active_id;
    this.diagramXML = defaultDiagramXML;
    this.state = useState({
      title: "",
      desc: "",
      dirty: false,
      modelId: this.modelId,
      isViewer: true,
    });
    onWillStart(this.onWillStart);
    onMounted(this.onMounted);
    onWillDestroy(this.onWillDestroy);
  }

  async onWillStart() {
    await ensureJQuery();
  }

  async onMounted() {
    if (!this.modelId) {
      alert("Record ID Not found");
      return;
    }
    browser.localStorage.setItem("rmt_bpmn_model_id", this.modelId);

    this.modeler = new BpmnViewer({
      container: this.root.el,
      keyboard: {
        bindTo: window,
      },
    });
    this.record = await this.orm
      .read("rmt.bpmn.model", [this.modelId], [])
      .then((ar) => ar[0]);
    this.state.title = this.record.name;
    this.state.desc = this.record.desc;
    if (this.record.bpmn_data)
      this.diagramXML = decodeURIComponent(this.record.bpmn_data);

    await this.openDiagram(this.diagramXML);
    await this.setupButtons();
  }

  onWillDestroy() {}

  async setupButtons() {
    let self = this;
    var downloadLink = $("#js-download-diagram");
    var downloadSvgLink = $("#js-download-svg");

    var encoded = async function () {
      try {
        const { svg } = await self.modeler.saveSVG();
        self.setEncoded(downloadSvgLink, "diagram.svg", svg);
      } catch (err) {
        console.error("Error happened saving svg: ", err);
        self.setEncoded(downloadSvgLink, "diagram.svg", null);
      }

      try {
        const { xml } = await self.modeler.saveXML({ format: true });
        self.setEncoded(downloadLink, "diagram.bpmn", xml);
      } catch (err) {
        console.error("Error happened saving XML: ", err);
        self.setEncoded(downloadLink, "diagram.bpmn", null);
      }
    };
    await encoded();

    var exportArtifacts = this.debounce(async function () {
      self.state.dirty = true;
      await encoded();
    }, 500);
    this.modeler.on("commandStack.changed", exportArtifacts);
  }

  toggleProperties(ev) {
    if ($("#bpmn_container").hasClass("col-md-9")) {
      $("#bpmn_container").removeClass("col-md-9");
      $("#bpmn_container").addClass("col-md-12");
      $("#bpmn_properties").hide();
    } else {
      $("#bpmn_container").removeClass("col-md-12");
      $("#bpmn_container").addClass("col-md-9");
      $("#bpmn_properties").show();
    }
    $(".btn-toggle-prop").toggleClass("active");
  }

  async back(ev) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "rmt.bpmn.model",
      views: [[false, "list"]],
      view_mode: "list",
      name: "BPMN Model",
      target: "main",
    });
  }

  debounce(fn, timeout) {
    var timer;
    return function () {
      if (timer) {
        clearTimeout(timer);
      }

      timer = setTimeout(fn, timeout);
    };
  }

  setEncoded(link, name, data) {
    var encodedData = encodeURIComponent(data);

    if (data) {
      link.attr({
        href: "data:application/bpmn20-xml;charset=UTF-8," + encodedData,
        download: name,
      });
    }
  }

  async openDiagram(xml) {
    try {
      await this.modeler.importXML(xml);
      var canvas = this.modeler.get("canvas");
      // zoom to fit full viewport
      canvas.zoom("fit-viewport");
    } catch (err) {
      console.error(err);
    }
  }
}
BPMNViewerAction.template = "rmt_bpmn.Viewer";

export class BPMNModelerAction extends BPMNViewerAction {
  setup() {
    super.setup();
    this.container = useRef("dropZone");
    this.fileInput = useRef("fileInput");
    this.state.isViewer = false;
  }

  async onMounted() {
    if (!this.modelId) {
      alert("Record ID Not found");
      return;
    }
    browser.localStorage.setItem("rmt_bpmn_model_id", this.modelId);
    this.modeler = new BpmnJS({
      container: this.root.el,
      propertiesPanel: {
        parent: this.propertiesPanel.el,
      },
      additionalModules: [
        BpmnComments,
        BpmnJSTokenSimulation,
        BpmnJSPropertiesPanel.BpmnPropertiesPanelModule,
        BpmnJSPropertiesPanel.BpmnPropertiesProviderModule,
        {
          __init__: ["colorContextPadProvider", "colorPopupProvider"],
          colorContextPadProvider: [
            "type",
            window.BpmnColorPicker.ColorContextPadProvider,
          ],
          colorPopupProvider: [
            "type",
            window.BpmnColorPicker.ColorPopupProvider,
          ],
        },
        {
          __init__: [
            [ 'eventBus', 'bpmnjs', 'toggleMode', function(eventBus, bpmnjs, toggleMode) {
              let active = 0
              eventBus.on('tokenSimulation.toggleMode', event => {
                document.body.classList.toggle('token-simulation-active', event.active);
      
                if (event.active) {
                  active = 1;
                  let buttons = document.querySelector('.buttons')
                  buttons.style.display = 'none';
                } else {
                  active = 0
                  let buttons = document.querySelector('.buttons')
                  buttons.style.display = 'block';
                }                  
              });
              eventBus.on('diagram.init', 500, () => {
                toggleMode.toggleMode(active);
              });
            } ]
          ]
        }
      ],
      colorPicker: {
        colors: [
          // Your custom colors, or just use the default ones from the extension
          { label: "My Custom Blue", fill: "#E3F2FD", stroke: "#1565C0" },
          ...window.BpmnColorPicker.COLORS, // You can merge with the default ones
        ],
      },
      keyboard: {
        bindTo: window,
      },
    });

    this.record = await this.orm
      .read("rmt.bpmn.model", [this.modelId], [])
      .then((ar) => ar[0]);
    this.state.title = this.record.name;
    this.state.desc = this.record.desc;
    if (this.record.bpmn_data)
      this.diagramXML = decodeURIComponent(this.record.bpmn_data);

    await this.createNewDiagram();
    await this.setupButtons();

    this.handleDragOverCallback = this.handleDragOver.bind(this);
    this.handleFileSelectCallback = this.handleFileSelect.bind(this);
    this.container.el.addEventListener(
      "dragover",
      this.handleDragOverCallback,
      false,
    );
    this.container.el.addEventListener(
      "drop",
      this.handleFileSelectCallback,
      false,
    );
    this.fileInput.el.addEventListener("change", this.handleFileSelectCallback);
  }

  onWillDestroy() {
    this.container.el.removeEventListener(
      "dragover",
      this.handleDragOverCallback,
    );
    this.container.el.removeEventListener(
      "drop",
      this.handleFileSelectCallback,
    );
    this.fileInput.el?.removeEventListener(
      "change",
      this.handleFileSelectCallback,
    );
  }

  openFile() {
    this.fileInput.el.click();
  }

  validateFile(file) {
    const allowedExtensions = ["bpmn", "xml"];
    const { name: fileName } = file;
    const fileExtension = fileName.split(".").pop();
    if (!allowedExtensions.includes(fileExtension)) {
      return false;
    }
    return true;
  }

  handleFileSelect(e) {
    e.stopPropagation();
    e.preventDefault();

    const self = this;
    var files;
    if (e.dataTransfer != null) files = e.dataTransfer.files;
    else if (e.target != null) files = e.target.files;

    var file = files[0];
    if (!this.validateFile(file)) {
      alert("File type not allowed");
      return;
    }
    var reader = new FileReader();
    reader.onload = function (e) {
      var xml = e.target.result;
      this.diagramXML = xml;
      self.openDiagram(xml);
      self.state.dirty = true;
    };
    reader.readAsText(file);
  }

  handleDragOver(e) {
    e.stopPropagation();
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy"; // Explicitly show this is a copy.
  }

  async back(ev) {
    this.saveDiagram(ev);
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "rmt.bpmn.model",
      views: [[false, "list"]],
      view_mode: "list",
      name: "BPMN Model",
      target: "main",
    });
  }

  async saveDiagram(ev) {
    try {
      const { xml } = await this.modeler.saveXML({ format: true });
      await this.orm.write("rmt.bpmn.model", [this.modelId], {
        bpmn_data: encodeURIComponent(xml),
      });
      this.notificationService.add(_t(`Diagram Saved`), { type: "info" });
      this.state.dirty = false;
    } catch (error) {
      console.error(error);
    }
  }

  async discardDiagram(ev) {
    if (this.state.dirty) {
      if (this.modelId)
        this.diagramXML = decodeURIComponent(this.record.bpmn_data);
      else this.diagramXML = defaultDiagramXML;
      await this.openDiagram(decodeURIComponent(this.diagramXML));
      this.state.dirty = false;
    }
  }

  async createNewDiagram() {
    await this.openDiagram(this.diagramXML);
  }
}
BPMNModelerAction.template = "rmt_bpmn.Viewer";

// remember the tag name we put in the first step
registry.category("actions").add("rmt_bpmn.BpmnModeler", BPMNModelerAction);
registry.category("actions").add("rmt_bpmn.BpmnViewer", BPMNViewerAction);
