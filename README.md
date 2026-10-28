
# Persona 4 Golden Save Converter

This repo contains:

- `convert_ps4topc.py`, a utility that converts decrypted P4G PS4 exports to
  the original PC save format, including embedded retry saves, `.binslot`
  metadata, and `remotecache.vdf`. See [PS4 Saves to PC](#ps4-saves-to-pc).

- `convert_vita2pc.py`, a utility that converts P4G PS Vita saves to P4G PC saves:

  - PS Vita `data00XX.bin` and `system.bin` files are converted to the PC format (see [FAQ #1](#faq)).
  - PS Vita `sdslot.dat` file is converted to PC `data00XX.binslot` files (see [FAQ #2](#faq)).
  - A `remotecache.vdf` file is generated with valid entries for each save file (see [FAQ #3](#faq)).

  **This tool will convert the above into proper PC `.bin`/`.binslot` files.**

  **There's no need to edit any hashes manually.**

- `convert_pc2vita.py`, a utility that converts P4G PC saves to P4G PS Vita saves.

**WARNING: REMEMBER TO BACKUP YOUR SAVES BEFORE CONVERSION.**

| PS Vita                       | PC                        |
| :---------------------------: | :-----------------------: |
| ![vita](img/preview_vita.png) | ![pc](img/preview_pc.png) |

## Requirements

- PS Vita with HENkaku + VitaShell or vita-savemgr
- Persona 4 Golden on PS Vita - supported versions:
  - `PCSE00120` (USA)
  - `PCSB00245` (EUR)
- Persona 4 Golden on PC
- Python 3

## Usage

### PS4 Saves to PC

Requires Python 3.8+ and **decrypted** PS4 saves. There are no third-party Python
dependencies. This does not decrypt the encrypted containers produced by the
PS4's normal USB export.

Point the script at an exported account directory, a parent containing its
exports, or one individual `SAVELIST` directory. For example:

```txt
10c7544b/
|- CUSA33873_SAVELIST0001/GAME.BIN
|- CUSA33873_SAVELIST0002/GAME.BIN
|- ...
|- CUSA33873_CHANNELSAVE/GAME.BIN  (optional; becomes PC system.bin)
\- CUSA33873_SYSTEMSAVE/GAME.BIN   (PS4 settings; skipped)
```

From this repository's directory:

```sh
python convert_ps4topc.py ../save-refs/ps4-save/unencrypted/10c7544b --output ../output/ps4-to-pc
```

The output directory must not already exist. Without `--output`, it defaults to
`<save_dir>_conv`. Original files are only read. The result is:

```txt
ps4-to-pc/
|- remotecache.vdf
\- remote/
   |- data0001.bin
   |- data0001.binslot
   |- ...
   |- system.bin       (when CHANNELSAVE is present)
   \- system.binslot
```

The default `--pc-format legacy` matches the existing Vita-to-PC converter and
the supplied original PC saves (`0x34D3D` bytes per slot). Main progress and
retry checkpoints are preserved; the two additional PS4 segments are removed
from both. `--custom-diff enable` or `--custom-diff disable` toggles the same
custom difficulty menu bits as the other converters, in both saves. Omitting
this option preserves the original difficulty settings.

An advanced `--pc-format extended` option retains the `0x35351`-byte PS4 segment
layout. With no difficulty override it preserves the slot bytes exactly while
generating PC metadata. This option has not been verified against a newer PC
game; use the default for the supplied older PC version.

The script validates segment IDs, lengths, header and body checksums, retry saves, and end
markers before writing anything. Duplicate slot exports across accounts are
rejected: select one account/export directory instead of silently mixing saves.
Slots 1 through 16 are supported; system-only exports and unknown layouts are
rejected. No PC donor save or Vita save is needed to run the converter.

#### Installing the output

1. Exit the game and Steam, and back up your existing
   `Steam/userdata/<user_id>/1113000/` directory.
2. Copy the files inside the generated `remote/` directory into the PC game's
   `1113000/remote/` directory.
3. If this output is the complete set of saves you want to install, copy its
   `remotecache.vdf` into `1113000/`. If merging with additional PC slots, run
   `python remotecache.py "<path to the combined remote directory>"` instead,
   so the cache includes those other saves too.
4. Launch the game and load the imported slots. Save each imported slot again
   to let the game refresh its save-menu descriptions.

The generated menu metadata uses the PS4 save's name, level, date, difficulty,
play time, and clear count. Only time/location labels confirmed by the supplied
PC/Vita references are translated; others display `Time N` or `Area X/Y` until
re-saved. Extra ending-description text from console metadata is not synthesized.
These display limitations do not change the saved game-state bytes.

#### PS4 format findings and validation

The CUSA33873 reference files have the following structure:

| Item | PS4 | Original PC target |
| --- | --- | --- |
| Per-slot file size | `0x35351` | `0x34D3D` |
| Main header checksum | Zero in PS4 samples at `0x36..0x37` | Recalculated for PC |
| Shared segments 1–19 | `0x00038..0x19D0F` | Identical bytes |
| Additional segments | ID `0x14`, payload `4`; ID `0x15`, payload `0x600` | Removed |
| Retry storage capacity | `0x1B000` | `0x1B000` |
| Active retry length in references | `0x1A331` | `0x19D1D` |
| Checksum footer offset | `0x35344` | `0x34D30` |
| Channel/system data | `CHANNELSAVE/GAME.BIN`, `0x8000` bytes | Copied as `system.bin` |
| PS4 preferences | `SYSTEMSAVE/GAME.BIN`, `0xBC` bytes | Skipped |

Each slot has **two separate checksums**. The header checksum is the byte sum
of `[0x04, 0x36)`, modulo 256, stored as a little-endian 16-bit value at `0x36`.
The final body checksum is the byte sum from `0x38` to the checksum segment,
modulo 256. The embedded retry save has its own header and body checksums and
must be converted independently. Changing its header also changes the outer
save's body checksum. Both `.binslot` MD5 hashes are generated using the format
documented below. Steam SHA-1 entries use the existing `remotecache.py` helper.
The `.binslot` timestamp starts at `0x30C` within its metadata payload, after
the two fields at `0x304`; the full `.binslot` size is `0x374`.

The supplied `pc-save/remote/data0003.BIN` is byte-identical to PS4 slot 3, but
its `.binslot` still hashes the original PC save. It is not an independent
example of a working PC-format conversion. The other supplied PC slots have
valid hashes and use the legacy layout. The decrypted Vita references provide
independent checks of menu fields and of the existing converter's output.

Run the regression suite with:

```sh
python -m unittest -v test_convert_ps4topc
```

The suite includes synthetic binary fixtures, malformed-input checks, output
protection, checksums, metadata, and Steam cache entries. When `../save-refs`
is present, it also checks all supplied PS4 saves and retry checkpoints, the
PC reference layout, channel data, and decrypted Vita conversions. Personal
save fixtures are not included in the repository.

Validation is structural and checksum-based; loading the converted saves in
the actual PC game remains the final compatibility check.

#### Fix for the "old version of save data" warning and load crash

The initial PS4 converter copied the PS4 header unchanged. PS4 leaves the word
at `0x36` zero, but the original PC loader uses this header checksum to choose
the format. Correct file sizes, segment checksums, and `.binslot` hashes alone
do not make a save loadable. The original Vita converter did not need to fix
this field because the decrypted Vita headers already contain a valid checksum.

The installed PC executable was inspected without modifying it. Its load
function at VA `0x72BE90` receives a pointer four bytes into the file and
compares the sum of the next `0x32` bytes with the word at pointer + `0x32`
(VA `0x72BF0E`). When they match, it starts reading segments at file offset
`0x38`. On mismatch it displays the Japanese "old version" warning and falls
back to file offset `0x24`. That offset contains name bytes in these saves,
so the loader reads invalid segment IDs and lengths. For example, the old
slot 12 output eventually supplies a bogus length of `0x02000000`, sending
the loader beyond the save buffer. The warning is different from the FAQ's
"retry point has not been saved" warning.

The converter now rebuilds the header checksum in both the main save and
the embedded retry save, and regenerates all dependent checksums and hashes.
It preserves the actual gameplay segments and retry checkpoints. Tests also
cover a missing header checksum with an otherwise valid body, the 16-bit
storage width, and a legitimate calculated checksum of zero.

In the supplied workspace, **use `output/ps4-to-pc-fixed` instead of the initial
`output/ps4-to-pc` output**. The corrected folder includes a
`validation_report.json` recording the executable hash, loader addresses,
changed bytes, and checks for all 16 slots. The regression suite passes 19
tests, and a bounded model of the observed loader reproduces the failure for
all initial outputs and accepts all corrected main/retry saves. This is static
validation; the corrected output still needs an in-game load check.

### PS Vita Saves to PC Saves

#### Dumping Saves from PS Vita

Use VitaShell or vita-savemgr to export a save.
Transfer the exported save directory to PC using FTP/USB.

For example, using VitaShell:

- Navigate to `ux0:user/00/savedata/`.
- "Select" the `PCSE00120` directory.
- Press *Triangle* and select *Open decrypted*.
- Using FTP/USB, copy the saves to a directory on PC.

The directory you exported to PC should look like the following, if all save slots were populated:

```txt
PCSE00120/
|- sce_sys/
|  \- sdslot.dat
|- data0001.bin
|- data0002.bin
|- ...
|- data0016.bin
\- system.bin
```

Note that the `sce_sys` directory contains other files, but they are not relevant to the conversion process.

#### Converting Saves to PC Format

1. Clone or download this repository.

2. Convert your PS Vita saves using:

   ```sh
   python convert_vita2pc.py [--custom-diff {disable,enable}] save_dir
   ```

   This utility will generate:

   - a `<save_dir>_conv` directory containing the converted saves
   - a `remotecache.vdf` file

3. Exit Steam - make sure Steam is not running in the background.

4. Backup the contents of the `%PROGRAMFILES(X86)%/Steam/userdata/<user_id>/1113000/` dir.

5. Copy the converted saves in `<save_dir>_conv` to `%PROGRAMFILES(X86)%/Steam/userdata/<user_id>/1113000/remote/`, overwriting files as necessary.

   Copy the generated `remotecache.vdf` to `%PROGRAMFILES(X86)%/Steam/userdata/<user_id>/1113000/`, overwriting the original file if necessary.

6. Start Steam and launch the game.
   In case of a Steam Cloud sync conflict, choose to upload local files to the cloud.

7. Your imported saves should now appear in the LOAD GAME menu.

### PC Saves to PS Vita

#### Converting Saves to PS Vita Format

1. Clone or download this repository.

2. Copy the saves in `%PROGRAMFILES(X86)%/Steam/userdata/<user_id>/1113000/remote/` to another location as a precaution.

3. Run the following on the directory you've copied:

   ```sh
   python convert_pc2vita.py [--custom-diff {disable,enable}] save_dir
   ```

   This utility will generate a `<save_dir>_conv` directory containing the converted saves.

4. Move the converted saves to PS Vita (see [here](#moving-converted-saves-to-ps-vita)) and launch the game.

5. Your imported saves should now appear in the LOAD GAME menu.

#### Moving Converted Saves to PS Vita

Copy the converted saves in `<save_dir>_conv` to `ux0:user/00/savedata/PCSE00120/` using VitaShell FTP/USB.
Overwrite files as needed (*remember to backup the saves already on PS Vita too*).
You should only need to overwrite `data00XX.bin`, `system.bin` and the `sce_sys/sdslot.dat` file.

**Do not replace the entire save directory on PS Vita**.
Only overwrite the `.bin` files within the save directory (as needed) + `sce_sys/sdslot.dat`.

## FAQ

1. Why do I need to convert the saves? PS Vita saves seem to work fine without conversion.

    - The PC save format is slightly different (see [Save Format Changes](#save-format-changes)).
      If you load a PS Vita save directly without conversion, you might get the following error:

        ![retry point error](img/retry_point.png)

        This can be avoided by converting the saves properly.

2. Why do I need to include `sdslot.dat`?

    - PS Vita saves store metadata in the `sdslot.dat` file, which can be found in `ux0:user/00/savedata/PCSE00120/sce_sys/`.
      PC saves store metadata in `binslot` files.
      This converter takes data found in `sdslot.dat` and converts it to the PC `binslot` format (see [Save Format Changes](#save-format-changes)).

3. Why can't I see some of my saves in the save select screen?
   Why am I getting a "Load failed." message when trying to load a save?
   Why do I need a `remotecache.vdf` file?

    - The game uses the Steam Storage API to enumerate game saves.
      Each save file needs to have a valid entry in `%PROGRAMFILES(X86)%/Steam/userdata/<user_id>/1113000/remotecache.vdf`.
      This program will generate a valid `remotecache.vdf` file when converting saves.

      You can also use `remotecache.py` to regenerate a valid `remotecache.vdf`.

4. Why does my Clear Data save look like this? Why aren't NG+ saves colored pink/purple in the save select screen?

    ![clear data bug](img/clear_data.png)

    - This is by a bug in the game itself.
      Note that the saves work as they should, the only issue is with how the save metadata is displayed.
      Wait for a patch, or use [this mod](https://github.com/zarroboogs/p4gpc.tinyfixes) to fix the issue.

        Also note that when converting a Clear Data (save 13 below) or NG+ save (save 14 below) *generated on PC* to PS Vita format, the save metadata is read correctly by the PS Vita version of the game:

        | PC                      | PS Vita                     |
        | :---------------------: | :-------------------------: |
        | ![pc](img/clear_pc.png) | ![vita](img/clear_vita.png) |

## Save Format Changes

### Config Settings

Config settings are no longer saved in `system.bin`, instead there's a config `P4G.ini` file in `%LOCALAPPDATA%/Sega/P4G/`.

### `.bin` Files

- The *Rescue Requests* save segment increased in size (due to internal struct changes), from `0x2908` bytes (PS Vita) to `0x3FAC` bytes (PC).
- PC saves contain a new save segment  (`0x30` bytes) which stores the Hero's name.
- PS Vita saves are padded to `0x38000` bytes with garbage data from PS Vita memory. PC saves aren't padded (`0x34D3D` bytes).

### `.binslot` Files

BINslot files are the PC alternative to `sdslot.dat`.

Stored metadata is identical to PS Vita apart from a new `LANG%d` parameter.

BINslot file structure:

```cpp
typedef struct
{
    char Magic[ 0x08 ]; // SAVE0001

    ubyte SlotFile_MD5[ 0x10 ]; // md5sum of bytes 0x28 to EOF (SlotData)
                                // *** with P4GOLDEN appended to the end ***

    ubyte SaveFile_MD5[ 0x10 ]; // md5sum of corresponding data00XX.bin or system.bin file

    ubyte SlotData[ 0x34C ]; // slot data, same as sdslot.dat data
                             // at offset 0x400 + <save_num> * 0x400
                             // save 0 == system.bin
                             // save 1 == data0001.bin
                             // etc.

} BINslot;

BINslot Slot;
```

<!--
Why append `P4GOLDEN` to the end of `SlotData` for md5sum calculation?

Because ATLUS.

That's why.

`(ノಠ益ಠ)ノ彡┻━┻`
-->
