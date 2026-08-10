' ******************************************************************************
' C:\Users\LVBO_ZY\AppData\Local\Temp\swx20076\Macro1.swb - macro recorded on 05/20/26 by Felix
' ******************************************************************************
Dim swApp As Object

Dim Part As Object
Dim boolstatus As Boolean
Dim longstatus As Long, longwarnings As Long

Sub main()

Set swApp = Application.SldWorks

Set Part = swApp.ActiveDoc
boolstatus = Part.Extension.SelectByID2("上视基准面", "PLANE", 0, 0, 0, False, 0, Nothing, 0)
Part.ClearSelection2 True
boolstatus = Part.Extension.SetUserPreferenceToggle(swUserPreferenceToggle_e.swSketchAddConstToRectEntity, swUserPreferenceOption_e.swDetailingNoOptionSpecified, True)
boolstatus = Part.Extension.SetUserPreferenceToggle(swUserPreferenceToggle_e.swSketchAddConstLineDiagonalType, swUserPreferenceOption_e.swDetailingNoOptionSpecified, True)
Dim vSkLines As Variant
vSkLines = Part.SketchManager.CreateCenterRectangle(-2.84454508902007E-03, 0, 0, 3.25344844556669E-02, -1.99118156231404E-02, 0)
boolstatus = Part.Extension.SelectByID2("上视基准面", "PLANE", 0, 0, 0, False, 0, Nothing, 0)

' Named View
Part.ShowNamedView2 "*上下二等角轴测", 8
Part.ViewZoomtofit2

' Zoom In/Out (MouseWheel)
Dim swModelView As Object
Set swModelView = Part.ActiveView
swModelView.Scale2 = 2.25868537673172
Dim swTranslation() As Double
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.84175072143349E-02
swTranslation(1) = -4.05177054425841E-05
swTranslation(2) = 3.47378950995134E-03
Dim swTranslationVar As Variant
swTranslationVar = swTranslation
Dim swMathUtils As Object
Set swMathUtils = swApp.GetMathUtility()
Dim swTranslationVector As MathVector
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.8822378139431
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.74704525798084E-02
swTranslation(1) = -3.37647545354931E-05
swTranslation(2) = 2.89482459162612E-03
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.56853151161925
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.66812403843697E-02
swTranslation(1) = -2.81372954462315E-05
swTranslation(2) = 2.4123538263551E-03
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.30710959301604
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.60235635548375E-02
swTranslation(1) = -2.34477462051897E-05
swTranslation(2) = 2.01029485529591E-03
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.08925799418004
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.54754995302273E-02
swTranslation(1) = -1.95397885043343E-05
swTranslation(2) = 1.67524571274659E-03
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.90771499515003
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.50187795097188E-02
swTranslation(1) = -1.62831570869485E-05
swTranslation(2) = 1.3960380939555E-03
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.756429162625025
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.46381794926284E-02
swTranslation(1) = -1.35692975724475E-05
swTranslation(2) = 1.16336507829625E-03
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.630357635520854
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.43210128117197E-02
swTranslation(1) = -1.13077479770396E-05
swTranslation(2) = 9.69470898580206E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.525298029600712
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.40567072442958E-02
swTranslation(1) = -9.42312331420602E-06
swTranslation(2) = 8.07892415483505E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.437748358000593
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.38364526047759E-02
swTranslation(1) = -7.85260276183835E-06
swTranslation(2) = 6.73243679569587E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.364790298333828
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.36529070718426E-02
swTranslation(1) = -6.5438356348621E-06
swTranslation(2) = 5.61036399641323E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.30399191527819
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.34999524610649E-02
swTranslation(1) = -5.4531963623787E-06
swTranslation(2) = 4.67530333034436E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.253326596065158
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.33724902854168E-02
swTranslation(1) = -4.54433030199183E-06
swTranslation(2) = 3.8960861086203E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.211105496720965
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.32662718057101E-02
swTranslation(1) = -3.78694191831695E-06
swTranslation(2) = 3.24673842385025E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.175921247267471
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.31777564059544E-02
swTranslation(1) = -3.15578493193717E-06
swTranslation(2) = 2.70561535320854E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.146601039389559
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.31039935728247E-02
swTranslation(1) = -2.6298207766175E-06
swTranslation(2) = 2.25467946100712E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.122167532824633
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.30425245452167E-02
swTranslation(1) = -2.19151731383835E-06
swTranslation(2) = 1.87889955083926E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.101806277353861
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.29913003555433E-02
swTranslation(1) = -1.82626442820819E-06
swTranslation(2) = 1.56574962569939E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 8.48385644615505E-02
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.29486135308154E-02
swTranslation(1) = -1.52188702349726E-06
swTranslation(2) = 1.30479135474949E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.102215137905482
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.00164018791562
swTranslation(1) = 6.34940768456277E-03
swTranslation(2) = 1.57203777680661E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.123150768560822
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -3.12652498992772E-02
swTranslation(1) = 1.40011300599679E-02
swTranslation(2) = 1.89402141783929E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.148374419952798
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -6.69580956627195E-02
swTranslation(1) = 0.023220072680938
swTranslation(2) = 2.28195351546903E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.178764361388913
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.109961524293373
swTranslation(1) = 3.43272324652393E-02
swTranslation(2) = 2.74934158490244E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.215378748661341
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.161772884089341
swTranslation(1) = 4.77093526872891E-02
swTranslation(2) = 3.31245974084632E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.259492468266676
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.224196209144724
swTranslation(1) = 6.38323890993972E-02
swTranslation(2) = 3.99091535041725E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.31264152803214
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.299405034512656
swTranslation(1) = 8.32577341742263E-02
swTranslation(2) = 4.80833174749067E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.376676539797759
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.390018077124621
swTranslation(1) = 0.106661764384864
swTranslation(2) = 5.79317078010924E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.453827156382842
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.499190417620966
swTranslation(1) = 0.134859391144668
swTranslation(2) = 6.97972383145691E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.546779706485352
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.630723357978007
swTranslation(1) = 0.168832435433589
swTranslation(2) = 8.40930582103242E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.658770730705244
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.789196780094924
swTranslation(1) = 0.209763814094939
swTranslation(2) = 0.001013169376028
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.548975608921036
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.653874786844574
swTranslation(1) = 0.174803178412449
swTranslation(2) = 8.44307813356669E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.457479674100864
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.541106459135949
swTranslation(1) = 0.145669315343708
swTranslation(2) = 7.03589844463891E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.38123306175072
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.447132852712095
swTranslation(1) = 0.121391096119756
swTranslation(2) = 5.86324870386576E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.3176942181256
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.36882151402555
swTranslation(1) = 0.101159246766464
swTranslation(2) = 4.8860405865548E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.264745181771333
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.303562065120095
swTranslation(1) = 8.42993723053863E-02
swTranslation(2) = 4.07170048879567E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.220620984809444
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.249179191032217
swTranslation(1) = 7.02494769211553E-02
swTranslation(2) = 3.39308374066305E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.183850820674537
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.203860129292318
swTranslation(1) = 5.85412307676294E-02
swTranslation(2) = 2.82756978388588E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.153209017228781
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.166094244509069
swTranslation(1) = 4.87843589730245E-02
swTranslation(2) = 2.35630815323823E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.127674181023984
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.134622673856361
swTranslation(1) = 4.06536324775204E-02
swTranslation(2) = 1.96359012769853E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.10639515085332
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -0.108396364979105
swTranslation(1) = 3.38780270646004E-02
swTranslation(2) = 1.63632510641544E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 0.0886626257111
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -8.65411075813916E-02
swTranslation(1) = 2.82316892205003E-02
swTranslation(2) = 1.3636042553462E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 7.38855214259167E-02
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -6.83283930832969E-02
swTranslation(1) = 2.35264076837503E-02
swTranslation(2) = 1.13633687945517E-04
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 6.15712678549306E-02
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -5.31511310015514E-02
swTranslation(1) = 1.96053397364585E-02
swTranslation(2) = 9.46947399545972E-05
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 5.13093898791088E-02
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -4.05034126000968E-02
swTranslation(1) = 1.63377831137154E-02
swTranslation(2) = 7.89122832954977E-05
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 4.27578248992574E-02
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -2.99636472655513E-02
swTranslation(1) = 1.36148192614295E-02
swTranslation(2) = 6.57602360795814E-05
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 3.56315207493811E-02
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -2.11805094867633E-02
swTranslation(1) = 0.011345682717858
swTranslation(2) = 5.48001967329845E-05
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 2.96929339578176E-02
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -1.38612280044401E-02
swTranslation(1) = 9.45473559821496E-03
swTranslation(2) = 4.56668306108204E-05
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 2.47441116315147E-02
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -7.7618267691707E-03
swTranslation(1) = 7.8789463318458E-03
swTranslation(2) = 3.80556921756837E-05
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 2.06200930262622E-02
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = -2.6789924064462E-03
swTranslation(1) = 6.56578860987149E-03
swTranslation(2) = 3.17130768130697E-05
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.71834108552185E-02
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 1.55670289582424E-03
swTranslation(1) = 5.47149050822625E-03
swTranslation(2) = 2.64275640108915E-05
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.43195090460154E-02
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 5.08644898104958E-03
swTranslation(1) = 4.55957542352187E-03
swTranslation(2) = 2.20229700090762E-05
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.19329242050129E-02
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 8.02790405207069E-03
swTranslation(1) = 3.79964618626823E-03
swTranslation(2) = 1.83524750075635E-05
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 9.94410350417739E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 0.010479116611255
swTranslation(1) = 3.1663718218902E-03
swTranslation(2) = 1.52937291729696E-05
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 8.28675292014783E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 1.25217937439085E-02
swTranslation(1) = 2.6386431849085E-03
swTranslation(2) = 1.2744774310808E-05
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 6.90562743345652E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 1.42240246877865E-02
swTranslation(1) = 2.19886932075708E-03
swTranslation(2) = 1.06206452590067E-05
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 5.75468952788044E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 1.56425504743514E-02
swTranslation(1) = 1.83239110063089E-03
swTranslation(2) = 8.85053771583889E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 4.79557460656703E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 1.68246552964889E-02
swTranslation(1) = 1.52699258385909E-03
swTranslation(2) = 7.37544809653241E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 3.99631217213919E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 1.78097426482701E-02
swTranslation(1) = 1.27249381988257E-03
swTranslation(2) = 6.14620674711034E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 3.33026014344933E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 1.86306487747545E-02
swTranslation(1) = 1.06041151656881E-03
swTranslation(2) = 5.12183895592528E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 2.77521678620777E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 1.93147372134915E-02
swTranslation(1) = 8.83676263807343E-04
swTranslation(2) = 4.26819912993774E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 2.31268065517314E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 1.98848109124389E-02
swTranslation(1) = 7.36396886506122E-04
swTranslation(2) = 3.55683260828145E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.92723387931095E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.03598723282285E-02
swTranslation(1) = 6.13664072088429E-04
swTranslation(2) = 2.96402717356787E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.60602823275913E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.07557568413865E-02
swTranslation(1) = 5.11386726740361E-04
swTranslation(2) = 2.47002264463989E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.33835686063261E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.10856606023514E-02
swTranslation(1) = 4.2615560561697E-04
swTranslation(2) = 2.05835220386658E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.61247814534049E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.12198590701789E-02
swTranslation(1) = 6.42181866061083E-04
swTranslation(2) = 2.47994241429708E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.94274475342228E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.13815439711758E-02
swTranslation(1) = 9.02454469005796E-04
swTranslation(2) = 2.98788242686396E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 2.34065632942443E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.15763450567143E-02
swTranslation(1) = 1.21603591833678E-03
swTranslation(2) = 3.59985834561922E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.95054694118703E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.17694841151246E-02
swTranslation(1) = 1.01336326528065E-03
swTranslation(2) = 2.99988195468269E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.62545578432252E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.19304333304665E-02
swTranslation(1) = 8.44469387733864E-04
swTranslation(2) = 2.49990162890224E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.35454648693543E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.20645576765848E-02
swTranslation(1) = 7.03724489778233E-04
swTranslation(2) = 2.08325135741853E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.12878873911286E-03
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.21763279650168E-02
swTranslation(1) = 5.86437074815194E-04
swTranslation(2) = 1.73604279784878E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 9.40657282594052E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.22694698720433E-02
swTranslation(1) = 4.88697562345979E-04
swTranslation(2) = 1.44670233154065E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 7.83881068828376E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.23470881278988E-02
swTranslation(1) = 4.07247968621665E-04
swTranslation(2) = 1.20558527628387E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 6.53234224023647E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.24117700077784E-02
swTranslation(1) = 3.39373307184705E-04
swTranslation(2) = 1.00465439690323E-06
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 5.44361853353039E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.24656715743447E-02
swTranslation(1) = 2.828110893206E-04
swTranslation(2) = 8.37211997419356E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 4.53634877794199E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.25105895464833E-02
swTranslation(1) = 2.35675907767161E-04
swTranslation(2) = 6.9767666451613E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 3.78029064828499E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.25480211899321E-02
swTranslation(1) = 1.96396589805973E-04
swTranslation(2) = 5.81397220430109E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 3.15024220690416E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.25792142261395E-02
swTranslation(1) = 1.63663824838302E-04
swTranslation(2) = 4.84497683691757E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 2.6252018390868E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 0.022605208422979
swTranslation(1) = 1.36386520698585E-04
swTranslation(2) = 4.03748069743131E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 2.187668199239E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.26268702536785E-02
swTranslation(1) = 1.13655433915497E-04
swTranslation(2) = 3.36456724785943E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.82305683269917E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.26449217792615E-02
swTranslation(1) = 9.4712861596241E-05
swTranslation(2) = 2.80380603988286E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.51921402724931E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.26599647172473E-02
swTranslation(1) = 7.8927384663531E-05
swTranslation(2) = 2.33650503323571E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.26601168937442E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.26725004989021E-02
swTranslation(1) = 6.57728205529489E-05
swTranslation(2) = 1.94708752769643E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.05500974114535E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.26829469836145E-02
swTranslation(1) = 5.48106837941177E-05
swTranslation(2) = 1.62257293974702E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 8.79174784287794E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.26916523875414E-02
swTranslation(1) = 4.56755698284282E-05
swTranslation(2) = 1.35214411645585E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 7.32645653573161E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.26989068908139E-02
swTranslation(1) = 3.80629748570203E-05
swTranslation(2) = 1.12678676371321E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 6.10538044644301E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.27049523102076E-02
swTranslation(1) = 3.17191457141836E-05
swTranslation(2) = 9.38988969761009E-08
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 7.35588005595544E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.25271060482362E-02
swTranslation(1) = -9.05887595807019E-04
swTranslation(2) = 1.13131201176025E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 8.86250609151257E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.23128334434513E-02
swTranslation(1) = -2.03553427233859E-03
swTranslation(2) = 1.36302652019307E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.06777181825453E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.20546736786502E-02
swTranslation(1) = -3.39655436454528E-03
swTranslation(2) = 1.64220062673864E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.28647207018618E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.17436378174442E-02
swTranslation(1) = -5.03633760816783E-03
swTranslation(2) = 1.97855497197427E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.5499663496219E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 0.021368895815991
swTranslation(1) = -7.01198007036367E-03
swTranslation(2) = 2.38380117105334E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.86742933689386E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.09173994286981E-02
swTranslation(1) = -9.39227219349117E-03
swTranslation(2) = 2.87204960367872E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector
boolstatus = Part.Extension.SketchBoxSelect("-171.723844", "97.011618", "0.000000", "254.783072", "-141.201990", "0.000000")

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.55619111407821E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.12203627584445E-02
swTranslation(1) = -7.82689349457597E-03
swTranslation(2) = 2.39337466973227E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.29682592839851E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.14728321998998E-02
swTranslation(1) = -6.52241124547998E-03
swTranslation(2) = 1.99447889144356E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.08068827366543E-04
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.16832234011125E-02
swTranslation(1) = -5.43534270456664E-03
swTranslation(2) = 1.66206574286963E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 9.00573561387855E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.18585494021231E-02
swTranslation(1) = -4.52945225380554E-03
swTranslation(2) = 1.38505478572469E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 7.50477967823213E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.20046544029653E-02
swTranslation(1) = -3.77454354483795E-03
swTranslation(2) = 1.15421232143724E-07
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 6.25398306519344E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.21264085703338E-02
swTranslation(1) = -3.14545295403162E-03
swTranslation(2) = 9.61843601197703E-08
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 5.21165255432787E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.22278703764742E-02
swTranslation(1) = -2.62121079502636E-03
swTranslation(2) = 8.01536334331419E-08
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 4.34304379527322E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.23124218815913E-02
swTranslation(1) = -2.18434232918864E-03
swTranslation(2) = 6.67946945276183E-08
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 3.61920316272769E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.23828814691888E-02
swTranslation(1) = -1.82028527432386E-03
swTranslation(2) = 5.56622454396819E-08
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 3.0160026356064E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.24415977921867E-02
swTranslation(1) = -1.51690439526988E-03
swTranslation(2) = 4.63852045330682E-08
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 2.513335529672E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.24905280613516E-02
swTranslation(1) = -1.26408699605823E-03
swTranslation(2) = 3.86543371108902E-08
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 2.09444627472667E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.25313032856557E-02
swTranslation(1) = -1.05340583004852E-03
swTranslation(2) = 3.22119475924085E-08
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.74537189560556E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.25652826392425E-02
swTranslation(1) = -8.77838191707104E-04
swTranslation(2) = 2.68432896603404E-08
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector

' Zoom In/Out (MouseWheel)
Set swModelView = Part.ActiveView
swModelView.Scale2 = 1.4544765796713E-05
ReDim swTranslation(0 To 2) As Double
swTranslation(0) = 2.25935987672315E-02
swTranslation(1) = -7.31531826422593E-04
swTranslation(2) = 2.23694080502837E-08
swTranslationVar = swTranslation
Set swMathUtils = swApp.GetMathUtility()
Set swTranslationVector = swMathUtils.CreateVector((swTranslationVar))
swModelView.Translation3 = swTranslationVector
Dim myFeature As Object
Set myFeature = Part.FeatureManager.FeatureExtrusion2(False, False, False, 0, 0, 0.029, 0.01, False, False, False, False, 1.74532925199433E-02, 1.74532925199433E-02, False, False, False, False, True, True, True, 0, 0, False)
Part.SelectionManager.EnableContourSelection = False

' Zoom To Fit
Part.ViewZoomtofit2
boolstatus = Part.Extension.SelectByRay(-2.09784740900432E-02, 2.89999999998258E-02, -1.49781195395349E-02, -0.400036026779312, -0.515038074910024, -0.758094294050284, 1.72167392455426E-04, 2, False, 0, 0)
Part.ClearSelection2 True
boolstatus = Part.Extension.SketchBoxSelect("0.000000", "0.000000", "0.000000", "0.000000", "0.000000", "0.000000")

' Zoom To Fit
Part.ViewZoomtofit2
End Sub
