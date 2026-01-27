@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
cd /d %~dp0
cl /EHsc /std:c++17 tests\test_http_client_standalone.cpp /Fe:test_http.exe winhttp.lib
