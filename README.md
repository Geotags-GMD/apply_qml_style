# Apply QML Style Manager

## Description
Apply QML Style Manager is a powerful QGIS plugin designed to streamline the process of applying QML styles to layers within specific layer groups. This plugin is particularly useful for managing and styling large sets of geospatial data where consistent visual representation is crucial.

### Key Features:
- **Multi-Select Layer Groups:** Users can select multiple layer groups simultaneously for efficient style management.
- **Automated Style Application:** Automatically applies predefined QML styles to layers based on a JSON configuration file (`qml_styles.json`) located in the selected folder.
- **Customizable Layer Order:** Rearranges layers within groups according to a specified order, ensuring that important layers are displayed on top.
- **Duplicate Removal:** Identifies and removes duplicate layers within the selected groups to maintain a clean and organized layer structure.
- **Progress Tracking:** A built-in progress bar provides real-time feedback on the status of the style application process.
- **Folder Selection and Persistence:** Users can select a folder containing QML files, with the option to save the selected folder path for future sessions.

### Use Cases:
- **Consistent Layer Styling:** Ensure that all layers within your project adhere to a consistent visual style, enhancing the readability and professionalism of your maps.
- **Efficient Layer Management:** Manage and organize large datasets more effectively by automatically applying styles and removing duplicates.
- **Batch Processing:** Apply styles to multiple layer groups in one go, saving time and reducing manual errors.

## Installation
Install the plugin through the QGIS Plugin Manager. Ensure that the `qml_styles.json` file is properly configured and located in the selected folder.

## Usage
1. Launch the plugin from the QGIS toolbar.
2. Select the folder containing your QML style files.
3. Choose the layer groups to which you want to apply the styles.
4. Click "Run" to apply the styles, rearrange layers, and remove duplicates.

This plugin is ideal for GIS professionals and map creators who require a streamlined and automated approach to managing layer styles in QGIS.
