"""Convert legacy PC P4G saves to decrypted PS4 GAME.BIN replacement files."""

import argparse
import struct
from pathlib import Path

from console_common import discover_flat_saves, output_path, write_prepared
from convert_ps4topc import (
    COMMON_LAYOUT, EXTRA_LAYOUT, RETRY_LAYOUT, RETRY_CAPACITY, SaveError,
    convert_bin as validate_ps4, discover_saves, finish_save, pack_segment,
    parse_save, validate_system,
)


def load_templates(path):
    """Accept one GAME.BIN for all slots, or match slots from an export tree."""
    path = Path(path)
    if path.is_file():
        templates = {None: path}
    else:
        files, _ = discover_saves(path)
        templates = {name: file for name, file in files.items() if name.startswith("data")}
    result = {}
    for name, file in templates.items():
        data = file.read_bytes()
        try:
            validate_ps4(data, "extended")  # Includes nested retry validation.
        except SaveError as exc:
            raise SaveError(f"PS4 template {file}: {exc}") from exc
        result[name] = data
    return result


def template_for(templates, name):
    if name in templates:
        return templates[name]
    if None in templates:
        return templates[None]
    raise SaveError(f"no PS4 template for {name}; supply its export or a single GAME.BIN template")


def convert_bin(data, template, custom_diff=None, has_retry=True):
    """Expand legacy segments using only IDs 0x14/0x15 from a PS4 template.

    An old PC save cannot reconstruct these PS4-only fields. The template never
    supplies the main progress, name, inventory, or retry checkpoint. When a
    template has a retry, its PS4-only fields are used for the source retry.
    """
    if custom_diff not in (None, "enable", "disable"):
        raise ValueError("custom_diff must be enable or disable")
    source = parse_save(data, "legacy", has_retry)
    target = parse_save(template, "extended", has_retry)
    if has_retry:
        # Validate the entire donor even when its retry will not be used.
        validate_ps4(template, "extended")
        enabled = struct.unpack("<I", source[0x10000001])[0]
        size = struct.unpack("<I", source[0x10000002])[0]
        if enabled not in (0, 1) or size > RETRY_CAPACITY or (enabled and not size):
            raise SaveError("invalid PC retry-save flag or length")
        if size:
            donor_size = struct.unpack("<I", target[0x10000002])[0]
            if donor_size:
                donor_retry = target[0x10000003][:donor_size]
            else:
                # Only the two extra fields are needed from this donor body.
                donor_body = bytearray(template[:0x38])
                for kind, _ in COMMON_LAYOUT + EXTRA_LAYOUT:
                    donor_body.extend(pack_segment(kind, target[kind]))
                donor_retry = finish_save(donor_body)
            retry = convert_bin(source[0x10000003][:size], donor_retry,
                                custom_diff, has_retry=False)
            if len(retry) > RETRY_CAPACITY:
                raise SaveError("converted retry save exceeds PS4 capacity")
            source[0x10000002] = struct.pack("<I", len(retry))
            source[0x10000003] = retry.ljust(RETRY_CAPACITY, b"\0")
        else:
            source[0x10000003] = bytes(RETRY_CAPACITY)
    result = bytearray(data[:0x38])
    result[0x36:0x38] = b"\0\0"  # Native PS4 headers leave this legacy field zero.
    layout = COMMON_LAYOUT + EXTRA_LAYOUT + (RETRY_LAYOUT if has_retry else ())
    for kind, _ in layout:
        result.extend(pack_segment(kind, target[kind] if kind in (0x14, 0x15) else source[kind]))
    if custom_diff == "enable":
        result[0x1304] |= 3
    elif custom_diff == "disable":
        result[0x1304] &= ~3
    result = finish_save(result)
    parse_save(result, "extended", has_retry)
    return result


def conv_bin(pc_bin, ps4_bin, template, custom_diff=None):
    pc_bin.seek(0)
    result = convert_bin(pc_bin.read(), template, custom_diff)
    ps4_bin.seek(0)
    ps4_bin.write(result)
    ps4_bin.truncate()


def convert_directory(source, ps4_template, destination=None, custom_diff=None):
    source = Path(source).resolve()
    output = output_path(source, destination, "_ps4", (ps4_template,))
    files = discover_flat_saves(source)
    templates = load_templates(ps4_template)
    prepared = {}
    for name, path in sorted(files.items()):
        try:
            data = path.read_bytes()
            if name == "system.bin":
                validate_system(data)
                directory = "CHANNELSAVE"
            else:
                data = convert_bin(data, template_for(templates, name), custom_diff)
                directory = "SAVELIST" + name[4:8]
            prepared[f"{directory}/GAME.BIN"] = data
        except SaveError as exc:
            raise SaveError(f"{path}: {exc}") from exc
    write_prepared(output, prepared)
    return output, len(files)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save_dir", type=Path, help="legacy PC remote directory")
    parser.add_argument("--ps4-template", required=True, type=Path,
                        help="decrypted PS4 export tree (matching slots), or one GAME.BIN for all slots")
    parser.add_argument("-o", "--output", type=Path, help="new output directory (default: <save_dir>_ps4)")
    parser.add_argument("--custom-diff", choices=("enable", "disable"))
    args = parser.parse_args(argv)
    try:
        output, count = convert_directory(args.save_dir, args.ps4_template, args.output, args.custom_diff)
    except (SaveError, OSError) as exc:
        parser.exit(1, f"error: {exc}\n")
    print(f"Converted {count} files to {output}")
    print("Replace GAME.BIN in matching decrypted PS4 exports and import them with your save manager.")
    print("PS4-only segments come from the template; console encryption/signing is not performed.")


if __name__ == "__main__":
    main()
