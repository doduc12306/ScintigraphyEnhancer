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

    def setup(self):
        super().setup()

        self.layout.addWidget(self._createInputSection())
        self.layout.addWidget(self._createActionSection())
        self.layout.addWidget(self._createAdvancedSection())
        self.layout.addWidget(self._createGuidanceSection())

        self.layout.addStretch(1)

        self._connectSignals()
        self._setControlsEnabled(False)

    def cleanup(self):
        pass

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

    def _createThresholdSection(self):
        groupBox = ctk.ctkCollapsibleButton()
        groupBox.text = "Ngưỡng hiển thị (Threshold)"
        groupBox.collapsed = True
        formLayout = qt.QFormLayout(groupBox)

        self.thresholdEnableCheckBox = qt.QCheckBox("Bật threshold")
        self.thresholdEnableCheckBox.checked = False

        self.thresholdRangeWidget = ctk.ctkRangeWidget()
        self.thresholdRangeWidget.decimals = 2
        self.thresholdRangeWidget.singleStep = 1.0
        self.thresholdRangeWidget.minimum = 0.0
        self.thresholdRangeWidget.maximum = 1000.0
        self.thresholdRangeWidget.minimumValue = 0.0
        self.thresholdRangeWidget.maximumValue = 1000.0
        self.thresholdRangeWidget.toolTip = "Điều chỉnh cận dưới/cận trên để lọc hiển thị"

        formLayout.addRow(self.thresholdEnableCheckBox)
        formLayout.addRow("Khoảng threshold:", self.thresholdRangeWidget)
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
        layout.addWidget(self._createThresholdSection())
        layout.addWidget(self._createColorSection())
        layout.addWidget(self._createSmoothingSection())
        return groupBox

    def _createGuidanceSection(self):
        groupBox = ctk.ctkCollapsibleButton()
        groupBox.text = "Hướng dẫn nhanh cho bác sĩ"
        groupBox.collapsed = False
        formLayout = qt.QFormLayout(groupBox)

        guidanceLabel = qt.QLabel(
            "1) Dùng 'Thiết lập PET-DICOM nhanh' cho thao tác thường quy (chỉ đổi LUT + invert).\n"
            "2) Nếu cần tự chỉnh Window/Level/Threshold theo thuật toán: mở mục Nâng cao và bấm 'Tự chỉnh WL/Threshold'.\n"
            "3) Giảm nhiễu Bilateral: PET thường Sigma 1.0-1.2; SPECT 1.2-2.0.\n"
            "4) Khi cần quay về trạng thái ban đầu, bấm 'Khôi phục'."
        )
        guidanceLabel.wordWrap = True
        formLayout.addRow(guidanceLabel)
        return groupBox

    def _createActionSection(self):
        groupBox = ctk.ctkCollapsibleButton()
        groupBox.text = "Thao tác"
        groupBox.collapsed = False
        layout = qt.QHBoxLayout(groupBox)

        self.autoAdjustButton = qt.QPushButton("Thiết lập PET-DICOM nhanh")
        self.autoAdjustButton.toolTip = "Đặt LUT PET-DICOM và bật Invert LUT"
        self.autoAdjustButton.setStyleSheet("font-weight: 600;")

        self.resetButton = qt.QPushButton("Khôi phục")
        self.resetButton.toolTip = "Khôi phục trạng thái ban đầu của volume đang chọn"

        layout.addWidget(self.autoAdjustButton)
        layout.addWidget(self.resetButton)
        return groupBox

    def _connectSignals(self):
        self.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onInputVolumeChanged)
        self.windowSlider.connect("valueChanged(double)", self.onWindowLevelChanged)
        self.levelSlider.connect("valueChanged(double)", self.onWindowLevelChanged)
        self.thresholdEnableCheckBox.connect("toggled(bool)", self.onThresholdChanged)
        self.thresholdRangeWidget.connect("valuesChanged(double,double)", self.onThresholdChanged)
        self.colormapComboBox.connect("currentTextChanged(QString)", self.onColormapChanged)
        self.invertLutCheckBox.connect("toggled(bool)", self.onColormapChanged)
        self.applySmoothingButton.connect("clicked()", self.onApplySmoothing)
        self.autoAdjustButton.connect("clicked()", self.onAutoAdjust)
        self.advancedAutoAdjustButton.connect("clicked()", self.onAutoAdjustAdvanced)
        self.resetButton.connect("clicked()", self.onReset)

    def _setControlsEnabled(self, enabled):
        self.windowSlider.enabled = enabled
        self.levelSlider.enabled = enabled
        self.thresholdEnableCheckBox.enabled = enabled
        self.thresholdRangeWidget.enabled = enabled
        self.colormapComboBox.enabled = enabled
        self.invertLutCheckBox.enabled = enabled
        self.sigmaSlider.enabled = enabled
        self.applySmoothingButton.enabled = enabled
        self.autoAdjustButton.enabled = enabled
        self.advancedAutoAdjustButton.enabled = enabled
        self.resetButton.enabled = enabled

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

        displayNode.SetAutoWindowLevel(False)
        displayNode.SetWindow(self.windowSlider.value)
        displayNode.SetLevel(self.levelSlider.value)

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

        if self.thresholdEnableCheckBox.checked:
            displayNode.ApplyThresholdOn()
            displayNode.SetLowerThreshold(self.thresholdRangeWidget.minimumValue)
            displayNode.SetUpperThreshold(self.thresholdRangeWidget.maximumValue)
        else:
            displayNode.ApplyThresholdOff()

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

        self._updatingColormap = True
        self.colormapComboBox.setCurrentText("PET-DICOM")
        self.invertLutCheckBox.checked = True
        self._updatingColormap = False
        self.onColormapChanged()

        slicer.util.showStatusMessage("Đã đặt LUT PET-DICOM và Invert LUT", 3000)

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
        self.thresholdEnableCheckBox.checked = True
        self.thresholdRangeWidget.minimumValue = 0.0
        self.thresholdRangeWidget.maximumValue = 255.0
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

            if state.get("applyThreshold") is not None:
                if state["applyThreshold"]:
                    displayNode.ApplyThresholdOn()
                else:
                    displayNode.ApplyThresholdOff()

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
        self.thresholdRangeWidget.minimum = minValue
        self.thresholdRangeWidget.maximum = maxValue
        lowerThreshold = min(max(displayNode.GetLowerThreshold(), minValue), maxValue)
        upperThreshold = min(max(displayNode.GetUpperThreshold(), minValue), maxValue)
        if lowerThreshold > upperThreshold:
            lowerThreshold = minValue
            upperThreshold = maxValue
        self.thresholdRangeWidget.minimumValue = lowerThreshold
        self.thresholdRangeWidget.maximumValue = upperThreshold
        self.thresholdEnableCheckBox.checked = bool(displayNode.GetApplyThreshold())
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


#
# ScintigraphyEnhancerLogic
#


class ScintigraphyEnhancerLogic(ScriptedLoadableModuleLogic):
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
