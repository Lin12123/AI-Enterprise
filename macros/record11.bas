Attribute VB_Name = "record11"
' ******************************************************************************
' C:\Users\LVBO_ZY\AppData\Local\Temp\swx27264\Macro1.swb - macro recorded on 06/15/26 by Felix
' ******************************************************************************
Dim swApp As Object

Dim Part As Object
Dim boolstatus As Boolean
Dim longstatus As Long, longwarnings As Long

Sub main()

Set swApp = Application.SldWorks

Set Part = swApp.ActiveDoc
boolstatus = Part.Extension.SelectByID2("Top", "PLANE", -5.78648748539642E-02, 1.87660800536715E-03, 2.92595660280035E-02, False, 0, Nothing, 0)
Part.SketchManager.InsertSketch True
Part.ClearSelection2 True
boolstatus = Part.Extension.SetUserPreferenceToggle(swUserPreferenceToggle_e.swSketchAddConstToRectEntity, swUserPreferenceOption_e.swDetailingNoOptionSpecified, True)
boolstatus = Part.Extension.SetUserPreferenceToggle(swUserPreferenceToggle_e.swSketchAddConstLineDiagonalType, swUserPreferenceOption_e.swDetailingNoOptionSpecified, True)
Dim vSkLines As Variant
vSkLines = Part.SketchManager.CreateCenterRectangle(-4.81399172020301E-02, 2.43634946815152E-02, 0, 3.22889688550202E-02, -1.36494277432586E-02, 0)

' Named View
Part.ShowNamedView2 "*上下二等角轴测", 8
Part.ViewZoomtofit2
Dim myFeature As Object
Set myFeature = Part.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, 0.01, 0.01, False, False, False, False, 1.74532925199433E-02, 1.74532925199433E-02, False, False, False, False, True, True, True, 0, 0, False)
Part.SelectionManager.EnableContourSelection = False
Part.ClearSelection2 True
boolstatus = Part.Extension.SelectByRay(-0.122975134918136, 6.03541995616297E-03, -8.14062548795391E-03, -0.400036026779312, -0.515038074910024, -0.758094294050284, 4.23603019039116E-04, 2, False, 0, 0)
boolstatus = Part.Extension.SelectByRay(-0.117388840909314, 9.99999999999091E-03, -5.09462873152984E-02, -0.400036026779312, -0.515038074910024, -0.758094294050284, 4.23603019039116E-04, 2, False, 0, 0)
boolstatus = Part.Extension.SelectByRay(2.24811102760327E-02, 3.44155684109637E-03, -0.041364601561952, -0.400036026779312, -0.515038074910024, -0.758094294050284, 4.23603019039116E-04, 2, False, 0, 0)
boolstatus = Part.Extension.SelectByRay(-0.138545860107683, 1.01314182515466E-02, -4.99283346817379E-02, -0.400036026779312, -0.515038074910024, -0.758094294050284, 4.23603019039116E-04, 1, False, 0, 0)
boolstatus = Part.Extension.SelectByRay(-0.10300691767344, 9.7060964501452E-03, -7.94095175382381E-03, -0.400036026779312, -0.515038074910024, -0.758094294050284, 4.23603019039116E-04, 1, False, 0, 0)
boolstatus = Part.Extension.SelectByRay(-1.13173197699439E-02, 0.010233290528447, -8.43249644795492E-02, -0.400036026779312, -0.515038074910024, -0.758094294050284, 4.23603019039116E-04, 1, False, 0, 0)
boolstatus = Part.Extension.SelectByRay(2.22683138495654E-02, 1.01652814438467E-02, -4.33696262043668E-02, -0.400036026779312, -0.515038074910024, -0.758094294050284, 4.23603019039116E-04, 1, False, 0, 0)

' Named View
Part.ShowNamedView2 "*后视", 2
Part.ViewZoomtofit2
boolstatus = Part.Extension.SelectByRay(-0.025614088306456, 3.7794566262115E-03, -0.08416647033755, 0, 0, 1, 4.05994252257781E-04, 2, False, 0, 0)
boolstatus = Part.Extension.SelectByRay(-2.85993401612926E-02, 9.86937041007823E-03, -0.08416647033755, 0, 0, 1, 4.05994252257781E-04, 1, False, 0, 0)
boolstatus = Part.Extension.SelectByRay(-2.72858293451645E-02, 1.97154400407547E-04, -0.08416647033755, 0, 0, 1, 4.05994252257781E-04, 1, False, 0, 0)
boolstatus = Part.Extension.SelectByRay(2.27703070807479E-02, 6.07738998462537E-03, -8.38772735326643E-02, -0.577452781453547, -0.577145190037241, 0.577452781453549, 4.1193598954331E-04, 1, False, 0, 0)
boolstatus = Part.Extension.SelectByRay(-0.138361029913654, 5.36112811283829E-03, -8.41508384128247E-02, -0.577452781453547, -0.577145190037241, 0.577452781453549, 4.1193598954331E-04, 1, True, 1, 0)
boolstatus = Part.Extension.SelectByRay(-0.138421525836122, 8.31605155298121E-03, -8.18548948558373E-03, -0.577452781453547, -0.577145190037241, 0.577452781453549, 4.1193598954331E-04, 1, True, 1, 0)
boolstatus = Part.Extension.SelectByRay(0.022624139766549, 5.62001362936826E-03, -7.99759599698291E-03, -0.577452781453547, -0.577145190037241, 0.577452781453549, 4.1193598954331E-04, 1, True, 1, 0)
Part.ClearSelection2 True
boolstatus = Part.Extension.SelectByRay(2.27703070807479E-02, 6.07738998462537E-03, -8.38772735326643E-02, -0.577452781453547, -0.577145190037241, 0.577452781453549, 4.1193598954331E-04, 1, False, 1, 0)
boolstatus = Part.Extension.SelectByRay(-0.138361029913654, 5.36112811283829E-03, -8.41508384128247E-02, -0.577452781453547, -0.577145190037241, 0.577452781453549, 4.1193598954331E-04, 1, True, 1, 0)
boolstatus = Part.Extension.SelectByRay(-0.138421525836122, 8.31605155298121E-03, -8.18548948558373E-03, -0.577452781453547, -0.577145190037241, 0.577452781453549, 4.1193598954331E-04, 1, True, 1, 0)
boolstatus = Part.Extension.SelectByRay(0.022624139766549, 5.62001362936826E-03, -7.99759599698291E-03, -0.577452781453547, -0.577145190037241, 0.577452781453549, 4.1193598954331E-04, 1, True, 1, 0)
Dim radiiArray2 As Variant
Dim radiis2 As Double
Dim dist2Array2 As Variant
Dim dists22 As Double
Dim conicRhosArray2 As Variant
Dim coniRhos2 As Double
Dim setBackArray2 As Variant
Dim setBacks2 As Double
Dim pointArray2 As Variant
Dim points2 As Double
Dim pointDist2Array2 As Variant
Dim pointsDist22 As Double
Dim pointRhoArray2 As Variant
Dim pointsRhos2 As Double
radiiArray2 = radiis2
dist2Array2 = dists22
conicRhosArray2 = coniRhos2
setBackArray2 = setBacks2
pointArray2 = points2
pointDist2Array2 = pointsDist22
pointRhoArray2 = pointsRhos2
Set myFeature = Part.FeatureManager.FeatureFillet3(195, 0.005, 0.01, 0, 0, 0, 0, (radiiArray2), (dist2Array2), (conicRhosArray2), (setBackArray2), (pointArray2), (pointDist2Array2), (pointRhoArray2))
Part.ClearSelection2 True
Part.EditUndo2 1
boolstatus = Part.Extension.SelectByRay(-3.61675591279891E-02, 9.99280709635286E-03, -8.14781455989078E-03, -0.577452781453547, -0.577145190037241, 0.577452781453549, 4.1193598954331E-04, 1, False, 0, 0)
boolstatus = Part.Extension.SelectByRay(-3.13644789220575E-02, 9.99999999987722E-03, -1.22655236324931E-02, -0.577452781453547, -0.577145190037241, 0.577452781453549, 4.1193598954331E-04, 2, False, 0, 0)
Part.EditDelete
boolstatus = Part.Extension.SketchBoxSelect("0.000000", "0.000000", "0.000000", "0.000000", "0.000000", "0.000000")
boolstatus = Part.Extension.SketchBoxSelect("0.000000", "0.000000", "0.000000", "0.000000", "0.000000", "0.000000")
Part.EditUndo2 1

' New Document
Dim swSheetWidth As Double
swSheetWidth = 0
Dim swSheetHeight As Double
swSheetHeight = 0
Set Part = swApp.NewDocument("C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\chinese-simplified\Tutorial\part.prtdot", 0, swSheetWidth, swSheetHeight)
Dim swPart As PartDoc
Set swPart = Part
swApp.ActivateDoc2 "零件3", False, longstatus
Set Part = swApp.ActiveDoc
End Sub
