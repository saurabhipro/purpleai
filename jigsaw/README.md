# PurpleMaps

PurpleMaps is an interactive entity mapping and structure diagramming tool built as an Odoo module. It allows users to visualize complex ownership hierarchies, relationships, and entity structures with a modern, responsive interface.

## 🚀 Key Features

-   **Interactive Diagrams**: Drag-and-drop nodes to customize your layout.
-   **Multi-Select & Pan/Zoom**: Efficiently navigate large diagrams with keyboard modifiers and mouse controls.
-   **Ownership Filtering**: Dynamically highlight upstream and downstream ownership paths with configurable percentage thresholds.
-   **Organization Tools**: Auto-layout algorithms (Tree Layout) and "Fit to Screen" functionality for instant clarity.
-   **Rich Metadata**: View and edit entity properties, relationships, and files directly from the diagram.
-   **Export Capabilities**: One-click export of entity data to CSV for external analysis.
-   **Customizable Aesthetics**: Change node colors and shapes based on entity types or individual preferences.
-   **Annotation System**: Add comments and track discussions directly on specific entities.

## 🛠 Technology Stack

-   **Framework**: Odoo 18.0
-   **Frontend**: Odoo OWL (Odoo Web Library) - a React-inspired declarative component framework.
-   **Styling**: SCSS / Vanilla CSS with modern features like `clip-path` and CSS variables.
-   **Icons**: Font Awesome (integrated with Odoo).
-   **Backend**: Python / PostgreSQL (Odoo Models).

## 📦 Project Structure

```text
jigsaw/
├── models/             # Odoo Python models (Diagrams, Entities, Relations)
├── views/              # Odoo XML views and menus
├── data/               # Demo data and system configuration
├── static/
│   └── src/
│       └── workshop/
│           ├── workshop.js    # Main OWL Component logic (React-style)
│           ├── workshop.xml   # OWL XML Template (JSX equivalent)
│           └── workshop.scss  # Component-specific styles
└── __manifest__.py     # Module metadata and asset registration
```

## 🎨 Design Philosophy

PurpleMaps prioritizes **Visual Excellence** and **User Engagement**:
-   **Modern Palette**: Uses vibrant, type-specific colors and sleek dark modes.
-   **Dynamic Feedback**: Hover effects, smooth transitions, and real-time updates make the interface feel alive.
-   **Functional Shapes**: Unique geometric shapes (using `clip-path`) help distinguish between different entity categories at a glance.

## 🚀 Getting Started

1.  **Install Odoo 18**: Ensure you have a working Odoo 18 environment.
2.  **Add Module**: Copy the `jigsaw` folder to your Odoo `addons` path.
3.  **Update App List**: Log in to Odoo, activate developer mode, and go to **Apps > Update App List**.
4.  **Install**: Search for `PurpleMaps` and click **Install**.
5.  **Access**: Find the `PurpleMaps` menu in the Odoo dashboard to start creating diagrams.

## ⌨️ Controls

-   **Left Click**: Select a node.
-   **Ctrl/Cmd + Click**: Multi-select nodes.
-   **Drag**: Move selected node(s).
-   **Right Click**: Open context menu for coloring and quick actions.
-   **Scroll / Ctrl+Scroll**: Pan and Zoom the canvas.

---

Developed with ❤️ by the Bhuarjan Team.
