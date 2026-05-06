Option Explicit

Dim objShell, objFSO
Dim pyExe, script, pyVer

Set objShell = CreateObject("WScript.Shell")
Set objFSO   = CreateObject("Scripting.FileSystemObject")

' ── Python 경로 탐색 ──────────────────────────────────────────
Dim versions, v
versions = Array("313","312","311","310","39","38")

pyExe = ""
For Each v In versions
    Dim candidate
    candidate = objShell.ExpandEnvironmentStrings("%USERPROFILE%") & _
                "\AppData\Local\Programs\Python\Python" & v & "\python.exe"
    If objFSO.FileExists(candidate) Then
        pyExe = candidate
        Exit For
    End If
Next

' 못 찾으면 C:\Python* 탐색
If pyExe = "" Then
    For Each v In versions
        candidate = "C:\Python" & v & "\python.exe"
        If objFSO.FileExists(candidate) Then
            pyExe = candidate
            Exit For
        End If
    Next
End If

If pyExe = "" Then
    MsgBox "Python 을 찾을 수 없습니다." & vbCrLf & vbCrLf & _
           "https://www.python.org/downloads/ 에서" & vbCrLf & _
           "Python 3.8 이상을 설치하세요." & vbCrLf & _
           "(설치 시 'Add Python to PATH' 체크)", _
           vbCritical, "Video Compressor Pro"
    WScript.Quit 1
End If

' ── main.py 경로 ──────────────────────────────────────────────
script = objFSO.GetParentFolderName(WScript.ScriptFullName) & "\main.py"

If Not objFSO.FileExists(script) Then
    MsgBox "main.py 를 찾을 수 없습니다." & vbCrLf & script, _
           vbCritical, "Video Compressor Pro"
    WScript.Quit 1
End If

' ── 실행 (창 숨김: 0) ─────────────────────────────────────────
Dim cmd
cmd = """" & pyExe & """ """ & script & """"
objShell.Run cmd, 0, False
