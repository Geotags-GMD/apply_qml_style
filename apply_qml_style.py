import os
import json , re
from qgis.core import QgsProject, QgsLayerTreeLayer
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QPushButton, QVBoxLayout, QDialog, QLabel, QProgressBar, QListWidget, QListWidgetItem, QHBoxLayout, QMessageBox, QComboBox
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QThread, pyqtSignal
import requests

class QMLUpdateWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, github_repo, qml_folder, qml_files, json_file):
        super().__init__()
        self.github_repo = github_repo
        self.qml_folder = qml_folder
        self.qml_files = qml_files
        self.json_file = json_file

    def run(self):
        try:
            # Check for internet connectivity
            test_url = f"{self.github_repo}{self.json_file}"
            requests.get(test_url, timeout=5)
        except requests.ConnectionError:
            self.error.emit("No Internet Connection. Please check your connection and try again.")
            return
        except Exception as e:
            self.error.emit(f"Error checking connectivity: {str(e)}")
            return

        total_files = len(self.qml_files)
        self.progress.emit(0, f"Starting download of {total_files} files...")

        for index, qml_file in enumerate(self.qml_files):
            try:
                url = f"{self.github_repo}{qml_file}"
                response = requests.get(url, stream=True)
                response.raise_for_status()

                qml_path = os.path.join(self.qml_folder, qml_file)
                os.makedirs(os.path.dirname(qml_path), exist_ok=True)

                with open(qml_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                progress = int(((index + 1) / total_files) * 100)
                self.progress.emit(progress, f"Updated QML file: {qml_file}")
            except Exception as e:
                self.error.emit(f"Error downloading {qml_file}: {str(e)}")
                return

        self.finished.emit()

class MyQGISPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = 'GMD Plugins'
        self.qml_folder = None
        self.json_file = "qml_files.json"  # The JSON file to load the QML names
        self.github_repo = "https://raw.githubusercontent.com/Geotags-GMD/qml-store/refs/heads/main/qml-files/"
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
        self.process_combo.addItems(["Select Style Format", "Geotagging", "Processing", "Digitize"])
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
        self.message_label = QLabel("")
        layout.addWidget(self.message_label)  # Add the label to the layout
        self.message_label.setVisible(False)  # Initially hide the label

        # Add version label at the bottom
        version_label = QLabel("Version: 6.1.0")
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

            # Check if there are QML files in the selected folder
            qml_files = [f for f in os.listdir(folder) if f.endswith('.qml')]
            if not qml_files:
                QMessageBox.warning(None, "No QML Files", "No QML files found in the selected folder. Please click 'Update QML' to download the latest QML files.")

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
        layer_name = layer.name().lower()  # Ensure lowercase for comparison
        
        for key, qml_file in qml_files.items():
            if key in layer_name:
                try:
                    result = layer.loadNamedStyle(qml_file)  # Check if successful
                    if result == 0:
                        iface.messageBar().pushWarning("Warning", f"Style file not applied for {layer_name}. Check the QML Folder.")
                    else:
                        layer.triggerRepaint()  # Ensure refresh

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

        # Check if there are QML files in the selected folder
        qml_files = [f for f in os.listdir(self.qml_folder) if f.endswith('.qml')]
        if not qml_files:
            iface.messageBar().pushCritical("Error", "No QML files found in the selected folder. Please click 'Update QML' to download the latest QML files.")
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
            'form8b': os.path.join(self.qml_folder, '3. 2024 POPCEN-CBMS Form 8B.qml'),
            'refSF': os.path.join(self.qml_folder, 'SF Reference Data.qml'),
            'refGP': os.path.join(self.qml_folder, 'GP Reference Data.qml')
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

         # Change to find any group ending with 'SFGP_RefData'
        refData = next((group for group in root.findGroups() if group.name().endswith('SFGP_RefData')), None)
        if refData:
            refDatalayer = [node.layer() for node in refData.children() if isinstance(node, QgsLayerTreeLayer)]
            for layer in refDatalayer:
                    if 'SF_RefData' in layer.name():
                        layer.loadNamedStyle(qml_files['refSF'])
                        layer.triggerRepaint()
                    elif 'GP_RefData' in layer.name():
                        layer.loadNamedStyle(qml_files['refGP'])
                        layer.triggerRepaint()


        # Ensure the progress bar reaches 100%
        self.progress_bar.setValue(total_layers)
        iface.messageBar().pushInfo("Process Complete", "Styles applied, layers rearranged, and duplicates removed for selected groups. Styles applied to layers outside the selected groups.")


    def update_qml(self):
        if not self.qml_folder:
            self.message_label.setText("Please select a QML folder first.")
            self.message_label.setVisible(True)
            return

        self.message_label.setVisible(True)
        self.message_label.setText("Updating QML files...")
        
        # Create and configure the worker with json_file parameter
        self.worker = QMLUpdateWorker(
            self.github_repo, 
            self.qml_folder, 
            self.qml_files,
            self.json_file
        )
        
        # Connect signals
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.update_completed)
        self.worker.error.connect(self.update_error)
        
        # Start the worker
        self.worker.start()
        
        # Disable the update button while working
        self.update_button.setEnabled(False)

    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.message_label.setText(message)

    def update_completed(self):
        self.message_label.setText("Download complete!")
        self.message_label.setVisible(False)
        self.update_button.setEnabled(True)
        QMessageBox.information(None, "Update Complete", "All QML files have been successfully updated.")

    def update_error(self, error_message):
        self.message_label.setText(error_message)
        self.message_label.setVisible(True)
        self.update_button.setEnabled(True)
        QMessageBox.critical(None, "Error", error_message)

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


    # Select the process to run
    def run_selected_process(self):
        selected = self.process_combo.currentText()

        if selected == "Select Style Format":
            self.iface.messageBar().pushWarning("Warning", "Please select a valid style format!")
            return

        if selected == "Geotagging":
            self.run_geotagging()
        elif selected == "Processing":
            self.run_processing()
        elif selected == "Digitize":
            self.run_digitize()


    #Activity Processing Style
    def run_processing(self):
        if not self.qml_folder:
            iface.messageBar().pushCritical("Error", "Please select a folder first.")
            return

        # Check if there are QML files in the selected folder
        qml_files = [f for f in os.listdir(self.qml_folder) if f.endswith('.qml')]
        if not qml_files:
            iface.messageBar().pushCritical("Error", "No QML files found in the selected folder. Please click 'Update QML' to download the latest QML files.")
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
            # 'form8a': os.path.join(self.qml_folder, '2. 2024 POPCEN-CBMS Form 8A.qml'),
            # 'form8b': os.path.join(self.qml_folder, '3. 2024 POPCEN-CBMS Form 8B.qml'),
            'refSF': os.path.join(self.qml_folder, 'SF Reference Data.qml'),
            'refGP': os.path.join(self.qml_folder, 'GP Reference Data.qml')
        }

      

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

    

        # Change to find any group ending with 'Form 8'
        # form8_group = next((group for group in root.findGroups() if group.name().endswith('Form 8')), None)
        # if form8_group:
        #     form8_layers = [node.layer() for node in form8_group.children() if isinstance(node, QgsLayerTreeLayer)]
        #     for layer in form8_layers:
        #         if layer.name().endswith('_SF'):
        #             layer.loadNamedStyle(qml_files['form8a'])
        #             layer.triggerRepaint()
        #         elif layer.name().endswith('_GP'):
        #             layer.loadNamedStyle(qml_files['form8b'])
        #             layer.triggerRepaint()

         # Change to find any group ending with 'SFGP_RefData'
        refData = next((group for group in root.findGroups() if group.name().endswith('SFGP_RefData')), None)
        if refData:
            refDatalayer = [node.layer() for node in refData.children() if isinstance(node, QgsLayerTreeLayer)]
            for layer in refDatalayer:
                    if 'SF_RefData' in layer.name():
                        layer.loadNamedStyle(qml_files['refSF'])
                        layer.triggerRepaint()
                    elif 'GP_RefData' in layer.name():
                        layer.loadNamedStyle(qml_files['refGP'])
                        layer.triggerRepaint()


        # Ensure the progress bar reaches 100%
        self.progress_bar.setValue(total_layers)
        iface.messageBar().pushInfo("Process Complete", "Styles applied, layers rearranged, and duplicates removed for selected groups. Styles applied to layers outside the selected groups.")

     #Activity Digitize Style
    def run_digitize(self):
        if not self.qml_folder:
            iface.messageBar().pushCritical("Error", "Please select a folder first.")
            return

        # Check if there are QML files in the selected folder
        qml_files = [f for f in os.listdir(self.qml_folder) if f.endswith('.qml')]
        if not qml_files:
            iface.messageBar().pushCritical("Error", "No QML files found in the selected folder. Please click 'Update QML' to download the latest QML files.")
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
            'formSF': os.path.join(self.qml_folder, 'SF Map Digitization.qml'),
            'formGP': os.path.join(self.qml_folder, 'GP Map Digitization.qml'),
        }


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

      
        form8_group = next((group for group in root.findGroups() if group.name().endswith('Form 8')), None)
        if form8_group:
            form8_layers = [node.layer() for node in form8_group.children() if isinstance(node, QgsLayerTreeLayer)]
            for layer in form8_layers:
                if layer.name().endswith('_SF'):
                    layer.loadNamedStyle(qml_files['formSF'])
                    layer.triggerRepaint()
                elif layer.name().endswith('_GP'):
                    layer.loadNamedStyle(qml_files['formGP'])
                    layer.triggerRepaint()


        # Ensure the progress bar reaches 100%
        self.progress_bar.setValue(total_layers)
        iface.messageBar().pushInfo("Process Complete", "Styles applied, layers rearranged, and duplicates removed for selected groups. Styles applied to layers outside the selected groups.")

