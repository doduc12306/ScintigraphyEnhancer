import logging

import ctk
import qt
import slicer
import vtk
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleTest,
    ScriptedLoadableModuleWidget,
)


#
# ScintigraphyEnhancer
#


class ScintigraphyEnhancer(ScriptedLoadableModule):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent.title = "ScintigraphyEnhancer"
        self.parent.categories = ["Nuclear Medicine"]
        self.parent.dependencies = []
        self.parent.contributors = ["Duc Do"]
        self.parent.helpText = (
            "Tiền xử lý ảnh Nuclear Medicine/PET/SPECT với Window-Level, LUT, "
            "Threshold, Bilateral smoothing và reset nhanh."
        )
        self.parent.acknowledgementText = "Scripted module for 3D Slicer"


#
# ScintigraphyEnhancerWidget
#


class ScintigraphyEnhancerWidget(ScriptedLoadableModuleWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logic = ScintigraphyEnhancerLogic()

        self._selectedVolumeNode = None
        self._updatingWindowLevelSliders = False
        self._updatingThresholdRange = False
        self._updatingColormap = False
        self._initialStateByVolumeID = {}

        self._colorPresets = {
            "Grey": ["Grey", "Grayscale"],
            "PET-DICOM": ["PET-DICOM", "PET DICOM"],
        }

        # --- Normalize click state ---
        self._normalizeActive = False
        self._normalizeObserverTags = []  # list of (interactor, tagId)

    def setup(self):
        super().setup()

        # Tìm đường dẫn thư mục Icons
        import os
        iconsPath = os.path.join(os.path.dirname(__file__), "Resources", "Icons")

        mainHLayout = qt.QHBoxLayout()
        self.layout.addLayout(mainHLayout)

        leftVLayout = qt.QVBoxLayout()
        mainHLayout.addLayout(leftVLayout)

        leftVLayout.addWidget(self._createInputSection())
        leftVLayout.addWidget(self._createActionSection(iconsPath))
        leftVLayout.addWidget(self._createAdvancedSection())
        leftVLayout.addStretch(1)

        # --- Cột phải: Threshold (Range Slider dọc, 1 thanh 2 handle) ---
        rightVLayout = qt.QVBoxLayout()
        rightVLayout.setAlignment(qt.Qt.AlignTop | qt.Qt.AlignHCenter)
        mainHLayout.addLayout(rightVLayout)

        sliderLabel = qt.QLabel("Threshold")
        sliderLabel.alignment = qt.Qt.AlignCenter
        sliderLabel.setStyleSheet("font-weight: bold;")
        rightVLayout.addWidget(sliderLabel)

        # SpinBox ngưỡng trên
        self.upperThresholdSpinBox = ctk.ctkDoubleSpinBox()
        self.upperThresholdSpinBox.decimals = 2
        self.upperThresholdSpinBox.minimum = 0.0
        self.upperThresholdSpinBox.maximum = 1000.0
        self.upperThresholdSpinBox.value = 1000.0
        self.upperThresholdSpinBox.setFixedWidth(100)
        self.upperThresholdSpinBox.toolTip = "Ngưỡng trên (Upper)"
        rightVLayout.addWidget(self.upperThresholdSpinBox, 0, qt.Qt.AlignHCenter)

        # Range Slider dọc (1 thanh, 2 handle)
        self.thresholdRangeSlider = ctk.ctkDoubleRangeSlider()
        self.thresholdRangeSlider.orientation = qt.Qt.Vertical
        self.thresholdRangeSlider.singleStep = 1.0
        self.thresholdRangeSlider.minimum = 0.0
        self.thresholdRangeSlider.maximum = 1000.0
        self.thresholdRangeSlider.minimumValue = 0.0
        self.thresholdRangeSlider.maximumValue = 1000.0
        self.thresholdRangeSlider.toolTip = "Kéo handle trên/dưới để chỉnh ngưỡng"
        self.thresholdRangeSlider.minimumHeight = 400
        rightVLayout.addWidget(self.thresholdRangeSlider, 1, qt.Qt.AlignHCenter)

        # SpinBox ngưỡng dưới
        self.lowerThresholdSpinBox = ctk.ctkDoubleSpinBox()
        self.lowerThresholdSpinBox.decimals = 2
        self.lowerThresholdSpinBox.minimum = 0.0
        self.lowerThresholdSpinBox.maximum = 1000.0
        self.lowerThresholdSpinBox.value = 0.0
        self.lowerThresholdSpinBox.setFixedWidth(100)
        self.lowerThresholdSpinBox.toolTip = "Ngưỡng dưới (Lower)"
        rightVLayout.addWidget(self.lowerThresholdSpinBox, 0, qt.Qt.AlignHCenter)

        # Đồng bộ range slider ↔ spinboxes
        self.thresholdRangeSlider.connect("maximumValueChanged(double)", self.upperThresholdSpinBox.setValue)
        self.thresholdRangeSlider.connect("minimumValueChanged(double)", self.lowerThresholdSpinBox.setValue)
        self.upperThresholdSpinBox.connect("valueChanged(double)", self._onUpperSpinBoxChanged)
        self.lowerThresholdSpinBox.connect("valueChanged(double)", self._onLowerSpinBoxChanged)

        self._connectSignals()
        self._setControlsEnabled(False)

    def cleanup(self):
        self._removeNormalizeObservers()

    def _createInputSection(self):
        groupBox = ctk.ctkCollapsibleButton()
        groupBox.text = "Dữ liệu vào"
        groupBox.collapsed = False
        formLayout = qt.QFormLayout(groupBox)

        self.inputVolumeSelector = slicer.qMRMLNodeComboBox()
        self.inputVolumeSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.inputVolumeSelector.selectNodeUponCreation = True
        self.inputVolumeSelector.addEnabled = False
        self.inputVolumeSelector.removeEnabled = False
        self.inputVolumeSelector.noneEnabled = True
        self.inputVolumeSelector.showHidden = False
        self.inputVolumeSelector.showChildNodeTypes = False
        self.inputVolumeSelector.setMRMLScene(slicer.mrmlScene)
        self.inputVolumeSelector.setToolTip("Chọn volume xạ hình cần chỉnh sửa")

        formLayout.addRow("Volume đầu vào:", self.inputVolumeSelector)
        return groupBox

    def _createWindowLevelSection(self):
        groupBox = ctk.ctkCollapsibleButton()
        groupBox.text = "Window / Level"
        groupBox.collapsed = True
        formLayout = qt.QFormLayout(groupBox)

        self.windowSlider = ctk.ctkSliderWidget()
        self.windowSlider.decimals = 2
        self.windowSlider.singleStep = 1.0
        self.windowSlider.minimum = 1.0
        self.windowSlider.maximum = 5000.0
        self.windowSlider.value = 400.0
        self.windowSlider.toolTip = "Điều chỉnh tương phản (Window)"

        self.levelSlider = ctk.ctkSliderWidget()
        self.levelSlider.decimals = 2
        self.levelSlider.singleStep = 1.0
        self.levelSlider.minimum = -1000.0
        self.levelSlider.maximum = 5000.0
        self.levelSlider.value = 40.0
        self.levelSlider.toolTip = "Điều chỉnh độ sáng (Level)"

        formLayout.addRow("Tương phản (Window):", self.windowSlider)
        formLayout.addRow("Độ sáng (Level):", self.levelSlider)
        return groupBox

    def _createColorSection(self):
        groupBox = ctk.ctkCollapsibleButton()
        groupBox.text = "Bản đồ màu"
        groupBox.collapsed = True
        formLayout = qt.QFormLayout(groupBox)

        self.colormapComboBox = qt.QComboBox()
        for presetName in self._colorPresets:
            self.colormapComboBox.addItem(presetName)
        self.colormapComboBox.toolTip = "Áp dụng nhanh LUT hiển thị cho PET/SPECT"

        self.invertLutCheckBox = qt.QCheckBox("Invert LUT")
        self.invertLutCheckBox.checked = True
        self.invertLutCheckBox.toolTip = "Đảo ngược màu LUT hiện tại"

        formLayout.addRow("Preset LUT:", self.colormapComboBox)
        formLayout.addRow(self.invertLutCheckBox)
        return groupBox



    def _createSmoothingSection(self):
        groupBox = ctk.ctkCollapsibleButton()
        groupBox.text = "Giảm nhiễu"
        groupBox.collapsed = True
        formLayout = qt.QFormLayout(groupBox)

        self.sigmaSlider = ctk.ctkSliderWidget()
        self.sigmaSlider.decimals = 2
        self.sigmaSlider.singleStep = 0.1
        self.sigmaSlider.minimum = 0.1
        self.sigmaSlider.maximum = 5.0
        self.sigmaSlider.value = 1.2
        self.sigmaSlider.toolTip = "Domain sigma cho Bilateral filter. Gợi ý PET: 0.8-1.5, SPECT: 1.2-2.0"

        self.applySmoothingButton = qt.QPushButton("Áp dụng làm mượt")
        self.applySmoothingButton.toolTip = "Áp dụng lọc Bilateral để giảm nhiễu và giữ biên tổn thương"

        formLayout.addRow("Mức lọc (Sigma):", self.sigmaSlider)
        formLayout.addRow(self.applySmoothingButton)
        return groupBox

    def _createAdvancedSection(self):
        groupBox = ctk.ctkCollapsibleButton()
        groupBox.text = "Nâng cao"
        groupBox.collapsed = True
        layout = qt.QVBoxLayout(groupBox)

        self.advancedAutoAdjustButton = qt.QPushButton("Tự chỉnh WL/Threshold (Otsu + Percentile)")
        self.advancedAutoAdjustButton.toolTip = "Tự động chỉnh window/level, threshold và mapping cường độ"
        layout.addWidget(self.advancedAutoAdjustButton)
        layout.addWidget(self._createWindowLevelSection())
        layout.addWidget(self._createColorSection())
        layout.addWidget(self._createSmoothingSection())
        return groupBox

    def _createActionSection(self, iconsPath):
        import os
        groupBox = ctk.ctkCollapsibleButton()
        groupBox.text = "Thao tác"
        groupBox.collapsed = False
        layout = qt.QVBoxLayout(groupBox)

        btnLayout = qt.QHBoxLayout()
        iconSize = qt.QSize(40, 40)

        self.autoAdjustButton = qt.QPushButton()
        petIconPath = os.path.join(iconsPath, "PetDicom.png")
        if os.path.exists(petIconPath):
            self.autoAdjustButton.setIcon(qt.QIcon(petIconPath))
            self.autoAdjustButton.setIconSize(iconSize)
        else:
            self.autoAdjustButton.text = "PET"
        self.autoAdjustButton.toolTip = "Thiết lập PET-DICOM nhanh (LUT + Invert)"
        self.autoAdjustButton.setStyleSheet("font-weight: 600; padding: 6px;")
        self.autoAdjustButton.setFixedSize(60, 60)

        self.normalizeToggleButton = qt.QPushButton()
        normalizeIconPath = os.path.join(iconsPath, "Normalize.png")
        if os.path.exists(normalizeIconPath):
            self.normalizeToggleButton.setIcon(qt.QIcon(normalizeIconPath))
            self.normalizeToggleButton.setIconSize(iconSize)
        else:
            self.normalizeToggleButton.text = "⊕"
        self.normalizeToggleButton.checkable = True
        self.normalizeToggleButton.checked = False
        self.normalizeToggleButton.toolTip = "Bật/tắt chọn điểm tham chiếu (click trái trên ảnh)"
        self.normalizeToggleButton.setStyleSheet(
            "QPushButton { padding: 6px; }"
            "QPushButton:checked { background-color: #2196F3; }"
        )
        self.normalizeToggleButton.setFixedSize(60, 60)

        self.resetButton = qt.QPushButton()
        resetIconPath = os.path.join(iconsPath, "Reset.png")
        if os.path.exists(resetIconPath):
            self.resetButton.setIcon(qt.QIcon(resetIconPath))
            self.resetButton.setIconSize(iconSize)
        else:
            self.resetButton.text = "↺"
        self.resetButton.toolTip = "Khôi phục trạng thái ban đầu"
        self.resetButton.setStyleSheet("padding: 6px;")
        self.resetButton.setFixedSize(60, 60)

        btnLayout.addWidget(self.autoAdjustButton)
        btnLayout.addWidget(self.normalizeToggleButton)
        btnLayout.addWidget(self.resetButton)
        
        layout.addLayout(btnLayout)

        self.normalizeInfoLabel = qt.QLabel("Ref: --")
        self.normalizeInfoLabel.setStyleSheet("color: #666; font-size: 11px;")
        self.normalizeInfoLabel.setAlignment(qt.Qt.AlignCenter)
        layout.addWidget(self.normalizeInfoLabel)

        return groupBox

    def _connectSignals(self):
        self.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onInputVolumeChanged)
        self.windowSlider.connect("valueChanged(double)", self.onWindowLevelChanged)
        self.levelSlider.connect("valueChanged(double)", self.onWindowLevelChanged)
        self.thresholdRangeSlider.connect("minimumValueChanged(double)", self.onThresholdChanged)
        self.thresholdRangeSlider.connect("maximumValueChanged(double)", self.onThresholdChanged)
        self.colormapComboBox.connect("currentTextChanged(QString)", self.onColormapChanged)
        self.invertLutCheckBox.connect("toggled(bool)", self.onColormapChanged)
        self.applySmoothingButton.connect("clicked()", self.onApplySmoothing)
        self.autoAdjustButton.connect("clicked()", self.onAutoAdjust)
        self.advancedAutoAdjustButton.connect("clicked()", self.onAutoAdjustAdvanced)
        self.resetButton.connect("clicked()", self.onReset)
        self.normalizeToggleButton.connect("toggled(bool)", self.onNormalizeToggled)

    def _onUpperSpinBoxChanged(self, value):
        self.thresholdRangeSlider.maximumValue = value

    def _onLowerSpinBoxChanged(self, value):
        self.thresholdRangeSlider.minimumValue = value

    def _setControlsEnabled(self, enabled):
        self.windowSlider.enabled = enabled
        self.levelSlider.enabled = enabled
        self.thresholdRangeSlider.enabled = enabled
        self.upperThresholdSpinBox.enabled = enabled
        self.lowerThresholdSpinBox.enabled = enabled
        self.colormapComboBox.enabled = enabled
        self.invertLutCheckBox.enabled = enabled
        self.sigmaSlider.enabled = enabled
        self.applySmoothingButton.enabled = enabled
        self.autoAdjustButton.enabled = enabled
        self.advancedAutoAdjustButton.enabled = enabled
        self.resetButton.enabled = enabled
        self.normalizeToggleButton.enabled = enabled
        if not enabled:
            self.normalizeToggleButton.checked = False

    def onInputVolumeChanged(self, node):
        self._selectedVolumeNode = node
        self._setControlsEnabled(node is not None)
        if not node:
            return

        self._ensureInitialStateCaptured(node)
        self._syncSlidersFromDisplayNode(node)

    def onWindowLevelChanged(self, _value):
        if self._updatingWindowLevelSliders:
            return

        volumeNode = self._selectedVolumeNode
        if not volumeNode:
            return

        displayNode = volumeNode.GetDisplayNode()
        if not displayNode:
            return

        ww = self.windowSlider.value
        wl = self.levelSlider.value

        displayNode.SetAutoWindowLevel(False)
        displayNode.SetWindow(ww)
        displayNode.SetLevel(wl)

        # Đồng bộ threshold từ W/L: lower = WL - WW/2, upper = WL + WW/2
        self._updatingThresholdRange = True
        newLower = wl - ww / 2.0
        newUpper = wl + ww / 2.0
        
        safeLower = max(self.thresholdRangeSlider.minimum, min(newLower, self.thresholdRangeSlider.maximum))
        safeUpper = min(self.thresholdRangeSlider.maximum, max(newUpper, self.thresholdRangeSlider.minimum))
        safeUpper = max(safeLower, safeUpper)
        
        self.thresholdRangeSlider.minimumValue = safeLower
        self.thresholdRangeSlider.maximumValue = safeUpper
        self.lowerThresholdSpinBox.value = safeLower
        self.upperThresholdSpinBox.value = safeUpper
        
        displayNode.ApplyThresholdOn()
        displayNode.SetLowerThreshold(safeLower)
        displayNode.SetUpperThreshold(safeUpper)
        
        self._updatingThresholdRange = False

    def onThresholdChanged(self, *args):
        del args
        if self._updatingThresholdRange:
            return

        volumeNode = self._selectedVolumeNode
        if not volumeNode:
            return

        displayNode = volumeNode.GetDisplayNode()
        if not displayNode:
            return

        lower = self.thresholdRangeSlider.minimumValue
        upper = self.thresholdRangeSlider.maximumValue

        displayNode.ApplyThresholdOn()
        displayNode.SetLowerThreshold(lower)
        displayNode.SetUpperThreshold(upper)

        # Đồng bộ W/L từ threshold: WW = upper - lower, WL = (upper + lower) / 2
        self._updatingWindowLevelSliders = True
        newWW = max(1.0, upper - lower)
        newWL = (upper + lower) / 2.0
        self.windowSlider.value = newWW
        self.levelSlider.value = newWL
        self._updatingWindowLevelSliders = False

        displayNode.SetAutoWindowLevel(False)
        displayNode.SetWindow(newWW)
        displayNode.SetLevel(newWL)

    def onColormapChanged(self, *args):
        del args
        if self._updatingColormap:
            return

        presetName = self.colormapComboBox.currentText
        volumeNode = self._selectedVolumeNode
        if not volumeNode:
            return

        displayNode = volumeNode.GetDisplayNode()
        if not displayNode:
            return

        colorNode = self._findColorNodeForPreset(presetName)
        if not colorNode:
            slicer.util.warningDisplay(
                "Không tìm thấy LUT '%s' trong scene." % presetName,
                windowTitle="ScintigraphyEnhancer",
            )
            return

        if self.invertLutCheckBox.checked:
            colorNode = self._getOrCreateInvertedColorNode(colorNode)

        displayNode.SetAndObserveColorNodeID(colorNode.GetID())

    def onApplySmoothing(self):
        volumeNode = self._selectedVolumeNode
        if not volumeNode:
            slicer.util.warningDisplay("Vui lòng chọn volume đầu vào.", windowTitle="ScintigraphyEnhancer")
            return

        self._ensureInitialStateCaptured(volumeNode)

        try:
            self.logic.applyBilateralSmoothingInPlace(volumeNode, self.sigmaSlider.value)
            slicer.util.showStatusMessage("Đã áp dụng Bilateral filter", 3000)
        except Exception as exc:
            logging.exception("Apply smoothing failed")
            slicer.util.errorDisplay("Lỗi khi smoothing: %s" % exc, windowTitle="ScintigraphyEnhancer")

    def onAutoAdjust(self):
        volumeNode = self._selectedVolumeNode
        if not volumeNode:
            slicer.util.warningDisplay("Vui lòng chọn volume đầu vào.", windowTitle="ScintigraphyEnhancer")
            return

        # Áp dụng PET-DICOM LUT
        self._updatingColormap = True
        self.colormapComboBox.setCurrentText("PET-DICOM")
        self.invertLutCheckBox.checked = True
        self._updatingColormap = False
        self.onColormapChanged()

        # Đăng ký custom layout 2 view coronal dọc (đứng cạnh nhau)
        customLayoutId = 501
        customLayout = """
        <layout type="horizontal" split="true">
          <item splitSize="500">
            <view class="vtkMRMLSliceNode" singletontag="Cor1">
              <property name="orientation" action="default">Coronal</property>
              <property name="viewlabel" action="default">C1</property>
              <property name="viewcolor" action="default">#E68A00</property>
            </view>
          </item>
          <item splitSize="500">
            <view class="vtkMRMLSliceNode" singletontag="Cor2">
              <property name="orientation" action="default">Coronal</property>
              <property name="viewlabel" action="default">C2</property>
              <property name="viewcolor" action="default">#D35400</property>
            </view>
          </item>
        </layout>
        """
        layoutManager = slicer.app.layoutManager()
        layoutNode = layoutManager.layoutLogic().GetLayoutNode()
        
        # Cập nhật hoặc thêm mới layout (ID 502 để tránh cache cũ nếu không khởi động lại)
        customLayoutId = 502
        if layoutNode.IsLayoutDescription(customLayoutId):
            layoutNode.SetLayoutDescription(customLayoutId, customLayout)
        else:
            layoutNode.AddLayoutDescription(customLayoutId, customLayout)
        
        layoutNode.SetViewArrangement(customLayoutId)

        # Gán volume vào từng view
        slicer.app.processEvents()
        for viewTag in ["Cor1", "Cor2"]:
            sliceWidget = layoutManager.sliceWidget(viewTag)
            if sliceWidget is None:
                continue
            sliceLogic = sliceWidget.sliceLogic()
            compositeNode = sliceLogic.GetSliceCompositeNode()
            compositeNode.SetBackgroundVolumeID(volumeNode.GetID())
            sliceNode = sliceLogic.GetSliceNode()
            sliceNode.SetOrientation("Coronal")
            sliceNode.SetBackgroundColor(1.0, 1.0, 1.0)
            sliceNode.SetBackgroundColor2(1.0, 1.0, 1.0)
            sliceLogic.FitSliceToAll()

        slicer.util.showStatusMessage("Layout 2 view coronal + PET-DICOM", 3000)

    def onAutoAdjustAdvanced(self):
        volumeNode = self._selectedVolumeNode
        if not volumeNode:
            slicer.util.warningDisplay("Vui lòng chọn volume đầu vào.", windowTitle="ScintigraphyEnhancer")
            return

        displayNode = volumeNode.GetDisplayNode()
        if not displayNode:
            slicer.util.warningDisplay("Volume chưa có display node.", windowTitle="ScintigraphyEnhancer")
            return

        self._ensureInitialStateCaptured(volumeNode)

        try:
            params = self.logic.applyOtsuPercentilePipelineInPlace(volumeNode)
        except Exception as exc:
            logging.exception("Auto adjust failed")
            slicer.util.errorDisplay("Lỗi auto adjust: %s" % exc, windowTitle="ScintigraphyEnhancer")
            return

        displayNode.SetAutoWindowLevel(False)
        displayNode.SetWindow(params["windowWidth"])
        displayNode.SetLevel(params["windowLevel"])
        displayNode.ApplyThresholdOn()
        displayNode.SetLowerThreshold(0.0)
        displayNode.SetUpperThreshold(255.0)

        self._updatingWindowLevelSliders = True
        self.windowSlider.value = params["windowWidth"]
        self.levelSlider.value = params["windowLevel"]
        self._updatingWindowLevelSliders = False

        self._updatingThresholdRange = True
        self.thresholdRangeSlider.minimumValue = 0.0
        self.thresholdRangeSlider.maximumValue = 255.0
        self._updatingThresholdRange = False

        self._updatingColormap = True
        if params["recommendedPreset"] in self._colorPresets:
            self.colormapComboBox.setCurrentText(params["recommendedPreset"])
        self.invertLutCheckBox.checked = bool(params["invertLut"])
        self._updatingColormap = False
        self.onColormapChanged()

        slicer.util.showStatusMessage(
            "Đã áp dụng Otsu + Percentile (P2=%.2f, P99.5=%.2f)" % (params["p2"], params["p995"]),
            4000,
        )

    def onReset(self):
        volumeNode = self._selectedVolumeNode
        if not volumeNode:
            return

        volumeID = volumeNode.GetID()
        if volumeID not in self._initialStateByVolumeID:
            slicer.util.infoDisplay(
                "Chưa có trạng thái ban đầu để reset cho volume này.",
                windowTitle="ScintigraphyEnhancer",
            )
            return

        state = self._initialStateByVolumeID[volumeID]
        originalImageData = state.get("imageData")
        if originalImageData is not None:
            restoredImageData = vtk.vtkImageData()
            restoredImageData.DeepCopy(originalImageData)
            volumeNode.SetAndObserveImageData(restoredImageData)
            volumeNode.Modified()

        displayNode = volumeNode.GetDisplayNode()
        if displayNode:
            if state.get("autoWindowLevel") is not None:
                displayNode.SetAutoWindowLevel(bool(state["autoWindowLevel"]))

            if state.get("colorNodeID"):
                displayNode.SetAndObserveColorNodeID(state["colorNodeID"])

            if state.get("window") is not None and state.get("level") is not None:
                displayNode.SetWindow(state["window"])
                displayNode.SetLevel(state["level"])

            displayNode.ApplyThresholdOn()

            if state.get("lowerThreshold") is not None:
                displayNode.SetLowerThreshold(state["lowerThreshold"])
            if state.get("upperThreshold") is not None:
                displayNode.SetUpperThreshold(state["upperThreshold"])

            self._updatingColormap = True
            self.colormapComboBox.setCurrentText(state.get("presetLut", "Grey"))
            self.invertLutCheckBox.checked = bool(state.get("invertLut", False))
            self._updatingColormap = False
            self.onColormapChanged()

        self._syncSlidersFromDisplayNode(volumeNode)

        # Tắt chế độ Normalize khi reset
        self.normalizeToggleButton.checked = False
        self.normalizeInfoLabel.text = "Ref: --"

        slicer.util.showStatusMessage("Đã khôi phục volume về trạng thái ban đầu", 3000)

    def _ensureInitialStateCaptured(self, volumeNode):
        volumeID = volumeNode.GetID()
        if volumeID in self._initialStateByVolumeID:
            return

        initialState = {
            "window": None,
            "level": None,
            "autoWindowLevel": None,
            "colorNodeID": None,
            "applyThreshold": None,
            "lowerThreshold": None,
            "upperThreshold": None,
            "invertLut": True,
            "presetLut": "Grey",
            "imageData": None,
        }

        displayNode = volumeNode.GetDisplayNode()
        if displayNode:
            initialState["window"] = displayNode.GetWindow()
            initialState["level"] = displayNode.GetLevel()
            initialState["autoWindowLevel"] = displayNode.GetAutoWindowLevel()
            initialState["colorNodeID"] = displayNode.GetColorNodeID()
            initialState["applyThreshold"] = bool(displayNode.GetApplyThreshold())
            initialState["lowerThreshold"] = displayNode.GetLowerThreshold()
            initialState["upperThreshold"] = displayNode.GetUpperThreshold()

            colorNode = displayNode.GetColorNode()
            if colorNode:
                colorName = colorNode.GetName()
                if colorName.endswith(" [Inverted]"):
                    initialState["invertLut"] = True
                    colorName = colorName[: -len(" [Inverted]")]

                loweredColorName = colorName.lower()
                for presetName, candidateNames in self._colorPresets.items():
                    loweredCandidates = [name.lower() for name in candidateNames]
                    if loweredColorName in loweredCandidates or any(candidate in loweredColorName for candidate in loweredCandidates):
                        initialState["presetLut"] = presetName
                        break

        imageData = volumeNode.GetImageData()
        if imageData:
            imageCopy = vtk.vtkImageData()
            imageCopy.DeepCopy(imageData)
            initialState["imageData"] = imageCopy

        self._initialStateByVolumeID[volumeID] = initialState

    def _syncSlidersFromDisplayNode(self, volumeNode):
        displayNode = volumeNode.GetDisplayNode()
        imageData = volumeNode.GetImageData()
        if not displayNode or not imageData:
            return

        scalarRange = imageData.GetScalarRange()
        minValue = float(scalarRange[0])
        maxValue = float(scalarRange[1])
        dataSpan = max(1.0, maxValue - minValue)

        self._updatingWindowLevelSliders = True
        self.windowSlider.minimum = 1.0
        self.windowSlider.maximum = max(2.0, dataSpan * 1.5)
        self.levelSlider.minimum = minValue - 0.5 * dataSpan
        self.levelSlider.maximum = maxValue + 0.5 * dataSpan
        self.windowSlider.value = displayNode.GetWindow()
        self.levelSlider.value = displayNode.GetLevel()
        self._updatingWindowLevelSliders = False

        self._updatingThresholdRange = True
        self.thresholdRangeSlider.minimum = minValue
        self.thresholdRangeSlider.maximum = maxValue
        self.upperThresholdSpinBox.minimum = minValue
        self.upperThresholdSpinBox.maximum = maxValue
        self.lowerThresholdSpinBox.minimum = minValue
        self.lowerThresholdSpinBox.maximum = maxValue
        upperThreshold = min(max(displayNode.GetUpperThreshold(), minValue), maxValue)
        lowerThreshold = min(max(displayNode.GetLowerThreshold(), minValue), maxValue)
        self.thresholdRangeSlider.minimumValue = lowerThreshold
        self.thresholdRangeSlider.maximumValue = upperThreshold
        self.lowerThresholdSpinBox.value = lowerThreshold
        self.upperThresholdSpinBox.value = upperThreshold
        self._updatingThresholdRange = False

        colorNode = displayNode.GetColorNode()
        if colorNode:
            colorName = colorNode.GetName()
            invertLut = False
            if colorName.endswith(" [Inverted]"):
                invertLut = True
                colorName = colorName[: -len(" [Inverted]")]

            matchedPreset = None
            loweredColorName = colorName.lower()
            for presetName, candidateNames in self._colorPresets.items():
                loweredCandidates = [name.lower() for name in candidateNames]
                if loweredColorName in loweredCandidates or any(candidate in loweredColorName for candidate in loweredCandidates):
                    matchedPreset = presetName
                    break

            if matchedPreset:
                self._updatingColormap = True
                self.colormapComboBox.setCurrentText(matchedPreset)
                self.invertLutCheckBox.checked = invertLut
                self._updatingColormap = False

    def _getOrCreateInvertedColorNode(self, baseColorNode):
        invertedNodeName = "%s [Inverted]" % baseColorNode.GetName()
        existingNode = slicer.util.getFirstNodeByName(invertedNodeName)
        if existingNode and existingNode.IsA("vtkMRMLProceduralColorNode"):
            return existingNode

        colorTransferFunction = vtk.vtkColorTransferFunction()

        if baseColorNode.IsA("vtkMRMLColorTableNode") and baseColorNode.GetLookupTable():
            lookupTable = baseColorNode.GetLookupTable()
            numberOfColors = lookupTable.GetNumberOfTableValues()
            if numberOfColors <= 0:
                return baseColorNode
            for index in range(numberOfColors):
                rgba = lookupTable.GetTableValue(numberOfColors - 1 - index)
                colorTransferFunction.AddRGBPoint(float(index), float(rgba[0]), float(rgba[1]), float(rgba[2]))
        elif hasattr(baseColorNode, "GetColorTransferFunction") and baseColorNode.GetColorTransferFunction():
            baseFunction = baseColorNode.GetColorTransferFunction()
            rangeMin, rangeMax = baseFunction.GetRange()
            samples = 256
            for index in range(samples):
                t = float(index) / float(samples - 1)
                x = rangeMin + t * (rangeMax - rangeMin)
                xInverted = rangeMax - t * (rangeMax - rangeMin)
                rgb = baseFunction.GetColor(xInverted)
                colorTransferFunction.AddRGBPoint(x, float(rgb[0]), float(rgb[1]), float(rgb[2]))
        else:
            return baseColorNode

        invertedNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLProceduralColorNode", invertedNodeName)
        invertedNode.SetHideFromEditors(True)
        invertedNode.SetAndObserveColorTransferFunction(colorTransferFunction)
        return invertedNode

    def _findColorNodeForPreset(self, presetName):
        candidateNames = self._colorPresets.get(presetName, [presetName])
        colorNodes = slicer.util.getNodesByClass("vtkMRMLColorNode")

        for candidate in candidateNames:
            for colorNode in colorNodes:
                if colorNode.GetName() == candidate:
                    return colorNode

        loweredCandidates = [name.lower() for name in candidateNames]
        for colorNode in colorNodes:
            nodeNameLower = colorNode.GetName().lower()
            if any(candidate in nodeNameLower for candidate in loweredCandidates):
                return colorNode

        return None

    # ------------------------------------------------------------------ #
    #  Normalize Click handlers                                          #
    # ------------------------------------------------------------------ #

    def onNormalizeToggled(self, checked):
        if checked:
            self._installNormalizeObservers()
            slicer.util.showStatusMessage(
                "Chế độ Normalize: BẬT — Click chuột trái vào điểm tham chiếu", 4000
            )
        else:
            self._removeNormalizeObservers()
            slicer.util.showStatusMessage("Chế độ Normalize: TẮT", 2000)

    def _installNormalizeObservers(self):
        self._removeNormalizeObservers()
        layoutManager = slicer.app.layoutManager()
        for viewName in ["Red", "Green", "Yellow"]:
            sliceWidget = layoutManager.sliceWidget(viewName)
            if sliceWidget is None:
                continue
            interactor = sliceWidget.sliceView().interactor()
            tag = interactor.AddObserver(
                vtk.vtkCommand.LeftButtonPressEvent, self._onNormalizeClick
            )
            self._normalizeObserverTags.append((interactor, tag))

    def _removeNormalizeObservers(self):
        for interactor, tag in self._normalizeObserverTags:
            try:
                interactor.RemoveObserver(tag)
            except Exception:
                pass
        self._normalizeObserverTags.clear()
        self._normalizeActive = False

    def _onNormalizeClick(self, caller, event):
        import numpy as np

        volumeNode = self._selectedVolumeNode
        if not volumeNode:
            return

        # Lấy tọa độ RAS từ Crosshair
        crosshairNode = slicer.util.getNode("Crosshair")
        ras = [0.0, 0.0, 0.0]
        crosshairNode.GetCursorPositionRAS(ras)

        # Chuyển RAS → IJK
        rasToIjk = vtk.vtkMatrix4x4()
        volumeNode.GetRASToIJKMatrix(rasToIjk)
        rasPoint = [ras[0], ras[1], ras[2], 1.0]
        ijkPoint = [0, 0, 0, 1]
        rasToIjk.MultiplyPoint(rasPoint, ijkPoint)
        ijk = [int(round(ijkPoint[i])) for i in range(3)]

        # Lấy giá trị voxel
        volumeArray = slicer.util.arrayFromVolume(volumeNode)
        shape = volumeArray.shape
        if not (0 <= ijk[2] < shape[0] and 0 <= ijk[1] < shape[1] and 0 <= ijk[0] < shape[2]):
            slicer.util.showStatusMessage("Điểm click nằm ngoài volume", 2000)
            return

        refValue = float(volumeArray[ijk[2], ijk[1], ijk[0]])

        if refValue <= 0:
            self.normalizeInfoLabel.text = "Ref: %.4f (không hợp lệ)" % refValue
            slicer.util.showStatusMessage("Giá trị tham chiếu phải > 0", 2000)
            return

        self._ensureInitialStateCaptured(volumeNode)

        try:
            self.logic.normalizeByReferencePoint(volumeNode, refValue)
            self.normalizeInfoLabel.text = "Ref: %.4f @ (%.0f,%.0f,%.0f)" % (
                refValue, ras[0], ras[1], ras[2]
            )
            slicer.util.showStatusMessage(
                "Đã normalize (Ref=%.4f)" % refValue, 3000
            )
            self._syncSlidersFromDisplayNode(volumeNode)
        except Exception as exc:
            logging.exception("Normalize failed")
            self.normalizeInfoLabel.text = "Lỗi normalize"
            slicer.util.showStatusMessage("Lỗi: %s" % exc, 3000)


#
# ScintigraphyEnhancerLogic
#


class ScintigraphyEnhancerLogic(ScriptedLoadableModuleLogic):
    def normalizeByReferencePoint(self, volumeNode, refValue):
        """Chuẩn hóa volume: mọi voxel / refValue * 100."""
        if volumeNode is None:
            raise ValueError("Input volume node không hợp lệ")

        refValue = float(refValue)
        if refValue <= 0:
            raise ValueError("Giá trị tham chiếu phải > 0")

        try:
            import numpy as np
        except Exception as importError:
            raise RuntimeError("Cần numpy trong Slicer để normalize") from importError

        arrayData = slicer.util.arrayFromVolume(volumeNode).astype(float)
        normalized = arrayData / refValue * 100.0
        slicer.util.updateVolumeFromArray(volumeNode, normalized.astype(np.float32))
        volumeNode.Modified()

    def applyBilateralSmoothingInPlace(self, volumeNode, sigma):
        if volumeNode is None:
            raise ValueError("Input volume node không hợp lệ")

        sigma = float(sigma)
        if sigma <= 0:
            raise ValueError("Sigma phải lớn hơn 0")

        try:
            import SimpleITK as sitk
            import sitkUtils
        except Exception as importError:
            raise RuntimeError("Không import được SimpleITK/sitkUtils trong Slicer") from importError

        image = sitkUtils.PullVolumeFromSlicer(volumeNode)
        imageArray = slicer.util.arrayFromVolume(volumeNode).astype(float)

        try:
            import numpy as np
        except Exception as importError:
            raise RuntimeError("Cần numpy trong Slicer để chạy Bilateral") from importError

        finiteValues = imageArray[np.isfinite(imageArray)]
        if finiteValues.size == 0:
            raise RuntimeError("Không có dữ liệu hợp lệ để lọc Bilateral")

        p10, p90 = np.percentile(finiteValues, [10, 90])
        dynamicRange = max(float(p90 - p10), 1.0)
        rangeSigma = max(0.01, dynamicRange * 0.1)

        bilateralFilter = sitk.BilateralImageFilter()
        bilateralFilter.SetDomainSigma(float(sigma))
        bilateralFilter.SetRangeSigma(float(rangeSigma))
        bilateralFilter.SetNumberOfRangeGaussianSamples(100)
        smoothed = bilateralFilter.Execute(image)

        sitkUtils.PushVolumeToSlicer(smoothed, targetNode=volumeNode)

    def _computeOtsuThreshold(self, values, bins=1024):
        import numpy as np

        if values.size == 0:
            raise RuntimeError("Không có dữ liệu để tính Otsu")

        vMin = float(np.min(values))
        vMax = float(np.max(values))
        if vMax <= vMin:
            return vMin

        hist, binEdges = np.histogram(values, bins=bins, range=(vMin, vMax))
        if hist.sum() <= 0:
            return float(np.median(values))

        binCenters = (binEdges[:-1] + binEdges[1:]) / 2.0
        prob = hist.astype(float) / float(hist.sum())
        omega = np.cumsum(prob)
        mu = np.cumsum(prob * binCenters)
        muTotal = mu[-1]
        eps = 1e-12
        sigmaBetween = ((muTotal * omega - mu) ** 2) / (omega * (1.0 - omega) + eps)
        return float(binCenters[int(np.argmax(sigmaBetween))])

    def applyOtsuPercentilePipelineInPlace(self, volumeNode):
        if volumeNode is None:
            raise ValueError("Input volume node không hợp lệ")

        try:
            import numpy as np
        except Exception as importError:
            raise RuntimeError("Cần numpy trong Slicer để auto adjust") from importError

        arrayData = slicer.util.arrayFromVolume(volumeNode)
        flat = arrayData.ravel().astype(float)
        valid = flat[np.isfinite(flat)]
        if valid.size == 0:
            raise RuntimeError("Không có dữ liệu hợp lệ để tính auto adjust")

        otsuThreshold = self._computeOtsuThreshold(valid, bins=1024)

        finiteMask = np.isfinite(arrayData)
        foregroundMask = finiteMask & (arrayData > otsuThreshold)
        foregroundValues = arrayData[foregroundMask].astype(float)

        if foregroundValues.size < 64:
            fallbackThreshold = float(np.percentile(valid, 50))
            foregroundMask = finiteMask & (arrayData > fallbackThreshold)
            foregroundValues = arrayData[foregroundMask].astype(float)

        if foregroundValues.size < 64:
            foregroundValues = valid

        p2, p995 = np.percentile(foregroundValues, [2.0, 99.5])
        p2 = float(p2)
        p995 = float(p995)
        if p995 <= p2:
            p2 = float(np.min(foregroundValues))
            p995 = float(np.max(foregroundValues))
            if p995 <= p2:
                p995 = p2 + 1.0

        windowLevel = float((p995 + p2) / 2.0)
        windowWidth = float(p995 - p2)

        mapped = (arrayData.astype(float) - p2) * (255.0 / (p995 - p2))
        mapped = np.clip(mapped, 0.0, 255.0)
        mapped[~finiteMask] = 0.0

        slicer.util.updateVolumeFromArray(volumeNode, mapped.astype(np.float32))
        volumeNode.Modified()

        return {
            "windowLevel": windowLevel,
            "windowWidth": windowWidth,
            "p2": p2,
            "p995": p995,
            "otsuThreshold": float(otsuThreshold),
            "recommendedPreset": "PET-DICOM",
            "invertLut": True,
        }


#
# ScintigraphyEnhancerTest
#


class ScintigraphyEnhancerTest(ScriptedLoadableModuleTest):
    def setUp(self):
        slicer.mrmlScene.Clear()

    def runTest(self):
        self.setUp()
        self.delayDisplay("ScintigraphyEnhancer smoke test passed")
