import os
import json , re
from qgis.core import QgsProject, QgsLayerTreeLayer
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QPushButton, QVBoxLayout, QDialog, QLabel, QProgressBar, QListWidget, QListWidgetItem, QHBoxLayout, QMessageBox, QComboBox
from qgis.PyQt.QtGui import QIcon
import requests

class MyQGISPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = 'GMD Plugins'
        self.qml_folder = None
        self.json_file = "qml_files.json"  # The JSON file to load the QML names
        self.github_repo = "https://raw.githubusercontent.com/kentemman-gmd/qml-store/refs/heads/main/qml-files/"
        # Load the saved folder path if it exists
        self.load_saved_folder()
        self.qml_files = self.load_qml_files()

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

        

        # Buttons layout
        button_layout = QHBoxLayout()
        self.select_button = QPushButton("Select Folder")
        self.select_button.clicked.connect(self.select_folder)
        self.update_button = QPushButton("Update QML")
        self.update_button.setFixedSize(70, 23)
        self.update_button.clicked.connect(self.update_qml)
        
        # # Run button
        # self.run_button = QPushButton("Run")
        # self.run_button.clicked.connect(self.run_selected_process)
        
        button_layout.addWidget(self.select_button)
        button_layout.addWidget(self.update_button)
        # button_layout.addWidget(self.run_button)
        layout.addLayout(button_layout)

        # Add dropdown menu
        self.process_combo = QComboBox()
        # layout.addWidget(QLabel("Select Style:"))
        self.process_combo.addItems(["Select Style Format", "Geotagging Style", "Processing Style"])
        layout.addWidget(self.process_combo)

        # ListWidget to select multiple layer groups
        self.group_listwidget = QListWidget()
        self.group_listwidget.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(QLabel("Select Layer Groups:"))
        layout.addWidget(self.group_listwidget)

        # Populate the ListWidget with available layer groups
        self.populate_layer_groups()

        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.run_selected_process)
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

         # Create a label to display messages
        self.label = QLabel("")
        layout.addWidget(self.label)  # Add the label to the layout
        self.label.setVisible(False)  # Initially hide the label

        # Add version label at the bottom
        version_label = QLabel("Version: 5.24")
        layout.addWidget(version_label)

       

        dialog.setLayout(layout)
        dialog.exec_()

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(None, "Select QML Folder")
        if folder:
            self.qml_folder = folder

            # Display only the last part of the path
            display_folder = os.path.basename(folder)
            self.folder_label.setText(f"Selected Folder: .../{display_folder}")

            # Save the folder path to a JSON file
            with open(self.get_folder_path_file(), 'w') as f:
                json.dump({'folder': folder}, f)

    def get_folder_path_file(self):
        return os.path.join(self.plugin_dir, 'folder_path.json')

    def load_saved_folder(self):
        path_file = self.get_folder_path_file()
        if os.path.exists(path_file):
            with open(path_file, 'r') as f:
                data = json.load(f)
                self.qml_folder = data.get('folder', '')

    def populate_layer_groups(self):
        """Populate the list widget with layer groups ending with '_2024maplayers'."""
        self.group_listwidget.clear()
        root = QgsProject.instance().layerTreeRoot()
        groups = root.findGroups()
        for group in groups:
            if group.name().endswith('Base Layers') or group.name().endswith('_2024maplayers'):
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


    #Activity Geotagging Style
    def run_geotagging(self):
        if not self.qml_folder:
            iface.messageBar().pushCritical("Error", "Please select a folder first.")
            return

        selected_groups = [item.text() for item in self.group_listwidget.selectedItems()]
        if not selected_groups:
            iface.messageBar().pushCritical("Error", "Please select at least one layer group.")
            return


        qml_files = {
            'bgy': os.path.join(self.qml_folder, '7. 2024 POPCEN-CBMS Barangay.qml'),
            'ea': os.path.join(self.qml_folder, '6. 2024 POPCEN-CBMS EA.qml'),
            'block': os.path.join(self.qml_folder, '5. 2024 POPCEN-CBMS Block.qml'),
            'landmark': os.path.join(self.qml_folder, '10. 2024 POPCEN-CBMS Landmark.qml'),
            'road': os.path.join(self.qml_folder, '8. 2024 POPCEN-CBMS Road.qml'),
            'river': os.path.join(self.qml_folder, '9. 2024 POPCEN-CBMS River.qml'),
            'bldg_point': os.path.join(self.qml_folder, '4. 2024 POPCEN-CBMS Building Points.qml'),
            'bldgpts': os.path.join(self.qml_folder, '4. 2024 POPCEN-CBMS Building Points.qml'),
            'form8a': os.path.join(self.qml_folder, '2. 2024 POPCEN-CBMS Form 8A.qml'),
            'form8b': os.path.join(self.qml_folder, '3. 2024 POPCEN-CBMS Form 8B.qml')
        }

        outside_group_qml_11 = os.path.join(self.qml_folder, '11. 2024 POPCEN-CBMS F2 Digitization.qml')
        outside_group_qml_12 = os.path.join(self.qml_folder, '12. 2024 POPCEN-CBMS F2 MP.qml')

        layer_order = ['river', 'road', 'block', 'ea', 'bgy', 'landmark', 'bldg_point','bldgpts']

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

        # Regular expression pattern to match a 14-digit number at the start of the layer name
        digit_pattern = re.compile(r'^\d{14}')

        # Process layers outside the selected groups
        for layer in outside_layers:

            # Check if the layer name starts with a 14-digit number
            if digit_pattern.match(layer.name()):
                try:
                    # Apply 11th QML style first
                    layer.loadNamedStyle(outside_group_qml_11)
                    layer.triggerRepaint()

                    # Then apply 12th QML style
                    layer.loadNamedStyle(outside_group_qml_12)
                    layer.triggerRepaint()

                except Exception as e:
                    iface.messageBar().pushCritical("Error", f"Failed to load style for {layer.name()}: {str(e)}")
                    
            # Update the progress bar for each layer processed
            self.progress_bar.setValue(self.progress_bar.value() + 1)

        # Change to find any group ending with 'Form 8'
        form8_group = next((group for group in root.findGroups() if group.name().endswith('Form 8')), None)
        if form8_group:
            form8_layers = [node.layer() for node in form8_group.children() if isinstance(node, QgsLayerTreeLayer)]
            for layer in form8_layers:
                if layer.name().endswith('_SF'):
                    layer.loadNamedStyle(qml_files['form8a'])
                    layer.triggerRepaint()
                elif layer.name().endswith('_GP'):
                    layer.loadNamedStyle(qml_files['form8b'])
                    layer.triggerRepaint()

        # Ensure the progress bar reaches 100%
        self.progress_bar.setValue(total_layers)
        iface.messageBar().pushInfo("Process Complete", "Styles applied, layers rearranged, and duplicates removed for selected groups. Styles applied to layers outside the selected groups.")


    def update_qml(self):
        if not self.qml_folder:
            self.label.setText("Please select a QML folder first.")
            return

        self.label.setVisible(True)  # Show the label at the start of the update
        self.label.setText("Updating QML files...")  # Set initial message

        total_files = len(self.qml_files)
        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(0)

        for index, qml_file in enumerate(self.qml_files):
            try:
                url = f"{self.github_repo}{qml_file}"
                response = requests.get(url, stream=True)
                response.raise_for_status()  # Raise an error for bad responses

                qml_path = os.path.join(self.qml_folder, qml_file)

                with open(qml_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:  # Filter out keep-alive new chunks
                            f.write(chunk)

                self.label.setText(f"Updated QML file downloaded: {qml_path}")
            except Exception as e:
                self.label.setText(f"Error downloading {qml_file}: {str(e)}")

            self.progress_bar.setValue(index + 1)

        self.label.setText("Download complete!")  # Final message
        # Optionally hide the label after completion
        self.label.setVisible(False)

        # Add message box to confirm completion
        QMessageBox.information(None, "Update Complete", "All QML files have been successfully updated.")

    def load_qml_files(self):
        """Load QML file names from a JSON file."""
        url = f"{self.github_repo}{self.json_file}"
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad responses
            json_data = response.json()
            return json_data.get("qml_files", [])
        except Exception as e:
            self.label.setText(f"Error loading QML files: {str(e)}")
            return []

    def run_selected_process(self):
        selected = self.process_combo.currentText()

        if selected == "Select Style Format":
            self.iface.messageBar().pushWarning("Warning", "Please select a valid style format!")
            return

        if selected == "Geotagging Style":
            self.run_geotagging()
        elif selected == "Processing Style":
            self.run_processing()


    #Activity Processing Style
    def run_processing(self):
        # Implement processing logic here 
        iface.messageBar().pushWarning("Processing", "Ongoing Development for Processing Style...")
