"""Build regression: real Java/D8 fixture is opt-in and writes only test temp data."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ApkToolchainTests(unittest.TestCase):
    def test_parameter_metadata_enabled(self):
        source = (ROOT / 'app/amazon_android_ui/build_apk.sh').read_text()
        self.assertIn('javac --release 8 -parameters -classpath', source)

    def test_actual_compiler_version_is_recorded(self):
        source = (ROOT / 'app/amazon_android_ui/build_apk.sh').read_text()
        self.assertIn('javac -version > "$BUILD/compiler-version.txt"', source)

    @unittest.skipUnless(os.environ.get('DEMOCART_TOOLCHAIN_TESTS') == '1', 'requires explicitly supplied read-only SDK/Java')
    def test_java21_anonymous_parameters_with_d8_34(self):
        java = Path(os.environ['JAVA_HOME']) / 'bin/java'
        sdk = Path(os.environ['ANDROID_SDK_ROOT'])
        d8 = sdk / 'build-tools/34.0.0/d8'
        android = sdk / 'platforms/android-34/android.jar'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for named in (False, True):
                stage = root / ('named' if named else 'unnamed')
                classes, dex = stage / 'classes', stage / 'dex'
                classes.mkdir(parents=True)
                dex.mkdir()
                # The local Java 21 runtime has the compiler module but no ct.sym.
                # Use Android's boot classpath; both outputs target class version 52.
                command = [str(java), '-m', 'jdk.compiler/com.sun.tools.javac.Main',
                           '-source', '8', '-target', '8', '-bootclasspath', str(android)]
                if named:
                    command.append('-parameters')
                built = subprocess.run([*command, '-d', str(classes), str(ROOT/'tests/android/D8Compatibility.java')],
                                       capture_output=True, text=True, timeout=30)
                self.assertEqual(built.returncode, 0, built.stderr)
                result = subprocess.run([str(d8), '--min-api', '23', '--lib', str(android), '--output', str(dex),
                                         *map(str, sorted(classes.glob('*.class')))],
                                        capture_output=True, text=True, timeout=30)
                if named:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertTrue((dex/'classes.dex').read_bytes().startswith(b'dex\n'))
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('NullPointerException', result.stderr)
