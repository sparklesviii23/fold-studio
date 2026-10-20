"""Lossless original trajectory packing with bounded, validated ZIP restoration."""
import ctypes
import hashlib
import os
import pathlib
import stat
import sys
import unicodedata
import zipfile


def logical_manifest(output):
    """Hash the same logical files in packed and unpacked representations."""
    from campaign_review import manifest
    physical = manifest(output)
    logical = {}
    identities = set()
    total = 0
    def add(name, raw):
        nonlocal total
        identity = unicodedata.normalize('NFC', name).casefold()
        total += len(raw)
        if identity in identities or total > 512 * 1024**2 or len(logical) >= 20000:
            raise ValueError('Trajectory archive has conflicting names or exceeds the bounded restore size.')
        identities.add(identity); logical[name] = hashlib.sha256(raw).hexdigest()
    for name, raw in physical.items():
        path = pathlib.PurePosixPath(name)
        if len(path.parts) != 2 or path.parts[0] != '1_Trajectories' or path.suffix != '.zip':
            add(name, raw); continue
        with zipfile.ZipFile(pathlib.Path(output) / name) as archive:
            entries = archive.infolist()
            if len(entries) > 20000:
                raise ValueError('Too many trajectory archive entries.')
            for entry in entries:
                member = entry.filename
                kind = stat.S_IFMT(entry.external_attr >> 16)
                pieces = member.rstrip('/').split('/')
                if (not member or '\\' in member or '\x00' in entry.orig_filename or
                    member.startswith('/') or any(piece in ('', '.', '..') for piece in pieces) or
                    pieces[0] != path.stem or kind not in (0, stat.S_IFREG, stat.S_IFDIR) or
                    entry.flag_bits & 1 or entry.file_size > 100 * 1024**2):
                    raise ValueError('Unsafe or unsupported trajectory archive member.')
                if entry.is_dir():
                    continue
                if total + entry.file_size > 512 * 1024**2:
                    raise ValueError('Trajectory archive exceeds the bounded restore size.')
                add('1_Trajectories/' + member, archive.read(entry))
    return logical


def transform(snapshot, operation):
    """Execute actual original functions; verify every logical byte survives."""
    from bindcraft.campaign_output import archive_campaign_trajectories, restore_campaign_trajectories
    snapshot = pathlib.Path(snapshot)
    stage = snapshot / '1_Trajectories'
    if not stage.is_dir():
        raise ValueError('This campaign has no saved trajectory stage.')
    before = logical_manifest(snapshot)
    if operation == 'archive':
        if any((directory.parent / (directory.name + '.zip')).exists() for directory in stage.iterdir() if directory.is_dir()):
            raise ValueError('A packed trajectory already conflicts with an unpacked folder.')
        changed = archive_campaign_trajectories(str(snapshot))
    elif operation == 'unarchive':
        if any(archive.with_suffix('').exists() for archive in stage.glob('*.zip')):
            raise ValueError('Restore would overwrite an existing trajectory folder.')
        changed = restore_campaign_trajectories(str(snapshot))
    else:
        raise ValueError('Choose archive or unarchive.')
    if not changed:
        raise ValueError('No ' + ('unpacked folders to compress.' if operation == 'archive' else 'packed trajectories to restore.'))
    if logical_manifest(snapshot) != before:
        raise ValueError('Original trajectory conversion changed scientific file contents.')
    return {'convertedPaths': [str(pathlib.Path(path).relative_to(snapshot)) for path in changed],
            'logicalManifest': before, 'logicalFileCount': len(before), 'logicalContentUnchanged': True}


def exchange_directories(left, right):
    """Atomic same-volume directory exchange; no missing-stage crash window.

    macOS sys/stdio.h defines renamex_np with RENAME_SWAP=0x00000002.
    Each path remains recoverable even if the calling process is terminated.
    """
    left, right = pathlib.Path(left), pathlib.Path(right)
    if sys.platform != 'darwin':
        raise ValueError('Atomic trajectory storage conversion requires macOS.')
    if left.is_symlink() or right.is_symlink() or not left.is_dir() or not right.is_dir():
        raise ValueError('Choose two actual trajectory directories.')
    if left.stat().st_dev != right.stat().st_dev:
        raise ValueError('Atomic storage conversion requires the same volume.')
    library = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    rename = library.renamex_np
    rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(os.fsencode(left), os.fsencode(right), 2):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
