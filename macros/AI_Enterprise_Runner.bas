Option Explicit

Private Const PROJECT_ROOT As String = "C:\Users\LVBO_ZY\Desktop\AI-SW-Enterprise"
Private Const JOB_FILE As String = PROJECT_ROOT & "\workspace\jobs\current_job.ini"
Private Const OUTPUT_ROOT As String = PROJECT_ROOT & "\workspace\outputs"
Private Const PARTS_DIR As String = OUTPUT_ROOT & "\parts"
Private Const EXPORTS_DIR As String = OUTPUT_ROOT & "\exports"
Private Const PREVIEWS_DIR As String = OUTPUT_ROOT & "\previews"
Private Const LOG_FILE As String = PROJECT_ROOT & "\workspace\logs\run_log.txt"

Private swApp As Object

Public Sub main()
    On Error GoTo Fail

    Set swApp = Application.SldWorks
    LogLine "=== AI_Enterprise_Runner started ==="

    If ReadIniValue(JOB_FILE, "template", "") <> "mounting_plate" Then
        Err.Raise vbObjectError + 100, "AI_Enterprise_Runner", "template must be mounting_plate"
    End If

    If ReadIniValue(JOB_FILE, "unit", "") <> "mm" Then
        Err.Raise vbObjectError + 101, "AI_Enterprise_Runner", "unit must be mm"
    End If

    If Not IsSafeOutputPath(OUTPUT_ROOT) Then
        Err.Raise vbObjectError + 102, "AI_Enterprise_Runner", "configured output root is outside workspace outputs"
    End If

    Dim swModel As Object
    Set swModel = swApp.NewPart
    If swModel Is Nothing Then
        Err.Raise vbObjectError + 103, "AI_Enterprise_Runner", "cannot create new part"
    End If

    CreateBasePlate swModel

    If ToBool(ReadIniValue(JOB_FILE, "corner_holes_enabled", "false")) Then
        CreateCornerHoles swModel
    End If

    If ToBool(ReadIniValue(JOB_FILE, "center_boss_enabled", "false")) Then
        CreateCenterBoss swModel
    End If

    If ToBool(ReadIniValue(JOB_FILE, "center_hole_enabled", "false")) Then
        CreateCenterHole swModel
    End If

    If ToBool(ReadIniValue(JOB_FILE, "fillet_enabled", "false")) Then
        ApplyFillet swModel
    End If

    swModel.ForceRebuild3 False
    SaveOutputs swModel

    LogLine "=== AI_Enterprise_Runner completed ==="
    MsgBox "AI Enterprise mounting plate completed. Check workspace outputs and logs.", vbInformation
    Exit Sub

Fail:
    LogLine "ERROR: " & Err.Description
    MsgBox "AI Enterprise Runner failed: " & Err.Description, vbCritical
End Sub

Public Function ReadIniValue(ByVal filePath As String, ByVal key As String, ByVal defaultValue As String) As String
    On Error GoTo UseDefault

    If filePath <> JOB_FILE Then
        Err.Raise vbObjectError + 200, "AI_Enterprise_Runner", "only current_job.ini may be read"
    End If

    Dim f As Integer
    f = FreeFile

    Dim lineText As String
    Dim pos As Long
    Open filePath For Input As #f
    Do While Not EOF(f)
        Line Input #f, lineText
        lineText = Trim(lineText)
        pos = InStr(1, lineText, "=", vbTextCompare)
        If pos > 0 Then
            If LCase(Trim(Left(lineText, pos - 1))) = LCase(key) Then
                ReadIniValue = Trim(Mid(lineText, pos + 1))
                Close #f
                Exit Function
            End If
        End If
    Loop
    Close #f

UseDefault:
    ReadIniValue = defaultValue
End Function

Public Function ToBool(ByVal value As String) As Boolean
    value = LCase(Trim(value))
    ToBool = (value = "true" Or value = "1" Or value = "yes")
End Function

Public Function MM(ByVal value As Double) As Double
    MM = value / 1000#
End Function

Private Function TopPlaneNameZh() As String
    TopPlaneNameZh = ChrW(&H4E0A) & ChrW(&H89C6) & ChrW(&H57FA) & ChrW(&H51C6) & ChrW(&H9762)
End Function

Private Function SelectTopPlane(ByVal swModel As Object) As Boolean
    swModel.ClearSelection2 True

    If TrySelectPlaneByID(swModel, "Top") Then
        SelectTopPlane = True
        Exit Function
    End If

    If TrySelectPlaneByID(swModel, "Top Plane") Then
        SelectTopPlane = True
        Exit Function
    End If

    If TrySelectPlaneByID(swModel, TopPlaneNameZh()) Then
        SelectTopPlane = True
        Exit Function
    End If

    If SelectFeatureByName(swModel, "Top") Then
        SelectTopPlane = True
        Exit Function
    End If

    If SelectFeatureByName(swModel, "Top Plane") Then
        SelectTopPlane = True
        Exit Function
    End If

    If SelectFeatureByName(swModel, TopPlaneNameZh()) Then
        SelectTopPlane = True
        Exit Function
    End If
End Function

Private Function TrySelectPlaneByID(ByVal swModel As Object, ByVal planeName As String) As Boolean
    On Error GoTo Failed

    TrySelectPlaneByID = swModel.Extension.SelectByID2(planeName, "PLANE", 0, 0, 0, False, 0, Nothing, 0)
    Exit Function

Failed:
    TrySelectPlaneByID = False
End Function

Private Function SelectFeatureByName(ByVal swModel As Object, ByVal featureName As String) As Boolean
    On Error GoTo Failed

    Dim swFeature As Object
    Set swFeature = swModel.FeatureByName(featureName)
    If Not swFeature Is Nothing Then
        SelectFeatureByName = swFeature.Select2(False, 0)
    End If
    Exit Function

Failed:
    SelectFeatureByName = False
End Function

Public Sub LogLine(ByVal message As String)
    On Error Resume Next

    Dim f As Integer
    f = FreeFile
    Open LOG_FILE For Append As #f
    Print #f, Format(Now, "yyyy-mm-dd hh:nn:ss") & " " & message
    Close #f
End Sub

Public Function IsSafeOutputPath(ByVal outputPath As String) As Boolean
    Dim expected As String
    expected = LCase(OUTPUT_ROOT)

    outputPath = LCase(Trim(outputPath))
    IsSafeOutputPath = (outputPath = expected Or Left(outputPath, Len(expected) + 1) = expected & "\")
End Function

Private Function IsSafeWritePath(ByVal filePath As String) As Boolean
    Dim lowerPath As String
    lowerPath = LCase(Trim(filePath))
    IsSafeWritePath = _
        Left(lowerPath, Len(LCase(PARTS_DIR)) + 1) = LCase(PARTS_DIR) & "\" Or _
        Left(lowerPath, Len(LCase(EXPORTS_DIR)) + 1) = LCase(EXPORTS_DIR) & "\" Or _
        Left(lowerPath, Len(LCase(PREVIEWS_DIR)) + 1) = LCase(PREVIEWS_DIR) & "\"
End Function

Public Function NextVersionedFilePath(ByVal folderPath As String, ByVal baseName As String, ByVal extensionName As String) As String
    Dim i As Integer
    Dim candidate As String

    For i = 1 To 999
        candidate = folderPath & "\" & baseName & "_v" & Format(i, "000") & extensionName
        If Not IsSafeWritePath(candidate) Then
            Err.Raise vbObjectError + 210, "AI_Enterprise_Runner", "output path is not safe"
        End If
        If Dir(candidate) = "" Then
            NextVersionedFilePath = candidate
            Exit Function
        End If
    Next i

    Err.Raise vbObjectError + 211, "AI_Enterprise_Runner", "no available versioned output file name"
End Function

Public Sub CreateBasePlate(ByVal swModel As Object)
    Dim shape As String
    Dim lengthMm As Double
    Dim widthMm As Double
    Dim diameterMm As Double
    Dim thicknessMm As Double

    shape = LCase(ReadIniValue(JOB_FILE, "base_shape", "rectangle"))
    lengthMm = CDbl(ReadIniValue(JOB_FILE, "base_length", "120"))
    widthMm = CDbl(ReadIniValue(JOB_FILE, "base_width", "80"))
    diameterMm = CDbl(ReadIniValue(JOB_FILE, "base_diameter", "0"))
    thicknessMm = CDbl(ReadIniValue(JOB_FILE, "base_thickness", "12"))

    If Not SelectTopPlane(swModel) Then
        Err.Raise vbObjectError + 300, "AI_Enterprise_Runner", "cannot select top plane"
    End If

    swModel.SketchManager.InsertSketch True
    If shape = "circle" Then
        swModel.SketchManager.CreateCircleByRadius 0, 0, 0, MM(diameterMm) / 2
    Else
        swModel.SketchManager.CreateCenterRectangle 0, 0, 0, MM(lengthMm) / 2, MM(widthMm) / 2, 0
    End If
    swModel.SketchManager.InsertSketch True

    swModel.FeatureManager.FeatureExtrusion2 True, False, False, 0, 0, MM(thicknessMm), 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False
    LogLine "Base plate created: shape=" & shape & ", length=" & CStr(lengthMm) & ", width=" & CStr(widthMm) & ", diameter=" & CStr(diameterMm) & ", thickness=" & CStr(thicknessMm) & " mm"
End Sub

Public Sub CreateCornerHoles(ByVal swModel As Object)
    If LCase(ReadIniValue(JOB_FILE, "base_shape", "rectangle")) <> "rectangle" Then
        Err.Raise vbObjectError + 320, "AI_Enterprise_Runner", "corner holes require rectangle base"
    End If

    Dim diameterMm As Double
    Dim offsetXmm As Double
    Dim offsetYmm As Double
    Dim topZ As Double

    diameterMm = CDbl(ReadIniValue(JOB_FILE, "corner_hole_diameter", "6.6"))
    offsetXmm = CDbl(ReadIniValue(JOB_FILE, "corner_hole_offset_x", "50"))
    offsetYmm = CDbl(ReadIniValue(JOB_FILE, "corner_hole_offset_y", "30"))
    topZ = CDbl(ReadIniValue(JOB_FILE, "base_thickness", "12"))

    SelectTopFace swModel, topZ
    swModel.SketchManager.InsertSketch True
    AddCircle swModel, -offsetXmm, -offsetYmm, diameterMm
    AddCircle swModel, offsetXmm, -offsetYmm, diameterMm
    AddCircle swModel, -offsetXmm, offsetYmm, diameterMm
    AddCircle swModel, offsetXmm, offsetYmm, diameterMm
    swModel.SketchManager.InsertSketch True

    ' TODO: Replace this cut call with a recorded through-all cut if your SOLIDWORKS version reverses direction.
    swModel.FeatureManager.FeatureCut3 True, False, False, 1, 0, 0, 0, False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, 0, 0, False
    LogLine "Corner holes created"
End Sub

Public Sub CreateCenterBoss(ByVal swModel As Object)
    Dim diameterMm As Double
    Dim heightMm As Double
    Dim topZ As Double

    diameterMm = CDbl(ReadIniValue(JOB_FILE, "center_boss_diameter", "30"))
    heightMm = CDbl(ReadIniValue(JOB_FILE, "center_boss_height", "25"))
    topZ = CDbl(ReadIniValue(JOB_FILE, "base_thickness", "12"))

    SelectTopFace swModel, topZ
    swModel.SketchManager.InsertSketch True
    AddCircle swModel, 0, 0, diameterMm
    swModel.SketchManager.InsertSketch True

    swModel.FeatureManager.FeatureExtrusion2 True, False, False, 0, 0, MM(heightMm), 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False
    LogLine "Center boss created"
End Sub

Public Sub CreateCenterHole(ByVal swModel As Object)
    Dim diameterMm As Double
    Dim topZ As Double

    diameterMm = CDbl(ReadIniValue(JOB_FILE, "center_hole_diameter", "10"))
    topZ = CDbl(ReadIniValue(JOB_FILE, "base_thickness", "12")) + CDbl(ReadIniValue(JOB_FILE, "center_boss_height", "0"))

    SelectTopFace swModel, topZ
    swModel.SketchManager.InsertSketch True
    AddCircle swModel, 0, 0, diameterMm
    swModel.SketchManager.InsertSketch True

    ' TODO: Replace this cut call with a recorded through-all cut if your SOLIDWORKS version reverses direction.
    swModel.FeatureManager.FeatureCut3 True, False, False, 1, 0, 0, 0, False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, 0, 0, False
    LogLine "Center hole created"
End Sub

Public Sub ApplyFillet(ByVal swModel As Object)
    Dim radiusMm As Double
    Dim lengthMm As Double
    Dim widthMm As Double
    Dim thicknessMm As Double
    Dim selectedCount As Integer
    Dim radiiArray As Variant
    Dim radiis As Double
    Dim dist2Array As Variant
    Dim dists2 As Double
    Dim conicRhosArray As Variant
    Dim conicRhos As Double
    Dim setBackArray As Variant
    Dim setBacks As Double
    Dim pointArray As Variant
    Dim points As Double
    Dim pointDist2Array As Variant
    Dim pointDists2 As Double
    Dim pointRhoArray As Variant
    Dim pointRhos As Double
    Dim myFeature As Object

    If LCase(ReadIniValue(JOB_FILE, "base_shape", "rectangle")) <> "rectangle" Then
        Err.Raise vbObjectError + 340, "AI_Enterprise_Runner", "fillet currently requires rectangle base"
    End If

    radiusMm = CDbl(ReadIniValue(JOB_FILE, "fillet_radius", "3"))
    lengthMm = CDbl(ReadIniValue(JOB_FILE, "base_length", "120"))
    widthMm = CDbl(ReadIniValue(JOB_FILE, "base_width", "80"))
    thicknessMm = CDbl(ReadIniValue(JOB_FILE, "base_thickness", "12"))

    If radiusMm <= 0 Then
        Err.Raise vbObjectError + 341, "AI_Enterprise_Runner", "fillet radius must be greater than zero"
    End If

    swModel.ClearSelection2 True
    selectedCount = SelectBaseCornerEdgesByTopology(swModel, lengthMm, widthMm, thicknessMm)

    If selectedCount < 4 Then
        Err.Raise vbObjectError + 342, "AI_Enterprise_Runner", "could not select all four base corner edges for fillet"
    End If

    radiiArray = radiis
    dist2Array = dists2
    conicRhosArray = conicRhos
    setBackArray = setBacks
    pointArray = points
    pointDist2Array = pointDists2
    pointRhoArray = pointRhos

    Set myFeature = swModel.FeatureManager.FeatureFillet3(195, MM(radiusMm), MM(radiusMm * 2), 0, 0, 0, 0, (radiiArray), (dist2Array), (conicRhosArray), (setBackArray), (pointArray), (pointDist2Array), (pointRhoArray))
    If myFeature Is Nothing Then
        Err.Raise vbObjectError + 343, "AI_Enterprise_Runner", "fillet feature creation failed"
    End If

    LogLine "Base vertical corner fillet created, radius mm=" & CStr(radiusMm) & ", selected edges=" & CStr(selectedCount)
End Sub

Private Sub AddCircle(ByVal swModel As Object, ByVal xMm As Double, ByVal yMm As Double, ByVal diameterMm As Double)
    swModel.SketchManager.CreateCircleByRadius MM(xMm), MM(yMm), 0, MM(diameterMm) / 2
End Sub

Private Function SelectBaseCornerEdgesByTopology(ByVal swModel As Object, ByVal lengthMm As Double, ByVal widthMm As Double, ByVal thicknessMm As Double) As Integer
    Dim bodies As Variant
    Dim edges As Variant
    Dim body As Variant
    Dim edge As Variant
    Dim selectData As Object

    bodies = swModel.GetBodies2(0, True)
    If IsEmpty(bodies) Then
        LogLine "Fillet topology select failed: no solid bodies"
        Exit Function
    End If

    Set selectData = swModel.SelectionManager.CreateSelectData

    For Each body In bodies
        edges = body.GetEdges
        If Not IsEmpty(edges) Then
            For Each edge In edges
                If IsBaseCornerVerticalEdge(edge, lengthMm, widthMm, thicknessMm) Then
                    If edge.Select4(SelectBaseCornerEdgesByTopology > 0, selectData) Then
                        SelectBaseCornerEdgesByTopology = SelectBaseCornerEdgesByTopology + 1
                    End If
                End If
            Next edge
        End If
    Next body

    LogLine "Fillet topology selected base corner edges=" & CStr(SelectBaseCornerEdgesByTopology)
End Function

Private Function IsBaseCornerVerticalEdge(ByVal edge As Object, ByVal lengthMm As Double, ByVal widthMm As Double, ByVal thicknessMm As Double) As Boolean
    Dim startVertex As Object
    Dim endVertex As Object
    Dim p1 As Variant
    Dim p2 As Variant
    Dim tol As Double
    Dim halfLength As Double
    Dim halfWidth As Double
    Dim thickness As Double
    Dim midX As Double
    Dim midZ As Double
    Dim minY As Double
    Dim maxY As Double

    Set startVertex = edge.GetStartVertex
    Set endVertex = edge.GetEndVertex
    If startVertex Is Nothing Or endVertex Is Nothing Then
        Exit Function
    End If

    p1 = startVertex.GetPoint
    p2 = endVertex.GetPoint
    tol = MM(0.35)
    halfLength = MM(lengthMm) / 2
    halfWidth = MM(widthMm) / 2
    thickness = MM(thicknessMm)

    If Abs(p1(0) - p2(0)) > tol Then Exit Function
    If Abs(p1(2) - p2(2)) > tol Then Exit Function
    If Abs(Abs(p1(1) - p2(1)) - thickness) > tol Then Exit Function

    midX = (p1(0) + p2(0)) / 2
    midZ = (p1(2) + p2(2)) / 2
    minY = p1(1)
    maxY = p2(1)
    If minY > maxY Then
        minY = p2(1)
        maxY = p1(1)
    End If

    If Abs(Abs(midX) - halfLength) > tol Then Exit Function
    If Abs(Abs(midZ) - halfWidth) > tol Then Exit Function
    If Abs(minY) > tol Then Exit Function
    If Abs(maxY - thickness) > tol Then Exit Function

    IsBaseCornerVerticalEdge = True
End Function

Private Sub SelectTopFace(ByVal swModel As Object, ByVal zMm As Double)
    swModel.ClearSelection2 True

    ' TODO: Face selection by coordinates is intentionally simple for the Enterprise.
    ' If selection is unreliable, replace this helper with a recorded top-face selection snippet.
    If Not swModel.Extension.SelectByID2("", "FACE", 0, 0, MM(zMm), False, 0, Nothing, 0) Then
        LogLine "Top face selection by coordinate returned false at z mm=" & CStr(zMm)
    End If
End Sub

Public Sub SaveOutputs(ByVal swModel As Object)
    Dim partName As String
    Dim errors As Long
    Dim warnings As Long

    partName = ReadIniValue(JOB_FILE, "part_name", "ai_mounting_plate")

    If ToBool(ReadIniValue(JOB_FILE, "save_sldprt", "true")) Then
        Dim partPath As String
        partPath = NextVersionedFilePath(PARTS_DIR, partName, ".SLDPRT")
        swModel.Extension.SaveAs partPath, 0, 1, Nothing, errors, warnings
        LogLine "Saved SLDPRT: " & partPath
    End If

    If ToBool(ReadIniValue(JOB_FILE, "export_step", "true")) Then
        Dim stepPath As String
        stepPath = NextVersionedFilePath(EXPORTS_DIR, partName, ".STEP")
        swModel.Extension.SaveAs stepPath, 0, 1, Nothing, errors, warnings
        LogLine "Exported STEP: " & stepPath
    End If

    If ToBool(ReadIniValue(JOB_FILE, "capture_png", "true")) Then
        Dim pngPath As String
        pngPath = NextVersionedFilePath(PREVIEWS_DIR, partName, ".PNG")
        swModel.ViewZoomtofit2
        swModel.SaveAs3 pngPath, 0, 0
        LogLine "Saved PNG preview attempt: " & pngPath
    End If
End Sub
