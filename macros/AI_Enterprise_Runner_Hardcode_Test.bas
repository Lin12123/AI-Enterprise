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

    If Not IsSafeOutputPath(ReadIniValue(JOB_FILE, "output_dir", "")) Then
        Err.Raise vbObjectError + 102, "AI_Enterprise_Runner", "output_dir is outside workspace outputs"
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
    Dim lengthMm As Double
    Dim widthMm As Double
    Dim thicknessMm As Double

    lengthMm = CDbl(ReadIniValue(JOB_FILE, "base_length", "120"))
    widthMm = CDbl(ReadIniValue(JOB_FILE, "base_width", "80"))
    thicknessMm = CDbl(ReadIniValue(JOB_FILE, "base_thickness", "12"))

    swModel.ClearSelection2 True
    If Not swModel.Extension.SelectByID2("Top Plane", "PLANE", 0, 0, 0, False, 0, Nothing, 0) Then
        If Not swModel.Extension.SelectByID2(TopPlaneNameZh(), "PLANE", 0, 0, 0, False, 0, Nothing, 0) Then
            Err.Raise vbObjectError + 300, "AI_Enterprise_Runner", "cannot select top plane"
        End If
    End If

    swModel.SketchManager.InsertSketch True
    swModel.SketchManager.CreateCenterRectangle 0, 0, 0, MM(lengthMm) / 2, MM(widthMm) / 2, 0
    swModel.SketchManager.InsertSketch True

    swModel.FeatureManager.FeatureExtrusion2 True, False, False, 0, 0, MM(thicknessMm), 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False
    LogLine "Base plate created: " & CStr(lengthMm) & " x " & CStr(widthMm) & " x " & CStr(thicknessMm) & " mm"
End Sub

Public Sub CreateCornerHoles(ByVal swModel As Object)
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
    radiusMm = CDbl(ReadIniValue(JOB_FILE, "fillet_radius", "3"))

    ' TODO: Add recorded edge selection for the intended outside edges, then call the fillet feature.
    ' The runner intentionally does not guess edge names because feature history varies by SOLIDWORKS version.
    LogLine "Fillet requested, radius mm=" & CStr(radiusMm) & ". Recorded edge selection still needed."
End Sub

Private Sub AddCircle(ByVal swModel As Object, ByVal xMm As Double, ByVal yMm As Double, ByVal diameterMm As Double)
    swModel.SketchManager.CreateCircleByRadius MM(xMm), MM(yMm), 0, MM(diameterMm) / 2
End Sub

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
