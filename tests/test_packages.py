import contextlib
import io
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from maccraft.cli import main, parser, launch_plan
from maccraft.elf import InvalidELF, inspect_elf
from maccraft.manifest import InvalidManifest, manifest_info
from maccraft.packages import import_packages, installation, verify_installation


def elf(machine=183):
    data = bytearray(224)
    data[:16] = b'\x7fELF\x02\x01\x01' + b'\0' * 9
    struct.pack_into('<HHIQQQIHHHHHH', data, 16, 3, machine, 1, 0, 64, 0, 0, 64, 56, 2, 0, 0, 0)
    struct.pack_into('<IIQQQQQQ', data, 64, 1, 5, 0, 0, 0, len(data), len(data), 4096)
    struct.pack_into('<IIQQQQQQ', data, 120, 2, 4, 176, 176, 176, 48, 48, 8)
    return bytes(data)


def manifest(code=123, split='', package='com.mojang.minecraftpe'):
    return (f'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{package}" '
            f'android:versionCode="{code}" android:versionName="1.21.73" split="{split}"/>').encode()


def binary_manifest(utf8=True, padding=''):
    strings = ['manifest', 'package', 'com.mojang.minecraftpe', 'versionCode', 'versionName', '1.21.73', padding]
    pool, offsets = bytearray(), []
    def length(value, unit):
        if unit == 1:
            return bytes([value]) if value < 128 else bytes([0x80 | value >> 8, value & 255])
        return struct.pack('<H', value) if value < 32768 else struct.pack('<HH', 0x8000 | value >> 16, value & 65535)
    for text in strings:
        offsets.append(len(pool))
        encoded = text.encode('utf-8' if utf8 else 'utf-16-le')
        if utf8:
            pool.extend(length(len(text), 1) + length(len(encoded), 1) + encoded + b'\0')
        else:
            pool.extend(length(len(encoded)//2, 2) + encoded + b'\0\0')
    start = 28 + 4 * len(strings)
    string_chunk = (struct.pack('<HHIIIIII', 1, 28, start + len(pool), len(strings), 0,
                                0x100 if utf8 else 0, start, 0)
                    + b''.join(struct.pack('<I', o) for o in offsets) + pool)
    attrs = b''.join(struct.pack('<IIIHBBI', 0xffffffff, key, 0xffffffff, 8, 0, kind, value)
                     for key, kind, value in [(1, 3, 2), (3, 0x10, 123), (4, 3, 5)])
    element = (struct.pack('<HHIII', 0x102, 16, 36+len(attrs), 1, 0xffffffff)
               + struct.pack('<IIHHHHHH', 0xffffffff, 0, 20, 20, 3, 0, 0, 0) + attrs)
    payload = string_chunk + element
    return struct.pack('<HHI', 3, 8, 8 + len(payload)) + payload


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.root = self.folder / 'home with spaces'

    def apk(self, name='game.apk', entries=None, xml=None):
        path = self.folder / name
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('AndroidManifest.xml', xml if xml is not None else manifest())
            for key, value in (entries if entries is not None else {
                'lib/arm64-v8a/libminecraftpe.so': elf(), 'assets/test.txt': b'assets'}).items():
                archive.writestr(key, value)
        return path

    def test_import_and_idempotence(self):
        apk = self.apk(xml=binary_manifest())
        version = import_packages([apk], self.root)
        self.assertEqual(version, import_packages([apk], self.root))
        game, info = installation(self.root, version)
        self.assertEqual(info['version_name'], '1.21.73')
        self.assertEqual(info['libraries']['libminecraftpe.so']['architecture'], 'arm64-v8a')
        verify_installation(game, info)

    def test_split_order_independent(self):
        base = self.apk('base.apk', {'assets/test.txt': b'assets'})
        split = self.apk('arm.apk', {'lib/arm64-v8a/libminecraftpe.so': elf()}, manifest(split='config.arm64_v8a'))
        self.assertEqual(import_packages([base, split], self.root), import_packages([split, base], self.root))

    def test_missing_arm64(self):
        with self.assertRaisesRegex(ValueError, 'Missing ARM64'):
            import_packages([self.apk(entries={'lib/x86_64/libminecraftpe.so': elf(), 'assets/a': b'a'})], self.root)
        self.assertEqual(list((self.root/'versions').iterdir()), [])

    def test_wrong_architecture(self):
        with self.assertRaises(InvalidELF):
            import_packages([self.apk(entries={'lib/arm64-v8a/libminecraftpe.so': elf(62), 'assets/a': b'a'})], self.root)

    def test_traversal(self):
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            import_packages([self.apk(entries={'assets/../../escaped': b'bad'})], self.root)
        self.assertFalse((self.folder/'escaped').exists())

    def test_symlink(self):
        path = self.apk()
        with zipfile.ZipFile(path, 'a') as archive:
            entry = zipfile.ZipInfo('assets/link')
            entry.external_attr = 0o120777 << 16
            archive.writestr(entry, '../outside')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            import_packages([path], self.root)

    def test_duplicate_within_archive(self):
        path = self.apk()
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(path, 'a') as archive:
                archive.writestr('assets/test.txt', b'other')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            import_packages([path], self.root)

    def test_wrong_package(self):
        with self.assertRaises(InvalidManifest):
            import_packages([self.apk(xml=manifest(package='other'))], self.root)

    def test_mismatched_split_versions(self):
        base = self.apk()
        split = self.apk('split.apk', {}, manifest(code=124, split='config.arm64_v8a'))
        with self.assertRaisesRegex(ValueError, 'matching version'):
            import_packages([base, split], self.root)

    def test_conflicting_split_resources(self):
        base = self.apk()
        split = self.apk('split.apk', {'assets/test.txt': b'conflict'}, manifest(split='assets'))
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            import_packages([base, split], self.root)
        self.assertEqual(list((self.root/'versions').iterdir()), [])

    def test_identical_split_resources(self):
        base = self.apk()
        split = self.apk('split.apk', {'assets/test.txt': b'assets'}, manifest(split='assets'))
        self.assertTrue(import_packages([base, split], self.root))

    def test_size_limit(self):
        with patch('maccraft.packages.MAX_TOTAL', 32):
            with self.assertRaisesRegex(ValueError, 'size or entry'):
                import_packages([self.apk()], self.root)

    def test_tamper_detection(self):
        version = import_packages([self.apk()], self.root)
        game, info = installation(self.root, version)
        (game/'assets/test.txt').write_text('modified')
        with self.assertRaisesRegex(ValueError, 'modified'):
            verify_installation(game, info)

    def test_invalid_installation_id(self):
        with self.assertRaisesRegex(ValueError, 'Invalid installation ID'):
            installation(self.root, '../../outside')

    def test_dry_run_preserves_argument_boundaries(self):
        version = import_packages([self.apk()], self.root)
        args = parser().parse_args(['--root', str(self.root), 'launch', version, '--dry-run',
                                   '--runtime', '/some path/runtime;test'])
        command, env, game, _ = launch_plan(args, self.root)
        self.assertEqual(command[0], '/some path/runtime;test')
        self.assertEqual(command[2], str(game)+'/')
        self.assertEqual(env['MACCRAFT_RENDERER'], 'legacy')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--root', str(self.root), 'launch', version, '--dry-run']), 0)
        self.assertEqual(json.loads(output.getvalue())['renderer'], 'legacy')

    def test_native_host_required(self):
        version = import_packages([self.apk()], self.root)
        with patch('maccraft.cli.platform.system', return_value='Linux'), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--root', str(self.root), 'launch', version]), 1)

    def test_metal_driver_required(self):
        version = import_packages([self.apk()], self.root)
        args = parser().parse_args(['launch', version, '--renderer', 'metal', '--dry-run'])
        with self.assertRaisesRegex(ValueError, 'requires --angle'):
            launch_plan(args, self.root)


class ParserTests(unittest.TestCase):
    def test_binary_xml_utf8_and_utf16(self):
        for utf8 in (True, False):
            for size in (0, 130, 32000 if utf8 else 33000):
                self.assertEqual(manifest_info(binary_manifest(utf8, 'x'*size))['version_code'], 123)

    def test_malformed_manifest(self):
        good = binary_manifest()
        for cut in (0, 4, 8, 20, len(good)-1):
            with self.assertRaises(InvalidManifest):
                manifest_info(good[:cut])

    def test_malformed_elf(self):
        data = bytearray(elf())
        struct.pack_into('<Q', data, 32, 999999)
        with self.assertRaises(InvalidELF):
            inspect_elf(bytes(data))
        with self.assertRaises(InvalidELF):
            inspect_elf(b'not a library')

    def test_dependencies(self):
        data = bytearray(elf()) + b'\0'*16 + b'liblog.so\0'
        struct.pack_into('<Q', data, 96, len(data))
        struct.pack_into('<Q', data, 104, len(data))
        struct.pack_into('<Q', data, 152, 64)
        struct.pack_into('<Q', data, 160, 64)
        for pos, tag, value in [(176, 1, 0), (192, 5, 240), (208, 10, 10), (224, 0, 0)]:
            struct.pack_into('<qQ', data, pos, tag, value)
        # 9-character name plus terminator.
        data.extend(b'\0')
        struct.pack_into('<Q', data, 96, len(data))
        struct.pack_into('<Q', data, 104, len(data))
        self.assertEqual(inspect_elf(bytes(data))['dependencies'], ['liblog.so'])
