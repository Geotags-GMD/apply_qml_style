import os
import json
import re
from qgis.core import QgsProject, QgsLayerTreeLayer
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QPushButton, QVBoxLayout, QDialog, QLabel, QProgressBar, QListWidget, QListWidgetItem
from qgis.PyQt.QtGui import QIcon

class MyQGISPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = 'GMD Plugins'
        self.qml_folder = None
        self.qml_config = None
        self.load_saved_folder()
        self.load_qml_config()

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.action = QAction(QIcon(icon_path), 'Open QML Style Manager', self.iface.mainWindow())
        self.action.setWhatsThis('Open QML Style Manager')
        self.action.triggered.connect(self.open_dialog)
        self.iface.addPluginToMenu(self.menu, self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        self.iface.removePluginMenu(self.menu, self.action)
        self.iface.removeToolBarIcon(self.action)

    def open_dialog(self):
        dialog = QDialog()
        dialog.setWindowTitle("QML Style Manager")

        layout = QVBoxLayout()

        self.folder_label = QLabel("Select the folder containing QML files:")
        layout.addWidget(self.folder_label)

        self.select_button = QPushButton("Select Folder")
        self.select_button.clicked.connect(self.select_folder)
        layout.addWidget(self.select_button)

        # ListWidget to select multiple layer groups
        self.group_listwidget = QListWidget()
        self.group_listwidget.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(QLabel("Select Layer Groups:"))
        layout.addWidget(self.group_listwidget)

        # Populate the ListWidget with available layer groups
        self.populate_layer_groups()

        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.run)
        layout.addWidget(self.run_button)

        # Add a progress bar to the dialog
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Display the saved folder path if available
        if self.qml_folder:
            display_folder = os.path.basename(self.qml_folder)
            self.folder_label.setText(f"Selected Folder: .../{display_folder}")

        # Add version label at the bottom
        version_label = QLabel("Version: 5.3 build 1")
        layout.addWidget(version_label)

        dialog.setLayout(layout)
        dialog.exec_()

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(None, "Select QML Folder")
        if folder:
            self.qml_folder = folder
            display_folder = os.path.basename(folder)
            self.folder_label.setText(f"Selected Folder: .../{display_folder}")
            with open(self.get_folder_path_file(), 'w') as f:
                json.dump({'folder': folder}, f)
            self.load_qml_config()
            self.populate_layer_groups()

    def get_folder_path_file(self):
        return os.path.join(self.plugin_dir, 'folder_path.json')

    def load_saved_folder(self):
        path_file = self.get_folder_path_file()
        if os.path.exists(path_file):
            with open(path_file, 'r') as f:
                data = json.load(f)
                self.qml_folder = data.get('folder', '')

    def load_qml_config(self):
        if self.qml_folder:
            qml_config_path = os.path.join(self.qml_folder, 'qml_config.json')
            try:
                with open(qml_config_path, 'r') as f:
                    self.qml_config = json.load(f)
            except FileNotFoundError:
                iface.messageBar().pushWarning("Warning", f"QML configuration file not found: {qml_config_path}")
                self.qml_config = None
            except json.JSONDecodeError:
                iface.messageBar().pushWarning("Warning", f"Invalid JSON in QML configuration file: {qml_config_path}")
                self.qml_config = None

    def populate_layer_groups(self):
        self.group_listwidget.clear()
        if self.qml_config is None:
            iface.messageBar().pushWarning("Warning", "No valid QML configuration loaded. Layer groups not populated.")
            return
        root = QgsProject.instance().layerTreeRoot()
        groups = root.findGroups()
        config_groups = self.qml_config.get('layer_groups', [])
        for group in groups:
            if any(group.name().endswith(suffix) for suffix in config_groups):
                item = QListWidgetItem(group.name())
                self.group_listwidget.addItem(item)

    def apply_styles_to_layer(self, layer, qml_files):
        """Apply QML styles to a given layer based on its name."""
        layer_name = layer.name()
        for key, qml_file in qml_files.items():
            if key in layer_name.lower():
                try:
                    layer.loadNamedStyle(qml_file)
                    layer.triggerRepaint()
                except Exception as e:
                    iface.messageBar().pushCritical("Error", f"Failed to load style for {layer_name}: {str(e)}")

    def rearrange_layers(self, group, layers, layer_order):
        """Rearrange layers within the selected group according to the specified order."""
        layer_dict = {layer.name().lower(): layer for layer in layers}
        for layer_name in layer_order:
            for key, layer in layer_dict.items():
                if layer_name in key:
                    group.removeChildNode(QgsLayerTreeLayer(layer))
                    group.insertChildNode(0, QgsLayerTreeLayer(layer))
                    break

    def remove_duplicate_layers(self, group):
        """Remove duplicate layers from the given group."""
        layer_names = set()
        nodes_to_remove = []
        
        for node in group.children():
            if isinstance(node, QgsLayerTreeLayer):
                layer = node.layer()
                layer_name = layer.name()
                if layer_name in layer_names:
                    nodes_to_remove.append(node)
                else:
                    layer_names.add(layer_name)
        
        for node in nodes_to_remove:
            group.removeChildNode(node)

    def run(self):
        if not self.qml_folder:
            iface.messageBar().pushCritical("Error", "Please select a folder first.")
            return

        selected_groups = [item.text() for item in self.group_listwidget.selectedItems()]
        if not selected_groups:
            iface.messageBar().pushCritical("Error", "Please select at least one layer group.")
            return

        # Load QML file paths from JSON
        qml_config_path = os.path.join(self.qml_folder, 'qml_config.json')
        try:
            with open(qml_config_path, 'r') as f:
                self.qml_config = json.load(f)
        except FileNotFoundError:
            iface.messageBar().pushCritical("Error", f"QML configuration file not found: {qml_config_path}")
            return
        except json.JSONDecodeError:
            iface.messageBar().pushCritical("Error", f"Invalid JSON in QML configuration file: {qml_config_path}")
            return

        qml_files = {key: os.path.join(self.qml_folder, value) for key, value in self.qml_config['qml_files'].items()}
        outside_group_qml = [os.path.join(self.qml_folder, qml) for qml in self.qml_config['outside_group_qml']]
        layer_order = self.qml_config['layer_order']

        root = QgsProject.instance().layerTreeRoot()
        total_layers = 0

        # Track layers that have been processed within selected groups
        processed_layers = set()

        # Process layers within selected groups
        for selected_group_name in selected_groups:
            selected_group = root.findGroup(selected_group_name)
            if not selected_group:
                iface.messageBar().pushCritical("Error", f"Layer group '{selected_group_name}' not found.")
                continue

            layers = [node.layer() for node in selected_group.children() if isinstance(node, QgsLayerTreeLayer)]
            total_layers += len(layers)

        # Add count for layers outside the selected groups
        all_layers = [node.layer() for node in root.children() if isinstance(node, QgsLayerTreeLayer)]
        outside_layers = [layer for layer in all_layers if layer not in processed_layers]
        total_layers += len(outside_layers)

        self.progress_bar.setMaximum(total_layers)
        self.progress_bar.setValue(0)

        # Process layers within selected groups
        for selected_group_name in selected_groups:
            selected_group = root.findGroup(selected_group_name)
            if not selected_group:
                continue

            layers = [node.layer() for node in selected_group.children() if isinstance(node, QgsLayerTreeLayer)]
            for layer in layers:
                self.apply_styles_to_layer(layer, qml_files)
                processed_layers.add(layer)
                self.progress_bar.setValue(self.progress_bar.value() + 1)

            # Rearrange layers within the selected group according to layer_order
            self.rearrange_layers(selected_group, layers, layer_order)
            
            # Remove duplicate layers
            self.remove_duplicate_layers(selected_group)

        # Process layers outside the selected groups
        for layer in outside_layers:
            if self.should_apply_outside_group_style(layer):
                for qml_file in outside_group_qml:
                    try:
                        layer.loadNamedStyle(qml_file)
                        layer.triggerRepaint()
                    except Exception as e:
                        iface.messageBar().pushCritical("Error", f"Failed to load style for {layer.name()}: {str(e)}")
            self.progress_bar.setValue(self.progress_bar.value() + 1)

        # Ensure the progress bar reaches 100%
        self.progress_bar.setValue(total_layers)
        iface.messageBar().pushInfo("Process Complete", "Styles applied, layers rearranged, and duplicates removed for selected groups. Styles applied to layers outside the selected groups.")

    def should_apply_outside_group_style(self, layer):
        """Determine if a layer should have styles applied from 'outside_group_qml'."""
        if self.qml_config is None:
            return False

        # Fetch the regex pattern from the config
        pattern = self.qml_config.get('outside_group_pattern', r'^\d{14}')

        # Fetch additional keywords from the config
        keywords = self.qml_config.get('additional_conditions', {}).get('keywords', [])
        
        # Check if the layer name matches the regex pattern
        matches_pattern = re.match(pattern, layer.name()) is not None
        
        # Check if the layer name contains any of the keywords
        matches_keyword = any(keyword in layer.name().lower() for keyword in keywords)

        # Return True if either condition is met
        return matches_pattern or matches_keyword
