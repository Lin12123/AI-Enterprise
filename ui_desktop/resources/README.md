# AI-SW Workbench Resources

AI-SW Workbench uses the following application icon assets:

```text
app_icon_source.png.png  Original 3D icon artwork supplied for the project
app_icon.png             PNG used by the PySide6 window and packaged resources
app_icon.ico             Multi-size Windows and PyInstaller application icon
```

The icon uses a simplified three-dimensional CAD form, an `AI` mark, and the
Workbench blue/teal palette. `app_icon.ico` contains 16, 20, 24, 32, 40, 48,
64, 128, and 256 pixel variants so Windows can render it in Explorer, the
taskbar, shortcuts, and window chrome.

Both icon paths are project-relative and work in source mode and a PyInstaller
bundle. The application still starts if an icon is unavailable.

After replacing the source artwork, regenerate `app_icon.png` and
`app_icon.ico`, then rebuild from the project root:

```cmd
build_desktop.bat
```

The packaged client is created at:

```text
dist\AI-SW Workbench\AI-SW Workbench.exe
```


A stable project-root launcher is also available:

```text
启动 AI-SW Workbench.bat
```

The current validated packaged client for this workspace is:

```text
dist_repacked_20260707_1519\\AI-SW Workbench\\AI-SW Workbench.exe
```





