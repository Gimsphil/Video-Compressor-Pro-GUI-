Option Explicit

Dim objShell, objFSO, oShortcut
Dim scriptDir, vbsPath, lnkPath

Set objShell = CreateObject("WScript.Shell")
Set objFSO   = CreateObject("Scripting.FileSystemObject")

scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
vbsPath   = scriptDir & "\run.vbs"
lnkPath   = objShell.SpecialFolders("Desktop") & "\Video Compressor Pro.lnk"

' 바로가기 생성
Set oShortcut = objShell.CreateShortcut(lnkPath)
oShortcut.TargetPath       = "wscript.exe"
oShortcut.Arguments        = """" & vbsPath & """"
oShortcut.WorkingDirectory = scriptDir
oShortcut.Description      = "Video Compressor Pro - H.265 Video Compression"
oShortcut.IconLocation     = "shell32.dll,46"
oShortcut.Save()

MsgBox "Shortcut created on Desktop!" & vbCrLf & vbCrLf & _
       lnkPath, vbInformation, "Video Compressor Pro"
