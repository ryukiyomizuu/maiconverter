@echo off
REM mod by bnnm

set PATH=C:\Program Files (x86)\mingw-w64\i686-8.1.0-win32-sjlj-rt_v6-rev0\mingw32\bin;%PATH%

g++ "-DLANG_US 1" clADX.cpp clCRID.cpp clUTF.cpp Source.cpp -o crid_mod.exe -static-libgcc -static-libstdc++

@echo on
