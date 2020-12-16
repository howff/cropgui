@echo off
rem This batch file runs CropGUI on Windows.
rem You need to have installed Python already, and made sure that python.exe is in the PATH.
rem You can make a Shortcut to this batch file if you want to set any properties
rem such as the terminal window size.
rem You can comment out the pause at the end to have the window close automatically.
python .\cropgui.py %*
pause
