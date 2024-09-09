Project SEKAI custom streaming CRIWARE HCA Decoder (Windows 64 bit native)
---
# Build
In this branch:
```powershell
cd Client
mkdir build
cd build
cmake ..
cmake --build . --config Release
```
You will get the `sssekai_streaming_hca_decoder.exe` in the project root's `dist/Release` folder.

# Usage
As always, you'd need to provide `cri_ware_unity.dll` yourself. Place it in the same folder as the executable.

```powershell
Project SEKAI custom streaming HCA decoder (native win64)
usage: <input directory (containing *.hca frames> <output .wav file>
        - the hca frames will be appended to the wav file one by one whilst being lexicographically sorted by their filenames
```

The HCA segements will be decoded and merged into a single, large (!) WAV file.
