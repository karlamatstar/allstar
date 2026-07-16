Set shell = CreateObject("WScript.Shell")
base = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.Run Chr(34) & base & "\start_qa.bat" & Chr(34), 0, False
